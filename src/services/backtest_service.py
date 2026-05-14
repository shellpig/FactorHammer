"""Backtest service — non-UI orchestration layer (Phase 10-A).

All functions return plain Python objects / dataclasses.
No Streamlit calls are made here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.backtest.cost import create_cost_calculator
from src.backtest.dca import DcaBacktestResult, run_dca_backtest
from src.backtest.engine_event import EventDrivenBacktester
from src.backtest.engine_vec import VectorizedBacktester
from src.backtest.metrics import BacktestResult
from src.core.config import get_config
from src.core.exceptions import FetcherError
from src.core.market import get_market_spec, normalize_market, normalize_symbol
from src.core.strategy_config import get_strategy_presets
from src.data.cleaner import DataCleaner
from src.data.fetcher import FinMindFetcher, IDataFetcher, YFinanceFetcher
from src.data.maintenance import DataMaintenance
from src.data.storage import DuckDBMeta, ParquetStorage
from src.strategy.examples.bias import BiasStrategy
from src.strategy.examples.bollinger_band import BollingerBandStrategy
from src.strategy.examples.donchian_breakout import DonchianBreakoutStrategy
from src.strategy.examples.kd_cross import KDCrossStrategy
from src.strategy.examples.ma_cross import MACrossStrategy
from src.strategy.examples.macd_cross import MACDCrossStrategy
from src.strategy.examples.rsi import RSIStrategy

_VECTOR_ENGINE = "vectorized"
_EVENT_ENGINE = "event_driven"

_SUPPORTED_TYPES = {
    "moving_average_cross",
    "dollar_cost_averaging",
    "rsi",
    "kd_cross",
    "macd_cross",
    "bollinger_band",
    "bias",
    "donchian_breakout",
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class BacktestJobResult:
    """Wraps the raw BacktestResult / DcaBacktestResult with metadata."""

    symbol: str
    market: str
    strategy_type: str
    strategy_params: dict[str, Any]
    currency: str
    engine: str
    result: BacktestResult | None = None
    dca_result: DcaBacktestResult | None = None
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    dca_warning: str | None = None
    error: str | None = None


@dataclass
class BacktestServiceError:
    code: str     # e.g. "INVALID_SYMBOL", "NO_DATA", "INVALID_PARAMS"
    message: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_backtest_data(
    symbol: str,
    start_ts: pd.Timestamp,
    end_exclusive: pd.Timestamp,
    *,
    market: str = "tw",
    require_adjusted: bool = True,
) -> pd.DataFrame | BacktestServiceError:
    """Load and auto-sync daily data for backtest.

    Returns a filtered DataFrame or a ``BacktestServiceError``.
    """
    normalized_market = normalize_market(market)
    timezone = get_market_spec(normalized_market).timezone
    storage = ParquetStorage()

    try:
        _sync_symbol_daily_data(symbol, storage, market=normalized_market)
    except FetcherError as exc:
        return BacktestServiceError(code="FETCH_FAILED", message=str(exc))
    except Exception as exc:  # noqa: BLE001
        return BacktestServiceError(code="FETCH_FAILED", message=str(exc))

    df = storage.load_adjusted(symbol, market=normalized_market)
    if df.empty and require_adjusted:
        return BacktestServiceError(
            code="NO_ADJUSTED_DATA",
            message=(
                f"{symbol} adjusted data is missing. "
                "Please run rebuild before backtest."
            ),
        )
    if df.empty:
        df = storage.load_daily(symbol, market=normalized_market)
    if df.empty:
        return BacktestServiceError(code="NO_DATA", message=f"{symbol} 無可用日線資料。")

    data = df.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).copy()
    if data["date"].dt.tz is None:
        data["date"] = data["date"].dt.tz_localize(timezone)
    else:
        data["date"] = data["date"].dt.tz_convert(timezone)

    for col in ("open", "high", "low", "close"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=["open", "high", "low", "close"])
    data = data[(data["date"] >= start_ts) & (data["date"] < end_exclusive)].copy()
    return data.sort_values("date").reset_index(drop=True)


def build_strategy(
    strategy_type: str,
    params: dict[str, Any],
) -> object | BacktestServiceError:
    """Instantiate a strategy from type + params dict.

    Returns the strategy object or a ``BacktestServiceError``.
    """
    try:
        if strategy_type == "moving_average_cross":
            ma_short = int(params.get("short_window", 20))
            ma_long = int(params.get("long_window", 60))
            if ma_short >= ma_long:
                return BacktestServiceError(
                    code="INVALID_PARAMS",
                    message="short_window 必須小於 long_window。",
                )
            return MACrossStrategy(ma_short=ma_short, ma_long=ma_long)

        if strategy_type == "rsi":
            return RSIStrategy(
                period=int(params.get("period", 14)),
                oversold=float(params.get("oversold", 30)),
                overbought=float(params.get("overbought", 70)),
            )

        if strategy_type == "kd_cross":
            return KDCrossStrategy(
                k_period=int(params.get("k_period", 9)),
                d_period=int(params.get("d_period", 3)),
                smooth_k=int(params.get("smooth_k", 3)),
            )

        if strategy_type == "macd_cross":
            return MACDCrossStrategy(
                fast=int(params.get("fast", 12)),
                slow=int(params.get("slow", 26)),
                signal=int(params.get("signal", 9)),
            )

        if strategy_type == "bollinger_band":
            return BollingerBandStrategy(
                period=int(params.get("period", 20)),
                std_dev=float(params.get("std_dev", 2.0)),
            )

        if strategy_type == "bias":
            return BiasStrategy(
                ma_period=int(params.get("ma_period", 20)),
                buy_bias=float(params.get("buy_bias", -10.0)),
                sell_bias=float(params.get("sell_bias", 10.0)),
            )

        if strategy_type == "donchian_breakout":
            return DonchianBreakoutStrategy(
                entry_period=int(params.get("entry_period", 20)),
                exit_period=int(params.get("exit_period", 10)),
            )

        return BacktestServiceError(
            code="UNSUPPORTED_STRATEGY",
            message=f"目前不支援策略類型：{strategy_type}",
        )

    except (ValueError, TypeError) as exc:
        return BacktestServiceError(code="INVALID_PARAMS", message=str(exc))


def run_backtest_job(
    *,
    symbol: str,
    start_ts: pd.Timestamp,
    end_exclusive: pd.Timestamp,
    strategy_preset: dict[str, Any],
    engine: str = _VECTOR_ENGINE,
    market: str = "tw",
) -> BacktestJobResult | BacktestServiceError:
    """Run a single backtest and return a ``BacktestJobResult``.

    Handles data loading, strategy instantiation, and engine dispatch.
    Returns ``BacktestServiceError`` on validation failures before execution.
    Execution errors are captured in ``BacktestJobResult.error``.
    """
    normalized_market = normalize_market(market)
    market_spec = get_market_spec(normalized_market)
    strategy_type = str(strategy_preset.get("type", "")).strip().lower()
    strategy_params: dict[str, Any] = (
        strategy_preset.get("params", {})
        if isinstance(strategy_preset.get("params"), dict)
        else {}
    )

    # ── load data ─────────────────────────────────────────────────────────
    data = load_backtest_data(
        symbol,
        start_ts,
        end_exclusive,
        market=normalized_market,
        require_adjusted=(strategy_type != "dollar_cost_averaging"),
    )
    if isinstance(data, BacktestServiceError):
        return data

    # ── DCA special path ─────────────────────────────────────────────────
    if strategy_type == "dollar_cost_averaging":
        dca_warning: str | None = None
        if normalized_market == "us":
            dca_warning = (
                "US-1 DCA 最小買入單位為 1 整股，不支援碎股。"
                "若每月投入金額低於股價，該期可能不會買進。"
            )
        try:
            dca_result = run_dca_backtest(
                data=data,
                symbol=symbol,
                start_ts=start_ts,
                end_exclusive=end_exclusive,
                params=strategy_params,
                cost_calculator=create_cost_calculator(market=normalized_market),
                market=normalized_market,
            )
        except Exception as exc:  # noqa: BLE001
            return BacktestJobResult(
                symbol=symbol,
                market=normalized_market,
                strategy_type=strategy_type,
                strategy_params=strategy_params,
                currency=market_spec.currency,
                engine="dca",
                data=data,
                error=str(exc),
            )
        return BacktestJobResult(
            symbol=symbol,
            market=normalized_market,
            strategy_type=strategy_type,
            strategy_params=strategy_params,
            currency=market_spec.currency,
            engine="dca",
            dca_result=dca_result,
            data=data,
            dca_warning=dca_warning,
        )

    # ── standard strategy path ────────────────────────────────────────────
    if data.empty:
        return BacktestServiceError(code="NO_DATA", message="資料區間內沒有可用日線資料。")

    strategy_obj = build_strategy(strategy_type, strategy_params)
    if isinstance(strategy_obj, BacktestServiceError):
        return strategy_obj

    cost_calculator = create_cost_calculator(market=normalized_market)
    engine_obj = (
        VectorizedBacktester(cost_calculator=cost_calculator)
        if engine == _VECTOR_ENGINE
        else EventDrivenBacktester(cost_calculator=cost_calculator)
    )
    try:
        result = engine_obj.run(strategy=strategy_obj, data=data)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        return BacktestJobResult(
            symbol=symbol,
            market=normalized_market,
            strategy_type=strategy_type,
            strategy_params=strategy_params,
            currency=market_spec.currency,
            engine=engine,
            data=data,
            error=str(exc),
        )

    return BacktestJobResult(
        symbol=symbol,
        market=normalized_market,
        strategy_type=strategy_type,
        strategy_params=strategy_params,
        currency=market_spec.currency,
        engine=engine,
        result=result,
        data=data,
    )


def list_strategy_presets() -> list[dict[str, Any]]:
    """Return current strategy presets from config."""
    return get_strategy_presets(get_config())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sync_symbol_daily_data(
    symbol: str,
    storage: ParquetStorage,
    market: str = "tw",
) -> None:
    normalized_market = normalize_market(market)
    fetchers = _build_fetchers_from_config(market=normalized_market)
    if not fetchers:
        raise FetcherError(f"{symbol} 自動更新日線資料失敗：No available data source. Details: n/a")

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

    raise FetcherError(f"{symbol} 自動更新日線資料失敗：{' | '.join(errors)}")


def _build_fetchers_from_config(market: str = "tw") -> list[tuple[str, IDataFetcher]]:
    normalized_market = normalize_market(market)
    cfg = get_config()
    data_section = cfg.get("data", {}) if isinstance(cfg, dict) else {}
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
