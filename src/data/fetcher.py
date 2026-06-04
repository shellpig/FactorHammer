from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
import ssl
import time
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
import yfinance as yf


from src.core.config import get_config
from src.core.constants import (
    DIVIDENDS_COLUMNS,
    EPS_COLUMNS,
    INSTITUTIONAL_COLUMNS,
    MARGIN_COLUMNS,
    MONTHLY_REVENUE_COLUMNS,
    PER_COLUMNS,
    SHAREHOLDER_MEETING_COLUMNS,
    SPLITS_COLUMNS,
    STANDARD_COLUMNS,
    TAIPEI_TZ,
)
from src.core.exceptions import FetcherError
from src.core.market import get_market_spec, normalize_market, normalize_symbol


def _empty_standard_dataframe(timezone: str = TAIPEI_TZ) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype=f"datetime64[ns, {timezone}]"),
            "open": pd.Series(dtype="float64"),
            "high": pd.Series(dtype="float64"),
            "low": pd.Series(dtype="float64"),
            "close": pd.Series(dtype="float64"),
            "volume": pd.Series(dtype="int64"),
            "symbol": pd.Series(dtype="object"),
        }
    )[STANDARD_COLUMNS]


def _empty_dividends_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype=f"datetime64[ns, {TAIPEI_TZ}]"),
            "cash_dividend": pd.Series(dtype="float64"),
            "stock_dividend": pd.Series(dtype="float64"),
            "symbol": pd.Series(dtype="object"),
        }
    )[DIVIDENDS_COLUMNS]


def _empty_splits_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype=f"datetime64[ns, {TAIPEI_TZ}]"),
            "before_price": pd.Series(dtype="float64"),
            "after_price": pd.Series(dtype="float64"),
            "symbol": pd.Series(dtype="object"),
        }
    )[SPLITS_COLUMNS]


def _empty_eps_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype=f"datetime64[ns, {TAIPEI_TZ}]"),
            "year": pd.Series(dtype="int64"),
            "quarter": pd.Series(dtype="int64"),
            "eps": pd.Series(dtype="float64"),
            "symbol": pd.Series(dtype="object"),
            "report_date": pd.Series(dtype=f"datetime64[ns, {TAIPEI_TZ}]"),
        }
    )[[*EPS_COLUMNS, "report_date"]]


def _empty_per_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype=f"datetime64[ns, {TAIPEI_TZ}]"),
            "per": pd.Series(dtype="float64"),
            "pbr": pd.Series(dtype="float64"),
            "dividend_yield": pd.Series(dtype="float64"),
            "symbol": pd.Series(dtype="object"),
        }
    )[PER_COLUMNS]


def _empty_monthly_revenue_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype=f"datetime64[ns, {TAIPEI_TZ}]"),
            "revenue": pd.Series(dtype="float64"),
            "revenue_month": pd.Series(dtype="int64"),
            "revenue_year": pd.Series(dtype="int64"),
            "symbol": pd.Series(dtype="object"),
        }
    )[MONTHLY_REVENUE_COLUMNS]


def _empty_institutional_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype=f"datetime64[ns, {TAIPEI_TZ}]"),
            "foreign_buy": pd.Series(dtype="int64"),
            "foreign_sell": pd.Series(dtype="int64"),
            "foreign_net": pd.Series(dtype="int64"),
            "trust_buy": pd.Series(dtype="int64"),
            "trust_sell": pd.Series(dtype="int64"),
            "trust_net": pd.Series(dtype="int64"),
            "dealer_buy": pd.Series(dtype="int64"),
            "dealer_sell": pd.Series(dtype="int64"),
            "dealer_net": pd.Series(dtype="int64"),
            "symbol": pd.Series(dtype="object"),
        }
    )[INSTITUTIONAL_COLUMNS]


def _empty_margin_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype=f"datetime64[ns, {TAIPEI_TZ}]"),
            "margin_buy": pd.Series(dtype="int64"),
            "margin_sell": pd.Series(dtype="int64"),
            "margin_balance": pd.Series(dtype="int64"),
            "short_buy": pd.Series(dtype="int64"),
            "short_sell": pd.Series(dtype="int64"),
            "short_balance": pd.Series(dtype="int64"),
            "symbol": pd.Series(dtype="object"),
        }
    )[MARGIN_COLUMNS]


@dataclass(frozen=True)
class USIntradaySnapshot:
    """Minimal intraday snapshot for US market (9-G)."""

    symbol: str
    price: float
    previous_raw_close: float
    change: float
    change_pct: float
    volume: int
    timestamp: pd.Timestamp  # America/New_York, timezone-aware
    source: str = "yfinance"
    interval: str = "1m"


def _localize_to_timezone(df: pd.DataFrame, timezone: str, col: str = "date") -> pd.DataFrame:
    target_dtype = f"datetime64[ns, {timezone}]"

    if col not in df.columns:
        raise FetcherError(f"Missing required datetime column: {col}")

    if df.empty:
        out = df.copy()
        out[col] = pd.Series(dtype=target_dtype)
        return out

    out = df.copy()
    series = pd.to_datetime(out[col], errors="coerce")

    if series.dt.tz is None:
        out[col] = series.dt.tz_localize(timezone)
    else:
        out[col] = series.dt.tz_convert(timezone)
    out[col] = out[col].astype(target_dtype)
    return out


def localize_to_taipei(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    """
    Standardize datetime column to Asia/Taipei.

    If source datetimes are naive, they are localized to Asia/Taipei.
    If source datetimes are timezone-aware, they are converted to Asia/Taipei.
    """
    return _localize_to_timezone(df=df, timezone=TAIPEI_TZ, col=col)


def _finalize_schema(df: pd.DataFrame, symbol: str, timezone: str = TAIPEI_TZ) -> pd.DataFrame:
    if df.empty:
        return _empty_standard_dataframe(timezone=timezone)

    out = df.copy()

    for col in STANDARD_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    out["symbol"] = out["symbol"].fillna(symbol).astype(str)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).copy()
    if out.empty:
        return _empty_standard_dataframe(timezone=timezone)

    out = _localize_to_timezone(out, timezone=timezone, col="date")

    for price_col in ("open", "high", "low", "close"):
        out[price_col] = pd.to_numeric(out[price_col], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"]).copy()
    if out.empty:
        return _empty_standard_dataframe(timezone=timezone)

    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0).astype("int64")
    out["open"] = out["open"].astype("float64")
    out["high"] = out["high"].astype("float64")
    out["low"] = out["low"].astype("float64")
    out["close"] = out["close"].astype("float64")

    out = out[STANDARD_COLUMNS].sort_values("date").reset_index(drop=True)
    return out


def _finalize_intraday_schema(raw: pd.DataFrame, symbol: str, timezone: str) -> pd.DataFrame:
    """Normalize yfinance intraday raw DataFrame to STANDARD_COLUMNS with bar timestamps.

    Used by YFinanceFetcher.fetch_us_intraday() (9-G).
    Timestamps are timezone-aware in the given timezone (America/New_York for US).
    """
    if raw is None or (hasattr(raw, "empty") and raw.empty):
        return _empty_standard_dataframe(timezone)

    normalized = raw.copy()
    if isinstance(normalized.columns, pd.MultiIndex):
        normalized.columns = normalized.columns.get_level_values(0)

    normalized = normalized.reset_index()
    date_col = normalized.columns[0]
    mapped = normalized.rename(
        columns={
            date_col: "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    mapped["symbol"] = symbol
    return _finalize_schema(mapped, symbol=symbol, timezone=timezone)


class IDataFetcher(ABC):
    """Abstract interface for all fetchers."""

    @abstractmethod
    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Fetch daily bars."""

    @abstractmethod
    def fetch_minute(self, symbol: str, start: str, end: str, freq: str = "1") -> pd.DataFrame:
        """Fetch minute bars."""

    @abstractmethod
    def fetch_per(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Fetch PER/PBR/dividend-yield time series."""

    @abstractmethod
    def fetch_monthly_revenue(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Fetch monthly revenue time series."""


class FinMindFetcher(IDataFetcher):
    """FinMind data source fetcher."""

    BASE_URL = "https://api.finmindtrade.com/api/v4/data"
    VALID_MINUTE_FREQ = {"1", "5", "15", "30", "60"}

    def __init__(
        self,
        token: str | None = None,
        session: requests.Session | None = None,
        retries: int = 3,
        timeout_seconds: int = 20,
    ):
        if token is None:
            config = get_config()
            secrets = config.get("secrets", {})
            if isinstance(secrets, dict):
                token = str(secrets.get("finmind_token", "")).strip()
            else:
                token = ""

        if not token:
            raise FetcherError("FINMIND_TOKEN is required for FinMindFetcher.")

        self._token = token
        self._session = session or requests.Session()
        self._retries = max(1, retries)
        self._timeout_seconds = timeout_seconds

    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        raw = self._request_data(
            {
                "dataset": "TaiwanStockPrice",
                "data_id": symbol,
                "start_date": start,
                "end_date": end,
            }
        )
        return self._normalize_finmind(raw, symbol=symbol)

    def fetch_minute(self, symbol: str, start: str, end: str, freq: str = "1") -> pd.DataFrame:
        if freq not in self.VALID_MINUTE_FREQ:
            raise ValueError(f"Unsupported minute frequency: {freq}")

        raw = self._request_data(
            {
                "dataset": "TaiwanStockPriceMinute",
                "data_id": symbol,
                "start_date": start,
                "end_date": end,
                "timeframe": freq,
            }
        )
        return self._normalize_finmind(raw, symbol=symbol)

    def fetch_per(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        raw = self._request_data(
            {
                "dataset": "TaiwanStockPER",
                "data_id": symbol,
                "start_date": start,
                "end_date": end,
            }
        )
        return self._normalize_per(raw, symbol=symbol)

    def fetch_monthly_revenue(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        raw = self._request_data(
            {
                "dataset": "TaiwanStockMonthRevenue",
                "data_id": symbol,
                "start_date": start,
                "end_date": end,
            }
        )
        return self._normalize_monthly_revenue(raw, symbol=symbol)

    def fetch_stock_info(self) -> pd.DataFrame:
        """Fetch Taiwan stock metadata for UI symbol lookup."""
        raw = self._request_data({"dataset": "TaiwanStockInfo"})
        if raw.empty:
            return pd.DataFrame(columns=["symbol", "name", "type", "industry"])

        out = raw.rename(
            columns={
                "stock_id": "symbol",
                "stock_name": "name",
                "industry_category": "industry",
            }
        ).copy()
        for col in ("symbol", "name", "type", "industry"):
            if col not in out.columns:
                out[col] = ""
            out[col] = out[col].fillna("").astype(str).str.strip()
        out = out[out["symbol"] != ""].drop_duplicates(subset=["symbol"], keep="first")
        return out[["symbol", "name", "type", "industry"]].sort_values("symbol").reset_index(drop=True)

    def fetch_dividends(self, symbol: str, start_date: str = "2000-01-01") -> pd.DataFrame:
        """
        Fetch Taiwan stock dividend events from FinMind.

        Returns columns:
        - date: ex-dividend trading date (tz-aware Asia/Taipei)
        - cash_dividend: cash dividend (NTD/share)
        - stock_dividend: stock dividend (NTD/share, ratio * 10)
        - symbol: stock id
        """
        raw = self._request_data(
            {
                "dataset": "TaiwanStockDividend",
                "data_id": symbol,
                "start_date": start_date,
            }
        )
        return self._normalize_dividends(raw, symbol=symbol)

    def fetch_eps(self, symbol: str, start_date: str = "2000-01-01") -> pd.DataFrame:
        """
        Fetch EPS records from FinMind financial statements dataset.

        Returns columns:
        - year: fiscal year
        - quarter: 1-4
        - eps: EPS value
        - symbol: stock id
        - report_date: source report date (tz-aware Asia/Taipei)
        """
        raw = self._request_data(
            {
                "dataset": "TaiwanStockFinancialStatements",
                "data_id": symbol,
                "start_date": start_date,
            }
        )
        return self._normalize_eps(raw, symbol=symbol)

    def fetch_splits(self, symbol: str, start_date: str = "2000-01-01") -> pd.DataFrame:
        """
        Fetch Taiwan stock split events from FinMind.

        Returns columns:
        - date: split trading date (tz-aware Asia/Taipei)
        - before_price: theoretical pre-split reference price
        - after_price: post-split reference/opening price
        - symbol: stock id
        """
        raw = self._request_data(
            {
                "dataset": "TaiwanStockSplitPrice",
                "data_id": symbol,
                "start_date": start_date,
            }
        )
        return self._normalize_splits(raw, symbol=symbol)

    def fetch_institutional(self, symbol: str, start_date: str) -> pd.DataFrame:
        """
        Fetch institutional buy/sell data and normalize to wide format.

        Returned unit is shares (股).
        """
        raw = self._request_data(
            {
                "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
                "data_id": symbol,
                "start_date": start_date,
            }
        )
        return self._normalize_institutional(raw, symbol=symbol)

    def fetch_margin(self, symbol: str, start_date: str) -> pd.DataFrame:
        """
        Fetch margin/short data and normalize to canonical schema.

        Returned unit is lots (張).
        """
        raw = self._request_data(
            {
                "dataset": "TaiwanStockMarginPurchaseShortSale",
                "data_id": symbol,
                "start_date": start_date,
            }
        )
        return self._normalize_margin(raw, symbol=symbol)

    def fetch_institutional_incremental(
        self,
        symbol: str,
        storage: Any,
        *,
        default_start_date: str = "2000-01-01",
    ) -> pd.DataFrame:
        existing = storage.load_institutional(symbol)
        if existing.empty:
            start_date = default_start_date
        else:
            last_date = pd.to_datetime(existing["date"], errors="coerce").max()
            if pd.isna(last_date):
                start_date = default_start_date
            else:
                start_date = (last_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        incoming = self.fetch_institutional(symbol, start_date)
        merged = pd.concat([existing, incoming], ignore_index=True)
        merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
        merged = merged.dropna(subset=["date"]).drop_duplicates(subset=["date", "symbol"], keep="last")
        merged = merged.sort_values("date").reset_index(drop=True)
        storage.save_institutional(symbol, merged)
        return merged

    def fetch_margin_incremental(
        self,
        symbol: str,
        storage: Any,
        *,
        default_start_date: str = "2000-01-01",
    ) -> pd.DataFrame:
        existing = storage.load_margin(symbol)
        if existing.empty:
            start_date = default_start_date
        else:
            last_date = pd.to_datetime(existing["date"], errors="coerce").max()
            if pd.isna(last_date):
                start_date = default_start_date
            else:
                start_date = (last_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        incoming = self.fetch_margin(symbol, start_date)
        merged = pd.concat([existing, incoming], ignore_index=True)
        merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
        merged = merged.dropna(subset=["date"]).drop_duplicates(subset=["date", "symbol"], keep="last")
        merged = merged.sort_values("date").reset_index(drop=True)
        storage.save_margin(symbol, merged)
        return merged

    def _request_data(self, params: dict[str, Any]) -> pd.DataFrame:
        headers = {"Authorization": f"Bearer {self._token}"}
        last_error: Exception | None = None

        for attempt in range(1, self._retries + 1):
            try:
                response = self._session.get(
                    self.BASE_URL,
                    params=params,
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                data = payload.get("data", [])
                if not isinstance(data, list):
                    raise FetcherError("Unexpected FinMind payload structure: data is not a list.")
                return pd.DataFrame(data)
            except (requests.RequestException, ValueError, FetcherError) as exc:
                last_error = exc
                if attempt < self._retries:
                    time.sleep(2 ** (attempt - 1))

        raise FetcherError(f"FinMind request failed after {self._retries} attempts.") from last_error

    def _normalize_finmind(self, raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if raw.empty:
            return _empty_standard_dataframe()

        mapped = raw.rename(
            columns={
                "date": "date",
                "open": "open",
                "max": "high",
                "min": "low",
                "close": "close",
                "Trading_Volume": "volume",
                "stock_id": "symbol",
            }
        )
        return _finalize_schema(mapped, symbol=symbol)

    def _normalize_dividends(self, raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if raw.empty:
            return _empty_dividends_dataframe()

        out = raw.copy()
        for col in (
            "CashExDividendTradingDate",
            "StockExDividendTradingDate",
            "date",
            "CashEarningsDistribution",
            "CashStatutorySurplus",
            "StockEarningsDistribution",
            "StockStatutorySurplus",
            "stock_id",
        ):
            if col not in out.columns:
                out[col] = pd.NA

        ex_date_series = out[["CashExDividendTradingDate", "StockExDividendTradingDate", "date"]].bfill(axis=1).iloc[:, 0]
        normalized = pd.DataFrame(
            {
                "date": ex_date_series,
                "cash_dividend": pd.to_numeric(out["CashEarningsDistribution"], errors="coerce").fillna(0.0)
                + pd.to_numeric(out["CashStatutorySurplus"], errors="coerce").fillna(0.0),
                "stock_dividend": pd.to_numeric(out["StockEarningsDistribution"], errors="coerce").fillna(0.0)
                + pd.to_numeric(out["StockStatutorySurplus"], errors="coerce").fillna(0.0),
                "symbol": out["stock_id"].fillna(symbol).astype(str),
            }
        )
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized = normalized.dropna(subset=["date"]).copy()
        if normalized.empty:
            return _empty_dividends_dataframe()

        normalized = localize_to_taipei(normalized, col="date")
        normalized["cash_dividend"] = normalized["cash_dividend"].astype("float64")
        normalized["stock_dividend"] = normalized["stock_dividend"].astype("float64")
        normalized = normalized[DIVIDENDS_COLUMNS]
        normalized = normalized.sort_values("date").drop_duplicates(subset=["date", "symbol"], keep="last").reset_index(drop=True)
        return normalized

    def _normalize_eps(self, raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if raw.empty:
            return _empty_eps_dataframe()

        out = raw.copy()
        for col in (
            "stock_id",
            "date",
            "type",
            "origin_name",
            "name",
            "item",
            "title",
            "value",
            "eps",
            "EPS",
            "year",
            "fiscal_year",
            "season",
            "quarter",
            "fiscal_quarter",
        ):
            if col not in out.columns:
                out[col] = pd.NA

        metric_label = out[["type", "origin_name", "name", "item", "title"]].bfill(axis=1).iloc[:, 0].astype(str)
        metric_mask = metric_label.str.contains("EPS", case=False, na=False) | metric_label.str.contains("每股", na=False)
        filtered = out[metric_mask].copy()
        if filtered.empty:
            return _empty_eps_dataframe()

        metric_label = metric_label.loc[filtered.index]
        report_date = pd.to_datetime(filtered["date"], errors="coerce")
        valid_report_dates = report_date.dropna()
        if valid_report_dates.empty:
            report_date = pd.Series(pd.NaT, index=filtered.index, dtype=f"datetime64[ns, {TAIPEI_TZ}]")
        elif valid_report_dates.dt.tz is None:
            report_date = report_date.dt.tz_localize(TAIPEI_TZ)
        else:
            report_date = report_date.dt.tz_convert(TAIPEI_TZ)

        year = pd.to_numeric(filtered["year"], errors="coerce")
        year = year.where(~year.isna(), pd.to_numeric(filtered["fiscal_year"], errors="coerce"))
        year = year.where(~year.isna(), report_date.dt.year if hasattr(report_date, "dt") else pd.Series(dtype="float64"))

        quarter_raw = filtered[["quarter", "season", "fiscal_quarter"]].bfill(axis=1).iloc[:, 0]
        quarter = quarter_raw.map(_parse_quarter_value)
        if hasattr(report_date, "dt"):
            quarter_from_date = ((report_date.dt.month - 1) // 3 + 1).astype("float64")
            quarter = quarter.where(~quarter.isna(), quarter_from_date)

        eps = pd.to_numeric(filtered["value"], errors="coerce")
        eps = eps.where(~eps.isna(), pd.to_numeric(filtered["eps"], errors="coerce"))
        eps = eps.where(~eps.isna(), pd.to_numeric(filtered["EPS"], errors="coerce"))

        normalized = pd.DataFrame(
            {
                "date": report_date,
                "year": year,
                "quarter": quarter,
                "eps": eps,
                "symbol": filtered["stock_id"].fillna(symbol).astype(str),
                "report_date": report_date,
                "priority": metric_label.map(_eps_metric_priority),
            }
        )
        normalized = normalized.dropna(subset=["year", "quarter", "eps"]).copy()
        if normalized.empty:
            return _empty_eps_dataframe()

        normalized["year"] = normalized["year"].astype("int64")
        normalized["quarter"] = normalized["quarter"].astype("int64")
        normalized = normalized[normalized["quarter"].between(1, 4)].copy()
        if normalized.empty:
            return _empty_eps_dataframe()

        normalized["eps"] = normalized["eps"].astype("float64")
        normalized = normalized.sort_values(
            ["year", "quarter", "priority", "report_date"],
            ascending=[True, True, True, False],
        )
        normalized = normalized.drop_duplicates(subset=["year", "quarter", "symbol"], keep="first")
        normalized = normalized.sort_values(["year", "quarter"]).reset_index(drop=True)
        return normalized[[*EPS_COLUMNS, "report_date"]]

    def _normalize_per(self, raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if raw.empty:
            return _empty_per_dataframe()

        out = raw.copy()
        for col in ("date", "stock_id", "PER", "PBR", "dividend_yield"):
            if col not in out.columns:
                out[col] = pd.NA

        normalized = pd.DataFrame(
            {
                "date": out["date"],
                "per": pd.to_numeric(out["PER"], errors="coerce"),
                "pbr": pd.to_numeric(out["PBR"], errors="coerce"),
                "dividend_yield": pd.to_numeric(out["dividend_yield"], errors="coerce"),
                "symbol": out["stock_id"].fillna(symbol).astype(str),
            }
        )
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized = normalized.dropna(subset=["date"]).copy()
        if normalized.empty:
            return _empty_per_dataframe()

        normalized = localize_to_taipei(normalized, col="date")
        normalized["per"] = normalized["per"].astype("float64")
        normalized["pbr"] = normalized["pbr"].astype("float64")
        normalized["dividend_yield"] = normalized["dividend_yield"].astype("float64")
        normalized = normalized[PER_COLUMNS]
        normalized = normalized.sort_values("date").drop_duplicates(subset=["date", "symbol"], keep="last").reset_index(drop=True)
        return normalized

    def _normalize_monthly_revenue(self, raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if raw.empty:
            return _empty_monthly_revenue_dataframe()

        out = raw.copy()
        for col in ("date", "stock_id", "revenue", "revenue_month", "revenue_year"):
            if col not in out.columns:
                out[col] = pd.NA

        normalized = pd.DataFrame(
            {
                "date": out["date"],
                "revenue": pd.to_numeric(out["revenue"], errors="coerce"),
                "revenue_month": pd.to_numeric(out["revenue_month"], errors="coerce"),
                "revenue_year": pd.to_numeric(out["revenue_year"], errors="coerce"),
                "symbol": out["stock_id"].fillna(symbol).astype(str),
            }
        )
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized = normalized.dropna(subset=["date"]).copy()
        if normalized.empty:
            return _empty_monthly_revenue_dataframe()

        normalized = localize_to_taipei(normalized, col="date")
        normalized["revenue"] = normalized["revenue"].astype("float64")
        normalized = normalized.dropna(subset=["revenue_month", "revenue_year"]).copy()
        if normalized.empty:
            return _empty_monthly_revenue_dataframe()
        normalized["revenue_month"] = normalized["revenue_month"].astype("int64")
        normalized["revenue_year"] = normalized["revenue_year"].astype("int64")
        normalized = normalized[MONTHLY_REVENUE_COLUMNS]
        normalized = normalized.sort_values("date").drop_duplicates(subset=["date", "symbol"], keep="last").reset_index(drop=True)
        return normalized

    def _normalize_splits(self, raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if raw.empty:
            return _empty_splits_dataframe()

        out = raw.copy()
        for col in ("date", "before_price", "after_price", "stock_id"):
            if col not in out.columns:
                out[col] = pd.NA

        normalized = pd.DataFrame(
            {
                "date": out["date"],
                "before_price": pd.to_numeric(out["before_price"], errors="coerce"),
                "after_price": pd.to_numeric(out["after_price"], errors="coerce"),
                "symbol": out["stock_id"].fillna(symbol).astype(str),
            }
        )
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized = normalized.dropna(subset=["date", "before_price", "after_price"]).copy()
        if normalized.empty:
            return _empty_splits_dataframe()

        normalized = normalized[
            (normalized["before_price"] > 0) & (normalized["after_price"] > 0)
        ].copy()
        if normalized.empty:
            return _empty_splits_dataframe()

        normalized = localize_to_taipei(normalized, col="date")
        normalized["before_price"] = normalized["before_price"].astype("float64")
        normalized["after_price"] = normalized["after_price"].astype("float64")
        normalized = normalized[SPLITS_COLUMNS]
        normalized = normalized.sort_values("date").drop_duplicates(subset=["date", "symbol"], keep="last").reset_index(drop=True)
        return normalized

    def _normalize_institutional(self, raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if raw.empty:
            return _empty_institutional_dataframe()

        out = raw.copy()
        for col in ("date", "name", "buy", "sell", "stock_id"):
            if col not in out.columns:
                out[col] = pd.NA

        out["buy"] = pd.to_numeric(out["buy"], errors="coerce").fillna(0).astype("int64")
        out["sell"] = pd.to_numeric(out["sell"], errors="coerce").fillna(0).astype("int64")
        out["net"] = out["buy"] - out["sell"]
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.dropna(subset=["date"]).copy()
        if out.empty:
            return _empty_institutional_dataframe()

        out["symbol"] = out["stock_id"].fillna(symbol).astype(str)
        out["category"] = out["name"].map(_institutional_name_to_category)
        out = out[out["category"].notna()].copy()
        if out.empty:
            return _empty_institutional_dataframe()

        grouped = (
            out.groupby(["date", "symbol", "category"], as_index=False)[["buy", "sell", "net"]]
            .sum()
            .reset_index(drop=True)
        )

        wide = grouped.pivot_table(
            index=["date", "symbol"],
            columns="category",
            values=["buy", "sell", "net"],
            aggfunc="sum",
            fill_value=0,
        )
        wide.columns = [f"{cat}_{metric}" for metric, cat in wide.columns]
        wide = wide.reset_index()

        normalized = pd.DataFrame(
            {
                "date": wide["date"],
                "foreign_buy": wide.get("foreign_buy", 0),
                "foreign_sell": wide.get("foreign_sell", 0),
                "foreign_net": wide.get("foreign_net", 0),
                "trust_buy": wide.get("trust_buy", 0),
                "trust_sell": wide.get("trust_sell", 0),
                "trust_net": wide.get("trust_net", 0),
                "dealer_buy": wide.get("dealer_buy", 0),
                "dealer_sell": wide.get("dealer_sell", 0),
                "dealer_net": wide.get("dealer_net", 0),
                "symbol": wide["symbol"],
            }
        )
        normalized = localize_to_taipei(normalized, col="date")
        for col in INSTITUTIONAL_COLUMNS:
            if col in {"date", "symbol"}:
                continue
            normalized[col] = pd.to_numeric(normalized[col], errors="coerce").fillna(0).astype("int64")
        normalized = normalized[INSTITUTIONAL_COLUMNS]
        normalized = normalized.sort_values("date").drop_duplicates(subset=["date", "symbol"], keep="last").reset_index(drop=True)
        return normalized

    def _normalize_margin(self, raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if raw.empty:
            return _empty_margin_dataframe()

        out = raw.copy()
        field_map = {
            "date": "date",
            "stock_id": "symbol",
            "MarginPurchaseBuy": "margin_buy",
            "MarginPurchaseSell": "margin_sell",
            "MarginPurchaseTodayBalance": "margin_balance",
            "ShortSaleBuy": "short_buy",
            "ShortSaleSell": "short_sell",
            "ShortSaleTodayBalance": "short_balance",
        }
        out = out.rename(columns=field_map)
        for col in MARGIN_COLUMNS:
            if col not in out.columns:
                out[col] = pd.NA

        out["symbol"] = out["symbol"].fillna(symbol).astype(str)
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.dropna(subset=["date"]).copy()
        if out.empty:
            return _empty_margin_dataframe()

        normalized = out[MARGIN_COLUMNS].copy()
        normalized = localize_to_taipei(normalized, col="date")
        for col in MARGIN_COLUMNS:
            if col in {"date", "symbol"}:
                continue
            normalized[col] = pd.to_numeric(normalized[col], errors="coerce").fillna(0).astype("int64")
        normalized = normalized.sort_values("date").drop_duplicates(subset=["date", "symbol"], keep="last").reset_index(drop=True)
        return normalized


def _parse_quarter_value(value: Any) -> float:
    if pd.isna(value):
        return float("nan")
    text = str(value).strip().upper()
    if not text:
        return float("nan")
    if text.startswith("Q") and text[1:].isdigit():
        return float(int(text[1:]))
    if text.endswith("Q") and text[:-1].isdigit():
        return float(int(text[:-1]))
    if text.isdigit():
        return float(int(text))
    if "第一季" in text:
        return 1.0
    if "第二季" in text:
        return 2.0
    if "第三季" in text:
        return 3.0
    if "第四季" in text:
        return 4.0
    return float("nan")


def _eps_metric_priority(label: str) -> int:
    label_text = str(label or "")
    name = label_text.upper()
    if "基本每股盈餘" in label_text or "BASIC EPS" in name or "BASICEPS" in name:
        return 0
    if "稀釋" in label_text or "DILUTED" in name:
        return 2
    return 1


def _institutional_name_to_category(name: Any) -> str | None:
    label = str(name or "").strip()
    if label in {"Foreign_Investor", "Foreign_Dealer_Self"}:
        return "foreign"
    if label == "Investment_Trust":
        return "trust"
    if label in {"Dealer_self", "Dealer_Hedging"}:
        return "dealer"
    return None


class YFinanceFetcher(IDataFetcher):
    """yfinance backup source fetcher."""

    VALID_MINUTE_FREQ = {"1", "5", "15", "30", "60"}

    def __init__(self, downloader: Callable[..., pd.DataFrame] | None = None, market: str = "tw"):
        self._downloader = downloader or yf.download
        self._market = normalize_market(market)
        self._timezone = get_market_spec(self._market).timezone

    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        normalized_symbol = normalize_symbol(symbol, market=self._market)
        ticker = self._ticker_from_symbol(normalized_symbol)
        raw = self._download_ohlcv(
            ticker=ticker,
            start=start,
            end=end,
            interval="1d",
            include_actions=False,
        )
        return self._normalize_yfinance(raw, symbol=normalized_symbol)

    def fetch_daily_with_adjusted(self, symbol: str, start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bool]:
        normalized_symbol = normalize_symbol(symbol, market=self._market)
        ticker = self._ticker_from_symbol(normalized_symbol)
        raw = self._download_ohlcv(
            ticker=ticker,
            start=start,
            end=end,
            interval="1d",
            include_actions=True,
        )
        if self._market != "us":
            daily = self._normalize_yfinance(raw, symbol=normalized_symbol)
            return daily, daily.copy(deep=True), _empty_splits_dataframe(), False

        extended = self._normalize_yfinance_extended(raw, symbol=normalized_symbol)
        return self._build_us_adjusted_bundle(extended, symbol=normalized_symbol)

    def fetch_minute(self, symbol: str, start: str, end: str, freq: str = "1") -> pd.DataFrame:
        if self._market == "us":
            raise FetcherError("US-1 does not support US minute data.")
        try:
            interval_map = {"1": "1m", "5": "5m", "15": "15m", "30": "30m", "60": "60m"}
            if freq not in self.VALID_MINUTE_FREQ:
                raise ValueError(f"Unsupported minute frequency: {freq}")

            normalized_symbol = normalize_symbol(symbol, market=self._market)
            ticker = self._ticker_from_symbol(normalized_symbol)
            raw = self._download_ohlcv(
                ticker=ticker,
                start=start,
                end=end,
                interval=interval_map[freq],
                include_actions=False,
            )
            return self._normalize_yfinance(raw, symbol=normalized_symbol)
        except ValueError:
            raise

    def fetch_per(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        raise NotImplementedError("US not supported in P11.")

    def fetch_monthly_revenue(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        raise NotImplementedError("US not supported in P11.")

    def _download_ohlcv(
        self,
        ticker: str,
        start: str,
        end: str,
        interval: str,
        include_actions: bool,
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {
            "start": start,
            "end": end,
            "interval": interval,
            "auto_adjust": False,
            "progress": False,
            "group_by": "column",
            "threads": False,
        }
        if include_actions:
            kwargs["actions"] = True
        try:
            return self._downloader(ticker, **kwargs)
        except Exception as exc:  # noqa: BLE001 - normalize provider errors
            raise FetcherError(f"yfinance download failed for {ticker}") from exc

    def _ticker_from_symbol(self, symbol: str) -> str:
        if self._market == "tw":
            return f"{symbol}.TW"
        return symbol

    def _normalize_yfinance(self, raw: pd.DataFrame | None, symbol: str) -> pd.DataFrame:
        extended = self._normalize_yfinance_extended(raw, symbol=symbol)
        if extended.empty:
            return _empty_standard_dataframe(self._timezone)
        return extended[STANDARD_COLUMNS].copy()

    def _normalize_yfinance_extended(self, raw: pd.DataFrame | None, symbol: str) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame(columns=[*STANDARD_COLUMNS, "adj_close", "stock_splits"])

        normalized = raw.copy()
        if isinstance(normalized.columns, pd.MultiIndex):
            normalized.columns = normalized.columns.get_level_values(0)

        normalized = normalized.reset_index()
        date_col = normalized.columns[0]
        mapped = normalized.rename(
            columns={
                date_col: "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
                "Stock Splits": "stock_splits",
            }
        )
        if "adj_close" not in mapped.columns:
            mapped["adj_close"] = pd.NA
        if "stock_splits" not in mapped.columns:
            mapped["stock_splits"] = pd.NA
        mapped["symbol"] = symbol

        standard = _finalize_schema(mapped, symbol=symbol, timezone=self._timezone)
        if standard.empty:
            return pd.DataFrame(columns=[*STANDARD_COLUMNS, "adj_close", "stock_splits"])

        extras = mapped[["date", "adj_close", "stock_splits"]].copy()
        extras["date"] = pd.to_datetime(extras["date"], errors="coerce")
        extras = extras.dropna(subset=["date"]).copy()
        if not extras.empty:
            extras = _localize_to_timezone(extras, timezone=self._timezone, col="date")
            extras["adj_close"] = pd.to_numeric(extras["adj_close"], errors="coerce")
            extras["stock_splits"] = pd.to_numeric(extras["stock_splits"], errors="coerce")
            extras = extras.sort_values("date").drop_duplicates(subset=["date"], keep="last")

        out = standard.merge(extras, on="date", how="left")
        out["adj_close"] = pd.to_numeric(out["adj_close"], errors="coerce")
        out["stock_splits"] = pd.to_numeric(out["stock_splits"], errors="coerce")
        return out[[*STANDARD_COLUMNS, "adj_close", "stock_splits"]]

    def _build_us_adjusted_bundle(
        self,
        extended: pd.DataFrame,
        symbol: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bool]:
        if extended.empty:
            empty = _empty_standard_dataframe(self._timezone)
            return empty, empty, _empty_splits_dataframe(), False

        work = extended.copy()
        work["close"] = pd.to_numeric(work["close"], errors="coerce")
        work["adj_close"] = pd.to_numeric(work["adj_close"], errors="coerce")
        work = work[work["close"] > 0].copy()
        if work.empty:
            empty = _empty_standard_dataframe(self._timezone)
            return empty, empty, _empty_splits_dataframe(), False

        ratio = pd.to_numeric(work["adj_close"] / work["close"], errors="coerce")
        ratio = ratio.replace([float("inf"), float("-inf")], pd.NA)
        valid_ratio_mask = ratio.notna() & (ratio > 0)
        has_any_valid_ratio = bool(valid_ratio_mask.any())
        if has_any_valid_ratio:
            work = work.loc[valid_ratio_mask].copy()
            work["price_ratio"] = ratio.loc[valid_ratio_mask].astype("float64")
        else:
            work["price_ratio"] = 1.0

        split_events = pd.to_numeric(work["stock_splits"], errors="coerce").fillna(0.0).astype("float64")
        has_split_column = "stock_splits" in extended.columns and extended["stock_splits"].notna().any()
        volume_split_adjusted = has_split_column

        cumulative = 1.0
        factors: list[float] = [1.0] * len(work)
        split_values = split_events.tolist()
        for idx in range(len(split_values) - 1, -1, -1):
            factors[idx] = cumulative
            split_val = split_values[idx]
            if split_val > 0:
                cumulative *= split_val

        adjusted = work.copy()
        for col in ("open", "high", "low"):
            adjusted[col] = pd.to_numeric(adjusted[col], errors="coerce") * adjusted["price_ratio"]
        if has_any_valid_ratio:
            adjusted["close"] = adjusted["adj_close"]
        else:
            adjusted["close"] = pd.to_numeric(adjusted["close"], errors="coerce")
        adjusted["volume"] = pd.to_numeric(adjusted["volume"], errors="coerce").fillna(0.0)
        if volume_split_adjusted:
            adjusted["volume"] = (adjusted["volume"] * pd.Series(factors, index=adjusted.index)).round()
        adjusted["volume"] = adjusted["volume"].astype("int64")
        adjusted = adjusted.dropna(subset=["open", "high", "low", "close"]).copy()
        adjusted = adjusted[STANDARD_COLUMNS].sort_values("date").reset_index(drop=True)

        raw_daily = work[STANDARD_COLUMNS].copy().sort_values("date").reset_index(drop=True)
        splits = self._build_us_splits_dataframe(work[["date", "stock_splits"]].copy(), symbol=symbol)
        return raw_daily, adjusted, splits, bool(volume_split_adjusted)

    def _build_us_splits_dataframe(self, splits_raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if splits_raw.empty:
            return _empty_splits_dataframe()

        out = splits_raw.copy()
        out["stock_splits"] = pd.to_numeric(out["stock_splits"], errors="coerce")
        out = out[out["stock_splits"] > 0].copy()
        if out.empty:
            return _empty_splits_dataframe()

        out["before_price"] = out["stock_splits"].astype("float64")
        out["after_price"] = 1.0
        out["symbol"] = symbol
        out = out[["date", "before_price", "after_price", "symbol"]]
        out = out.sort_values("date").drop_duplicates(subset=["date", "symbol"], keep="last").reset_index(drop=True)
        return out

    def fetch_us_intraday(
        self,
        symbol: str,
        period: str = "1d",
        interval: str = "1m",
        prepost: bool = False,
    ) -> tuple[pd.DataFrame, USIntradaySnapshot | None, str | None]:
        """Fetch US intraday bars from yfinance (9-G).

        Returns:
            (intraday_df, snapshot, error_msg)
            - intraday_df: OHLCV bars with America/New_York timestamps
            - snapshot: USIntradaySnapshot if today's data is available, else None
            - error_msg: human-readable provider limitation message, or None

        This method is US-market-only and must not be used for TW symbols.
        fetch_minute(market="us") continues to raise FetcherError (US-1 restriction).
        """
        if self._market != "us":
            return _empty_standard_dataframe(self._timezone), None, "fetch_us_intraday is only for US market."

        us_tz = "America/New_York"
        normalized_symbol = normalize_symbol(symbol, market="us")
        ticker = self._ticker_from_symbol(normalized_symbol)

        try:
            raw = self._downloader(
                ticker,
                period=period,
                interval=interval,
                prepost=prepost,
                auto_adjust=False,
                progress=False,
                group_by="column",
                threads=False,
            )
        except Exception as exc:  # noqa: BLE001
            return _empty_standard_dataframe(us_tz), None, f"yfinance intraday 外部資料源限制：{exc}"

        if raw is None or (hasattr(raw, "empty") and raw.empty):
            return _empty_standard_dataframe(us_tz), None, "yfinance 無可用的盤中資料，已改用最新日線資料。"

        # Normalize to STANDARD_COLUMNS schema with US timezone
        intraday_df = _finalize_intraday_schema(raw, symbol=normalized_symbol, timezone=us_tz)
        if intraday_df.empty:
            return _empty_standard_dataframe(us_tz), None, "yfinance 無可用的盤中資料，已改用最新日線資料。"

        # Determine "today" in New York
        today_ny = pd.Timestamp.now(tz=us_tz).date()
        latest_bar = intraday_df.tail(1).iloc[0]
        latest_ts = pd.to_datetime(latest_bar["date"])
        if latest_ts.tz is None:
            latest_ts = latest_ts.tz_localize(us_tz)
        else:
            latest_ts = latest_ts.tz_convert(us_tz)

        if latest_ts.date() != today_ny:
            return intraday_df, None, "目前無法取得美股盤中分 K（非今日紐約交易日），已改用最新日線資料。"

        latest_price = float(latest_bar["close"])
        volume_total = int(intraday_df["volume"].fillna(0).sum())

        # Snapshot has no prev_close yet; caller must inject previous_raw_close from raw daily
        snapshot = USIntradaySnapshot(
            symbol=normalized_symbol,
            price=latest_price,
            previous_raw_close=float("nan"),  # caller fills this from raw daily
            change=float("nan"),
            change_pct=float("nan"),
            volume=volume_total,
            timestamp=latest_ts,
        )
        return intraday_df, snapshot, None


def _parse_tw_roc_date(value: Any) -> pd.Timestamp | pd.NaT:
    text = str(value or "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) < 7:
        return pd.NaT
    digits = digits[-7:]
    try:
        roc_year = int(digits[:3])
        month = int(digits[3:5])
        day = int(digits[5:7])
        if roc_year <= 0:
            return pd.NaT
        return pd.Timestamp(datetime(roc_year + 1911, month, day), tz=TAIPEI_TZ)
    except Exception:  # noqa: BLE001
        return pd.NaT


def _normalize_meeting_type(value: Any) -> str | None:
    text = str(value or "").strip()
    if "臨時" in text:
        return "臨時會"
    if "常" in text:
        return "常會"
    return None


class TWSEFetcher:
    """TWSE/TPEx open data fetcher for shareholder meeting calendar (11-C)."""

    TWSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap41_L"
    TPEX_URL = "https://www.tpex.org.tw/openapi/v1/t187ap41_O"

    def __init__(self, session: requests.Session | None = None, timeout_seconds: int = 20):
        self._session = session
        self._timeout_seconds = timeout_seconds

    def fetch_shareholder_meeting(self, session: requests.Session | None = None) -> pd.DataFrame:
        client = session or self._session or requests.Session()
        now = pd.Timestamp.now(tz=TAIPEI_TZ)

        twse_df = self._fetch_one(client, self.TWSE_URL)
        tpex_df = self._fetch_one(client, self.TPEX_URL)
        merged = pd.concat([twse_df, tpex_df], ignore_index=True)

        if merged.empty:
            return pd.DataFrame(
                {
                    "date": pd.Series(dtype=f"datetime64[ns, {TAIPEI_TZ}]"),
                    "symbol": pd.Series(dtype="object"),
                    "meeting_type": pd.Series(dtype="object"),
                    "source": pd.Series(dtype="object"),
                    "updated_at": pd.Series(dtype=f"datetime64[ns, {TAIPEI_TZ}]"),
                }
            )[SHAREHOLDER_MEETING_COLUMNS]

        out = merged.copy()
        out["symbol"] = out["symbol"].astype(str).str.strip()
        out["date"] = out["date"].map(_parse_tw_roc_date)
        out["meeting_type"] = out["meeting_type"].map(_normalize_meeting_type)
        out = out.dropna(subset=["date", "meeting_type"]).copy()
        out = out[out["symbol"] != ""].copy()
        out["source"] = "auto"
        out["updated_at"] = now
        out = out[SHAREHOLDER_MEETING_COLUMNS]
        out = out.drop_duplicates(subset=["symbol", "date"], keep="last")
        out = out.sort_values(["date", "symbol"]).reset_index(drop=True)
        return out

    def _fetch_one(self, client: requests.Session, url: str) -> pd.DataFrame:
        try:
            response = client.get(url, timeout=self._timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise FetcherError(f"Shareholder meeting fetch failed: {url}") from exc

        if not isinstance(payload, list):
            raise FetcherError(f"Unexpected shareholder meeting payload: {url}")

        raw = pd.DataFrame(payload)
        if raw.empty:
            return pd.DataFrame(columns=["symbol", "date", "meeting_type"])

        out = raw.rename(
            columns={
                "公司代號": "symbol",
                "開會日期": "date",
                "股東常(臨時)會": "meeting_type",
            }
        )
        for col in ("symbol", "date", "meeting_type"):
            if col not in out.columns:
                out[col] = pd.NA
        return out[["symbol", "date", "meeting_type"]].copy()


class ActiveEtfSource(ABC):
    """Abstract base class for Active ETF holding data sources."""

    @abstractmethod
    def fetch_list(self) -> pd.DataFrame:
        """Fetch active ETF list.

        Returns:
            pd.DataFrame: Columns ['etf_code', 'etf_name']
        """

    @abstractmethod
    def fetch_holdings(self, etf_code: str) -> tuple[date, pd.DataFrame]:
        """Fetch holdings for a given ETF.

        Returns:
            tuple[date, pd.DataFrame]: (snapshot_date, holdings_df)
                holdings_df has columns: ['holding_code', 'holding_name', 'shares', 'weight_pct']
        """

    @abstractmethod
    def fetch_latest_close_date(self, etf_code: str) -> date | None:
        """Fetch the latest close date for a given ETF from the market.

        Returns:
            date | None: Latest trading close date, or None if failed.
        """



class _RelaxedStrictHTTPAdapter(HTTPAdapter):
    """Keeps full TLS chain verification but disables OpenSSL 3.x strict mode.

    MoneyDJ's certificate chain contains a CA cert missing the Subject Key
    Identifier extension; OpenSSL 3.x's VERIFY_X509_STRICT (on by default in
    newer urllib3) rejects this with "Missing Subject Key Identifier". Clearing
    only that flag lets the otherwise-trusted chain validate normally, without
    falling back to verify=False (which would disable trust entirely).
    """

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> Any:
        ctx = create_urllib3_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class MoneyDjActiveEtfSource(ActiveEtfSource):
    """MoneyDJ active ETF holding source."""

    HOLDINGS_URL = "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid={CODE}.TW"

    def __init__(self, session: requests.Session | None = None, timeout_seconds: int = 20):
        if session is None:
            self._session = requests.Session()
            self._session.mount("https://www.moneydj.com", _RelaxedStrictHTTPAdapter())
        else:
            self._session = session
        self._timeout_seconds = timeout_seconds

    def fetch_list(self) -> pd.DataFrame:
        """Fetch active ETF list from stock info cache with fallback."""
        from src.core.config import get_data_dir
        import datetime

        cache_path = get_data_dir() / "stock_info_tw.parquet"
        df = pd.DataFrame(columns=["etf_code", "etf_name"])

        # Try warm cache first
        loaded_from_cache = False
        if cache_path.exists():
            try:
                mtime = datetime.datetime.fromtimestamp(cache_path.stat().st_mtime)
                age_days = (datetime.datetime.now() - mtime).days
                if age_days < 7:
                    cache_df = pd.read_parquet(cache_path)
                    if {"symbol", "name"}.issubset(cache_df.columns):
                        filtered = cache_df[cache_df["symbol"].astype(str).str.match(r"^\d{5}A$", na=False)].copy()
                        df = filtered.rename(columns={"symbol": "etf_code", "name": "etf_name"})[["etf_code", "etf_name"]].reset_index(drop=True)
                        loaded_from_cache = True
            except Exception:  # noqa: BLE001
                pass

        if not loaded_from_cache:
            try:
                fetcher = FinMindFetcher()
                raw_df = fetcher.fetch_stock_info()
                if not raw_df.empty:
                    raw_df[["symbol", "name"]].to_parquet(cache_path, index=False)
                    filtered = raw_df[raw_df["symbol"].astype(str).str.match(r"^\d{5}A$", na=False)].copy()
                    df = filtered.rename(columns={"symbol": "etf_code", "name": "etf_name"})[["etf_code", "etf_name"]].reset_index(drop=True)
            except Exception:  # noqa: BLE001
                # Swallowing token missing / network exceptions
                # Fallback to loading stale cache if it exists as last resort
                if cache_path.exists():
                    try:
                        cache_df = pd.read_parquet(cache_path)
                        if {"symbol", "name"}.issubset(cache_df.columns):
                            filtered = cache_df[cache_df["symbol"].astype(str).str.match(r"^\d{5}A$", na=False)].copy()
                            df = filtered.rename(columns={"symbol": "etf_code", "name": "etf_name"})[["etf_code", "etf_name"]].reset_index(drop=True)
                    except Exception:  # noqa: BLE001
                        pass

        # Ensure code is uppercase and cleaned
        if not df.empty:
            df["etf_code"] = df["etf_code"].astype(str).str.strip().str.upper()
            df["etf_name"] = df["etf_name"].astype(str).str.strip()
            df = df.drop_duplicates(subset=["etf_code"]).reset_index(drop=True)
        return df

    def fetch_latest_close_date(self, etf_code: str) -> date | None:
        """Fetch the latest close date for a TW active ETF from primary source (FinMind) or fallback (yfinance)."""
        import datetime
        import re

        normalized_code = str(etf_code).strip().upper()
        if not re.match(r"^\d{5}A$", normalized_code):
            return None

        # 1. 取得近幾天的區間（例如過去 10 天，足夠拿到最後一筆交易日）
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=10)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # 2. 嘗試用 FinMindFetcher 抓取日線
        try:
            fetcher = FinMindFetcher()
            # FinMind 用純碼 '00981A'
            df = fetcher.fetch_daily(normalized_code, start_str, end_str)
            if not df.empty and "date" in df.columns:
                dates = pd.to_datetime(df["date"])
                if not dates.empty:
                    return dates.max().date()
        except Exception:  # noqa: BLE001
            pass

        # 3. 嘗試用 YFinanceFetcher 抓取日線
        try:
            # yfinance 用 '00981A.TW'
            yf_symbol = f"{normalized_code}.TW"
            fetcher = YFinanceFetcher(market="tw")
            df = fetcher.fetch_daily(yf_symbol, start_str, end_str)
            if not df.empty and "date" in df.columns:
                dates = pd.to_datetime(df["date"])
                if not dates.empty:
                    return dates.max().date()
        except Exception:  # noqa: BLE001
            pass

        return None

    def fetch_holdings(self, etf_code: str) -> tuple[date, pd.DataFrame]:
        """Fetch active ETF holdings from MoneyDJ URL."""
        import re

        # Ensure code is normalized to 5 digits + A (uppercase)
        normalized_code = str(etf_code).strip().upper()
        if not re.match(r"^\d{5}A$", normalized_code):
            raise FetcherError(f"Invalid ETF code format: {etf_code}")

        url = self.HOLDINGS_URL.format(CODE=normalized_code)
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        try:
            response = self._session.get(url, headers=headers, timeout=self._timeout_seconds)
            response.raise_for_status()
            # MoneyDJ serves UTF-8 but omits charset in Content-Type, so requests
            # defaults to ISO-8859-1 and mangles the Chinese holdings table. Fall
            # back to the body-detected encoding when that default kicks in.
            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding or "utf-8"
            html_content = response.text
        except Exception as exc:  # noqa: BLE001
            raise FetcherError(f"Failed to fetch holdings for {normalized_code} from MoneyDJ: {exc}") from exc

        return self.parse_holdings_html(html_content, normalized_code)

    def parse_holdings_html(self, html_content: str, etf_code: str) -> tuple[date, pd.DataFrame]:
        """Parse MoneyDJ Holdings Basic0007B.xdjhtm raw HTML."""
        import re
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Parse date from ctl00_ctl00_MainContent_MainContent_sdate3 div
        date_div = soup.find("div", id="ctl00_ctl00_MainContent_MainContent_sdate3")
        date_str = ""
        if date_div:
            date_str = date_div.get_text(strip=True)

        # Fallback to finding the first date in form of YYYY/MM/DD
        if not date_str or not re.match(r"^\d{4}/\d{2}/\d{2}$", date_str):
            date_match = re.search(r"(\d{4}/\d{2}/\d{2})", html_content)
            if date_match:
                date_str = date_match.group(1)

        if not date_str:
            raise FetcherError(f"Cannot parse snapshot date for ETF {etf_code} from HTML content.")

        try:
            snapshot_date = datetime.strptime(date_str, "%Y/%m/%d").date()
        except Exception as exc:  # noqa: BLE001
            raise FetcherError(f"Invalid date format parsed: {date_str} for ETF {etf_code}") from exc

        # 2. Parse holdings table
        holdings_table = None
        for table in soup.find_all("table"):
            first_row = table.find("tr")
            if not first_row:
                continue
            cells = [c.get_text(strip=True) for c in first_row.find_all(["th", "td"])]
            # Match table headers containing "個股名稱" or "成分股" and "比例", "權重", "%"
            is_match = any("個股名稱" in cell or "成分股" in cell for cell in cells) and any("比例" in cell or "權重" in cell or "%" in cell for cell in cells)
            if is_match:
                holdings_table = table
                break

        if holdings_table is None:
            raise FetcherError(f"Cannot find holdings table for ETF {etf_code} in HTML.")

        rows = holdings_table.find_all("tr")
        holding_rows = []
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            name_text = cells[0].get_text(strip=True)
            weight_text = cells[1].get_text(strip=True)
            shares_text = cells[2].get_text(strip=True)

            if "個股名稱" in name_text or "成分股" in name_text or not name_text:
                continue

            try:
                weight_pct = float(weight_text.replace("%", "").replace(",", "").strip())
            except ValueError:
                weight_pct = 0.0

            try:
                shares = int(re.sub(r"[^\d]", "", shares_text))
            except ValueError:
                shares = 0

            # Extract ticker inside parentheses at the end of name_text
            match = re.search(r"\(([^)]+)\)$", name_text)
            if match:
                holding_code = match.group(1).strip()
                holding_name = name_text[:match.start()].strip()
            else:
                holding_code = ""
                holding_name = name_text

            holding_rows.append({
                "holding_code": holding_code,
                "holding_name": holding_name,
                "shares": shares,
                "weight_pct": weight_pct
            })

        df = pd.DataFrame(holding_rows)
        if df.empty:
            df = pd.DataFrame(columns=["holding_code", "holding_name", "shares", "weight_pct"])
        else:
            df = df[["holding_code", "holding_name", "shares", "weight_pct"]]

        return snapshot_date, df
