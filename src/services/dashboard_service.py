"""Dashboard service — non-UI payload builder (Phase 10-A).

All functions return dataclasses or raise exceptions.
No Streamlit calls are made here.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
import threading
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from src.ai.advisor import AIAdvisor, DashboardAnalysis
from src.services.dividend_policy_service import get_goodinfo_dividend_policy
from src.analysis.chip_analysis import ChipSummary, generate_chip_summary
from src.analysis.pattern import (
    CandlePattern,
    ChartPatternResult,
    MultiTimeframeAnalysis,
    analyze_multi_timeframe,
    detect_candle_patterns,
    detect_chart_pattern,
)
from src.analysis.technical_summary import TechnicalSummary, generate_technical_summary
from src.core.config import get_config, get_data_dir
from src.core.exceptions import AICallError, AIDisabledError
from src.core.market import get_market_spec, normalize_market
from src.data.cleaner import DataCleaner
from src.data.fetcher import (
    FinMindFetcher,
    IDataFetcher,
    USIntradaySnapshot,
    YFinanceFetcher,
)
from src.data.maintenance import DataMaintenance
from src.data.realtime import BidAskStructure, RealtimeFetcher, RealtimeQuote
from src.data.storage import DuckDBMeta, ParquetStorage

_INDUSTRY_LOCK_REGISTRY: dict[str, threading.Lock] = {}
_INDUSTRY_LOCK_REGISTRY_GUARD = threading.Lock()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class DashboardPayload:
    """Complete payload for rendering the stock dashboard."""

    symbol: str
    market: str
    daily_df: pd.DataFrame
    technical: TechnicalSummary
    candle_patterns: list[CandlePattern]
    chart_patterns: list[ChartPatternResult]
    multi_timeframe: MultiTimeframeAnalysis
    ai_enabled: bool
    # Optional fields — None means not applicable for the given market
    quote: RealtimeQuote | None = None
    bid_ask: BidAskStructure | None = None
    chip: ChipSummary | None = None
    chip_recent_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    chip_error: str | None = None
    intraday_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    intraday_snapshot: USIntradaySnapshot | None = None
    intraday_error: str | None = None
    analysis: DashboardAnalysis | None = None
    subject_name: str = ""
    analysis_time: str = ""


@dataclass
class DashboardError:
    """Returned when payload assembly fails before producing any useful data."""

    code: str          # e.g. "SYMBOL_NOT_FOUND", "DATA_STALE", "FETCH_FAILED"
    message: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_dashboard_payload(
    symbol: str,
    market: str = "tw",
    bars: int = 250,
) -> DashboardPayload | DashboardError:
    """Assemble the complete dashboard payload.

    No UI operations performed.  Returns ``DashboardPayload`` on success or
    ``DashboardError`` on failure.

    Args:
        symbol: Normalised symbol (e.g. ``"2330"``, ``"AAPL"``).
        market: ``"tw"`` or ``"us"``.
        bars: Not currently used to truncate the loaded df, reserved for API use.
    """
    normalized_market = normalize_market(market)
    market_spec = get_market_spec(normalized_market)
    storage = ParquetStorage()

    # ── daily data ────────────────────────────────────────────────────────
    daily, daily_error = _prepare_daily_data(symbol, storage, market=normalized_market)
    if daily_error:
        return DashboardError(code="FETCH_FAILED", message=daily_error)
    if daily.empty:
        return DashboardError(
            code="SYMBOL_NOT_FOUND",
            message=f"{symbol} 尚無可用日線資料。",
        )

    daily = _normalize_daily_df(daily, market=normalized_market)
    technical = generate_technical_summary(daily)

    # ── market-specific data ──────────────────────────────────────────────
    quote: RealtimeQuote | None = None
    bid_ask: BidAskStructure | None = None
    chip: ChipSummary | None = None
    chip_recent_df: pd.DataFrame = pd.DataFrame()
    chip_error: str | None = None
    intraday_df: pd.DataFrame = pd.DataFrame()
    intraday_snapshot: USIntradaySnapshot | None = None
    intraday_error: str | None = None
    realtime_warning: str | None = None

    if normalized_market == "tw":
        quote, bid_ask, realtime_warning = _fetch_tw_realtime(symbol)
        chip, chip_recent_df, chip_error = _prepare_chip_data(symbol, storage)
    else:
        chip_error = "US-1 尚未支援美股籌碼資料。"
        raw_daily = storage.load_daily(symbol, market=normalized_market)
        intraday_df, intraday_snapshot, intraday_error = _fetch_us_intraday_snapshot(
            symbol=symbol, raw_daily=raw_daily
        )

    # ── pattern & multi-timeframe ─────────────────────────────────────────
    candle_patterns = detect_candle_patterns(daily)
    chart_patterns = detect_chart_pattern(daily)
    multi_timeframe = analyze_multi_timeframe(daily.set_index("date"))

    # ── AI analysis ───────────────────────────────────────────────────────
    config = get_config()
    ai_section = config.get("ai", {}) if isinstance(config, dict) else {}
    ai_enabled = bool(ai_section.get("enabled", False))
    analysis: DashboardAnalysis | None = None
    if ai_enabled:
        analysis, _ = _try_ai_analysis(
            symbol=symbol,
            technical=technical,
            chip=chip,
            daily=daily,
            market=normalized_market,
            currency=market_spec.currency,
        )

    # ── subject name & time ───────────────────────────────────────────────
    subject_name = str(getattr(quote, "name", "") or "").strip() or symbol
    analysis_time = _format_analysis_time(normalized_market)

    return DashboardPayload(
        symbol=symbol,
        market=normalized_market,
        daily_df=daily,
        technical=technical,
        candle_patterns=candle_patterns,
        chart_patterns=chart_patterns,
        multi_timeframe=multi_timeframe,
        ai_enabled=ai_enabled,
        quote=quote,
        bid_ask=bid_ask,
        chip=chip,
        chip_recent_df=chip_recent_df,
        chip_error=chip_error,
        intraday_df=intraday_df,
        intraday_snapshot=intraday_snapshot,
        intraday_error=intraday_error,
        analysis=analysis,
        subject_name=subject_name,
        analysis_time=analysis_time,
    )


def get_valuation(symbol: str, market: str = "tw") -> dict[str, Any]:
    normalized_market = normalize_market(market)
    if normalized_market != "tw":
        raise NotImplementedError("US not supported in P11.")

    storage = ParquetStorage()
    per_df = storage.load_per(symbol, market=normalized_market)
    if per_df.empty:
        return {
            "symbol": symbol,
            "market": normalized_market,
            "date": None,
            "per": None,
            "pbr": None,
            "dividend_yield": None,
            "industry": None,
        }

    latest = per_df.sort_values("date").iloc[-1]
    industry = _lookup_symbol_industry(symbol=symbol)
    return {
        "symbol": symbol,
        "market": normalized_market,
        "date": _to_iso_ts(latest.get("date")),
        "per": _to_float_or_none(latest.get("per")),
        "pbr": _to_float_or_none(latest.get("pbr")),
        "dividend_yield": _to_float_or_none(latest.get("dividend_yield")),
        "industry": industry,
    }


def get_monthly_revenue(symbol: str, months: int = 12, market: str = "tw") -> dict[str, Any]:
    normalized_market = normalize_market(market)
    if normalized_market != "tw":
        raise NotImplementedError("US not supported in P11.")

    storage = ParquetStorage()
    revenue_df = storage.load_monthly_revenue(symbol, market=normalized_market)
    if revenue_df.empty:
        return {
            "symbol": symbol,
            "market": normalized_market,
            "latest_month": None,
            "latest_revenue": None,
            "items": [],
        }

    out = revenue_df.sort_values(["revenue_year", "revenue_month"]).reset_index(drop=True).copy()
    out["yoy"] = out["revenue"].pct_change(12) * 100
    out["mom"] = out["revenue"].pct_change(1) * 100

    window = out.tail(max(1, int(months)))
    latest = window.iloc[-1]
    items = [
        {
            "date": _to_iso_ts(row["date"]),
            "revenue": _to_float_or_none(row["revenue"]),
            "revenue_year": int(row["revenue_year"]),
            "revenue_month": int(row["revenue_month"]),
            "yoy": _to_float_or_none(row.get("yoy")),
            "mom": _to_float_or_none(row.get("mom")),
        }
        for _, row in window.iterrows()
    ]
    return {
        "symbol": symbol,
        "market": normalized_market,
        "latest_month": f"{int(latest['revenue_year']):04d}-{int(latest['revenue_month']):02d}",
        "latest_revenue": _to_float_or_none(latest.get("revenue")),
        "items": items,
    }


def _lookup_nearest_close(daily: pd.DataFrame, target_key: str) -> tuple[float | None, str | None]:
    """Return (close, date_str) for the nearest trading day on or before target_key (YYYY-MM-DD).

    Uses string comparison on pre-computed date_key column to stay timezone-safe.
    Falls back to None when daily is empty or no trading day exists before target.
    """
    if daily.empty or "date_key" not in daily.columns:
        return None, None
    candidates = daily[daily["date_key"] <= target_key].sort_values("date_key", ascending=False)
    if candidates.empty:
        return None, None
    best = candidates.iloc[0]
    close = _to_float_or_none(best.get("close"))
    if close is None:
        return None, None
    return close, str(best["date_key"])


def get_dividend_history_with_pe(symbol: str, count: int = 5, market: str = "tw") -> dict[str, Any]:
    normalized_market = normalize_market(market)
    if normalized_market != "tw":
        raise NotImplementedError("US not supported in P11.")

    storage = ParquetStorage()
    dividends_df = storage.load_dividends(symbol, market=normalized_market)
    daily_df = storage.load_daily(symbol, market=normalized_market)
    eps_df = storage.load_eps(symbol, market=normalized_market)

    if dividends_df.empty:
        return {"symbol": symbol, "market": normalized_market, "items": []}

    work = dividends_df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["cash_dividend"] = pd.to_numeric(work["cash_dividend"], errors="coerce").fillna(0.0)
    if "stock_dividend" in work.columns:
        work["stock_dividend"] = pd.to_numeric(work["stock_dividend"], errors="coerce").fillna(0.0)
    else:
        work["stock_dividend"] = 0.0
    work = work.dropna(subset=["date"]).sort_values("date", ascending=False)
    work = work[work["cash_dividend"] > 0].head(max(1, int(count)))

    daily = daily_df.copy()
    if not daily.empty:
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
        daily["close"] = pd.to_numeric(daily["close"], errors="coerce")
        daily = daily.dropna(subset=["date", "close"]).copy()
        daily["date_key"] = daily["date"].dt.strftime("%Y-%m-%d")
    eps = eps_df.copy()
    if not eps.empty:
        if "date" not in eps.columns and "report_date" in eps.columns:
            eps["date"] = eps["report_date"]
        eps["date"] = pd.to_datetime(eps["date"], errors="coerce")
        eps["eps"] = pd.to_numeric(eps["eps"], errors="coerce")
        eps = eps.dropna(subset=["date", "eps"]).sort_values("date").copy()

    items: list[dict[str, Any]] = []
    for _, row in work.iterrows():
        dividend_date = pd.to_datetime(row["date"], errors="coerce")
        if pd.isna(dividend_date):
            continue
        date_key = dividend_date.strftime("%Y-%m-%d")

        close_value, price_date = _lookup_nearest_close(daily, date_key)

        ttm_pe: float | None = None
        if close_value is not None and not eps.empty:
            candidates = eps[eps["date"] <= dividend_date].tail(4)
            if len(candidates) == 4:
                ttm_eps = float(candidates["eps"].sum())
                if ttm_eps > 0:
                    ttm_pe = close_value / ttm_eps

        items.append(
            {
                "date": date_key,
                "cash_dividend": _to_float_or_none(row.get("cash_dividend")),
                "stock_dividend": float(row.get("stock_dividend", 0.0)),
                "ttm_pe": _to_float_or_none(ttm_pe),
                "price_date": price_date,
            }
        )

    return {"symbol": symbol, "market": normalized_market, "items": items}


def get_industry_per_table(symbol: str, market: str = "tw") -> dict[str, Any]:
    normalized_market = normalize_market(market)
    if normalized_market != "tw":
        raise NotImplementedError("US not supported in P11.")

    info = _load_stock_info_table()
    if info.empty:
        return {
            "symbol": symbol,
            "market": normalized_market,
            "industry": None,
            "median": None,
            "mean": None,
            "count": 0,
            "items": [],
            "cached_at": None,
        }

    target = info[info["symbol"] == symbol]
    if target.empty:
        return {
            "symbol": symbol,
            "market": normalized_market,
            "industry": None,
            "median": None,
            "mean": None,
            "count": 0,
            "items": [],
            "cached_at": None,
        }

    industry = str(target.iloc[0].get("industry", "")).strip() or None
    if not industry:
        return {
            "symbol": symbol,
            "market": normalized_market,
            "industry": None,
            "median": None,
            "mean": None,
            "count": 0,
            "items": [],
            "cached_at": None,
        }

    peers = info[info["industry"] == industry].copy()
    peers = peers.drop_duplicates(subset=["symbol"], keep="first")
    peers = peers[peers["symbol"].astype(str).str.strip() != ""]

    cache_path = _industry_cache_path(industry=industry)
    lock = _get_industry_lock(industry)
    with lock:
        if cache_path.exists():
            cached = pd.read_parquet(cache_path)
            cached_at = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=ZoneInfo("Asia/Taipei")).isoformat()
            return _build_industry_per_payload(
                symbol=symbol,
                market=normalized_market,
                industry=industry,
                df=cached,
                cached_at=cached_at,
            )

        peer_rows = peers[["symbol", "name"]].to_dict(orient="records")
        rows: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(_fetch_peer_per_row, row["symbol"], row.get("name", "")): row["symbol"]
                for row in peer_rows
            }
            for future in as_completed(futures):
                rows.append(future.result())

        df = pd.DataFrame(rows)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_path, index=False)
        cached_at = datetime.now(ZoneInfo("Asia/Taipei")).isoformat()
        return _build_industry_per_payload(
            symbol=symbol,
            market=normalized_market,
            industry=industry,
            df=df,
            cached_at=cached_at,
        )


def get_institutional_cost(symbol: str, days: int = 30, market: str = "tw") -> dict[str, Any]:
    normalized_market = normalize_market(market)
    if normalized_market != "tw":
        raise NotImplementedError("US not supported in P11.")

    storage = ParquetStorage()
    daily = storage.load_daily(symbol, market=normalized_market)
    institutional = storage.load_institutional(symbol, market=normalized_market)

    if institutional.empty:
        try:
            fetcher = _build_chip_fetcher()
            fetcher.fetch_institutional_incremental(symbol, storage)
            institutional = storage.load_institutional(symbol, market=normalized_market)
        except Exception:  # noqa: BLE001
            institutional = storage.load_institutional(symbol, market=normalized_market)

    if not daily.empty:
        daily = daily.copy()
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
        daily = daily.dropna(subset=["date"]).copy()
        daily["typical_price"] = (
            pd.to_numeric(daily["high"], errors="coerce")
            + pd.to_numeric(daily["low"], errors="coerce")
            + pd.to_numeric(daily["close"], errors="coerce")
        ) / 3.0
        daily["date_key"] = daily["date"].dt.strftime("%Y-%m-%d")
        daily = daily.dropna(subset=["typical_price"]).copy()
    if not institutional.empty:
        institutional = institutional.copy()
        institutional["date"] = pd.to_datetime(institutional["date"], errors="coerce")
        institutional = institutional.dropna(subset=["date"]).sort_values("date").tail(max(1, int(days))).copy()
        institutional["date_key"] = institutional["date"].dt.strftime("%Y-%m-%d")

    current_price: float | None = None
    if not daily.empty:
        latest_close = pd.to_numeric(daily["close"], errors="coerce").dropna()
        if not latest_close.empty:
            current_price = float(latest_close.iloc[-1])

    def _cost_for(net_col: str) -> dict[str, float | None]:
        if daily.empty or institutional.empty:
            return {"cost": None, "pnl": None}
        work = institutional[["date_key", net_col]].copy()
        work[net_col] = pd.to_numeric(work[net_col], errors="coerce").fillna(0.0)
        work = work[work[net_col] > 0].copy()
        if work.empty:
            return {"cost": None, "pnl": None}
        joined = work.merge(daily[["date_key", "typical_price"]], on="date_key", how="inner")
        if joined.empty:
            return {"cost": None, "pnl": None}
        total_shares = float(joined[net_col].sum())
        if total_shares <= 0:
            return {"cost": None, "pnl": None}
        weighted_sum = float((joined[net_col] * joined["typical_price"]).sum())
        cost = weighted_sum / total_shares
        pnl = None if current_price is None else float(current_price - cost)
        return {"cost": _to_float_or_none(cost), "pnl": _to_float_or_none(pnl)}

    return {
        "symbol": symbol,
        "market": normalized_market,
        "days": int(days),
        "current_price": _to_float_or_none(current_price),
        "foreign": _cost_for("foreign_net"),
        "trust": _cost_for("trust_net"),
        "dealer": _cost_for("dealer_net"),
    }


def _serialize_event_entry(row: pd.Series, *, include_countdown: bool, today: pd.Timestamp) -> dict[str, Any]:
    date_ts = pd.Timestamp(row["date"])
    countdown = None
    if include_countdown:
        countdown = int((date_ts.normalize() - today.normalize()) / pd.Timedelta(days=1))
    return {
        "date": date_ts.strftime("%Y-%m-%d"),
        "meeting_type": str(row.get("meeting_type", "")).strip() or None,
        "source": str(row.get("source", "")).strip() or None,
        "is_manual": str(row.get("source", "")).strip() == "manual",
        "days_until": countdown,
    }


def _resolve_shareholder_meeting_event(symbol: str, storage: ParquetStorage) -> pd.DataFrame:
    auto_df = storage.load_shareholder_meeting()
    manual_df = storage.load_shareholder_meeting_override()

    auto_row = auto_df[auto_df["symbol"] == symbol].copy() if not auto_df.empty else auto_df.iloc[0:0].copy()
    manual_row = manual_df[manual_df["symbol"] == symbol].copy() if not manual_df.empty else manual_df.iloc[0:0].copy()
    if auto_row.empty and manual_row.empty:
        return auto_row
    if auto_row.empty:
        return manual_row
    if manual_row.empty:
        return auto_row

    auto_latest = auto_row.sort_values("updated_at").iloc[-1]
    manual_latest = manual_row.sort_values("updated_at").iloc[-1]
    auto_updated = pd.Timestamp(auto_latest["updated_at"])
    manual_updated = pd.Timestamp(manual_latest["updated_at"])
    return manual_row if manual_updated >= auto_updated else auto_row


def get_event_calendar(symbol: str, market: str = "tw") -> dict[str, Any]:
    normalized_market = normalize_market(market)
    if normalized_market != "tw":
        raise NotImplementedError("US not supported in P11.")

    storage = ParquetStorage()
    today = pd.Timestamp.now(tz="Asia/Taipei")

    dividends = storage.load_dividends(symbol, market=normalized_market)
    if not dividends.empty:
        dividends = dividends.copy()
        dividends["date"] = pd.to_datetime(dividends["date"], errors="coerce")
        if dividends["date"].dt.tz is None:
            dividends["date"] = dividends["date"].dt.tz_localize("Asia/Taipei")
        else:
            dividends["date"] = dividends["date"].dt.tz_convert("Asia/Taipei")
        dividends["cash_dividend"] = pd.to_numeric(dividends["cash_dividend"], errors="coerce")
        if "stock_dividend" in dividends.columns:
            dividends["stock_dividend"] = pd.to_numeric(dividends["stock_dividend"], errors="coerce").fillna(0.0)
        else:
            dividends["stock_dividend"] = 0.0
        dividends = dividends.dropna(subset=["date"]).copy()
        dividends = dividends[dividends["cash_dividend"].fillna(0) > 0].copy()
        dividends = dividends.sort_values("date").reset_index(drop=True)

    next_ex_dividend: dict[str, Any] | None = None
    last_ex_dividend: dict[str, Any] | None = None
    if not dividends.empty:
        future = dividends[dividends["date"] >= today]
        past = dividends[dividends["date"] < today]

        if not future.empty:
            row = future.iloc[0]
            days_until = int((pd.Timestamp(row["date"]).normalize() - today.normalize()) / pd.Timedelta(days=1))
            next_ex_dividend = {
                "date": pd.Timestamp(row["date"]).strftime("%Y-%m-%d"),
                "cash_dividend": _to_float_or_none(row.get("cash_dividend")),
                "stock_dividend": float(row.get("stock_dividend", 0.0)),
                "days_until": days_until,
                "is_estimated": False,
            }
        if not past.empty:
            row = past.iloc[-1]
            last_ex_dividend = {
                "date": pd.Timestamp(row["date"]).strftime("%Y-%m-%d"),
                "cash_dividend": _to_float_or_none(row.get("cash_dividend")),
                "stock_dividend": float(row.get("stock_dividend", 0.0)),
            }

    dividend_policy_fallback: dict[str, Any] | None = None
    if next_ex_dividend is None:
        dividend_policy_fallback = get_goodinfo_dividend_policy(symbol, today=today)

    meeting_df = _resolve_shareholder_meeting_event(symbol, storage)
    next_shareholder_meeting: dict[str, Any] | None = None
    last_shareholder_meeting: dict[str, Any] | None = None
    if not meeting_df.empty:
        row = meeting_df.sort_values("updated_at").iloc[-1]
        date_ts = pd.Timestamp(row["date"])
        if date_ts.tzinfo is None:
            date_ts = date_ts.tz_localize("Asia/Taipei")
        else:
            date_ts = date_ts.tz_convert("Asia/Taipei")
        if date_ts >= today.normalize():
            next_shareholder_meeting = _serialize_event_entry(row, include_countdown=True, today=today)
        else:
            last_shareholder_meeting = _serialize_event_entry(row, include_countdown=False, today=today)

    return {
        "symbol": symbol,
        "market": normalized_market,
        "next_ex_dividend": next_ex_dividend,
        "last_ex_dividend": last_ex_dividend,
        "dividend_policy_fallback": dividend_policy_fallback,
        "next_shareholder_meeting": next_shareholder_meeting,
        "last_shareholder_meeting": last_shareholder_meeting,
        "missing_shareholder_meeting": next_shareholder_meeting is None and last_shareholder_meeting is None,
        "is_etf": _lookup_is_etf(symbol),
    }


def upsert_shareholder_meeting_override(symbol: str, date: str, meeting_type: str, market: str = "tw") -> dict[str, Any]:
    normalized_market = normalize_market(market)
    if normalized_market != "tw":
        raise NotImplementedError("US not supported in P11.")
    storage = ParquetStorage()
    storage.upsert_shareholder_meeting_override(symbol=symbol, date=date, meeting_type=meeting_type)
    return {
        "symbol": symbol,
        "market": normalized_market,
        "date": date,
        "meeting_type": meeting_type,
        "source": "manual",
    }


def delete_shareholder_meeting_override(symbol: str, market: str = "tw") -> dict[str, Any]:
    normalized_market = normalize_market(market)
    if normalized_market != "tw":
        raise NotImplementedError("US not supported in P11.")
    storage = ParquetStorage()
    storage.delete_shareholder_meeting_override(symbol=symbol)
    return {"symbol": symbol, "market": normalized_market, "deleted": True}


# ---------------------------------------------------------------------------
# Internal helpers — these are pure Python, no st.* calls
# ---------------------------------------------------------------------------


def _to_iso_ts(value: Any) -> str | None:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize("Asia/Taipei")
    return ts.isoformat()


def _to_float_or_none(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(num):
        return None
    return num


def _load_stock_info_table() -> pd.DataFrame:
    cache_path = get_data_dir() / "stock_info_tw.parquet"
    if cache_path.exists():
        try:
            cached = pd.read_parquet(cache_path)
            if {"symbol", "name", "industry"}.issubset(cached.columns):
                out = cached[["symbol", "name", "industry"]].copy()
                out["symbol"] = out["symbol"].astype(str).str.strip()
                out["name"] = out["name"].fillna("").astype(str).str.strip()
                out["industry"] = out["industry"].fillna("").astype(str).str.strip()
                return out[out["symbol"] != ""].drop_duplicates(subset=["symbol"], keep="first")
        except Exception:  # noqa: BLE001
            pass

    try:
        fetcher = FinMindFetcher()
        info = fetcher.fetch_stock_info()
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=["symbol", "name", "industry"])

    if info.empty:
        return pd.DataFrame(columns=["symbol", "name", "industry"])

    out = info.copy()
    for col in ("symbol", "name", "industry"):
        if col not in out.columns:
            out[col] = ""
        out[col] = out[col].fillna("").astype(str).str.strip()
    out = out[out["symbol"] != ""].drop_duplicates(subset=["symbol"], keep="first")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    out[["symbol", "name", "industry"]].to_parquet(cache_path, index=False)
    return out[["symbol", "name", "industry"]]


def _lookup_is_etf(symbol: str) -> bool:
    info = _load_stock_info_table()
    if info.empty:
        return False
    row = info[info["symbol"] == symbol]
    if row.empty:
        return False
    return str(row.iloc[0].get("industry", "")).strip().upper() == "ETF"


def _lookup_symbol_industry(symbol: str) -> str | None:
    info = _load_stock_info_table()
    if info.empty:
        return None
    row = info[info["symbol"] == symbol]
    if row.empty:
        return None
    value = str(row.iloc[0].get("industry", "")).strip()
    return value or None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", value.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "unknown"


def _industry_cache_path(industry: str) -> Path:
    today = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d")
    slug = _slugify(industry)
    return get_data_dir() / "cache" / "industry_per" / f"{slug}_{today}.parquet"


def _get_industry_lock(industry: str) -> threading.Lock:
    key = _slugify(industry)
    with _INDUSTRY_LOCK_REGISTRY_GUARD:
        lock = _INDUSTRY_LOCK_REGISTRY.get(key)
        if lock is None:
            lock = threading.Lock()
            _INDUSTRY_LOCK_REGISTRY[key] = lock
    return lock


def _fetch_peer_per_row(symbol: str, name: str) -> dict[str, Any]:
    try:
        fetcher = FinMindFetcher()
        end = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d")
        start = "2015-01-01"
        per_df = fetcher.fetch_per(symbol=symbol, start=start, end=end)
        if per_df.empty:
            return {
                "symbol": symbol,
                "name": name,
                "date": None,
                "per": None,
                "pbr": None,
                "dividend_yield": None,
            }
        latest = per_df.sort_values("date").iloc[-1]
        return {
            "symbol": symbol,
            "name": name,
            "date": _to_iso_ts(latest.get("date")),
            "per": _to_float_or_none(latest.get("per")),
            "pbr": _to_float_or_none(latest.get("pbr")),
            "dividend_yield": _to_float_or_none(latest.get("dividend_yield")),
        }
    except Exception:  # noqa: BLE001
        return {
            "symbol": symbol,
            "name": name,
            "date": None,
            "per": None,
            "pbr": None,
            "dividend_yield": None,
        }


def _build_industry_per_payload(
    symbol: str,
    market: str,
    industry: str,
    df: pd.DataFrame,
    cached_at: str | None,
) -> dict[str, Any]:
    work = df.copy()
    for col in ("symbol", "name", "date", "per", "pbr", "dividend_yield"):
        if col not in work.columns:
            work[col] = None
    work["symbol"] = work["symbol"].astype(str)
    work["name"] = work["name"].fillna("").astype(str)
    work["per"] = pd.to_numeric(work["per"], errors="coerce")
    work["pbr"] = pd.to_numeric(work["pbr"], errors="coerce")
    work["dividend_yield"] = pd.to_numeric(work["dividend_yield"], errors="coerce")

    valid_per = work["per"].dropna()
    median_value = float(valid_per.median()) if not valid_per.empty else None
    mean_value = float(valid_per.mean()) if not valid_per.empty else None

    items = []
    for _, row in work.iterrows():
        row_symbol = str(row.get("symbol", "")).strip()
        items.append(
            {
                "symbol": row_symbol,
                "name": str(row.get("name", "")).strip(),
                "date": row.get("date"),
                "per": _to_float_or_none(row.get("per")),
                "pbr": _to_float_or_none(row.get("pbr")),
                "dividend_yield": _to_float_or_none(row.get("dividend_yield")),
                "is_current": row_symbol == symbol,
            }
        )

    return {
        "symbol": symbol,
        "market": market,
        "industry": industry,
        "median": median_value,
        "mean": mean_value,
        "count": int(len(items)),
        "items": items,
        "cached_at": cached_at,
    }


def _prepare_daily_data(
    symbol: str,
    storage: ParquetStorage,
    market: str = "tw",
) -> tuple[pd.DataFrame, str | None]:
    """Return (df, error_message).  error_message is None on success."""
    normalized_market = normalize_market(market)
    try:
        _sync_symbol_daily_data(symbol, storage, market=normalized_market)
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame(), f"{symbol} 日線資料更新失敗：{exc}"

    if normalized_market == "us":
        adjusted_df = storage.load_adjusted(symbol, market=normalized_market)
        if adjusted_df.empty:
            return pd.DataFrame(), f"{symbol} 尚無可用美股 adjusted 日線資料。"
        return adjusted_df, None

    return storage.load_daily(symbol, market=normalized_market), None


def _normalize_daily_df(df: pd.DataFrame, market: str = "tw") -> pd.DataFrame:
    timezone = get_market_spec(market).timezone
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if not out.empty:
        if out["date"].dt.tz is None:
            out["date"] = out["date"].dt.tz_localize(timezone)
        else:
            out["date"] = out["date"].dt.tz_convert(timezone)
    for col in ("open", "high", "low", "close", "volume"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close", "volume"])
    return out.reset_index(drop=True)


def _sync_symbol_daily_data(
    symbol: str,
    storage: ParquetStorage,
    market: str = "tw",
) -> None:
    """Auto-sync daily data via available fetchers.

    If the symbol has no local daily data yet (i.e. first-time access from the
    dashboard for a brand-new symbol), run a full ``rebuild_symbol`` so that
    P11 datasets (PER / monthly_revenue / EPS / dividends) are populated
    alongside the daily K-line. Otherwise run the lightweight ``update_daily``.

    Raises RuntimeError on total failure across all configured sources.
    """
    normalized_market = normalize_market(market)
    fetchers = _build_fetchers_from_config(market=normalized_market)
    if not fetchers:
        raise RuntimeError("No available data source. Details: n/a")

    # Decide rebuild vs update based on local daily presence. Checked once before
    # the fetcher loop so a fallback fetcher still uses the same strategy.
    is_first_time = storage.load_daily(symbol, market=normalized_market).empty

    errors: list[str] = []
    for source, fetcher in fetchers:
        meta = DuckDBMeta()
        try:
            maintenance = DataMaintenance(
                fetcher=fetcher,
                storage=storage,
                meta=meta,
                cleaner=DataCleaner(),
            )
            if is_first_time:
                # Full rebuild — daily + P11 (P11 failures are best-effort and do
                # not abort the daily pipeline, see DataMaintenance).
                maintenance.rebuild_symbol(symbol, market=normalized_market)
            else:
                maintenance.update_daily(symbol, market=normalized_market)
            return
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{source}: {exc}")
        finally:
            meta.close()

    raise RuntimeError(f"Daily data update failed for all sources. Details: {' | '.join(errors)}")


def _build_fetchers_from_config(market: str = "tw") -> list[tuple[str, IDataFetcher]]:
    normalized_market = normalize_market(market)
    config = get_config()
    data_section = config.get("data", {}) if isinstance(config, dict) else {}
    primary = str(data_section.get("primary_source", "finmind")).strip().lower()
    fallback = str(data_section.get("fallback_source", "yfinance")).strip().lower()
    order = [primary, fallback]

    fetchers: list[tuple[str, IDataFetcher]] = []
    for source in order:
        if source in {name for name, _ in fetchers}:
            continue
        try:
            if source == "finmind" and normalized_market == "tw":
                fetchers.append((source, FinMindFetcher()))
            elif source == "yfinance":
                fetchers.append((source, YFinanceFetcher(market=normalized_market)))
        except Exception:  # noqa: BLE001
            continue
    return fetchers


def _fetch_tw_realtime(
    symbol: str,
) -> tuple[RealtimeQuote | None, BidAskStructure | None, str | None]:
    """Return (quote, bid_ask, warning_message).  All may be None."""
    try:
        realtime = RealtimeFetcher.from_config()
        quote = realtime.fetch_quote(symbol)
        bid_ask = realtime.fetch_bid_ask_structure(quote)
        return quote, bid_ask, None
    except Exception as exc:  # noqa: BLE001
        return None, None, f"即時行情暫時不可用，已改用日線資料顯示：{exc}"


def _prepare_chip_data(
    symbol: str,
    storage: ParquetStorage,
) -> tuple[ChipSummary | None, pd.DataFrame, str | None]:
    try:
        fetcher = _build_chip_fetcher()
        institutional_df = fetcher.fetch_institutional_incremental(symbol, storage)
        margin_df = fetcher.fetch_margin_incremental(symbol, storage)
    except Exception as exc:  # noqa: BLE001
        return None, pd.DataFrame(), f"籌碼資料僅支援 FinMind，抓取失敗：{exc}"

    if institutional_df.empty and margin_df.empty:
        return None, pd.DataFrame(), "目前無可用籌碼資料。"

    chip = generate_chip_summary(institutional_df, margin_df, n_days=5)
    recent_df = _build_recent_institutional_table(institutional_df, n_days=5)
    return chip, recent_df, None


def _build_chip_fetcher() -> FinMindFetcher:
    config = get_config()
    data_section = config.get("data", {}) if isinstance(config, dict) else {}
    primary = str(data_section.get("primary_source", "finmind")).strip().lower()
    fallback = str(data_section.get("fallback_source", "yfinance")).strip().lower()
    order = [primary, fallback]

    errors: list[str] = []
    for source in order:
        if source != "finmind":
            continue
        try:
            return FinMindFetcher()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{source}: {exc}")

    raise RuntimeError(
        f"No available chip fetcher. Details: {' | '.join(errors) if errors else 'finmind not configured'}"
    )


def _build_recent_institutional_table(
    institutional_df: pd.DataFrame, *, n_days: int = 5
) -> pd.DataFrame:
    required = {"date", "foreign_net", "trust_net", "dealer_net"}
    if institutional_df.empty or not required.issubset(institutional_df.columns):
        return pd.DataFrame(columns=["日期", "外資", "投信", "自營商"])

    out = institutional_df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date").tail(max(1, int(n_days))).copy()
    if out.empty:
        return pd.DataFrame(columns=["日期", "外資", "投信", "自營商"])

    for col in ("foreign_net", "trust_net", "dealer_net"):
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    return pd.DataFrame(
        {
            "日期": out["date"].dt.strftime("%Y-%m-%d"),
            "外資": (out["foreign_net"] / 1000.0).astype(int),
            "投信": (out["trust_net"] / 1000.0).astype(int),
            "自營商": (out["dealer_net"] / 1000.0).astype(int),
        }
    ).reset_index(drop=True)


def _fetch_us_intraday_snapshot(
    symbol: str,
    raw_daily: pd.DataFrame,
) -> tuple[pd.DataFrame, USIntradaySnapshot | None, str | None]:
    """Attempt to fetch US intraday snapshot.  Returns (intraday_df, snapshot, error)."""
    try:
        fetcher = YFinanceFetcher(market="us")
        intraday_df = fetcher.fetch_us_intraday(symbol, period="1d", interval="1m", prepost=False)
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame(), None, f"美股盤中分K暫時不可用：{exc}"

    if intraday_df.empty:
        return pd.DataFrame(), None, "目前無法取得美股盤中分 K，已改用最新日線資料。"

    # Determine previous raw daily close
    previous_raw_close: float | None = None
    if not raw_daily.empty and "close" in raw_daily.columns:
        closes = pd.to_numeric(raw_daily["close"], errors="coerce").dropna()
        if len(closes) >= 2:
            previous_raw_close = float(closes.iloc[-2])
        elif len(closes) == 1:
            previous_raw_close = float(closes.iloc[-1])

    # Check if intraday data is from today (New York date)
    ny_tz = "America/New_York"
    today_ny = pd.Timestamp.now(tz=ny_tz).date()
    dates = intraday_df.get("date", pd.Series(dtype="object"))
    if dates.empty:
        return pd.DataFrame(), None, "目前無法取得美股盤中分 K，已改用最新日線資料。"

    latest_ts = pd.to_datetime(dates.iloc[-1], errors="coerce")
    if latest_ts is pd.NaT or pd.isna(latest_ts):
        return pd.DataFrame(), None, "目前無法取得美股盤中分 K，已改用最新日線資料。"

    if latest_ts.tzinfo is None:
        latest_ts = latest_ts.tz_localize(ny_tz)
    else:
        latest_ts = latest_ts.tz_convert(ny_tz)

    if latest_ts.date() != today_ny:
        return pd.DataFrame(), None, "目前無法取得美股盤中分 K（非今日資料），已改用最新日線資料。"

    # Build snapshot
    latest_close = float(pd.to_numeric(intraday_df["close"].iloc[-1], errors="coerce"))
    volume = int(pd.to_numeric(intraday_df.get("volume", pd.Series([0])), errors="coerce").fillna(0).sum())

    change: float = float("nan")
    change_pct: float = float("nan")
    if previous_raw_close is not None and previous_raw_close != 0:
        change = latest_close - previous_raw_close
        change_pct = change / previous_raw_close * 100.0

    snapshot = USIntradaySnapshot(
        symbol=symbol,
        price=latest_close,
        previous_raw_close=previous_raw_close if previous_raw_close is not None else float("nan"),
        change=change,
        change_pct=change_pct,
        volume=volume,
        timestamp=latest_ts,
        source="yfinance",
        interval="1m",
    )
    return intraday_df, snapshot, None


def _try_ai_analysis(
    *,
    symbol: str,
    technical: TechnicalSummary,
    chip: ChipSummary | None,
    daily: pd.DataFrame,
    market: str,
    currency: str,
) -> tuple[DashboardAnalysis | None, str | None]:
    """Run AI analysis.  Returns (analysis, error_message).  Both may be None."""
    try:
        advisor = AIAdvisor()
        analysis = advisor.generate_stock_dashboard_analysis(
            symbol=symbol,
            technical_summary=technical,
            chip_summary=chip,
            company_info=None,
            recent_prices=daily.tail(60),
            market=market,
            currency=currency,
        )
        return analysis, None
    except AIDisabledError:
        return None, None
    except (AICallError, Exception) as exc:  # noqa: BLE001
        return None, f"AI 劇本生成失敗：{exc}"


def _format_analysis_time(market: str = "tw") -> str:
    timezone = get_market_spec(market).timezone
    return datetime.now(ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M:%S")
