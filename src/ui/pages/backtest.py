"""Backtest page."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ModuleNotFoundError:  # pragma: no cover
    go = None
    make_subplots = None

try:
    import pandas_ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

try:
    from streamlit_extras.metric_cards import style_metric_cards
    HAS_EXTRAS = True
except ImportError:
    HAS_EXTRAS = False

from src.backtest.batch import BatchResult, run_strategy_batch, save_batch_result_csv
from src.backtest.sweep import (
    MAX_COMBOS,
    SWEEP_PARAM_SPECS,
    SweepResult,
    SweepRunSummary,
    generate_param_grid,
    parse_param_values,
    run_parameter_sweep,
    save_sweep_result_csv,
)
from src.backtest.walk_forward import (
    DEFAULT_IS_MONTHS,
    DEFAULT_OOS_MONTHS,
    DEFAULT_STEP_MONTHS,
    MAX_WFA_WINDOWS,
    MIN_WFA_WINDOWS,
    SUPPORTED_OPTIMIZE_METRICS,
    WalkForwardSummary,
    required_months_for_wfa,
    run_walk_forward_analysis,
    save_walk_forward_summary_csv,
)
from src.backtest.engine_event import EventDrivenBacktester
from src.backtest.engine_vec import VectorizedBacktester
from src.backtest.metrics import BacktestResult
from src.backtest.report import TearsheetReport
from src.backtest.dca import DcaBacktestResult, run_dca_backtest
from src.core.config import get_config
from src.core.constants import TAIPEI_TZ
from src.core.exceptions import FetcherError
from src.core.strategy_config import (
    STRATEGY_META,
    format_param_caption,
    get_strategy_meta,
    get_strategy_presets,
    make_strategy_label,
)
from src.data.fetcher import FinMindFetcher
from src.data.storage import ParquetStorage
from src.strategy.examples.bias import BiasStrategy
from src.strategy.examples.bollinger_band import BollingerBandStrategy
from src.strategy.examples.donchian_breakout import DonchianBreakoutStrategy
from src.strategy.examples.kd_cross import KDCrossStrategy
from src.strategy.examples.ma_cross import MACrossStrategy
from src.strategy.examples.macd_cross import MACDCrossStrategy
from src.strategy.examples.rsi import RSIStrategy

_TW_SYMBOL_PATTERN = re.compile(r"^\d{4,6}$")
_VECTOR_ENGINE_LABEL = "向量化引擎"
_EVENT_ENGINE_LABEL = "事件驅動引擎"
_TRADE_MARKER_BASE_SIZE = 10
_TRADE_MARKER_HEIGHT_MULTIPLIER = 2.5
_TRADE_MARKER_STEM_SIZE = int(round(_TRADE_MARKER_BASE_SIZE * _TRADE_MARKER_HEIGHT_MULTIPLIER))
_COMPARISONS_DIR = Path("data/backtest/strategy_comparisons")
_SWEEPS_DIR = Path("data/backtest/parameter_sweeps")
_WFA_DIR = Path("data/backtest/walk_forward")

_OPTIMIZE_METRIC_LABELS: dict[str, str] = {
    "sharpe_ratio": "Sharpe Ratio（夏普比率）",
    "total_return": "總報酬",
    "annual_return": "年化報酬",
}

_SUPPORTED_TYPES = {
    "moving_average_cross", "dollar_cost_averaging",
    "rsi", "kd_cross", "macd_cross", "bollinger_band", "bias", "donchian_breakout",
}


# ---------------------------------------------------------------------------
# Top-level render
# ---------------------------------------------------------------------------

def render() -> None:
    st.title("回測")
    st.caption("執行策略回測、查看 Tearsheet，並補充股價均線與 EPS 資訊。")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["單次回測", "策略比較", "參數掃描", "Walk-Forward（滾動樣本外驗證）", "歷史結果"]
    )

    with tab1:
        _render_single_backtest_tab()

    with tab2:
        _render_batch_comparison_tab()

    with tab3:
        _render_sweep_tab()

    with tab4:
        _render_walk_forward_tab()

    with tab5:
        _render_history_tab()


# ---------------------------------------------------------------------------
# Tab 1: single backtest
# ---------------------------------------------------------------------------

def _render_single_backtest_tab() -> None:
    symbol, start_date, end_date = _input_symbol_and_dates("single")

    c1, c2 = st.columns(2)
    with c1:
        engine_name = st.selectbox("回測引擎", options=[_VECTOR_ENGINE_LABEL, _EVENT_ENGINE_LABEL], index=0, key="single_engine")
    with c2:
        strategy_presets = get_strategy_presets(get_config())
        strategy_labels = [make_strategy_label(p) for p in strategy_presets]
        strategy_label = st.selectbox("策略", options=strategy_labels, index=0, key="single_strategy")

    selected_strategy = strategy_presets[strategy_labels.index(strategy_label)]
    selected_type = str(selected_strategy.get("type", "")).strip().lower()
    selected_params = selected_strategy.get("params", {}) if isinstance(selected_strategy.get("params"), dict) else {}

    if selected_type in _SUPPORTED_TYPES:
        meta = get_strategy_meta(selected_type)
        if meta:
            st.caption(f"{meta['description']}　買進：{meta['buy_hint']}　賣出：{meta['sell_hint']}")
        param_caption = format_param_caption(selected_type, selected_params)
        if param_caption:
            st.caption(f"策略參數：{param_caption}")
    else:
        st.warning(f"此策略類型目前未支援執行：{selected_type}")

    if st.button("開始回測", type="primary", key="single_run"):
        _run_backtest(
            symbol=symbol,
            start_date=pd.Timestamp(start_date),
            end_date=pd.Timestamp(end_date),
            engine_name=engine_name,
            strategy_preset=selected_strategy,
        )


# ---------------------------------------------------------------------------
# Tab 2: batch comparison
# ---------------------------------------------------------------------------

def _render_batch_comparison_tab() -> None:
    symbol, start_date, end_date = _input_symbol_and_dates("batch")

    if st.button("批次回測全部策略", type="primary", key="batch_run"):
        if not _TW_SYMBOL_PATTERN.fullmatch(symbol):
            st.error("股票代碼格式錯誤，請輸入 4 到 6 碼台股代碼。")
            return
        start_ts = _as_taipei_start(pd.Timestamp(start_date))
        end_exclusive = _as_taipei_start(pd.Timestamp(end_date)) + pd.Timedelta(days=1)
        if end_exclusive <= start_ts:
            st.error("結束日期必須晚於開始日期。")
            return

        with st.spinner("載入資料並執行批次回測…"):
            try:
                data = _load_backtest_data(
                    symbol=symbol,
                    start_ts=start_ts,
                    end_exclusive=end_exclusive,
                    require_adjusted=True,
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"讀取資料失敗：{exc}")
                return

            if data.empty:
                st.warning("資料區間內沒有可用日線資料。")
                return

            presets = get_strategy_presets(get_config())
            batch = run_strategy_batch(
                data=data,
                symbol=symbol,
                start_date=start_ts.strftime("%Y-%m-%d"),
                end_date=(end_exclusive - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                presets=presets,
            )

        st.session_state["batch_result"] = batch
        st.session_state["batch_data"] = data
        st.session_state["batch_presets"] = presets

    batch: BatchResult | None = st.session_state.get("batch_result")
    if batch is None:
        st.info("設定股票代碼與日期後，點選「批次回測全部策略」。")
        return

    # Build comparison dataframe
    rows = []
    for s in batch.summaries:
        meta = STRATEGY_META.get(s.strategy_type)
        type_label = meta["label"] if meta else s.strategy_type
        pf = s.profit_factor
        rows.append({
            "策略名稱": s.preset_name,
            "策略類型": type_label,
            "總報酬": f"{s.total_return * 100:.2f}%" if not s.error else "—",
            "年化報酬": f"{s.annual_return * 100:.2f}%" if not s.error else "—",
            "最大回撤": f"{s.max_drawdown * 100:.2f}%" if not s.error else "—",
            "Sharpe（夏普比率）": f"{s.sharpe_ratio:.2f}" if not s.error else "—",
            "勝率": f"{s.win_rate * 100:.2f}%" if not s.error else "—",
            "Profit Factor": ("N/A" if pf >= 999.0 else f"{pf:.2f}") if not s.error else "—",
            "交易次數": s.total_trades if not s.error else "—",
            "備註": s.error or "",
        })

    df_compare = pd.DataFrame(rows)

    st.subheader(f"{batch.symbol} 策略比較（{batch.start_date} ~ {batch.end_date}）")

    sel = st.dataframe(
        df_compare,
        width="stretch",
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key="batch_table",
        column_config={
            "備註": st.column_config.TextColumn("備註", width="large"),
        },
    )

    # Export button
    if st.button("匯出結果為 CSV", key="batch_export"):
        saved_path = save_batch_result_csv(batch)
        st.success(f"已儲存：{saved_path}")

    # Expand selected strategy
    selected_rows = sel.selection.get("rows", []) if sel and hasattr(sel, "selection") else []
    if selected_rows:
        idx = selected_rows[0]
        summary = batch.summaries[idx]
        if summary.error:
            st.warning(f"此策略回測失敗，無法展開詳細結果：{summary.error}")
        elif summary.result is not None:
            st.divider()
            st.subheader(f"詳細結果：{summary.preset_name}")
            result = summary.result
            data: pd.DataFrame = st.session_state.get("batch_data", pd.DataFrame())
            presets = st.session_state.get("batch_presets", [])
            preset = next((p for p in presets if p.get("name") == summary.preset_name), {})
            _render_tearsheet_metrics(result)
            _render_price_and_indicator_panel(
                price_df=data,
                trades=result.trades,
                signals=result.signals,
                symbol=batch.symbol,
                strategy_type=summary.strategy_type,
                strategy_params=preset.get("params", {}),
            )


# ---------------------------------------------------------------------------
# Tab 3: history
# ---------------------------------------------------------------------------

def _render_history_tab() -> None:
    st.subheader("歷史比較結果")
    _COMPARISONS_DIR.mkdir(parents=True, exist_ok=True)
    _SWEEPS_DIR.mkdir(parents=True, exist_ok=True)
    _WFA_DIR.mkdir(parents=True, exist_ok=True)

    comparison_files = sorted(_COMPARISONS_DIR.glob("*.csv"), reverse=True)
    sweep_files = sorted(_SWEEPS_DIR.glob("*.csv"), reverse=True)
    wfa_files = sorted(_WFA_DIR.glob("*.csv"), reverse=True)

    file_entries: list[tuple[str, Path]] = (
        [(f"[策略比較] {f.name}", f) for f in comparison_files]
        + [(f"[參數掃描] {f.name}", f) for f in sweep_files]
        + [(f"[Walk-Forward] {f.name}", f) for f in wfa_files]
    )

    if not file_entries:
        st.info(
            f"尚無歷史結果。執行回測並匯出後，檔案會出現在 {_COMPARISONS_DIR}、{_SWEEPS_DIR} 或 {_WFA_DIR}。"
        )
        return

    labels = [label for label, _ in file_entries]
    chosen = st.selectbox("選擇歷史檔案", options=labels, key="history_file")
    if chosen:
        _, filepath = file_entries[labels.index(chosen)]
        try:
            df = pd.read_csv(filepath, encoding="utf-8-sig")
            st.dataframe(df, width="stretch", hide_index=True)
            st.caption(f"檔案路徑：{filepath}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"讀取檔案失敗：{exc}")


# ---------------------------------------------------------------------------
# Tab 3: parameter sweep
# ---------------------------------------------------------------------------

_SWEEP_DEFAULTS: dict[str, dict[str, str]] = {
    "moving_average_cross": {"short_window": "5,10,20", "long_window": "40,60,120"},
    "rsi": {"period": "7,14,21", "oversold": "20,30", "overbought": "70,80"},
    "kd_cross": {"k_period": "9,14", "d_period": "3,5", "smooth_k": "3,5"},
    "macd_cross": {"fast": "8,12", "slow": "20,26", "signal": "7,9"},
    "bollinger_band": {"period": "10,20,30", "std_dev": "1.5,2.0,2.5"},
    "bias": {"ma_period": "10,20,30", "buy_bias": "-15,-10,-5", "sell_bias": "5,10,15"},
    "donchian_breakout": {"entry_period": "10,20,55", "exit_period": "5,10,20"},
}


def _render_sweep_tab() -> None:
    symbol, start_date, end_date = _input_symbol_and_dates("sweep")

    sweep_types = list(SWEEP_PARAM_SPECS.keys())
    type_labels = [STRATEGY_META[t]["label"] for t in sweep_types]
    type_label = st.selectbox("策略類型", options=type_labels, key="sweep_strategy_type")
    strategy_type = sweep_types[type_labels.index(type_label)]

    meta = STRATEGY_META[strategy_type]
    param_specs = SWEEP_PARAM_SPECS[strategy_type]
    param_label_map = meta["param_labels"]
    defaults = _SWEEP_DEFAULTS.get(strategy_type, {})

    st.markdown("**參數掃描範圍**（每個參數輸入逗號分隔的候選值，如 `5,10,20`）")
    param_inputs: dict[str, str] = {}
    for param_key in param_specs:
        label = param_label_map.get(param_key, param_key)
        param_inputs[param_key] = st.text_input(
            label,
            value=defaults.get(param_key, ""),
            key=f"sweep_{strategy_type}_{param_key}",
        )

    param_candidates: dict[str, list[Any]] = {}
    parse_error = False
    for k, raw in param_inputs.items():
        vals = parse_param_values(raw)
        if not vals:
            st.warning(f"參數「{param_label_map.get(k, k)}」格式無效，請輸入逗號分隔的數字。")
            parse_error = True
        else:
            param_candidates[k] = vals

    over_limit = False
    if not parse_error:
        total_count, valid_list = generate_param_grid(strategy_type, param_candidates)
        n_valid = len(valid_list)
        over_limit = n_valid > MAX_COMBOS
        if over_limit:
            st.warning(f"合法組合數 {n_valid} 超過上限 {MAX_COMBOS}，請縮小參數範圍。")
        else:
            st.info(f"{total_count} 組合中 {n_valid} 個合法")

    initial_capital = st.number_input(
        "初始資金", value=1_000_000, min_value=1, step=100_000, key="sweep_capital_input"
    )

    if st.button("開始掃描", type="primary", key="sweep_run", disabled=(parse_error or over_limit)):
        if not _TW_SYMBOL_PATTERN.fullmatch(symbol):
            st.error("股票代碼格式錯誤，請輸入 4 到 6 碼台股代碼。")
            return
        start_ts = _as_taipei_start(pd.Timestamp(start_date))
        end_exclusive = _as_taipei_start(pd.Timestamp(end_date)) + pd.Timedelta(days=1)
        if end_exclusive <= start_ts:
            st.error("結束日期必須晚於開始日期。")
            return

        with st.spinner("載入資料並執行參數掃描…"):
            try:
                data = _load_backtest_data(
                    symbol=symbol,
                    start_ts=start_ts,
                    end_exclusive=end_exclusive,
                    require_adjusted=True,
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"讀取資料失敗：{exc}")
                return

            if data.empty:
                st.warning("資料區間內沒有可用日線資料。")
                return

            sweep = run_parameter_sweep(
                data=data,
                symbol=symbol,
                start_date=start_ts.strftime("%Y-%m-%d"),
                end_date=(end_exclusive - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                strategy_type=strategy_type,
                param_candidates=param_candidates,
                initial_capital=float(initial_capital),
            )

        st.session_state["sweep_result"] = sweep
        st.session_state["sweep_data"] = data
        st.session_state["sweep_run_capital"] = float(initial_capital)

    sweep_result: SweepResult | None = st.session_state.get("sweep_result")
    if sweep_result is None:
        st.info("設定股票代碼、日期與參數範圍後，點選「開始掃描」。")
        return

    _render_sweep_results(
        sweep_result,
        st.session_state.get("sweep_data", pd.DataFrame()),
        initial_capital=st.session_state.get("sweep_run_capital", 1_000_000.0),
    )


def _render_sweep_results(
    sweep: SweepResult,
    data: pd.DataFrame,
    initial_capital: float,
) -> None:
    meta = STRATEGY_META.get(sweep.strategy_type)
    type_label = meta["label"] if meta else sweep.strategy_type

    st.subheader(f"{sweep.symbol} 參數掃描結果（{sweep.start_date} ~ {sweep.end_date}）")
    st.caption(
        f"策略：{type_label}　"
        f"{sweep.total_combos} 組合中 {sweep.valid_combos} 個合法"
    )

    _SORT_OPTIONS: dict[str, tuple[str, bool]] = {
        "Sharpe Ratio（夏普比率）": ("sharpe_ratio", False),
        "總報酬": ("total_return", False),
        "年化報酬": ("annual_return", False),
        "最大回撤（升序）": ("max_drawdown", True),
        "勝率": ("win_rate", False),
        "Profit Factor": ("profit_factor", False),
    }
    sort_label = st.selectbox(
        "排序依據", options=list(_SORT_OPTIONS.keys()), index=0, key="sweep_sort"
    )
    sort_col, sort_asc = _SORT_OPTIONS[sort_label]
    top_n = st.slider("顯示筆數", min_value=1, max_value=50, value=20, key="sweep_top_n")

    param_keys = SWEEP_PARAM_SPECS.get(sweep.strategy_type, [])
    rows = []
    for s in sweep.results:
        if s.error:
            continue
        pf = s.profit_factor
        dd = s.max_drawdown

        trades_display = f"⚠ {s.total_trades} (樣本不足)" if s.sample_warning else str(s.total_trades)
        dd_display = f"⚠ {dd * 100:.2f}%" if dd > 0.5 else f"{dd * 100:.2f}%"
        pf_display = "N/A" if pf >= 999.0 else f"{pf:.2f}"

        row: dict[str, Any] = {k: s.params.get(k, "") for k in param_keys}
        row.update({
            "總報酬": f"{s.total_return * 100:.2f}%",
            "年化報酬": f"{s.annual_return * 100:.2f}%",
            "最大回撤": dd_display,
            "Sharpe（夏普比率）": f"{s.sharpe_ratio:.2f}",
            "勝率": f"{s.win_rate * 100:.2f}%",
            "Profit Factor": pf_display,
            "交易次數": trades_display,
            "_sharpe_ratio": s.sharpe_ratio,
            "_total_return": s.total_return,
            "_annual_return": s.annual_return,
            "_max_drawdown": dd,
            "_win_rate": s.win_rate,
            "_profit_factor": pf,
            "_summary": s,
        })
        rows.append(row)

    if not rows:
        st.warning("掃描結果全部出錯，無法顯示。")
        return

    df_all = pd.DataFrame(rows)
    df_sorted = df_all.sort_values(f"_{sort_col}", ascending=sort_asc).head(top_n).reset_index(drop=True)

    display_cols = param_keys + ["總報酬", "年化報酬", "最大回撤", "Sharpe（夏普比率）", "勝率", "Profit Factor", "交易次數"]
    display_df = df_sorted[[c for c in display_cols if c in df_sorted.columns]]

    st.subheader(f"Top {min(top_n, len(df_sorted))} 結果（依 {sort_label}）")

    sel = st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key="sweep_table",
    )

    if st.button("匯出掃描結果", key="sweep_export"):
        saved_path = save_sweep_result_csv(sweep)
        st.success(f"已儲存：{saved_path}")

    selected_rows = sel.selection.get("rows", []) if sel and hasattr(sel, "selection") else []
    if not selected_rows:
        return

    row_idx = selected_rows[0]
    s: SweepRunSummary = df_sorted.iloc[row_idx]["_summary"]
    param_str = ", ".join(f"{k}={s.params[k]}" for k in param_keys if k in s.params)

    st.divider()
    st.subheader(f"詳細結果：{param_str}")

    if s.result is None:
        st.warning("此組合無詳細結果（執行時出錯）。")
        return

    _render_tearsheet_metrics(s.result)
    if not data.empty:
        _render_price_and_indicator_panel(
            price_df=data,
            trades=s.result.trades,
            signals=s.result.signals,
            symbol=sweep.symbol,
            strategy_type=sweep.strategy_type,
            strategy_params=s.params,
        )


# ---------------------------------------------------------------------------
# Tab 4: Walk-Forward Analysis
# ---------------------------------------------------------------------------

def _render_walk_forward_tab() -> None:
    st.info(
        "**Walk-Forward 分析（WFA）** 將歷史資料切為多段滾動視窗，逐段執行：\n\n"
        "1. **IS（樣本內／訓練期）**：在此期間網格搜尋找出最佳參數\n"
        "2. **OOS（樣本外／驗證期）**：以最佳參數在未見資料上回測，評估策略泛化能力\n\n"
        f"最多 **{MAX_WFA_WINDOWS}** 段視窗；每段組合數不可超過 **{MAX_COMBOS}**。"
    )

    symbol, start_date, end_date = _input_symbol_and_dates("wfa")

    sweep_types = list(SWEEP_PARAM_SPECS.keys())
    type_labels = [STRATEGY_META[t]["label"] for t in sweep_types]
    type_label = st.selectbox("策略類型", options=type_labels, key="wfa_strategy_type")
    strategy_type = sweep_types[type_labels.index(type_label)]

    meta = STRATEGY_META[strategy_type]
    param_specs = SWEEP_PARAM_SPECS[strategy_type]
    param_label_map = meta["param_labels"]
    defaults = _SWEEP_DEFAULTS.get(strategy_type, {})

    st.markdown("**參數掃描範圍**（每個參數輸入逗號分隔的候選值，如 `5,10,20`）")
    param_inputs: dict[str, str] = {}
    for param_key in param_specs:
        label = param_label_map.get(param_key, param_key)
        param_inputs[param_key] = st.text_input(
            label,
            value=defaults.get(param_key, ""),
            key=f"wfa_{strategy_type}_{param_key}",
        )

    param_candidates: dict[str, list[Any]] = {}
    parse_error = False
    for k, raw in param_inputs.items():
        vals = parse_param_values(raw)
        if not vals:
            st.warning(f"參數「{param_label_map.get(k, k)}」格式無效，請輸入逗號分隔的數字。")
            parse_error = True
        else:
            param_candidates[k] = vals

    c1, c2, c3 = st.columns(3)
    with c1:
        is_months = st.number_input(
            "IS 訓練期（月）", value=DEFAULT_IS_MONTHS, min_value=3, max_value=36, step=1, key="wfa_is_months"
        )
    with c2:
        oos_months = st.number_input(
            "OOS 驗證期（月）", value=DEFAULT_OOS_MONTHS, min_value=1, max_value=24, step=1, key="wfa_oos_months"
        )
    with c3:
        step_months = st.number_input(
            "步進（月）", value=DEFAULT_STEP_MONTHS, min_value=1, max_value=24, step=1, key="wfa_step_months"
        )

    is_m, oos_m, step_m = int(is_months), int(oos_months), int(step_months)
    req_months = required_months_for_wfa(is_months=is_m, oos_months=oos_m, step_months=step_m)

    # Estimate window count from user-selected date range (approximation; actual depends on trading days)
    _start_est = pd.Timestamp(start_date)
    _end_est = pd.Timestamp(end_date)
    _total_months = (_end_est.year - _start_est.year) * 12 + (_end_est.month - _start_est.month)
    _span = _total_months - is_m - oos_m
    est_windows = min(MAX_WFA_WINDOWS, max(0, _span // step_m + 1)) if _span >= 0 else 0

    st.caption(
        f"最少需要 **{req_months}** 個月資料（{MIN_WFA_WINDOWS} 段視窗）；"
        f"最多執行 **{MAX_WFA_WINDOWS}** 段；依目前日期區間預估 **{est_windows}** 段。"
    )

    over_limit = False
    if not parse_error:
        total_count, valid_list = generate_param_grid(strategy_type, param_candidates)
        n_valid = len(valid_list)
        over_limit = n_valid > MAX_COMBOS
        if over_limit:
            st.warning(
                f"合法組合數 {n_valid} 超過每段上限 {MAX_COMBOS}，請縮小參數範圍。"
            )
        else:
            st.info(
                f"預估 **{est_windows}** 段 × **{n_valid}** 組合 = 最多 **{est_windows * n_valid}** 次回測"
                f"（{total_count} 組合中 {n_valid} 個合法；實際視窗數以載入資料後為準）"
            )

    sorted_metrics = sorted(SUPPORTED_OPTIMIZE_METRICS)
    metric_label_options = [_OPTIMIZE_METRIC_LABELS.get(m, m) for m in sorted_metrics]
    default_metric_idx = sorted_metrics.index("sharpe_ratio") if "sharpe_ratio" in sorted_metrics else 0
    metric_label = st.selectbox(
        "最佳化指標（IS 期用來挑選最佳參數的指標）",
        options=metric_label_options,
        index=default_metric_idx,
        key="wfa_optimize_metric",
    )
    label_to_key = {v: k for k, v in _OPTIMIZE_METRIC_LABELS.items()}
    optimize_metric = label_to_key.get(metric_label, "sharpe_ratio")

    initial_capital = st.number_input(
        "初始資金", value=1_000_000, min_value=1, step=100_000, key="wfa_capital"
    )

    if st.button(
        "開始 Walk-Forward 分析", type="primary", key="wfa_run",
        disabled=(parse_error or over_limit),
    ):
        if not _TW_SYMBOL_PATTERN.fullmatch(symbol):
            st.error("股票代碼格式錯誤，請輸入 4 到 6 碼台股代碼。")
            return
        start_ts = _as_taipei_start(pd.Timestamp(start_date))
        end_exclusive = _as_taipei_start(pd.Timestamp(end_date)) + pd.Timedelta(days=1)
        if end_exclusive <= start_ts:
            st.error("結束日期必須晚於開始日期。")
            return

        with st.spinner("載入資料中…"):
            try:
                data = _load_backtest_data(
                    symbol=symbol,
                    start_ts=start_ts,
                    end_exclusive=end_exclusive,
                    require_adjusted=True,
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"讀取資料失敗：{exc}")
                return

            if data.empty:
                st.warning("資料區間內沒有可用日線資料。")
                return

        progress_bar = st.progress(0.0)
        status_text = st.empty()

        def on_progress(done: int, total: int) -> None:
            progress_bar.progress(done / total if total > 0 else 1.0)
            status_text.text(f"正在執行第 {done} / {total} 段 WFA...")

        try:
            wfa_data = data.set_index("date")
            summary = run_walk_forward_analysis(
                symbol=symbol,
                data=wfa_data,
                strategy_type=strategy_type,
                param_ranges=param_candidates,
                optimize_metric=optimize_metric,
                initial_capital=float(initial_capital),
                is_months=int(is_months),
                oos_months=int(oos_months),
                step_months=int(step_months),
                progress_fn=on_progress,
            )
        except ValueError as exc:
            progress_bar.empty()
            status_text.empty()
            st.error(str(exc))
            return

        progress_bar.progress(1.0)
        status_text.text("WFA 完成！")

        st.session_state["wfa_result"] = summary
        st.session_state["wfa_result_symbol"] = symbol

    wfa_summary: WalkForwardSummary | None = st.session_state.get("wfa_result")
    if wfa_summary is None:
        st.info("設定股票代碼、日期與參數範圍後，點選「開始 Walk-Forward 分析」。")
        return

    _render_wfa_results(wfa_summary, symbol=st.session_state.get("wfa_result_symbol", ""))


def _fmt_wfa_metric(value: float, metric: str) -> str:
    if metric == "sharpe_ratio":
        return f"{value:.2f}"
    return f"{value * 100:.2f}%"


def _render_wfa_results(summary: WalkForwardSummary, *, symbol: str) -> None:
    meta = STRATEGY_META.get(summary.strategy_type)
    type_label = meta["label"] if meta else summary.strategy_type
    metric_label = _OPTIMIZE_METRIC_LABELS.get(summary.optimize_metric, summary.optimize_metric)

    st.subheader(f"{symbol} Walk-Forward 分析結果")
    st.caption(f"策略：{type_label}　IS 最佳化指標：{metric_label}")

    agg = summary.aggregate

    c1, c2, c3 = st.columns(3)
    c1.metric("有效視窗數", f"{summary.valid_window_count} / {summary.total_window_count}")
    c2.metric("OOS 獲利視窗率", f"{agg.get('oos_win_window_rate', 0.0) * 100:.1f}%")
    c3.metric("平均 OOS 報酬", f"{agg.get('avg_oos_return', 0.0) * 100:.2f}%")

    c4, c5, c6 = st.columns(3)
    c4.metric("平均 OOS Sharpe（夏普比率）", f"{agg.get('avg_oos_sharpe', 0.0):.2f}")
    worst_dd = agg.get("worst_oos_drawdown", 0.0)
    c5.metric("最差 OOS 回撤", f"{worst_dd * 100:.2f}%")
    avg_deg = agg.get("avg_degradation")
    c6.metric(
        "平均退化（OOS−IS）",
        _fmt_wfa_metric(avg_deg, summary.optimize_metric) if avg_deg is not None else "N/A",
    )

    st.subheader("各視窗結果（IS=樣本內訓練期，OOS=樣本外驗證期）")
    win_rows = []
    all_window_warnings: list[tuple[int, str]] = []

    for wr in summary.windows:
        w = wr.window
        all_window_warnings.extend((w.window_id, msg) for msg in wr.warnings)

        if wr.skipped:
            first_warn = wr.warnings[0] if wr.warnings else "略過"
            if "IS 掃描" in first_warn:
                status_str = "掃描失敗，跳過"
            elif "OOS" in first_warn:
                status_str = "OOS 失敗，跳過"
            else:
                status_str = "略過"
        elif wr.warnings:
            status_str = f"完成（⚠ {len(wr.warnings)}）"
        else:
            status_str = "完成"

        row: dict[str, Any] = {
            "視窗": w.window_id,
            "IS 期間": f"{w.is_start.strftime('%Y-%m-%d')} ~ {w.is_end.strftime('%Y-%m-%d')}",
            "OOS 期間": f"{w.oos_start.strftime('%Y-%m-%d')} ~ {w.oos_end.strftime('%Y-%m-%d')}",
            "狀態": status_str,
            "最佳參數": (
                ", ".join(f"{k}={v}" for k, v in wr.best_params.items())
                if wr.best_params else "—"
            ),
        }

        if wr.is_best and not wr.skipped:
            row[f"IS {metric_label}"] = _fmt_wfa_metric(
                getattr(wr.is_best, summary.optimize_metric, 0.0), summary.optimize_metric
            )
        else:
            row[f"IS {metric_label}"] = "—"

        if wr.oos_result and not wr.skipped:
            row[f"OOS {metric_label}"] = _fmt_wfa_metric(
                getattr(wr.oos_result, summary.optimize_metric, 0.0), summary.optimize_metric
            )
            row["OOS 報酬"] = f"{wr.oos_result.total_return * 100:.2f}%"
            row["OOS Sharpe（夏普比率）"] = f"{wr.oos_result.sharpe_ratio:.2f}"
            row["OOS 交易次數"] = wr.oos_result.total_trades
        else:
            row[f"OOS {metric_label}"] = "—"
            row["OOS 報酬"] = "—"
            row["OOS Sharpe（夏普比率）"] = "—"
            row["OOS 交易次數"] = "—"

        row["退化"] = (
            _fmt_wfa_metric(wr.degradation, summary.optimize_metric)
            if wr.degradation is not None else "—"
        )

        if wr.warnings:
            first = wr.warnings[0]
            row["警告"] = first[:45] + ("…" if len(first) > 45 else "")
        else:
            row["警告"] = "—"

        win_rows.append(row)

    st.dataframe(pd.DataFrame(win_rows), width="stretch", hide_index=True)

    if all_window_warnings:
        with st.expander(f"視窗警告詳情（共 {len(all_window_warnings)} 則）"):
            for wid, msg in all_window_warnings:
                st.warning(f"視窗 {wid}：{msg}")

    stab = summary.parameter_stability
    overall_status = stab.get("overall_status", "")
    status_display = {"stable": "穩定 ✓", "moderate": "中等 ⚠", "unstable": "不穩定 ✗"}.get(
        overall_status, overall_status
    )
    st.subheader(f"參數穩定性：{status_display}")
    st.caption(
        "CV（變異係數）= 標準差 ÷ |均值|；衡量最佳參數跨視窗的一致程度。"
        "CV < 0.15 穩定，0.15–0.40 中等，≥ 0.40 不穩定（過度配適風險高）。"
    )

    stab_params = stab.get("params", {})
    if stab_params:
        status_map = {"stable": "穩定", "moderate": "中等", "unstable": "不穩定"}
        stab_rows = [
            {
                "參數": param,
                "最小值": f"{stat.get('min', 0):.4g}",
                "最大值": f"{stat.get('max', 0):.4g}",
                "平均": f"{stat.get('mean', 0):.4g}",
                "中位數": f"{stat.get('median', 0):.4g}",
                "標準差": f"{stat.get('std', 0):.4g}",
                "CV（變異係數）": f"{stat.get('cv', 0):.2f}",
                "狀態": status_map.get(stat.get("status", ""), stat.get("status", "")),
            }
            for param, stat in stab_params.items()
        ]
        st.dataframe(pd.DataFrame(stab_rows), width="stretch", hide_index=True)

    warnings_list = agg.get("warnings", [])
    if warnings_list:
        st.subheader("綜合警告")
        for msg in warnings_list:
            st.warning(msg)

    if st.button("匯出 WFA 結果 CSV", key="wfa_export"):
        try:
            win_path, stab_path = save_walk_forward_summary_csv(summary)
            st.success(f"已儲存：{win_path}，{stab_path}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"儲存失敗：{exc}")


# ---------------------------------------------------------------------------
# Shared input helper
# ---------------------------------------------------------------------------

def _input_symbol_and_dates(key_prefix: str) -> tuple[str, Any, Any]:
    today = pd.Timestamp.today().date()
    default_start = (pd.Timestamp.today() - pd.Timedelta(days=365 * 3)).date()
    symbol = st.text_input("股票代碼", value="2330", key=f"{key_prefix}_symbol").strip()
    d1, d2 = st.columns(2)
    with d1:
        start_date = st.date_input("開始日期", value=default_start, key=f"{key_prefix}_start")
    with d2:
        end_date = st.date_input("結束日期", value=today, key=f"{key_prefix}_end")
    return symbol, start_date, end_date


# ---------------------------------------------------------------------------
# Single backtest execution
# ---------------------------------------------------------------------------

def _run_backtest(
    *,
    symbol: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    engine_name: str,
    strategy_preset: dict[str, object],
) -> None:
    if not _TW_SYMBOL_PATTERN.fullmatch(symbol):
        st.error("股票代碼格式錯誤，請輸入 4 到 6 碼台股代碼。")
        return

    start_ts = _as_taipei_start(start_date)
    end_exclusive = _as_taipei_start(end_date) + pd.Timedelta(days=1)
    if end_exclusive <= start_ts:
        st.error("結束日期必須晚於開始日期。")
        return

    try:
        data = _load_backtest_data(
            symbol=symbol,
            start_ts=start_ts,
            end_exclusive=end_exclusive,
            require_adjusted=True,
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"讀取資料失敗：{exc}")
        return

    strategy_type = str(strategy_preset.get("type", "")).strip().lower()
    strategy_params = strategy_preset.get("params", {}) if isinstance(strategy_preset.get("params"), dict) else {}

    if data.empty and strategy_type != "dollar_cost_averaging":
        st.warning("資料區間內沒有可用日線資料。")
        return

    try:
        if strategy_type == "moving_average_cross":
            ma_short = int(strategy_params.get("short_window", 20))
            ma_long = int(strategy_params.get("long_window", 60))
            if ma_short >= ma_long:
                st.error("策略參數錯誤：short_window 必須小於 long_window。")
                return
            strategy = MACrossStrategy(ma_short=ma_short, ma_long=ma_long)
            _run_standard_backtest(strategy, data, engine_name, symbol, start_ts, end_exclusive, strategy_type, strategy_params)
            return

        if strategy_type == "dollar_cost_averaging":
            if engine_name != _VECTOR_ENGINE_LABEL:
                st.info("定期定額策略使用專用回測流程，已忽略回測引擎選擇。")
            dca_result = run_dca_backtest(
                data=data,
                symbol=symbol,
                start_ts=start_ts,
                end_exclusive=end_exclusive,
                params=strategy_params,
            )
            _render_dca_summary(dca_result)
            _render_dca_transactions(dca_result.transactions)
            trade_markers = _dca_transactions_to_trade_markers(dca_result.transactions)
            st.divider()
            _render_price_and_indicator_panel(
                price_df=data,
                trades=trade_markers,
                signals=None,
                symbol=symbol,
                strategy_type=strategy_type,
                strategy_params=strategy_params,
            )
            st.divider()
            _render_eps_panel(symbol=symbol, end_ts=end_exclusive - pd.Timedelta(days=1))
            return

        if strategy_type == "rsi":
            strategy = RSIStrategy(
                period=int(strategy_params.get("period", 14)),
                oversold=float(strategy_params.get("oversold", 30)),
                overbought=float(strategy_params.get("overbought", 70)),
            )
        elif strategy_type == "kd_cross":
            strategy = KDCrossStrategy(
                k_period=int(strategy_params.get("k_period", 9)),
                d_period=int(strategy_params.get("d_period", 3)),
                smooth_k=int(strategy_params.get("smooth_k", 3)),
            )
        elif strategy_type == "macd_cross":
            strategy = MACDCrossStrategy(
                fast=int(strategy_params.get("fast", 12)),
                slow=int(strategy_params.get("slow", 26)),
                signal=int(strategy_params.get("signal", 9)),
            )
        elif strategy_type == "bollinger_band":
            strategy = BollingerBandStrategy(
                period=int(strategy_params.get("period", 20)),
                std_dev=float(strategy_params.get("std_dev", 2.0)),
            )
        elif strategy_type == "bias":
            strategy = BiasStrategy(
                ma_period=int(strategy_params.get("ma_period", 20)),
                buy_bias=float(strategy_params.get("buy_bias", -10.0)),
                sell_bias=float(strategy_params.get("sell_bias", 10.0)),
            )
        elif strategy_type == "donchian_breakout":
            strategy = DonchianBreakoutStrategy(
                entry_period=int(strategy_params.get("entry_period", 20)),
                exit_period=int(strategy_params.get("exit_period", 10)),
            )
        else:
            st.error(f"目前不支援策略類型：{strategy_type}")
            return

        _run_standard_backtest(strategy, data, engine_name, symbol, start_ts, end_exclusive, strategy_type, strategy_params)

    except Exception as exc:  # noqa: BLE001
        st.error(f"回測執行失敗：{exc}")


def _run_standard_backtest(
    strategy: object,
    data: pd.DataFrame,
    engine_name: str,
    symbol: str,
    start_ts: pd.Timestamp,
    end_exclusive: pd.Timestamp,
    strategy_type: str = "",
    strategy_params: dict | None = None,
) -> None:
    engine = VectorizedBacktester() if engine_name == _VECTOR_ENGINE_LABEL else EventDrivenBacktester()
    result = engine.run(strategy=strategy, data=data)  # type: ignore[arg-type]

    _render_tearsheet_metrics(result)

    st.divider()
    _render_price_and_indicator_panel(
        price_df=data,
        trades=result.trades,
        signals=result.signals,
        symbol=symbol,
        strategy_type=strategy_type,
        strategy_params=strategy_params or {},
    )
    st.divider()
    _render_eps_panel(symbol=symbol, end_ts=end_exclusive - pd.Timedelta(days=1))


def _render_tearsheet_metrics(result: BacktestResult) -> None:
    report = TearsheetReport(result)
    figures = report.get_streamlit_figures()

    m0, m1, m2, m3, m4 = st.columns(5)
    m0.metric("交易次數", f"{int(result.total_trades)}")
    m1.metric("總報酬率", f"{result.total_return * 100:.2f}%")
    m2.metric("年化報酬率", f"{result.annual_return * 100:.2f}%")
    m3.metric("最大回撤", f"{result.max_drawdown * 100:.2f}%")
    m4.metric("Sharpe（夏普比率）", f"{result.sharpe_ratio:.2f}")

    config = get_config()
    ui_section = config.get("ui", {}) if isinstance(config, dict) else {}
    if bool(ui_section.get("use_extras", True)) and HAS_EXTRAS:
        from src.ui.themes import get_theme
        theme_name = str(ui_section.get("theme", "midnight_blue"))
        _, palette = get_theme(theme_name)
        style_metric_cards(
            background_color=palette["surface"],
            border_left_color=palette["primary"],
            border_color=palette["surface"],
        )

    st.plotly_chart(figures["equity"], width="stretch")
    st.plotly_chart(figures["drawdown"], width="stretch")
    st.plotly_chart(figures["monthly"], width="stretch")
    st.plotly_chart(figures["summary"], width="stretch")


# ---------------------------------------------------------------------------
# Price + indicator chart (7-B-4, 7-B-5, 7-B-6)
# ---------------------------------------------------------------------------

def _render_price_and_indicator_panel(
    *,
    price_df: pd.DataFrame,
    trades: pd.DataFrame,
    signals: pd.Series | None,
    symbol: str,
    strategy_type: str | None = None,
    strategy_params: dict | None = None,
) -> None:
    st.subheader("股價走勢、均線與成交點位")
    if price_df.empty:
        st.info("本區間沒有可顯示的股價資料。")
        return
    if go is None:
        st.warning("缺少 plotly，無法顯示圖表。")
        return

    params = strategy_params or {}
    features = _build_price_features(price_df)

    has_ohlc = all(c in price_df.columns for c in ("open", "high", "low", "close"))
    indicator_rows = _indicator_subplot_rows(strategy_type)
    n_rows = 1 + len(indicator_rows)
    row_heights = _compute_row_heights(n_rows)

    if n_rows > 1:
        subplot_titles = [""] + [r["title"] for r in indicator_rows]
        fig = make_subplots(
            rows=n_rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=row_heights,
            subplot_titles=subplot_titles,
        )
    else:
        fig = go.Figure()

    def _add(trace: go.BaseTraceType, row: int = 1) -> None:
        if n_rows > 1:
            fig.add_trace(trace, row=row, col=1)
        else:
            fig.add_trace(trace)

    # --- Main chart: candlestick or fallback line ---
    dates = features["date"]
    if has_ohlc:
        _add(go.Candlestick(
            x=dates,
            open=price_df["open"],
            high=price_df["high"],
            low=price_df["low"],
            close=price_df["close"],
            name="K線",
            increasing_line_color="#d62728",
            decreasing_line_color="#2ca02c",
            increasing_fillcolor="#d62728",
            decreasing_fillcolor="#2ca02c",
        ))
    else:
        _add(go.Scatter(x=dates, y=features["close"], mode="lines", name="收盤價",
                        line={"color": "#1f77b4", "width": 2}, hoverinfo="skip"))

    # MA lines
    _add(go.Scatter(x=dates, y=features["ma5"], mode="lines", name="週線 MA5",
                    line={"color": "#ff7f0e", "width": 1.4}, hoverinfo="skip"))
    _add(go.Scatter(x=dates, y=features["ma20"], mode="lines", name="月線 MA20",
                    line={"color": "#2ca02c", "width": 1.4}, hoverinfo="skip"))
    _add(go.Scatter(x=dates, y=features["ma60"], mode="lines", name="季線 MA60",
                    line={"color": "#9467bd", "width": 1.4}, hoverinfo="skip"))

    # Overlays for BB and Donchian on main chart
    if strategy_type == "bollinger_band" and HAS_PANDAS_TA:
        period = int(params.get("period", 20))
        std_dev = float(params.get("std_dev", 2.0))
        close = pd.to_numeric(price_df["close"], errors="coerce")
        bb = pandas_ta.bbands(close, length=period, std=std_dev)
        if bb is not None:
            upper_col = next((c for c in bb.columns if c.startswith("BBU_")), None)
            mid_col = next((c for c in bb.columns if c.startswith("BBM_")), None)
            lower_col = next((c for c in bb.columns if c.startswith("BBL_")), None)
            bb_dates = dates if len(bb) == len(dates) else dates.iloc[-len(bb):]
            if upper_col:
                _add(go.Scatter(x=bb_dates, y=bb[upper_col], mode="lines", name="BB上軌",
                                line={"color": "#aec7e8", "width": 1, "dash": "dot"}, hoverinfo="skip"))
            if mid_col:
                _add(go.Scatter(x=bb_dates, y=bb[mid_col], mode="lines", name="BB中軌",
                                line={"color": "#aec7e8", "width": 1}, hoverinfo="skip"))
            if lower_col:
                _add(go.Scatter(x=bb_dates, y=bb[lower_col], mode="lines", name="BB下軌",
                                line={"color": "#aec7e8", "width": 1, "dash": "dot"}, hoverinfo="skip"))

    elif strategy_type == "donchian_breakout":
        entry_period = int(params.get("entry_period", 20))
        exit_period = int(params.get("exit_period", 10))
        high = pd.to_numeric(price_df["high"], errors="coerce")
        low = pd.to_numeric(price_df["low"], errors="coerce")
        dc_upper = high.rolling(entry_period).max().shift(1)
        dc_lower = low.rolling(exit_period).min().shift(1)
        _add(go.Scatter(x=dates, y=dc_upper, mode="lines", name=f"DC上軌({entry_period})",
                        line={"color": "#17becf", "width": 1, "dash": "dot"}, hoverinfo="skip"))
        _add(go.Scatter(x=dates, y=dc_lower, mode="lines", name=f"DC下軌({exit_period})",
                        line={"color": "#bcbd22", "width": 1, "dash": "dot"}, hoverinfo="skip"))

    # Trade markers (7-B-5)
    buy_marks, sell_marks = _extract_trade_markers(trades=trades)
    _add_trade_marker_traces(fig=fig, marks=buy_marks, label="買進點", hover_title="買進",
                             color="#d62728", tip_symbol="triangle-up", stem_symbol="line-ns-open",
                             row=1, n_rows=n_rows)
    _add_trade_marker_traces(fig=fig, marks=sell_marks, label="賣出點", hover_title="賣出",
                             color="#17becf", tip_symbol="triangle-down", stem_symbol="line-ns-open",
                             row=1, n_rows=n_rows)

    # Signal markers (7-B-5) — only for vectorized engine
    if signals is not None:
        _add_signal_marker_traces(fig=fig, signals=signals, price_df=price_df, row=1, n_rows=n_rows)

    # Hover alignment frame on main chart
    hover_frame = _build_hover_alignment_frame(features)
    hover_trace = go.Scatter(
        x=hover_frame["calendar_date"],
        y=hover_frame["close"],
        mode="lines+markers",
        showlegend=False,
        name="",
        line={"width": 1, "color": "rgba(0,0,0,0.001)"},
        marker={"size": 8, "color": "rgba(0,0,0,0.001)"},
        customdata=hover_frame[["trade_date_text", "close_text", "ma5_text", "ma20_text", "ma60_text"]].to_numpy(),
        hovertemplate=(
            "日期: %{customdata[0]}<br>"
            "收盤價: %{customdata[1]}<br>"
            "週線 MA5: %{customdata[2]}<br>"
            "月線 MA20: %{customdata[3]}<br>"
            "季線 MA60: %{customdata[4]}<extra></extra>"
        ),
    )
    _add(hover_trace)

    # Indicator subplots (7-B-6)
    for subplot_idx, irow in enumerate(indicator_rows, start=2):
        _add_indicator_subplot(
            fig=fig,
            row=subplot_idx,
            n_rows=n_rows,
            price_df=price_df,
            strategy_type=strategy_type,
            params=params,
            irow_cfg=irow,
        )

    # Layout
    from src.ui.themes import get_theme
    config = get_config()
    ui_section = config.get("ui", {}) if isinstance(config, dict) else {}
    theme_name = str(ui_section.get("theme", "arctic_light"))
    _, palette = get_theme(theme_name)

    layout_kw: dict = dict(
        template=palette["plotly_template"],
        paper_bgcolor=palette["surface"],
        plot_bgcolor=palette["surface"],
        font={"color": palette["text"]},
        title=f"{symbol} 回測區間走勢",
        hovermode="x unified" if n_rows > 1 else "closest",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
    )
    if n_rows == 1:
        layout_kw["xaxis_title"] = "日期"
        layout_kw["yaxis_title"] = "價格"

    fig.update_layout(**layout_kw)

    # Hide rangeslider on all but last x-axis to keep layout tidy
    if n_rows > 1:
        fig.update_xaxes(rangeslider_visible=False)

    st.plotly_chart(fig, width="stretch")
    st.caption("K線：漲紅跌綠（台股慣例）。均線：MA5 / MA20 / MA60。Signal marker（菱形）為策略原始訊號，Trade marker（三角形）為引擎實際成交點。")


def _indicator_subplot_rows(strategy_type: str | None) -> list[dict]:
    """Return list of subplot row configs for the given strategy type."""
    if strategy_type == "rsi":
        return [{"title": "RSI", "kind": "rsi"}]
    if strategy_type == "kd_cross":
        return [{"title": "KD", "kind": "kd"}]
    if strategy_type == "macd_cross":
        return [{"title": "MACD", "kind": "macd"}]
    if strategy_type == "bias":
        return [{"title": "乖離率 BIAS", "kind": "bias"}]
    return []


def _compute_row_heights(n_rows: int) -> list[float]:
    if n_rows == 1:
        return [1.0]
    main = 0.65
    sub = (1.0 - main) / (n_rows - 1)
    return [main] + [sub] * (n_rows - 1)


def _add_indicator_subplot(
    *,
    fig: go.Figure,
    row: int,
    n_rows: int,
    price_df: pd.DataFrame,
    strategy_type: str | None,
    params: dict,
    irow_cfg: dict,
) -> None:
    if not HAS_PANDAS_TA:
        return

    kind = irow_cfg["kind"]
    close = pd.to_numeric(price_df["close"], errors="coerce")
    dates = pd.to_datetime(
        price_df["date"] if "date" in price_df.columns else price_df.index, errors="coerce"
    )

    def _add(trace: go.BaseTraceType) -> None:
        fig.add_trace(trace, row=row, col=1)

    if kind == "rsi":
        period = int(params.get("period", 14))
        rsi = pandas_ta.rsi(close, length=period)
        oversold = float(params.get("oversold", 30))
        overbought = float(params.get("overbought", 70))
        _add(go.Scatter(x=dates, y=rsi, mode="lines", name="RSI",
                        line={"color": "#1f77b4", "width": 1.5}))
        _add(go.Scatter(x=dates, y=[overbought] * len(dates), mode="lines", name=f"超買({overbought:.0f})",
                        line={"color": "#d62728", "width": 1, "dash": "dash"}, hoverinfo="skip"))
        _add(go.Scatter(x=dates, y=[oversold] * len(dates), mode="lines", name=f"超賣({oversold:.0f})",
                        line={"color": "#2ca02c", "width": 1, "dash": "dash"}, hoverinfo="skip",
                        fill="tonexty", fillcolor="rgba(44,160,44,0.05)"))

    elif kind == "kd":
        k_period = int(params.get("k_period", 9))
        d_period = int(params.get("d_period", 3))
        smooth_k = int(params.get("smooth_k", 3))
        high = pd.to_numeric(price_df["high"], errors="coerce")
        low = pd.to_numeric(price_df["low"], errors="coerce")
        stoch = pandas_ta.stoch(high=high, low=low, close=close,
                                k=k_period, d=d_period, smooth_k=smooth_k)
        if stoch is not None:
            k_col = next((c for c in stoch.columns if c.startswith("STOCHk_")), None)
            d_col = next((c for c in stoch.columns if c.startswith("STOCHd_")), None)
            if k_col:
                _add(go.Scatter(x=dates, y=stoch[k_col], mode="lines", name="K值",
                                line={"color": "#1f77b4", "width": 1.5}))
            if d_col:
                _add(go.Scatter(x=dates, y=stoch[d_col], mode="lines", name="D值",
                                line={"color": "#ff7f0e", "width": 1.5}))

    elif kind == "macd":
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        signal_p = int(params.get("signal", 9))
        macd_df = pandas_ta.macd(close, fast=fast, slow=slow, signal=signal_p)
        if macd_df is not None:
            macd_col = next((c for c in macd_df.columns if c.startswith("MACD_")), None)
            sig_col = next((c for c in macd_df.columns if c.startswith("MACDs_")), None)
            hist_col = next((c for c in macd_df.columns if c.startswith("MACDh_")), None)
            if hist_col:
                hist = macd_df[hist_col]
                bar_colors = ["#d62728" if v >= 0 else "#2ca02c" for v in hist.fillna(0)]
                _add(go.Bar(x=dates, y=hist, name="Histogram", marker_color=bar_colors,
                            opacity=0.6, showlegend=True))
            if macd_col:
                _add(go.Scatter(x=dates, y=macd_df[macd_col], mode="lines", name="MACD",
                                line={"color": "#1f77b4", "width": 1.5}))
            if sig_col:
                _add(go.Scatter(x=dates, y=macd_df[sig_col], mode="lines", name="Signal",
                                line={"color": "#ff7f0e", "width": 1.5}))

    elif kind == "bias":
        ma_period = int(params.get("ma_period", 20))
        ma = close.rolling(ma_period, min_periods=ma_period).mean()
        bias = (close - ma) / ma * 100
        buy_bias = float(params.get("buy_bias", -10.0))
        sell_bias = float(params.get("sell_bias", 10.0))
        _add(go.Scatter(x=dates, y=bias, mode="lines", name="BIAS",
                        line={"color": "#1f77b4", "width": 1.5}))
        _add(go.Scatter(x=dates, y=[sell_bias] * len(dates), mode="lines",
                        name=f"賣出門檻({sell_bias:.1f}%)",
                        line={"color": "#d62728", "width": 1, "dash": "dash"}, hoverinfo="skip"))
        _add(go.Scatter(x=dates, y=[buy_bias] * len(dates), mode="lines",
                        name=f"買進門檻({buy_bias:.1f}%)",
                        line={"color": "#2ca02c", "width": 1, "dash": "dash"}, hoverinfo="skip"))


def _add_signal_marker_traces(
    *,
    fig: go.Figure,
    signals: pd.Series,
    price_df: pd.DataFrame,
    row: int,
    n_rows: int,
) -> None:
    """Add semi-transparent diamond markers for raw strategy signals."""
    price_indexed = price_df.copy()
    if "date" in price_indexed.columns:
        price_indexed = price_indexed.set_index(pd.to_datetime(price_indexed["date"], errors="coerce"))
    close_map = price_indexed["close"].to_dict()

    sig_index = pd.to_datetime(signals.index, errors="coerce")
    buy_dates = sig_index[signals.values == 1]
    sell_dates = sig_index[signals.values == -1]

    def _prices(dates: pd.DatetimeIndex) -> list[float]:
        return [float(close_map.get(d, float("nan"))) for d in dates]

    def _add(trace: go.BaseTraceType) -> None:
        if n_rows > 1:
            fig.add_trace(trace, row=row, col=1)
        else:
            fig.add_trace(trace)

    if len(buy_dates):
        _add(go.Scatter(
            x=buy_dates, y=_prices(buy_dates),
            mode="markers", name="買進訊號",
            marker={"symbol": "diamond", "size": 9, "color": "rgba(214,39,40,0.4)",
                    "line": {"width": 1, "color": "rgba(214,39,40,0.7)"}},
            hovertemplate="買進訊號: %{x|%Y-%m-%d}<br>收盤: %{y:.2f}<extra></extra>",
        ))
    if len(sell_dates):
        _add(go.Scatter(
            x=sell_dates, y=_prices(sell_dates),
            mode="markers", name="賣出訊號",
            marker={"symbol": "diamond", "size": 9, "color": "rgba(23,190,207,0.4)",
                    "line": {"width": 1, "color": "rgba(23,190,207,0.7)"}},
            hovertemplate="賣出訊號: %{x|%Y-%m-%d}<br>收盤: %{y:.2f}<extra></extra>",
        ))


# ---------------------------------------------------------------------------
# DCA helpers (unchanged)
# ---------------------------------------------------------------------------

def _render_dca_summary(result: DcaBacktestResult) -> None:
    st.subheader("定期定額回測摘要")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("累積投入金額", f"{result.cumulative_invested:,.2f}")
    c2.metric("目前市值", f"{result.market_value:,.2f}")
    c3.metric("帳戶現金", f"{result.cash_balance:,.2f}")
    c4.metric("未實現損益", f"{result.unrealized_pnl:,.2f}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("總報酬率", f"{result.total_return_rate * 100:.2f}%")
    c6.metric("累積買入股數", f"{result.cumulative_shares:,}")
    c7.metric("平均成本", f"{result.average_cost:,.4f}")
    c8.metric("投入次數", f"{result.contribution_count}")

    config = get_config()
    ui_section = config.get("ui", {}) if isinstance(config, dict) else {}
    if bool(ui_section.get("use_extras", True)) and HAS_EXTRAS:
        from src.ui.themes import get_theme
        theme_name = str(ui_section.get("theme", "midnight_blue"))
        _, palette = get_theme(theme_name)
        style_metric_cards(
            background_color=palette["surface"],
            border_left_color=palette["primary"],
            border_color=palette["surface"],
        )


def _render_dca_transactions(transactions: pd.DataFrame) -> None:
    st.subheader("定期定額交易紀錄")
    if transactions is None or transactions.empty:
        st.info("尚無定期定額交易紀錄。")
        return

    reason_labels = {
        "": "",
        "NO_TRADING_DATES": "無交易日資料",
        "NO_TRADING_DAY_UNTIL_MONTH_END": "指定日後至月底無交易日",
        "NO_TRADING_DAY_AFTER_MONTH_END": "月底後無可順延交易日",
        "BUY_DATE_PRICE_MISSING": "買入日價格缺失",
        "INVALID_BUY_PRICE": "買入價無效",
        "INSUFFICIENT_FOR_MIN_BUY_UNIT": "投入金額不足買入最小單位",
    }

    view = transactions.copy()
    view["date"] = pd.to_datetime(view["date"], errors="coerce")
    view["reason"] = view["reason"].map(lambda v: reason_labels.get(str(v), str(v)))
    view["status"] = view["status"].map(lambda v: "成功" if str(v).upper() == "FILLED" else "略過")

    display = pd.DataFrame({
        "日期": view["date"].dt.strftime("%Y-%m-%d"),
        "狀態": view["status"],
        "原因": view["reason"],
        "投入金額": view["invested_amount"],
        "買入價格": view["buy_price"],
        "買入股數": view["buy_shares"],
        "手續費": view["commission"],
        "實際花費": view["spend"],
        "剩餘現金": view["cash_balance"],
        "累積股數": view["cumulative_shares"],
        "累積投入": view["cumulative_invested"],
        "平均成本": view["average_cost"],
    })
    st.dataframe(display, width="stretch", hide_index=True)


def _dca_transactions_to_trade_markers(transactions: pd.DataFrame) -> pd.DataFrame:
    if transactions is None or transactions.empty:
        return pd.DataFrame(columns=["entry_date", "entry_price", "quantity", "exit_date", "exit_price"])

    filled = transactions.copy()
    filled["status"] = filled["status"].astype(str).str.upper()
    filled = filled[(filled["status"] == "FILLED") & (pd.to_numeric(filled["buy_shares"], errors="coerce") > 0)].copy()
    if filled.empty:
        return pd.DataFrame(columns=["entry_date", "entry_price", "quantity", "exit_date", "exit_price"])

    return pd.DataFrame({
        "entry_date": pd.to_datetime(filled["date"], errors="coerce"),
        "entry_price": pd.to_numeric(filled["buy_price"], errors="coerce"),
        "quantity": pd.to_numeric(filled["buy_shares"], errors="coerce"),
        "exit_date": pd.NaT,
        "exit_price": float("nan"),
    })


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_backtest_data(
    *,
    symbol: str,
    start_ts: pd.Timestamp,
    end_exclusive: pd.Timestamp,
    require_adjusted: bool = True,
) -> pd.DataFrame:
    storage = ParquetStorage()
    df = storage.load_adjusted(symbol)
    if df.empty and require_adjusted:
        raise FetcherError(
            f"{symbol} adjusted data is missing. Please run rebuild_adj_factors (or rebuild_symbol) before backtest."
        )
    if df.empty:
        df = storage.load_daily(symbol)
    if df.empty:
        return df

    data = df.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).copy()
    if data["date"].dt.tz is None:
        data["date"] = data["date"].dt.tz_localize(TAIPEI_TZ)
    else:
        data["date"] = data["date"].dt.tz_convert(TAIPEI_TZ)

    for col in ("open", "high", "low", "close"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=["open", "high", "low", "close"])
    data = data[(data["date"] >= start_ts) & (data["date"] < end_exclusive)].copy()
    return data.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _build_price_features(price_df: pd.DataFrame) -> pd.DataFrame:
    out = price_df[["date", "close"]].copy()
    out = out.sort_values("date").reset_index(drop=True)
    out["ma5"] = out["close"].rolling(window=5).mean()
    out["ma20"] = out["close"].rolling(window=20).mean()
    out["ma60"] = out["close"].rolling(window=60).mean()
    return out


def _extract_trade_markers(*, trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if trades is None or trades.empty:
        empty = pd.DataFrame(columns=["date", "price", "quantity"])
        return empty, empty

    buys = pd.DataFrame({
        "date": pd.to_datetime(trades.get("entry_date"), errors="coerce"),
        "price": pd.to_numeric(trades.get("entry_price"), errors="coerce"),
        "quantity": pd.to_numeric(trades.get("quantity"), errors="coerce"),
    }).dropna(subset=["date", "price"])

    sells = pd.DataFrame({
        "date": pd.to_datetime(trades.get("exit_date"), errors="coerce"),
        "price": pd.to_numeric(trades.get("exit_price"), errors="coerce"),
        "quantity": pd.to_numeric(trades.get("quantity"), errors="coerce"),
    }).dropna(subset=["date", "price"])

    return buys.sort_values("date"), sells.sort_values("date")


def _add_trade_marker_traces(
    *,
    fig: go.Figure,
    marks: pd.DataFrame,
    label: str,
    hover_title: str,
    color: str,
    tip_symbol: str,
    stem_symbol: str,
    row: int,
    n_rows: int,
) -> None:
    if marks.empty:
        return

    enriched = marks.copy()
    enriched["quantity_text"] = enriched.get("quantity", pd.Series(dtype="float64")).map(_format_quantity_value)

    def _add(trace: go.BaseTraceType) -> None:
        if n_rows > 1:
            fig.add_trace(trace, row=row, col=1)
        else:
            fig.add_trace(trace)

    _add(go.Scatter(
        x=enriched["date"], y=enriched["price"], mode="markers",
        showlegend=False, legendgroup=label,
        marker={"symbol": "circle", "size": max(_TRADE_MARKER_STEM_SIZE, 24), "color": "rgba(0,0,0,0)"},
        customdata=enriched[["quantity_text"]].to_numpy(),
        hovertemplate=(
            f"{hover_title}: %{{x|%Y-%m-%d}}<br>"
            "成交價: %{y:.2f}<br>"
            "數量: %{customdata[0]}<extra></extra>"
        ),
    ))
    _add(go.Scatter(
        x=enriched["date"], y=enriched["price"], mode="markers",
        showlegend=False, legendgroup=label,
        marker={"symbol": stem_symbol, "size": _TRADE_MARKER_STEM_SIZE, "color": color, "line": {"width": 1}},
        hoverinfo="skip",
    ))
    _add(go.Scatter(
        x=enriched["date"], y=enriched["price"], mode="markers",
        name=label, legendgroup=label,
        marker={"symbol": tip_symbol, "size": _TRADE_MARKER_BASE_SIZE, "color": color},
        hoverinfo="skip",
    ))


def _build_hover_alignment_frame(price_df: pd.DataFrame) -> pd.DataFrame:
    if price_df.empty:
        return pd.DataFrame(columns=[
            "calendar_date", "trade_date_text", "close", "close_text",
            "ma5_text", "ma20_text", "ma60_text",
        ])

    trading_dates = pd.DatetimeIndex(price_df["date"])
    calendar_dates = pd.date_range(
        start=trading_dates.min().normalize(),
        end=trading_dates.max().normalize(),
        freq="D",
        tz=trading_dates.tz,
    )
    nearest_idx = _nearest_trading_indices(calendar_dates, trading_dates)
    aligned = price_df.iloc[nearest_idx].reset_index(drop=True)

    return pd.DataFrame({
        "calendar_date": calendar_dates,
        "trade_date_text": aligned["date"].dt.strftime("%Y-%m-%d"),
        "close": aligned["close"],
        "close_text": aligned["close"].map(_format_price_value),
        "ma5_text": aligned["ma5"].map(_format_price_value),
        "ma20_text": aligned["ma20"].map(_format_price_value),
        "ma60_text": aligned["ma60"].map(_format_price_value),
    })


def _nearest_trading_indices(target_dates: pd.DatetimeIndex, trading_dates: pd.DatetimeIndex) -> np.ndarray:
    if len(trading_dates) == 0:
        return np.array([], dtype="int64")

    targets = _to_utc_index(target_dates)
    trades = _to_utc_index(trading_dates)

    trade_ns = trades.asi8
    target_ns = targets.asi8
    insert_pos = np.searchsorted(trade_ns, target_ns, side="left")

    prev_idx = np.clip(insert_pos - 1, 0, len(trade_ns) - 1)
    next_idx = np.clip(insert_pos, 0, len(trade_ns) - 1)

    chosen = prev_idx.copy()
    no_prev = insert_pos == 0
    chosen[no_prev] = next_idx[no_prev]

    between = (insert_pos > 0) & (insert_pos < len(trade_ns))
    if np.any(between):
        prev_dist = np.abs(target_ns[between] - trade_ns[prev_idx[between]])
        next_dist = np.abs(trade_ns[next_idx[between]] - target_ns[between])
        use_next = next_dist <= prev_dist
        chosen[between] = np.where(use_next, next_idx[between], prev_idx[between])

    return chosen.astype("int64")


def _to_utc_index(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if index.tz is None:
        return index.tz_localize(TAIPEI_TZ).tz_convert("UTC")
    return index.tz_convert("UTC")


# ---------------------------------------------------------------------------
# EPS panel (unchanged)
# ---------------------------------------------------------------------------

def _render_eps_panel(*, symbol: str, end_ts: pd.Timestamp) -> None:
    st.subheader("近 15 年 EPS 紀錄")
    end_year = pd.Timestamp(end_ts).year
    start_year = end_year - 14

    try:
        fetcher = FinMindFetcher()
        eps_df = fetcher.fetch_eps(symbol=symbol, start_date=f"{start_year}-01-01")
    except FetcherError as exc:
        st.info(f"EPS 資料暫時無法取得：{exc}")
        return
    except Exception as exc:  # noqa: BLE001
        st.warning(f"EPS 資料讀取失敗：{exc}")
        return

    display = _build_eps_display_table(eps_df=eps_df, end_year=end_year)
    if display.empty:
        st.info("此股票在近 15 年範圍內沒有可用 EPS 資料。")
        return

    st.dataframe(display, width="stretch", hide_index=True)
    st.caption("年度 EPS 為已取得季度 EPS 加總，不補值、不推估。")


def _build_eps_display_table(*, eps_df: pd.DataFrame, end_year: int) -> pd.DataFrame:
    if eps_df is None or eps_df.empty:
        return pd.DataFrame(columns=["年度", "Q1 EPS", "Q2 EPS", "Q3 EPS", "Q4 EPS", "年度 EPS"])

    work = eps_df.copy()
    work["year"] = pd.to_numeric(work.get("year"), errors="coerce")
    work["quarter"] = pd.to_numeric(work.get("quarter"), errors="coerce")
    work["eps"] = pd.to_numeric(work.get("eps"), errors="coerce")
    work = work.dropna(subset=["year", "quarter", "eps"])
    if work.empty:
        return pd.DataFrame(columns=["年度", "Q1 EPS", "Q2 EPS", "Q3 EPS", "Q4 EPS", "年度 EPS"])

    work["year"] = work["year"].astype("int64")
    work["quarter"] = work["quarter"].astype("int64")
    work = work[work["quarter"].between(1, 4)].copy()
    work = work[work["year"].between(end_year - 14, end_year)].copy()
    if work.empty:
        return pd.DataFrame(columns=["年度", "Q1 EPS", "Q2 EPS", "Q3 EPS", "Q4 EPS", "年度 EPS"])

    pivot = work.pivot_table(index="year", columns="quarter", values="eps", aggfunc="last")
    pivot = pivot.reindex(columns=[1, 2, 3, 4]).sort_index(ascending=False)
    annual = pivot.sum(axis=1, min_count=1)

    return pd.DataFrame({
        "年度": pivot.index.astype("int64"),
        "Q1 EPS": pivot[1].map(_format_eps_value),
        "Q2 EPS": pivot[2].map(_format_eps_value),
        "Q3 EPS": pivot[3].map(_format_eps_value),
        "Q4 EPS": pivot[4].map(_format_eps_value),
        "年度 EPS": annual.map(_format_eps_value),
    }).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_price_value(value: float) -> str:
    if pd.isna(value):
        return "尚無資料"
    return f"{float(value):.2f}"


def _format_quantity_value(value: float) -> str:
    if pd.isna(value):
        return "尚無資料"
    return f"{int(round(float(value))):,} 股"


def _format_eps_value(value: float) -> str:
    if pd.isna(value):
        return "尚無資料"
    return f"{float(value):.2f}"


def _as_taipei_start(value: pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value).normalize()
    if ts.tzinfo is None:
        return ts.tz_localize(TAIPEI_TZ)
    return ts.tz_convert(TAIPEI_TZ)


if __name__ == "__main__":
    render()
