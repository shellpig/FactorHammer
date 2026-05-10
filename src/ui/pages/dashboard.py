"""Stock dashboard page (Phase 8-F)."""

from __future__ import annotations

from dataclasses import asdict
import re
from typing import Any

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
except ModuleNotFoundError:  # pragma: no cover
    go = None

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
from src.data.realtime import BidAskStructure, RealtimeFetcher, RealtimeQuote
from src.data.storage import ParquetStorage
from src.ui.themes import get_theme

_TW_SYMBOL_PATTERN = re.compile(r"^[0-9A-Z]{4,6}$")
_STATE_KEY = "dashboard_payload"


def render() -> None:
    render_dashboard_page()


def render_dashboard_page() -> None:
    """Render stock dashboard page."""
    st.title("個股分析")
    st.caption("整合技術面、籌碼、型態與 AI 劇本的個股儀表板。")

    symbol = st.text_input("股票代碼", value="", key="dashboard_symbol").strip().upper()
    analyze_clicked = st.button("分析", type="primary", key="dashboard_analyze")

    if not symbol:
        st.info("請先輸入股票代碼。")
        return
    if not _TW_SYMBOL_PATTERN.fullmatch(symbol):
        st.warning("股票代碼格式錯誤，請輸入 4~6 位英數台股代碼。")
        return

    if analyze_clicked:
        payload = _build_dashboard_payload(symbol)
        st.session_state[_STATE_KEY] = payload

    payload = st.session_state.get(_STATE_KEY)
    if not payload or payload.get("symbol") != symbol:
        st.info("輸入股票代碼後，點選「分析」。")
        return

    is_ready = bool(payload.get("ready", "technical" in payload))
    if not is_ready:
        st.warning(str(payload.get("error", "個股分析資料尚未準備完成。")))
        return

    tabs = st.tabs(["總覽", "籌碼與量價", "型態與週期", "AI 劇本"])
    with tabs[0]:
        refresh_clicked = _render_tab_overview(
            quote=payload.get("quote"),
            technical=payload["technical"],
            df=payload["daily_df"],
        )
    with tabs[1]:
        _render_tab_chip(
            chip=payload.get("chip"),
            bid_ask=payload.get("bid_ask"),
            technical=payload["technical"],
        )
    with tabs[2]:
        _render_tab_pattern(
            candle_patterns=payload["candle_patterns"],
            chart_patterns=payload["chart_patterns"],
            mtf=payload["multi_timeframe"],
        )
    with tabs[3]:
        _render_tab_ai(
            analysis=payload.get("analysis"),
            technical=payload["technical"],
            ai_enabled=payload["ai_enabled"],
        )

    if refresh_clicked:
        refreshed_quote, refreshed_bid_ask, refresh_error = _refresh_realtime_snapshot(symbol)
        if refreshed_quote is not None:
            payload["quote"] = refreshed_quote
        if refreshed_bid_ask is not None:
            payload["bid_ask"] = refreshed_bid_ask
        st.session_state[_STATE_KEY] = payload
        if refresh_error:
            st.warning(refresh_error)
        st.rerun()


def _build_dashboard_payload(symbol: str) -> dict[str, Any]:
    storage = ParquetStorage()
    daily = storage.load_daily(symbol)
    if daily.empty:
        return {
            "symbol": symbol,
            "ready": False,
            "error": f"{symbol} 尚無本機日線資料，請先到「資料管理」更新。",
        }

    daily = _normalize_daily_df(daily)
    technical = generate_technical_summary(daily)

    quote: RealtimeQuote | None = None
    bid_ask: BidAskStructure | None = None
    try:
        realtime = RealtimeFetcher.from_config()
        quote = realtime.fetch_quote(symbol)
        bid_ask = realtime.fetch_bid_ask_structure(quote)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"即時行情暫時不可用，已改用日線資料顯示：{exc}")

    chip: ChipSummary | None = None
    try:
        institutional_df = storage.load_institutional(symbol)
        margin_df = storage.load_margin(symbol)
        if not institutional_df.empty or not margin_df.empty:
            chip = generate_chip_summary(institutional_df, margin_df, n_days=5)
    except Exception as exc:  # noqa: BLE001
        st.info(f"籌碼資料尚未載入：{exc}")

    candle_patterns = detect_candle_patterns(daily)
    chart_patterns = detect_chart_pattern(daily)
    multi_timeframe = analyze_multi_timeframe(daily.set_index("date"))

    config = get_config()
    ai_section = config.get("ai", {}) if isinstance(config, dict) else {}
    ai_enabled = bool(ai_section.get("enabled", False))
    analysis: DashboardAnalysis | None = None
    if ai_enabled:
        try:
            advisor = AIAdvisor()
            analysis = advisor.generate_stock_dashboard_analysis(
                symbol=symbol,
                technical_summary=technical,
                chip_summary=chip,
                company_info=None,
                recent_prices=daily.tail(60),
            )
        except AIDisabledError:
            analysis = None
        except AICallError as exc:
            st.warning(f"AI 劇本生成失敗：{exc}")
        except Exception as exc:  # noqa: BLE001
            st.warning(f"AI 劇本生成失敗：{exc}")

    return {
        "symbol": symbol,
        "ready": True,
        "error": None,
        "daily_df": daily,
        "technical": technical,
        "quote": quote,
        "bid_ask": bid_ask,
        "chip": chip,
        "candle_patterns": candle_patterns,
        "chart_patterns": chart_patterns,
        "multi_timeframe": multi_timeframe,
        "analysis": analysis,
        "ai_enabled": ai_enabled,
    }


def _normalize_daily_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for col in ("open", "high", "low", "close", "volume"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close", "volume"])
    return out.reset_index(drop=True)


def _render_tab_overview(
    quote: RealtimeQuote | None,
    technical: TechnicalSummary,
    df: pd.DataFrame,
) -> bool:
    st.subheader("行情總覽")
    if quote is not None:
        bid_ask_text = "盤中資料" if quote.is_market_open else "盤後資料"
        cols = st.columns(5)
        cols[0].metric("即時價", f"{quote.price:.2f}")
        cols[1].metric("漲跌", f"{quote.change:+.2f}")
        cols[2].metric("漲跌幅", f"{quote.change_pct:+.2f}%")
        cols[3].metric("成交量(張)", f"{quote.volume:,}")
        cols[4].metric("狀態", bid_ask_text)
    else:
        st.info("目前未取得即時報價，以下以日線資料顯示。")

    _render_price_chart(df, technical)

    st.markdown("**技術分析總覽**")
    row1 = st.columns(3)
    row1[0].metric("趨勢方向", technical.trend_direction)
    row1[1].metric("均線狀態", technical.ma_status)
    row1[2].metric("KD 狀態", technical.kd_status)
    row2 = st.columns(3)
    row2[0].metric("MACD 狀態", technical.macd_status)
    row2[1].metric("量能狀態", technical.volume_status)
    row2[2].metric("量價關係", technical.volume_price_relation)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**壓力區**")
        if technical.resistance_levels:
            for lvl in technical.resistance_levels:
                st.write(f"- {lvl.label}: {lvl.value:.2f}")
        else:
            st.write("- 尚無資料")
    with c2:
        st.markdown("**支撐區**")
        if technical.support_levels:
            for lvl in technical.support_levels:
                st.write(f"- {lvl.label}: {lvl.value:.2f}")
        else:
            st.write("- 尚無資料")

    st.markdown("**短線綜合分數**")
    score_pct = max(0.0, min(1.0, float(technical.short_term_score)))
    st.progress(score_pct, text=f"{technical.short_term_label}（{score_pct * 100:.1f}%）")
    refresh_clicked = st.button("重新整理報價", key="dashboard_refresh_quote", help="重新查詢即時報價")
    return bool(refresh_clicked)


def _refresh_realtime_snapshot(symbol: str) -> tuple[RealtimeQuote | None, BidAskStructure | None, str | None]:
    try:
        realtime = RealtimeFetcher.from_config()
        quote = realtime.fetch_quote(symbol)
        bid_ask = realtime.fetch_bid_ask_structure(quote)
        return quote, bid_ask, None
    except Exception as exc:  # noqa: BLE001
        return None, None, f"即時報價更新失敗：{exc}"


def _render_price_chart(df: pd.DataFrame, technical: TechnicalSummary) -> None:
    if go is None or df.empty:
        return
    config = get_config()
    ui = config.get("ui", {}) if isinstance(config, dict) else {}
    theme_name = str(ui.get("theme", "midnight_blue"))
    _, palette = get_theme(theme_name)

    chart_df = df.copy()
    chart_df["ma5"] = chart_df["close"].rolling(5).mean()
    chart_df["ma20"] = chart_df["close"].rolling(20).mean()
    chart_df["ma60"] = chart_df["close"].rolling(60).mean()
    chart_df = chart_df.tail(120).reset_index(drop=True)

    price_min = float(chart_df["low"].min())
    price_max = float(chart_df["high"].max())
    y_padding = (price_max - price_min) * 0.05

    dates = chart_df["date"]

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=chart_df["open"],
            high=chart_df["high"],
            low=chart_df["low"],
            close=chart_df["close"],
            name="日K",
            increasing_line_color="#ef4444",
            increasing_fillcolor="#ef4444",
            decreasing_line_color="#22c55e",
            decreasing_fillcolor="#22c55e",
        )
    )
    fig.add_trace(go.Scatter(x=dates, y=chart_df["ma5"], mode="lines", name="MA5", line={"width": 1}))
    fig.add_trace(go.Scatter(x=dates, y=chart_df["ma20"], mode="lines", name="MA20", line={"width": 1}))
    fig.add_trace(go.Scatter(x=dates, y=chart_df["ma60"], mode="lines", name="MA60", line={"width": 1}))

    seg_x0 = dates.iloc[max(0, len(dates) - 20)]
    seg_x1 = dates.iloc[-1]
    for level in technical.resistance_levels:
        y = float(level.value)
        fig.add_shape(type="line", x0=seg_x0, x1=seg_x1, y0=y, y1=y, xref="x", yref="y",
                      line={"dash": "dot", "color": "#ef4444", "width": 1})
        fig.add_annotation(x=seg_x1, y=y, xref="x", yref="y", text=f" 壓 {y:.1f}",
                           showarrow=False, font={"size": 10, "color": "#ef4444"}, xanchor="left")
    for level in technical.support_levels:
        y = float(level.value)
        fig.add_shape(type="line", x0=seg_x0, x1=seg_x1, y0=y, y1=y, xref="x", yref="y",
                      line={"dash": "dot", "color": "#22c55e", "width": 1})
        fig.add_annotation(x=seg_x1, y=y, xref="x", yref="y", text=f" 撐 {y:.1f}",
                           showarrow=False, font={"size": 10, "color": "#22c55e"}, xanchor="left")

    fig.update_layout(
        template=palette["plotly_template"],
        title="日K + 均線 + 支撐壓力",
        xaxis_title="日期",
        xaxis_rangeslider={"visible": True, "thickness": 0.04},
        xaxis_rangebreaks=[{"bounds": ["sat", "mon"]}],
        yaxis_title="價格",
        yaxis_autorange=True,
        yaxis_fixedrange=True,
        font={"color": palette["text"]},
        height=650,
        dragmode="pan",
    )
    st.plotly_chart(fig, width="stretch")


def _render_tab_chip(
    chip: ChipSummary | None,
    bid_ask: BidAskStructure | None,
    technical: TechnicalSummary,
) -> None:
    st.subheader("籌碼與量價")
    if chip is None:
        st.info("尚未載入籌碼資料")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("外資近N日", chip.foreign_label)
        c2.metric("投信近N日", chip.trust_label)
        c3.metric("自營商近N日", chip.dealer_label)
        st.write(f"籌碼集中度：{chip.chip_concentration} / 趨勢：{chip.chip_trend}")
        st.caption(chip.chip_description)
        c4, c5 = st.columns(2)
        c4.metric("融資餘額變化(張)", f"{chip.margin_balance_change:+d}")
        c5.metric("融券餘額變化(張)", f"{chip.short_balance_change:+d}")

    if bid_ask is not None:
        st.metric("買賣力道估算", bid_ask.label)
        st.caption(f"買方佔比 {bid_ask.bid_ratio:.2%} / 賣方佔比 {bid_ask.ask_ratio:.2%}")
    else:
        st.info("尚未取得五檔買賣量，買賣力道暫不可用。")

    st.markdown("**量價結構分析**")
    st.write(technical.volume_price_divergence or "資料不足")
    st.write(technical.ma_bias or "資料不足")
    st.write(technical.operation_observation or "資料不足")


def _render_tab_pattern(
    candle_patterns: list[CandlePattern],
    chart_patterns: list[ChartPatternResult],
    mtf: MultiTimeframeAnalysis,
) -> None:
    st.subheader("型態與週期")
    detected = [p for p in candle_patterns if p.detected]
    not_detected = [p for p in candle_patterns if not p.detected]
    if detected:
        st.markdown("**偵測到的型態：**")
        for p in detected:
            st.success(f"**{p.name}** — {p.description}")
    if not_detected:
        with st.expander("未偵測到的型態", expanded=False):
            rows = [{"型態": p.name, "說明": p.description} for p in not_detected]
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    for pattern in chart_patterns:
        if pattern.formed:
            st.success(f"{pattern.pattern_type}：{pattern.description}")
            if pattern.key_points:
                st.caption(", ".join(f"{name}={value:.2f}" for name, value in pattern.key_points if name != "索引區間"))
        else:
            st.info(f"{pattern.pattern_type}：{pattern.description}")

    c1, c2, c3 = st.columns(3)
    c1.metric("日線", f"{mtf.daily.trend_direction} / {mtf.daily.strength}")
    c2.metric("週線", f"{mtf.weekly.trend_direction} / {mtf.weekly.strength}")
    c3.metric("月線", f"{mtf.monthly.trend_direction} / {mtf.monthly.strength}")


def _render_tab_ai(
    analysis: DashboardAnalysis | None,
    technical: TechnicalSummary,
    ai_enabled: bool,
) -> None:
    st.subheader("AI 劇本")
    if not ai_enabled or analysis is None:
        st.info("請啟用 AI 功能")
        st.write(technical.operation_observation or "目前無可用的 rule-based 結論。")
        return

    st.markdown("**產業概況**")
    for item in analysis.industry_overview:
        st.write(f"- {item}")
    st.markdown("**公司概況**")
    for item in analysis.company_overview:
        st.write(f"- {item}")

    st.markdown("**量價分析**")
    st.write(analysis.volume_price_analysis)

    st.markdown("**三情境操作劇本**")
    scenario_rows = [asdict(item) for item in analysis.scenarios]
    st.dataframe(pd.DataFrame(scenario_rows), width="stretch", hide_index=True)

    st.markdown("**整體結論**")
    st.success(analysis.conclusion)
    st.caption("非投資建議，僅供研究與風險控管參考。")


if __name__ == "__main__":
    render_dashboard_page()
