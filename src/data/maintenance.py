"""Data maintenance workflows for refresh/rebuild/validation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time

import pandas as pd

from src.core.constants import TAIPEI_TZ
from src.core.market import normalize_market
from src.data.cleaner import DataCleaner, QualityReport, adjust_prices
from src.data.fetcher import IDataFetcher, TWSEFetcher
from src.data.storage import DuckDBMeta, ParquetStorage, merge_shareholder_meeting_auto

US_YFINANCE_REQUEST_INTERVAL_SECONDS = 1.0


def should_update_shareholder_meeting(meta_path: Path, now: pd.Timestamp) -> bool:
    if not meta_path.exists():
        return True
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        raw_last = meta.get("last_updated_at")
        if not raw_last:
            return True
        last = pd.Timestamp(raw_last)
    except Exception:  # noqa: BLE001
        return True

    now_ts = pd.Timestamp(now)
    if now_ts.tzinfo is None:
        now_ts = now_ts.tz_localize(TAIPEI_TZ)
    else:
        now_ts = now_ts.tz_convert(TAIPEI_TZ)

    if last.tzinfo is None:
        last = last.tz_localize(TAIPEI_TZ)
    else:
        last = last.tz_convert(TAIPEI_TZ)

    return last.normalize() < now_ts.normalize()


def _empty_dividends() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "cash_dividend": pd.Series(dtype="float64"),
            "stock_dividend": pd.Series(dtype="float64"),
            "symbol": pd.Series(dtype="object"),
        }
    )


def _empty_splits() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "before_price": pd.Series(dtype="float64"),
            "after_price": pd.Series(dtype="float64"),
            "symbol": pd.Series(dtype="object"),
        }
    )


def _empty_per() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "per": pd.Series(dtype="float64"),
            "pbr": pd.Series(dtype="float64"),
            "dividend_yield": pd.Series(dtype="float64"),
            "symbol": pd.Series(dtype="object"),
        }
    )


def _empty_monthly_revenue() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "revenue": pd.Series(dtype="float64"),
            "revenue_month": pd.Series(dtype="int64"),
            "revenue_year": pd.Series(dtype="int64"),
            "symbol": pd.Series(dtype="object"),
        }
    )


def _empty_eps() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "year": pd.Series(dtype="int64"),
            "quarter": pd.Series(dtype="int64"),
            "eps": pd.Series(dtype="float64"),
            "symbol": pd.Series(dtype="object"),
            "report_date": pd.Series(dtype="datetime64[ns]"),
        }
    )


class DataMaintenance:
    """
    Data maintenance operations.

    Dependencies are injected for testability.
    """

    def __init__(
        self,
        fetcher: IDataFetcher,
        storage: ParquetStorage,
        meta: DuckDBMeta,
        cleaner: DataCleaner,
    ):
        self.fetcher = fetcher
        self.storage = storage
        self.meta = meta
        self.cleaner = cleaner
        self._last_us_yfinance_request_ts: float | None = None
        self.warnings: list[str] = []
        self.errors: list[str] = []


    def rebuild_symbol(self, symbol: str, market: str = "tw") -> QualityReport:
        """
        Fully rebuild one symbol:
        1. Download full daily history
        2. Download dividends
        3. Run L1/L2 cleaning
        4. Compute forward-adjusted prices
        5. Save raw + processed
        6. Update metadata
        7. Return quality report
        """
        normalized_market = normalize_market(market)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._supports_us_adjusted_bundle(normalized_market):
            raw_df, adjusted_df, splits_df, _ = self._fetch_us_daily_bundle(symbol=symbol, start="2000-01-01", end=today)
            cleaned_df, report = self.cleaner.clean(raw_df, symbol=symbol)
            self.storage.save_daily(symbol, cleaned_df, market=normalized_market)
            self.storage.save_adjusted(
                symbol,
                self._filter_adjusted_by_cleaned_dates(adjusted_df=adjusted_df, cleaned_df=cleaned_df),
                market=normalized_market,
            )
            if not splits_df.empty:
                self.storage.save_splits(symbol, splits_df, market=normalized_market)
                self._update_meta(symbol=symbol, freq="splits", source=self._source_name(), df=splits_df, market=normalized_market)
            self._update_meta(symbol=symbol, freq="daily", source=self._source_name(), df=cleaned_df, market=normalized_market)
            return report

        raw_df = self.fetcher.fetch_daily(symbol=symbol, start="2000-01-01", end=today)
        cleaned_df, report = self.cleaner.clean(raw_df, symbol=symbol)
        self.storage.save_daily(symbol, cleaned_df, market=normalized_market)
        self._rebuild_adjusted_from_raw(symbol=symbol, raw_df=cleaned_df, market=normalized_market)
        self._update_meta(symbol=symbol, freq="daily", source=self._source_name(), df=cleaned_df, market=normalized_market)
        if normalized_market == "tw":
            self._rebuild_p11_datasets_best_effort(symbol=symbol, market=normalized_market)
        return report

    def rebuild_adj_factors(self, symbol: str, market: str = "tw") -> None:
        """Recompute adjusted prices from stored raw daily data."""
        normalized_market = normalize_market(market)
        if self._supports_us_adjusted_bundle(normalized_market):
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            raw_df, adjusted_df, splits_df, _ = self._fetch_us_daily_bundle(symbol=symbol, start="2000-01-01", end=today)
            cleaned_df, _ = self.cleaner.clean(raw_df, symbol=symbol)
            self.storage.save_adjusted(
                symbol,
                self._filter_adjusted_by_cleaned_dates(adjusted_df=adjusted_df, cleaned_df=cleaned_df),
                market=normalized_market,
            )
            if not splits_df.empty:
                self.storage.save_splits(symbol, splits_df, market=normalized_market)
                self._update_meta(symbol=symbol, freq="splits", source=self._source_name(), df=splits_df, market=normalized_market)
            return

        raw_df = self.storage.load_daily(symbol, market=normalized_market)
        if raw_df.empty:
            return

        self._rebuild_adjusted_from_raw(symbol=symbol, raw_df=raw_df, market=normalized_market)

    def validate_data(self, symbol: str, market: str = "tw") -> QualityReport:
        """Run L1/L2 validation against stored raw data."""
        normalized_market = normalize_market(market)
        raw_df = self.storage.load_daily(symbol, market=normalized_market)
        _, report = self.cleaner.clean(raw_df, symbol=symbol)
        return report

    def list_stale_symbols(self, days: int = 7) -> list[dict]:
        """List metadata rows whose updated_at is older than N days."""
        rows = self.meta.list_all()
        if rows.empty:
            return []

        threshold = pd.Timestamp(datetime.now(timezone.utc) - timedelta(days=days))
        updated_series = pd.to_datetime(rows["updated_at"], errors="coerce", utc=True)
        stale_mask = updated_series < threshold
        stale = rows.loc[stale_mask].copy()
        if stale.empty:
            return []
        return stale.to_dict(orient="records")

    def update_daily(self, symbol: str, market: str = "tw") -> int:
        """
        Incremental daily update from last saved date + 1 day to today.

        Returns number of new rows added.
        """
        normalized_market = normalize_market(market)
        existing = self.storage.load_daily(symbol, market=normalized_market)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if existing.empty:
            start = "2000-01-01"
        else:
            last_date = pd.to_datetime(existing["date"], errors="coerce").dropna().max()
            if pd.isna(last_date):
                start = "2000-01-01"
            else:
                start = (last_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        if self._supports_us_adjusted_bundle(normalized_market):
            raw_new, adjusted_new, splits_df, _ = self._fetch_us_daily_bundle(symbol=symbol, start=start, end=today)
            if raw_new.empty:
                self._update_meta(symbol=symbol, freq="daily", source=self._source_name(), df=existing, market=normalized_market)
                return 0

            cleaned_new, _ = self.cleaner.clean(raw_new, symbol=symbol)
            before_count = len(existing)
            self.storage.save_daily(symbol, cleaned_new, market=normalized_market)
            self.storage.save_adjusted(
                symbol,
                self._filter_adjusted_by_cleaned_dates(adjusted_df=adjusted_new, cleaned_df=cleaned_new),
                market=normalized_market,
            )
            if not splits_df.empty:
                self.storage.save_splits(symbol, splits_df, market=normalized_market)
                self._update_meta(symbol=symbol, freq="splits", source=self._source_name(), df=splits_df, market=normalized_market)
            merged = self.storage.load_daily(symbol, market=normalized_market)
            self._update_meta(symbol=symbol, freq="daily", source=self._source_name(), df=merged, market=normalized_market)
            return max(0, len(merged) - before_count)

        new_df = self.fetcher.fetch_daily(symbol=symbol, start=start, end=today)
        if new_df.empty:
            self._rebuild_adjusted_from_raw(symbol=symbol, raw_df=existing, market=normalized_market)
            self._update_meta(symbol=symbol, freq="daily", source=self._source_name(), df=existing, market=normalized_market)
            return 0


        cleaned_new, _ = self.cleaner.clean(new_df, symbol=symbol)
        before_count = len(existing)
        self.storage.save_daily(symbol, cleaned_new, market=normalized_market)
        merged = self.storage.load_daily(symbol, market=normalized_market)
        self._rebuild_adjusted_from_raw(symbol=symbol, raw_df=merged, market=normalized_market)
        self._update_meta(symbol=symbol, freq="daily", source=self._source_name(), df=merged, market=normalized_market)
        return max(0, len(merged) - before_count)

    def _rebuild_adjusted_from_raw(self, symbol: str, raw_df: pd.DataFrame, market: str) -> None:
        if raw_df.empty:
            return

        dividends = self._fetch_dividends(symbol)
        splits = self._fetch_splits(symbol)
        adjusted_df = adjust_prices(raw_df, dividends, splits=splits, method="forward")
        self.storage.save_adjusted(symbol, adjusted_df, market=market)
        if not splits.empty:
            self.storage.save_splits(symbol, splits, market=market)
            self._update_meta(symbol=symbol, freq="splits", source=self._source_name(), df=splits, market=market)

    def _fetch_dividends(self, symbol: str) -> pd.DataFrame:
        method = getattr(self.fetcher, "fetch_dividends", None)
        if callable(method):
            return method(symbol=symbol)
        return _empty_dividends()

    def _fetch_splits(self, symbol: str) -> pd.DataFrame:
        method = getattr(self.fetcher, "fetch_splits", None)
        if callable(method):
            return method(symbol=symbol)
        return _empty_splits()

    def _fetch_per(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        method = getattr(self.fetcher, "fetch_per", None)
        if not callable(method):
            return _empty_per()
        try:
            return method(symbol=symbol, start=start, end=end)
        except NotImplementedError:
            return _empty_per()

    def _fetch_monthly_revenue(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        method = getattr(self.fetcher, "fetch_monthly_revenue", None)
        if not callable(method):
            return _empty_monthly_revenue()
        try:
            return method(symbol=symbol, start=start, end=end)
        except NotImplementedError:
            return _empty_monthly_revenue()

    def _fetch_eps(self, symbol: str, start_date: str) -> pd.DataFrame:
        method = getattr(self.fetcher, "fetch_eps", None)
        if not callable(method):
            return _empty_eps()
        try:
            return method(symbol=symbol, start_date=start_date)
        except NotImplementedError:
            return _empty_eps()

    def _is_p11_missing(self, symbol: str, market: str) -> bool:
        if market != "tw":
            return False
        return (
            self.storage.load_per(symbol, market=market).empty
            or self.storage.load_monthly_revenue(symbol, market=market).empty
            or self.storage.load_eps(symbol, market=market).empty
            or self.storage.load_dividends(symbol, market=market).empty
        )

    _P11_LABELS = {
        "per": "PER",
        "monthly_revenue": "月營收",
        "dividends": "股利",
        "eps": "EPS",
    }

    def _rebuild_p11_datasets(self, symbol: str, market: str) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        source = self._source_name()

        # Each entry: (freq, fetcher_callable, saver, loader, post_process)
        def _filter_dividends(df: pd.DataFrame) -> pd.DataFrame:
            if df.empty:
                return df
            dividend_dates = pd.to_datetime(df["date"], errors="coerce")
            threshold = pd.Timestamp("2015-01-01")
            if getattr(dividend_dates.dt, "tz", None) is not None:
                threshold = threshold.tz_localize(dividend_dates.dt.tz)
            return df.loc[dividend_dates >= threshold].reset_index(drop=True)

        plans = [
            (
                "per",
                lambda: self._fetch_per(symbol=symbol, start="2015-01-01", end=today),
                self.storage.save_per,
                self.storage.load_per,
                None,
            ),
            (
                "monthly_revenue",
                lambda: self._fetch_monthly_revenue(symbol=symbol, start="2015-01-01", end=today),
                self.storage.save_monthly_revenue,
                self.storage.load_monthly_revenue,
                None,
            ),
            (
                "dividends",
                lambda: self._fetch_dividends(symbol=symbol),
                self.storage.save_dividends,
                self.storage.load_dividends,
                _filter_dividends,
            ),
            (
                "eps",
                lambda: self._fetch_eps(symbol=symbol, start_date="2015-01-01"),
                self.storage.save_eps,
                self.storage.load_eps,
                None,
            ),
        ]

        for freq, fetch_fn, save_fn, load_fn, post in plans:
            label = self._P11_LABELS[freq]
            existing_df = load_fn(symbol, market=market)
            try:
                new_df = fetch_fn()
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"{label} 更新失敗：{exc}")
                continue

            if post is not None:
                new_df = post(new_df)

            if new_df is None or new_df.empty:
                if not existing_df.empty:
                    self.warnings.append(
                        f"{label} 新抓回空資料，已保留本機既有 {len(existing_df)} 筆"
                    )
                continue

            # Non-empty new data → clear that one parquet then write fresh to
            # avoid upsert-merge preserving stale rows.
            self.storage.clear_p11_parquets(symbol, market=market, freqs=[freq])
            save_fn(symbol, new_df, market=market)
            self._update_meta(
                symbol=symbol,
                freq=freq,
                source=source,
                df=load_fn(symbol, market=market),
                market=market,
            )

    def _rebuild_p11_datasets_best_effort(self, symbol: str, market: str) -> None:
        # P11 datasets are additive for dashboard analytics. Per-dataset failures
        # are recorded in self.errors / self.warnings; only catch unexpected outer
        # exceptions (e.g. filesystem) so the primary daily pipeline never aborts.
        try:
            self._rebuild_p11_datasets(symbol=symbol, market=market)
        except Exception as exc:  # noqa: BLE001
            self.errors.append(f"P11 {symbol} rebuild failed: {exc}")


    def _source_name(self) -> str:
        cls = self.fetcher.__class__.__name__.lower()
        return cls.replace("fetcher", "")

    def _update_meta(self, symbol: str, freq: str, source: str, df: pd.DataFrame, market: str = "tw") -> None:
        if df.empty:
            self.meta.delete_meta_freq(symbol=symbol, freq=freq, market=market)
            return

        dates = pd.to_datetime(df["date"], errors="coerce").dropna()
        if dates.empty:
            return

        self.meta.upsert_meta(
            symbol=symbol,
            freq=freq,
            source=source,
            first_date=dates.min(),
            last_date=dates.max(),
            row_count=len(df),
            market=market,
        )

    def _supports_us_adjusted_bundle(self, market: str) -> bool:
        if market != "us":
            return False
        if self._source_name() != "yfinance":
            return False
        return callable(getattr(self.fetcher, "fetch_daily_with_adjusted", None))

    def _maybe_throttle_us_yfinance(self) -> None:
        if self._last_us_yfinance_request_ts is None:
            return
        elapsed = time.monotonic() - self._last_us_yfinance_request_ts
        if elapsed >= US_YFINANCE_REQUEST_INTERVAL_SECONDS:
            return
        time.sleep(US_YFINANCE_REQUEST_INTERVAL_SECONDS - elapsed)

    def _fetch_us_daily_bundle(self, symbol: str, start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bool]:
        self._maybe_throttle_us_yfinance()
        method = getattr(self.fetcher, "fetch_daily_with_adjusted", None)
        if not callable(method):
            raise RuntimeError("US adjusted bundle is not available from current fetcher.")
        try:
            raw_df, adjusted_df, splits_df, volume_adjusted = method(symbol=symbol, start=start, end=end)
        finally:
            self._last_us_yfinance_request_ts = time.monotonic()
        return raw_df, adjusted_df, splits_df, bool(volume_adjusted)

    def _filter_adjusted_by_cleaned_dates(self, adjusted_df: pd.DataFrame, cleaned_df: pd.DataFrame) -> pd.DataFrame:
        if adjusted_df.empty or cleaned_df.empty:
            return adjusted_df.iloc[0:0].copy()
        clean_dates = pd.to_datetime(cleaned_df["date"], errors="coerce").dropna()
        adjusted_dates = pd.to_datetime(adjusted_df["date"], errors="coerce")
        out = adjusted_df.loc[adjusted_dates.isin(clean_dates)].copy()
        return out.sort_values("date").reset_index(drop=True)

    def refresh_shareholder_meeting_once_per_day(self, market: str = "tw", now: pd.Timestamp | None = None) -> bool:
        normalized_market = normalize_market(market)
        if normalized_market != "tw":
            return False

        now_ts = pd.Timestamp(now or pd.Timestamp.now(tz=TAIPEI_TZ))
        if now_ts.tzinfo is None:
            now_ts = now_ts.tz_localize(TAIPEI_TZ)
        else:
            now_ts = now_ts.tz_convert(TAIPEI_TZ)

        meta_path = self.storage._shareholder_meeting_meta_path()  # noqa: SLF001
        data_path = self.storage._shareholder_meeting_path()  # noqa: SLF001

        if not should_update_shareholder_meeting(meta_path, now_ts):
            return False

        had_data = data_path.exists()
        had_meta = meta_path.exists()
        existing_df = self.storage.load_shareholder_meeting()
        existing_meta = self.storage.load_shareholder_meeting_meta()

        try:
            fetched = TWSEFetcher().fetch_shareholder_meeting()
            merged = merge_shareholder_meeting_auto(
                new_rows=fetched,
                existing=existing_df,
                now=now_ts,
                timezone=TAIPEI_TZ,
            )
            self.storage.save_shareholder_meeting(merged)
            self.storage.save_shareholder_meeting_meta({"last_updated_at": now_ts.isoformat()})
            return True
        except Exception:  # noqa: BLE001
            if had_data:
                self.storage.save_shareholder_meeting(existing_df)
            elif data_path.exists():
                data_path.unlink()

            if had_meta:
                self.storage.save_shareholder_meeting_meta(existing_meta)
            elif meta_path.exists():
                meta_path.unlink()
            raise
