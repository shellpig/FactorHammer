"""Dashboard service — non-UI payload builder (Phase 10-A).

All functions return dataclasses or raise exceptions.
No Streamlit calls are made here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from src.ai.advisor import AIAdvisor, DashboardAnalysis
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
from src.core.config import get_config
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


# ---------------------------------------------------------------------------
# Internal helpers — these are pure Python, no st.* calls
# ---------------------------------------------------------------------------


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
    """Auto-sync daily data via available fetchers.  Raises RuntimeError on total failure."""
    normalized_market = normalize_market(market)
    fetchers = _build_fetchers_from_config(market=normalized_market)
    if not fetchers:
        raise RuntimeError("No available data source. Details: n/a")

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
