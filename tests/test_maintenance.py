from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from src.core.constants import STANDARD_COLUMNS
from src.core.market import get_market_spec
from src.data.cleaner import DataCleaner
import src.data.maintenance as maintenance_module
from src.data.maintenance import DataMaintenance, should_update_shareholder_meeting
from src.data.storage import DuckDBMeta, ParquetStorage, _rmtree_with_retry
from src.core.exceptions import FetcherError


def _make_daily(symbol: str, start: str, periods: int, close_base: float = 100.0) -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=periods, freq="D")
    return pd.DataFrame(
        {
            "date": idx,
            "open": [close_base + i for i in range(periods)],
            "high": [close_base + i + 1 for i in range(periods)],
            "low": [close_base + i - 1 for i in range(periods)],
            "close": [close_base + i for i in range(periods)],
            "volume": [1000] * periods,
            "symbol": [symbol] * periods,
        }
    )[STANDARD_COLUMNS]


class StubFetcher:
    def __init__(
        self,
        full_daily: pd.DataFrame,
        incremental_daily: pd.DataFrame | None,
        dividends: pd.DataFrame,
        splits: pd.DataFrame | None = None,
    ):
        self.full_daily = full_daily
        self.incremental_daily = incremental_daily
        self.dividends = dividends
        self.splits = splits if splits is not None else pd.DataFrame(columns=["date", "before_price", "after_price", "symbol"])
        self.daily_calls: list[tuple[str, str, str]] = []
        self.per_calls: list[tuple[str, str, str]] = []
        self.monthly_calls: list[tuple[str, str, str]] = []
        self.eps_calls: list[tuple[str, str]] = []

    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        self.daily_calls.append((symbol, start, end))
        if start <= "2000-01-01":
            return self.full_daily.copy(deep=True)

        if self.incremental_daily is None or self.incremental_daily.empty:
            return pd.DataFrame(columns=STANDARD_COLUMNS)

        out = self.incremental_daily.copy(deep=True)
        out["date"] = pd.to_datetime(out["date"])
        mask = (out["date"] >= pd.Timestamp(start)) & (out["date"] <= pd.Timestamp(end))
        return out.loc[mask, STANDARD_COLUMNS].reset_index(drop=True)

    def fetch_minute(self, symbol: str, start: str, end: str, freq: str = "1") -> pd.DataFrame:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        return self.dividends.copy(deep=True)

    def fetch_splits(self, symbol: str) -> pd.DataFrame:
        return self.splits.copy(deep=True)

    def fetch_per(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        self.per_calls.append((symbol, start, end))
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-05-16"]),
                "per": [20.1],
                "pbr": [4.1],
                "dividend_yield": [2.3],
                "symbol": [symbol],
            }
        )

    def fetch_monthly_revenue(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        self.monthly_calls.append((symbol, start, end))
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-05-10"]),
                "revenue": [300_000_000_000.0],
                "revenue_month": [4],
                "revenue_year": [2026],
                "symbol": [symbol],
            }
        )

    def fetch_eps(self, symbol: str, start_date: str = "2015-01-01") -> pd.DataFrame:
        self.eps_calls.append((symbol, start_date))
        return pd.DataFrame(
            {
                "report_date": pd.to_datetime(["2026-05-15"]),
                "year": [2026],
                "quarter": [1],
                "eps": [3.2],
                "symbol": [symbol],
            }
        )


class StubFetcherP11Failure(StubFetcher):
    def fetch_per(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        raise RuntimeError("FinMind quota exceeded")


class YFinanceFetcher:
    def __init__(
        self,
        full_raw: pd.DataFrame,
        full_adjusted: pd.DataFrame,
        incremental_raw: pd.DataFrame | None,
        incremental_adjusted: pd.DataFrame | None,
        splits: pd.DataFrame | None = None,
        raise_fetch_error: bool = False,
    ) -> None:
        self.full_raw = full_raw
        self.full_adjusted = full_adjusted
        self.incremental_raw = incremental_raw
        self.incremental_adjusted = incremental_adjusted
        self.splits = splits if splits is not None else pd.DataFrame(columns=["date", "before_price", "after_price", "symbol"])
        self.bundle_calls: list[tuple[str, str, str]] = []
        self.raise_fetch_error = raise_fetch_error

    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    def fetch_minute(self, symbol: str, start: str, end: str, freq: str = "1") -> pd.DataFrame:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    def fetch_daily_with_adjusted(self, symbol: str, start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bool]:
        if self.raise_fetch_error:
            raise FetcherError("yfinance provider rate limited (HTTP 429).")
        self.bundle_calls.append((symbol, start, end))
        if start <= "2000-01-01":
            return (
                self.full_raw.copy(deep=True),
                self.full_adjusted.copy(deep=True),
                self.splits.copy(deep=True),
                True,
            )
        if self.incremental_raw is None or self.incremental_raw.empty:
            return (
                pd.DataFrame(columns=STANDARD_COLUMNS),
                pd.DataFrame(columns=STANDARD_COLUMNS),
                pd.DataFrame(columns=["date", "before_price", "after_price", "symbol"]),
                True,
            )
        return (
            self.incremental_raw.copy(deep=True),
            self.incremental_adjusted.copy(deep=True) if self.incremental_adjusted is not None else pd.DataFrame(columns=STANDARD_COLUMNS),
            self.splits.copy(deep=True),
            True,
        )


def test_rebuild_symbol_saves_and_updates_meta(tmp_path) -> None:
    full_daily = _make_daily("2330", "2024-06-24", 4)
    dividends = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-06-26")],
            "cash_dividend": [5.0],
            "stock_dividend": [0.0],
            "symbol": ["2330"],
        }
    )
    fetcher = StubFetcher(full_daily=full_daily, incremental_daily=None, dividends=dividends)
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    report = maintenance.rebuild_symbol("2330")

    assert report.total_rows == len(full_daily)
    raw_saved = storage.load_daily("2330")
    adj_saved = storage.load_adjusted("2330")
    assert not raw_saved.empty
    assert not adj_saved.empty
    adj_saved_dates = pd.to_datetime(adj_saved["date"], errors="coerce")
    target_close = adj_saved.loc[adj_saved_dates.dt.strftime("%Y-%m-%d") == "2024-06-24", "close"].iloc[0]
    assert target_close != 100.0

    row = meta.get_meta("2330", "daily")
    assert row is not None
    assert row["row_count"] == len(raw_saved)
    assert not storage.load_per("2330").empty
    assert not storage.load_monthly_revenue("2330").empty
    assert not storage.load_dividends("2330").empty
    assert not storage.load_eps("2330").empty
    assert meta.get_meta("2330", "per") is not None
    assert meta.get_meta("2330", "monthly_revenue") is not None
    assert meta.get_meta("2330", "dividends") is not None
    assert meta.get_meta("2330", "eps") is not None


def test_rebuild_symbol_applies_split(tmp_path) -> None:
    full_daily = pd.DataFrame(
        {
            "date": pd.Series(pd.to_datetime(["2025-06-17", "2025-06-18", "2025-06-19"]).tz_localize("Asia/Taipei")).astype("datetime64[ns, Asia/Taipei]"),
            "open": [188.65, 47.16, 47.5],
            "high": [189.0, 48.0, 48.0],
            "low": [188.0, 46.5, 47.0],
            "close": [188.65, 47.16, 47.8],
            "volume": [1000, 1000, 1000],
            "symbol": ["0050", "0050", "0050"],
        }
    )[STANDARD_COLUMNS]
    splits = pd.DataFrame(
        {
            "date": pd.Series(pd.to_datetime(["2025-06-18"]).tz_localize("Asia/Taipei")).astype("datetime64[ns, Asia/Taipei]"),
            "before_price": [188.65],
            "after_price": [47.16],
            "symbol": ["0050"],
        }
    )

    fetcher = StubFetcher(
        full_daily=full_daily,
        incremental_daily=None,
        dividends=pd.DataFrame(),
        splits=splits,
    )
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    maintenance.rebuild_symbol("0050")

    adjusted = storage.load_adjusted("0050")
    split_saved = storage.load_splits("0050")
    assert not adjusted.empty
    assert not split_saved.empty
    adj_pre_close = adjusted.loc[pd.to_datetime(adjusted["date"]) == pd.Timestamp("2025-06-17", tz="Asia/Taipei"), "close"].iloc[0]
    adj_split_close = adjusted.loc[pd.to_datetime(adjusted["date"]) == pd.Timestamp("2025-06-18", tz="Asia/Taipei"), "close"].iloc[0]
    assert adj_pre_close == pytest.approx(adj_split_close, abs=0.01)


def test_rebuild_adj_factors_overwrites_adjusted(tmp_path) -> None:
    full_daily = _make_daily("2330", "2024-06-24", 4)
    dividends = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-06-26")],
            "cash_dividend": [5.0],
            "stock_dividend": [0.0],
            "symbol": ["2330"],
        }
    )
    fetcher = StubFetcher(full_daily=full_daily, incremental_daily=None, dividends=dividends)
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    storage.save_daily("2330", full_daily)
    maintenance.rebuild_adj_factors("2330")
    adjusted = storage.load_adjusted("2330")
    assert not adjusted.empty
    adjusted_dates = pd.to_datetime(adjusted["date"], errors="coerce")
    target_close = adjusted.loc[adjusted_dates.dt.strftime("%Y-%m-%d") == "2024-06-24", "close"].iloc[0]
    assert target_close != 100.0


def test_validate_data_returns_quality_report(tmp_path) -> None:
    raw = _make_daily("2330", "2024-01-01", 3)
    raw.loc[1, "close"] = -10.0

    fetcher = StubFetcher(full_daily=raw, incremental_daily=None, dividends=pd.DataFrame())
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)
    storage.save_daily("2330", raw)

    report = maintenance.validate_data("2330")
    assert report.negative_price_count >= 1


def test_list_stale_symbols(tmp_path) -> None:
    fetcher = StubFetcher(full_daily=pd.DataFrame(columns=STANDARD_COLUMNS), incremental_daily=None, dividends=pd.DataFrame())
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    meta.upsert_meta(
        symbol="2330",
        freq="daily",
        source="stub",
        first_date=pd.Timestamp("2024-01-01"),
        last_date=pd.Timestamp("2024-01-10"),
        row_count=10,
    )
    meta._conn.execute("UPDATE data_meta SET updated_at = TIMESTAMP '2000-01-01 00:00:00+00';")

    stale = maintenance.list_stale_symbols(days=7)
    assert any(item["symbol"] == "2330" for item in stale)


def test_should_update_shareholder_meeting_when_meta_missing(tmp_path) -> None:
    meta_path = tmp_path / "shareholder_meeting.meta.json"
    now = pd.Timestamp("2026-05-17T10:00:00+08:00")
    assert should_update_shareholder_meeting(meta_path, now) is True


def test_should_update_shareholder_meeting_when_meta_is_today(tmp_path) -> None:
    meta_path = tmp_path / "shareholder_meeting.meta.json"
    meta_path.write_text('{"last_updated_at":"2026-05-17T01:00:00+08:00"}', encoding="utf-8")
    now = pd.Timestamp("2026-05-17T10:00:00+08:00")
    assert should_update_shareholder_meeting(meta_path, now) is False


def test_should_update_shareholder_meeting_when_meta_is_yesterday(tmp_path) -> None:
    meta_path = tmp_path / "shareholder_meeting.meta.json"
    meta_path.write_text('{"last_updated_at":"2026-05-16T23:59:59+08:00"}', encoding="utf-8")
    now = pd.Timestamp("2026-05-17T00:01:00+08:00")
    assert should_update_shareholder_meeting(meta_path, now) is True


def test_update_daily_returns_added_rows(tmp_path) -> None:
    existing = _make_daily("2330", "2024-01-01", 2)
    incremental = _make_daily("2330", "2024-01-03", 2)
    fetcher = StubFetcher(full_daily=existing, incremental_daily=incremental, dividends=pd.DataFrame())
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    storage.save_daily("2330", existing)
    added = maintenance.update_daily("2330")
    merged = storage.load_daily("2330")

    assert added == 2
    assert len(merged) == 4
    assert pd.to_datetime(merged["date"]).max().date() >= datetime(2024, 1, 4).date()


def test_update_daily_tw_does_not_touch_p11(tmp_path) -> None:
    """update_daily 只更新日 K，不應觸發 P11 抓取（即使 P11 fetch 會炸也不該被呼叫）。"""
    existing = _make_daily("2330", "2024-01-01", 2)
    incremental = _make_daily("2330", "2024-01-03", 2)
    fetcher = StubFetcherP11Failure(full_daily=existing, incremental_daily=incremental, dividends=pd.DataFrame())
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    storage.save_daily("2330", existing)
    added = maintenance.update_daily("2330", market="tw")
    merged = storage.load_daily("2330")

    assert added == 2
    assert len(merged) == 4
    # P11 should not be touched on update — fetcher.per_calls must stay empty
    assert fetcher.per_calls == []
    assert fetcher.monthly_calls == []
    assert fetcher.eps_calls == []
    assert maintenance.warnings == []
    assert maintenance.errors == []
    # P11 parquets should remain empty since update never fetches them
    assert storage.load_per("2330").empty


def test_update_daily_rebuilds_adjusted_when_no_new_rows(tmp_path) -> None:
    existing = _make_daily("2330", "2024-06-24", 2)
    dividends = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-06-25")],
            "cash_dividend": [5.0],
            "stock_dividend": [0.0],
            "symbol": ["2330"],
        }
    )
    fetcher = StubFetcher(full_daily=existing, incremental_daily=pd.DataFrame(columns=STANDARD_COLUMNS), dividends=dividends)
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    storage.save_daily("2330", existing)
    added = maintenance.update_daily("2330")

    adjusted = storage.load_adjusted("2330")
    assert added == 0
    assert not adjusted.empty
    adjusted_dates = pd.to_datetime(adjusted["date"], errors="coerce")
    adjusted_first = adjusted.loc[adjusted_dates.dt.strftime("%Y-%m-%d") == "2024-06-24", "close"].iloc[0]
    assert adjusted_first == pytest.approx(95.0)


def test_update_daily_tw_does_not_backfill_p11_when_missing_and_no_new_rows(tmp_path) -> None:
    """更新只動日 K — 即使 P11 為空，也不可以自動補抓 P11。"""
    existing = _make_daily("2330", "2024-06-24", 2)
    fetcher = StubFetcher(
        full_daily=existing,
        incremental_daily=pd.DataFrame(columns=STANDARD_COLUMNS),
        dividends=pd.DataFrame(),
    )
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    storage.save_daily("2330", existing)
    assert meta.get_meta("2330", "per") is None

    added = maintenance.update_daily("2330", market="tw")

    assert added == 0
    # P11 must stay untouched — explicit rebuild is required to populate it.
    assert storage.load_per("2330").empty
    assert storage.load_monthly_revenue("2330").empty
    assert storage.load_eps("2330").empty
    assert meta.get_meta("2330", "per") is None
    assert fetcher.per_calls == []


def test_maintenance_passes_market_to_storage(tmp_path) -> None:
    existing = _make_daily("AAPL", "2024-01-01", 2)
    incremental = _make_daily("AAPL", "2024-01-03", 1)
    fetcher = StubFetcher(full_daily=existing, incremental_daily=incremental, dividends=pd.DataFrame())
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    storage.save_daily("AAPL", existing, market="us")
    added = maintenance.update_daily("AAPL", market="us")
    loaded = storage.load_daily("AAPL", market="us")
    row = meta.get_meta("AAPL", "daily", market="us")
    expected_path = tmp_path / "data" / "raw" / "us" / "AAPL" / "daily.parquet"

    assert added == 1
    assert expected_path.exists()
    assert str(loaded["date"].dtype) == f"datetime64[ns, {get_market_spec('us').timezone}]"
    assert row is not None
    assert row["market"] == "us"


def test_maintenance_rebuild_us_symbol_saves_raw_and_adjusted(tmp_path) -> None:
    ny_tz = get_market_spec("us").timezone
    full_raw = pd.DataFrame(
        {
            "date": pd.Series(pd.date_range("2024-01-01", periods=2, tz=ny_tz)),
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.0, 101.0],
            "volume": [1000, 1200],
            "symbol": ["AAPL", "AAPL"],
        }
    )[STANDARD_COLUMNS]
    full_adjusted = full_raw.copy(deep=True)
    full_adjusted["close"] = [95.0, 96.0]

    fetcher = YFinanceFetcher(
        full_raw=full_raw,
        full_adjusted=full_adjusted,
        incremental_raw=None,
        incremental_adjusted=None,
    )
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    report = maintenance.rebuild_symbol("AAPL", market="us")
    raw_saved = storage.load_daily("AAPL", market="us")
    adjusted_saved = storage.load_adjusted("AAPL", market="us")

    assert report.total_rows == 2
    assert len(raw_saved) == 2
    assert len(adjusted_saved) == 2
    assert adjusted_saved.loc[0, "close"] == pytest.approx(95.0)


def test_maintenance_update_us_symbol_is_incremental(tmp_path) -> None:
    ny_tz = get_market_spec("us").timezone
    existing = pd.DataFrame(
        {
            "date": pd.Series(pd.date_range("2024-01-01", periods=2, tz=ny_tz)),
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.0, 101.0],
            "volume": [1000, 1200],
            "symbol": ["AAPL", "AAPL"],
        }
    )[STANDARD_COLUMNS]
    existing_adj = existing.copy(deep=True)
    existing_adj["close"] = [95.0, 96.0]
    incremental = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-03", tz=ny_tz)],
            "open": [102.0],
            "high": [103.0],
            "low": [101.0],
            "close": [102.0],
            "volume": [1300],
            "symbol": ["AAPL"],
        }
    )[STANDARD_COLUMNS]
    incremental_adj = incremental.copy(deep=True)
    incremental_adj["close"] = [97.0]

    fetcher = YFinanceFetcher(
        full_raw=existing,
        full_adjusted=existing_adj,
        incremental_raw=incremental,
        incremental_adjusted=incremental_adj,
    )
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    storage.save_daily("AAPL", existing, market="us")
    storage.save_adjusted("AAPL", existing_adj, market="us")

    added = maintenance.update_daily("AAPL", market="us")
    merged_raw = storage.load_daily("AAPL", market="us")
    merged_adj = storage.load_adjusted("AAPL", market="us")

    assert added == 1
    assert len(merged_raw) == 3
    assert len(merged_adj) == 3
    assert float(merged_adj.loc[len(merged_adj) - 1, "close"]) == pytest.approx(97.0)


def test_maintenance_batch_update_us_symbols_throttles_yfinance(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    ny_tz = get_market_spec("us").timezone
    incremental = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01", tz=ny_tz)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [1000],
            "symbol": ["AAPL"],
        }
    )[STANDARD_COLUMNS]
    fetcher = YFinanceFetcher(
        full_raw=incremental,
        full_adjusted=incremental,
        incremental_raw=incremental,
        incremental_adjusted=incremental,
    )
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    fake_now = {"t": 100.0}
    sleeps: list[float] = []

    def fake_monotonic() -> float:
        return fake_now["t"]

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        fake_now["t"] += seconds

    monkeypatch.setattr(maintenance_module.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(maintenance_module.time, "sleep", fake_sleep)

    maintenance.update_daily("AAPL", market="us")
    maintenance.update_daily("MSFT", market="us")

    assert sleeps
    assert sleeps[-1] >= maintenance_module.US_YFINANCE_REQUEST_INTERVAL_SECONDS


def test_maintenance_us_rate_limit_reports_provider_error(tmp_path) -> None:
    empty = pd.DataFrame(columns=STANDARD_COLUMNS)
    fetcher = YFinanceFetcher(
        full_raw=empty,
        full_adjusted=empty,
        incremental_raw=empty,
        incremental_adjusted=empty,
        raise_fetch_error=True,
    )
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    with pytest.raises(FetcherError, match="rate limited|429"):
        maintenance.update_daily("AAPL", market="us")

    assert meta.get_meta("AAPL", "daily", market="us") is None
    assert storage.load_daily("AAPL", market="us").empty


def test_storage_delete_symbol_removes_parquets(tmp_path) -> None:
    """ParquetStorage.delete_symbol must remove all raw/ and processed/ files for the symbol."""
    storage = ParquetStorage(data_dir=tmp_path / "data")
    daily = _make_daily("2330", "2024-01-01", 3)
    storage.save_daily("2330", daily)
    assert not storage.load_daily("2330").empty

    storage.delete_symbol("2330", market="tw")

    assert storage.load_daily("2330").empty


def test_delete_symbol_keeps_global_shareholder_files(tmp_path) -> None:
    storage = ParquetStorage(data_dir=tmp_path / "data")
    storage.save_daily("2330", _make_daily("2330", "2024-01-01", 2))
    storage.save_shareholder_meeting(
        pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2026-06-30", tz="Asia/Taipei"),
                    "symbol": "2330",
                    "meeting_type": "常會",
                    "source": "auto",
                    "updated_at": pd.Timestamp("2026-05-17T10:00:00+08:00"),
                }
            ]
        )
    )
    storage.save_shareholder_meeting_meta({"last_updated_at": "2026-05-17T10:00:00+08:00"})
    storage.upsert_shareholder_meeting_override(symbol="2330", date="2026-06-30", meeting_type="常會")

    storage.delete_symbol("2330", market="tw")

    assert storage.load_daily("2330").empty
    assert not storage.load_shareholder_meeting().empty
    assert storage.load_shareholder_meeting_meta().get("last_updated_at") is not None
    assert not storage.load_shareholder_meeting_override().empty


def test_meta_delete_symbol_removes_rows(tmp_path) -> None:
    """DuckDBMeta.delete_symbol must remove all metadata rows for the symbol."""
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    meta.upsert_meta("2330", "daily", "finmind", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"), 250, market="tw")
    meta.upsert_meta("2330", "per", "finmind", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"), 250, market="tw")
    assert meta.get_meta("2330", "daily", market="tw") is not None

    meta.delete_symbol("2330", market="tw")

    assert meta.get_meta("2330", "daily", market="tw") is None
    assert meta.get_meta("2330", "per", market="tw") is None


def test_rebuild_p11_replaces_stale_eps(tmp_path) -> None:
    """_rebuild_p11_datasets must overwrite old EPS data instead of upsert-merging it,
    so stale records with wrong dates do not survive a rebuild."""
    existing = _make_daily("2330", "2024-01-01", 3)
    fetcher = StubFetcher(
        full_daily=existing,
        incremental_daily=pd.DataFrame(columns=STANDARD_COLUMNS),
        dividends=pd.DataFrame(),
    )
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    # Seed stale EPS with a wrong year (simulating corrupt old data)
    stale_eps = pd.DataFrame(
        {
            "report_date": pd.to_datetime(["2020-05-01"]),
            "year": [1999],  # intentionally wrong
            "quarter": [1],
            "eps": [99.0],
            "symbol": ["2330"],
        }
    )
    storage.save_eps("2330", stale_eps)
    loaded_before = storage.load_eps("2330")
    assert 1999 in loaded_before["year"].values

    # Rebuild should overwrite; StubFetcher.fetch_eps returns year=2026/Q1
    storage.save_daily("2330", existing)
    maintenance.rebuild_symbol("2330", market="tw")

    loaded_after = storage.load_eps("2330")
    # Stale year=1999 must be gone
    assert 1999 not in loaded_after["year"].values
    assert 2026 in loaded_after["year"].values


# ---------------------------------------------------------------------------
# _rmtree_with_retry — Windows ReadOnly attribute
# ---------------------------------------------------------------------------


def test_rmtree_with_retry_removes_readonly_directory(tmp_path: pytest.TempPathFactory) -> None:
    import os
    import stat

    target = tmp_path / "readonly_dir"
    target.mkdir()
    (target / "file.txt").write_text("data")

    # Mark directory and file as read-only (simulates Windows ReadOnly attribute)
    for p in [target / "file.txt", target]:
        current = os.stat(p).st_mode
        os.chmod(p, current & ~stat.S_IWRITE)

    # Plain rmtree would raise PermissionError on Windows; _rmtree_with_retry must succeed
    _rmtree_with_retry(target)
    assert not target.exists()


def test_rebuild_symbol_tw_replaces_stale_meta_when_parquet_is_empty(tmp_path) -> None:
    """重建 (而非更新) 才是 P11 補抓的入口。stale meta + 空 parquet 重建後要被新資料覆蓋。"""
    existing = _make_daily("2330", "2024-06-24", 2)
    fetcher = StubFetcher(
        full_daily=existing,
        incremental_daily=pd.DataFrame(columns=STANDARD_COLUMNS),
        dividends=pd.DataFrame(),
    )
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    # Seed stale metadata for per where parquet is actually empty
    meta.upsert_meta(
        symbol="2330",
        freq="per",
        source="finmind",
        first_date=pd.Timestamp("2024-01-01"),
        last_date=pd.Timestamp("2024-01-10"),
        row_count=10,
        market="tw",
    )
    assert meta.get_meta("2330", "per", market="tw") is not None
    assert storage.load_per("2330").empty

    storage.save_daily("2330", existing)
    maintenance.rebuild_symbol("2330", market="tw")

    assert not storage.load_per("2330").empty
    assert meta.get_meta("2330", "per", market="tw") is not None
    assert meta.get_meta("2330", "per", market="tw")["row_count"] == 1


def test_rebuild_p11_preserves_old_dividends_when_fetch_returns_empty(tmp_path) -> None:
    """當 P11 新 fetch 回空但本機原本有 dividends，必須保留舊資料並 warning。"""
    existing = _make_daily("2330", "2024-06-24", 2)
    fetcher = StubFetcher(
        full_daily=existing,
        incremental_daily=pd.DataFrame(columns=STANDARD_COLUMNS),
        dividends=pd.DataFrame(),  # ← P11 dividends fetch returns empty
    )
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    # Seed old dividends locally
    old_dividends = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-06-15", "2024-06-15"]),
            "cash_dividend": [4.0, 5.0],
            "stock_dividend": [0.0, 0.0],
            "symbol": ["2330", "2330"],
        }
    )
    storage.save_dividends("2330", old_dividends)
    assert len(storage.load_dividends("2330")) == 2

    storage.save_daily("2330", existing)
    maintenance.rebuild_symbol("2330", market="tw")

    # Old dividends must remain — not wiped by the empty new fetch
    preserved = storage.load_dividends("2330")
    assert len(preserved) == 2
    # A warning must be recorded so the user/UI sees the issue
    assert any("股利" in w and "保留本機" in w for w in maintenance.warnings)
    assert maintenance.errors == []


def test_rebuild_p11_records_error_when_fetch_raises(tmp_path) -> None:
    """P11 fetch 拋例外時要列入 errors（紅色 toast 來源），不能拖垮整個 rebuild。"""
    existing = _make_daily("2330", "2024-06-24", 2)
    fetcher = StubFetcherP11Failure(
        full_daily=existing,
        incremental_daily=pd.DataFrame(columns=STANDARD_COLUMNS),
        dividends=pd.DataFrame(),
    )
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    storage.save_daily("2330", existing)
    maintenance.rebuild_symbol("2330", market="tw")

    # PER fetch raises; should accumulate in errors, but other P11 datasets still attempt
    assert any("PER" in e and "FinMind quota" in e for e in maintenance.errors)
    # Monthly revenue / EPS / dividends still ran (per StubFetcher behavior)
    assert fetcher.monthly_calls != [] or fetcher.eps_calls != []




def test_update_meta_removes_meta_from_db_on_empty_dataframe(tmp_path) -> None:
    fetcher = StubFetcher(
        full_daily=pd.DataFrame(columns=STANDARD_COLUMNS),
        incremental_daily=pd.DataFrame(columns=STANDARD_COLUMNS),
        dividends=pd.DataFrame(),
    )
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    # Seed metadata
    meta.upsert_meta(
        symbol="2330",
        freq="per",
        source="finmind",
        first_date=pd.Timestamp("2024-01-01"),
        last_date=pd.Timestamp("2024-01-10"),
        row_count=10,
        market="tw",
    )
    assert meta.get_meta("2330", "per", market="tw") is not None

    # Call _update_meta with empty DataFrame
    maintenance._update_meta(
        symbol="2330",
        freq="per",
        source="finmind",
        df=pd.DataFrame(),
        market="tw",
    )

    # Metadata should be deleted from DB
    assert meta.get_meta("2330", "per", market="tw") is None

