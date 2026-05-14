from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.analysis.chip_analysis import ChipSummary
from src.analysis.pattern import CandlePattern, ChartPatternResult
from src.analysis.technical_summary import PriceLevel, TechnicalSummary
from src.analysis.pattern import MultiTimeframeAnalysis, TimeframeTrend
from src.data.storage import ParquetStorage
from src.data.realtime import BidAskStructure, RealtimeQuote
from src.ui.pages.dashboard import (
    _HELP_TEXTS,
    _PATTERN_DETAILS,
    _build_technical_metric_details,
    _build_recent_institutional_table,
    _build_dashboard_payload,
    _prepare_chip_data_for_dashboard,
    _render_price_chart,
    _render_tab_ai,
    _render_tab_chip,
    _render_tab_overview,
    _render_tab_pattern,
    _style_recent_institutional_table,
    render_dashboard_page,
)


class _DummyCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False

    def metric(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def write(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def caption(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None


class _DummySt:
    def __init__(self, *, symbol: str = "", analyze_clicked: bool = False, button_map: dict[str, bool] | None = None):
        self._symbol = symbol
        self._analyze_clicked = analyze_clicked
        self._button_map = button_map or {}
        self.session_state: dict[str, object] = {}
        self.info_messages: list[str] = []
        self.warning_messages: list[str] = []
        self.caption_messages: list[str] = []
        self.tabs_called_count = 0
        self.rerun_called_count = 0

    def title(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def caption(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        if args:
            self.caption_messages.append(str(args[0]))
        return None

    def text_input(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        return self._symbol

    def form(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return _DummyCtx()

    def form_submit_button(self, *args, **kwargs) -> bool:  # noqa: ANN002, ANN003
        key = str(kwargs.get("key", ""))
        if key in self._button_map:
            return bool(self._button_map[key])
        return self._analyze_clicked

    def button(self, *args, **kwargs) -> bool:  # noqa: ANN002, ANN003
        key = str(kwargs.get("key", ""))
        if key in self._button_map:
            return bool(self._button_map[key])
        return self._analyze_clicked

    def selectbox(self, *args, **kwargs):  # noqa: ANN002, ANN003
        options = kwargs.get("options")
        index = int(kwargs.get("index", 0))
        if isinstance(options, (list, tuple)) and options:
            return options[index]
        return None

    def info(self, message: str, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.info_messages.append(message)

    def warning(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        if args:
            self.warning_messages.append(str(args[0]))
        return None

    def subheader(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def columns(self, n: int | list[int], *args, **kwargs):  # noqa: ANN002, ANN003
        if isinstance(n, list):
            count = len(n)
        else:
            count = int(n)
        return [_DummyCtx() for _ in range(count)]

    def markdown(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def expander(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return _DummyCtx()

    def write(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def metric(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def progress(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def dataframe(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def success(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def tabs(self, labels):  # noqa: ANN001
        self.tabs_called_count += 1
        return [_DummyCtx() for _ in labels]

    def plotly_chart(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def rerun(self) -> None:
        self.rerun_called_count += 1


class _MetricCaptureCtx(_DummyCtx):
    def __init__(self, sink: list[tuple[str, str]]):
        self._sink = sink

    def metric(self, label, value, *args, **kwargs) -> None:  # noqa: ANN001, ANN002, ANN003
        self._sink.append((str(label), str(value)))


class _MetricCaptureSt(_DummySt):
    def __init__(self, **kwargs):  # noqa: ANN003
        super().__init__(**kwargs)
        self.metrics: list[tuple[str, str]] = []

    def columns(self, n: int | list[int], *args, **kwargs):  # noqa: ANN002, ANN003
        if isinstance(n, list):
            count = len(n)
        else:
            count = int(n)
        return [_MetricCaptureCtx(self.metrics) for _ in range(count)]


class _PlotlyCaptureSt(_DummySt):
    def __init__(self, **kwargs):  # noqa: ANN003
        super().__init__(**kwargs)
        self.figure = None

    def plotly_chart(self, fig, *args, **kwargs) -> None:  # noqa: ANN001, ANN002, ANN003
        self.figure = fig


def _make_technical_summary() -> TechnicalSummary:
    return TechnicalSummary(
        trend_direction="多頭趨勢",
        ma_status="多頭排列 (5>20>60)",
        kd_status="KD 多方",
        macd_status="正值擴張",
        volume_status="量能正常",
        volume_price_relation="量價同步",
        short_term_score=0.66,
        short_term_label="中等偏多",
        short_term_components={"ma": 0.7, "kd": 0.6, "volume_price": 0.6, "breakout": 0.7},
        resistance_levels=[PriceLevel(value=110.0, label="近20日高點", kind="resistance")],
        support_levels=[PriceLevel(value=100.0, label="MA20", kind="support")],
        volume_price_divergence="量價同步",
        ma_bias="與 MA20 乖離約 +1.20%，中性",
        chip_behavior="法人偏多",
        operation_observation="偏多但留意波動",
    )


def _make_daily_df(periods: int = 90, symbol: str = "2330") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=periods, freq="D"),
            "open": [100.0 + i for i in range(periods)],
            "high": [101.0 + i for i in range(periods)],
            "low": [99.0 + i for i in range(periods)],
            "close": [100.5 + i for i in range(periods)],
            "volume": [1000 + i for i in range(periods)],
            "symbol": [symbol] * periods,
        }
    )


def test_dashboard_page_imports() -> None:
    from src.ui.pages.dashboard import render_dashboard_page as imported  # noqa: PLC0415

    assert callable(imported)


def test_dashboard_page_render_no_symbol(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _DummySt(symbol="", analyze_clicked=False)
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "render_stock_selector", lambda *args, **kwargs: dummy._symbol.strip().upper())
    render_dashboard_page()
    assert any("請先輸入股票代碼" in msg for msg in dummy.info_messages)


def test_dashboard_page_accepts_alphanumeric_symbol(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _DummySt(symbol="00981a", analyze_clicked=True)
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "render_stock_selector", lambda *args, **kwargs: dummy._symbol.strip().upper())
    monkeypatch.setattr(
        dashboard_module,
        "_build_dashboard_payload",
        lambda symbol, market="tw": {"symbol": symbol, "market": market, "ready": False, "error": f"{symbol} 尚無本機日線資料"},
    )

    render_dashboard_page()

    assert not dummy.info_messages
    assert any("00981A 尚無本機日線資料" in msg for msg in dummy.warning_messages)


def test_dashboard_tab_overview_renders(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ui": {"theme": "midnight_blue"}})
    monkeypatch.setattr(dashboard_module, "st", _DummySt())
    _render_tab_overview(
        quote=None,
        technical=_make_technical_summary(),
        df=pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "symbol"]),
    )


def test_price_chart_hover_shows_ohlc_and_mas_together(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _PlotlyCaptureSt()
    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ui": {"theme": "midnight_blue"}})
    monkeypatch.setattr(dashboard_module, "st", dummy)

    _render_price_chart(_make_daily_df(periods=65), _make_technical_summary(), kline_count=10)

    assert dummy.figure is not None
    hover_templates = [trace.hovertemplate for trace in dummy.figure.data[:4]]
    assert len(set(hover_templates)) == 1
    assert "Open: %{customdata[1]}" in hover_templates[0]
    assert "High: %{customdata[2]}" in hover_templates[0]
    assert "Low: %{customdata[3]}" in hover_templates[0]
    assert "Close: %{customdata[4]}" in hover_templates[0]
    assert "MA5: %{customdata[5]}" in hover_templates[0]
    assert "MA20: %{customdata[6]}" in hover_templates[0]
    assert "MA60: %{customdata[7]}" in hover_templates[0]
    first_visible_row = list(dummy.figure.data[0].customdata[0])
    last_visible_row = list(dummy.figure.data[0].customdata[-1])
    assert first_visible_row[7] == "—"
    assert last_visible_row[1:] == [
        "164.00",
        "165.00",
        "163.00",
        "164.50",
        "162.50",
        "155.00",
        "135.00",
    ]


def test_help_texts_has_all_required_keys() -> None:
    required_keys = {
        "trend_direction",
        "ma_status",
        "kd_status",
        "macd_status",
        "volume_status",
        "volume_price_relation",
        "resistance",
        "support",
        "short_term_score",
        "foreign",
        "trust",
        "dealer",
        "chip_concentration",
        "margin_balance",
        "short_balance",
        "bid_ask",
        "volume_price_divergence",
        "ma_bias",
        "operation_observation",
        "timeframe_daily",
        "timeframe_weekly",
        "timeframe_monthly",
        "timeframe_strength",
    }
    assert required_keys.issubset(_HELP_TEXTS.keys())


def test_pattern_details_has_all_10_candle_patterns() -> None:
    expected = {
        "長紅 K",
        "長黑 K",
        "十字線",
        "錘子",
        "吊人",
        "吞噬",
        "晨星",
        "夜星",
        "帶上影線",
        "帶下影線",
    }
    assert expected.issubset(_PATTERN_DETAILS.keys())


def test_pattern_details_has_chart_patterns() -> None:
    assert "W底（雙底）" in _PATTERN_DETAILS
    assert "M頭（雙頂）" in _PATTERN_DETAILS


def test_help_texts_values_are_nonempty_strings() -> None:
    assert all(isinstance(value, str) and len(value) > 0 for value in _HELP_TEXTS.values())


def test_pattern_details_values_are_nonempty_strings() -> None:
    assert all(isinstance(value, str) and len(value) > 0 for value in _PATTERN_DETAILS.values())


def test_technical_metric_details_include_actual_indicator_values() -> None:
    details = _build_technical_metric_details(_make_daily_df(periods=90))

    assert "MA5" in details["trend_direction"]
    assert "MA20" in details["ma_status"]
    assert "K " in details["kd_status"]
    assert "D " in details["kd_status"]
    assert "DIF" in details["macd_status"]
    assert "DEA" in details["macd_status"]
    assert "倍數" in details["volume_status"]
    assert "收盤變化" in details["volume_price_relation"]


def test_dashboard_tab_overview_intraday_uses_bid_ask_not_mid_estimate(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _MetricCaptureSt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    quote = RealtimeQuote(
        symbol="3293",
        name="鈊象",
        price=731.5,
        change=-35.0,
        change_pct=-1.53,
        open=725.0,
        high=740.0,
        low=720.0,
        yesterday_close=2287.5,
        volume=1234,
        timestamp="10:05:00",
        best_bid=[2255.0],
        best_ask=[2260.0],
        is_market_open=True,
        is_estimated_price=True,
        price_label="委買賣估算價",
    )
    _render_tab_overview(
        quote=quote,
        technical=_make_technical_summary(),
        df=pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "symbol"]),
    )

    labels = [label for label, _ in dummy.metrics]
    metric_map = dict(dummy.metrics)
    values = [value for _, value in dummy.metrics]
    assert "買一" in labels
    assert "賣一" in labels
    assert "即時價" not in labels
    assert "731.50" not in values
    assert metric_map.get("漲跌") == "-32.50"
    assert metric_map.get("漲跌幅") == "-1.42%"


def test_dashboard_tab_overview_after_hours_uses_latest_daily_close_and_volume(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _MetricCaptureSt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    quote = RealtimeQuote(
        symbol="2330",
        name="台積電",
        price=999.0,
        change=0.0,
        change_pct=0.0,
        open=0.0,
        high=0.0,
        low=0.0,
        yesterday_close=120.0,
        volume=1,
        timestamp="14:00:00",
        is_market_open=False,
    )
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-09", "2026-05-10"]),
            "open": [120.0, 121.0],
            "high": [121.0, 123.0],
            "low": [119.0, 120.5],
            "close": [121.5, 122.0],
            "volume": [9000, 9876],
            "symbol": ["2330", "2330"],
        }
    )
    _render_tab_overview(quote=quote, technical=_make_technical_summary(), df=df)

    metric_map = dict(dummy.metrics)
    assert metric_map.get("收盤價") == "122.00"
    assert metric_map.get("日成交量(張)") == "9"


def test_dashboard_tab_overview_after_hours_uses_quote_when_daily_is_stale(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _MetricCaptureSt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    quote = RealtimeQuote(
        symbol="3163",
        name="波若威",
        price=1040.0,
        change=30.0,
        change_pct=2.9703,
        open=1030.0,
        high=1050.0,
        low=1000.0,
        yesterday_close=1010.0,
        volume=697,
        timestamp="13:30:00",
        trade_date="2026-05-11",
        is_market_open=False,
    )
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-07", "2026-05-08"]),
            "open": [1075.0, 1035.0],
            "high": [1100.0, 1050.0],
            "low": [1070.0, 1000.0],
            "close": [1085.0, 1010.0],
            "volume": [1259591, 1353449],
            "symbol": ["3163", "3163"],
        }
    )
    _render_tab_overview(quote=quote, technical=_make_technical_summary(), df=df)

    metric_map = dict(dummy.metrics)
    assert metric_map.get("收盤價") == "1040.00"
    assert metric_map.get("日成交量(張)") == "697"
    assert metric_map.get("漲跌") == "+30.00"


def test_dashboard_tab_overview_after_hours_ignores_estimated_stale_quote(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _MetricCaptureSt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    quote = RealtimeQuote(
        symbol="3163",
        name="波若威",
        price=1010.0,
        change=0.0,
        change_pct=0.0,
        open=1030.0,
        high=1050.0,
        low=1000.0,
        yesterday_close=1010.0,
        volume=697,
        timestamp="13:30:00",
        trade_date="2026-05-11",
        is_market_open=False,
        is_estimated_price=True,
        price_label="昨收價(無成交)",
    )
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-08"]),
            "open": [1035.0],
            "high": [1050.0],
            "low": [1000.0],
            "close": [1010.0],
            "volume": [1353449],
            "symbol": ["3163"],
        }
    )
    _render_tab_overview(quote=quote, technical=_make_technical_summary(), df=df)

    metric_map = dict(dummy.metrics)
    assert metric_map.get("收盤價") == "1010.00"
    assert metric_map.get("日成交量(張)") == "1,353"


def test_dashboard_tab_chip_no_data(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _DummySt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    _render_tab_chip(chip=None, bid_ask=None, technical=_make_technical_summary())
    assert any("尚未載入籌碼資料" in msg for msg in dummy.info_messages)


def test_dashboard_tab_chip_us_mode_shows_not_supported(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _DummySt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    _render_tab_chip(chip=None, bid_ask=None, technical=_make_technical_summary(), market="us")
    assert any("US-1 尚未支援美股籌碼資料" in msg for msg in dummy.info_messages)


def test_tab_overview_renders_with_help_texts(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ui": {"theme": "midnight_blue"}})
    monkeypatch.setattr(dashboard_module, "st", _DummySt())
    _render_tab_overview(
        quote=None,
        technical=_make_technical_summary(),
        df=pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "symbol"]),
    )


def test_tab_chip_renders_with_help_texts(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    monkeypatch.setattr(dashboard_module, "st", _DummySt())
    chip = ChipSummary(
        foreign_net_n_days=10,
        trust_net_n_days=-2,
        dealer_net_n_days=1,
        foreign_label="買超 10 張",
        trust_label="賣超 2 張",
        dealer_label="買超 1 張",
        chip_concentration="穩定",
        chip_trend="中性",
        chip_description="法人進出互見，籌碼趨於穩定。",
        margin_balance_change=100,
        short_balance_change=-50,
    )
    bid_ask = BidAskStructure(
        total_bid_vol=1000,
        total_ask_vol=800,
        bid_ratio=0.55,
        ask_ratio=0.45,
        label="買盤較積極",
    )
    _render_tab_chip(
        chip=chip,
        bid_ask=bid_ask,
        technical=_make_technical_summary(),
        chip_recent_df=pd.DataFrame({"日期": ["2026-01-01"], "外資": [1], "投信": [0], "自營商": [-1]}),
    )


def test_dashboard_tab_overview_us_mode_uses_shares_label(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _MetricCaptureSt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ui": {"theme": "midnight_blue"}})
    _render_tab_overview(
        quote=None,
        technical=_make_technical_summary(),
        df=_make_daily_df(symbol="AAPL", periods=80),
        market="us",
    )

    metric_map = dict(dummy.metrics)
    assert "成交量(shares)" in metric_map
    assert "日成交量(張)" not in metric_map
    assert any("美股日期以紐約交易日為準" in msg for msg in dummy.caption_messages)


def test_tab_pattern_renders_with_details(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    monkeypatch.setattr(dashboard_module, "st", _DummySt())
    candle_patterns = [
        CandlePattern(name="長紅 K", detected=True, description="多方力道"),
        CandlePattern(name="十字線", detected=False, description="多空拉鋸"),
    ]
    chart_patterns = [
        ChartPatternResult(
            pattern_type="W底（雙底）",
            formed=True,
            description="突破頸線",
            key_points=[("頸線", 100.0), ("右底", 95.0)],
        ),
        ChartPatternResult(
            pattern_type="M頭（雙頂）",
            formed=False,
            description="未形成標準M頭型態",
            key_points=[],
        ),
    ]
    _render_tab_pattern(
        candle_patterns=candle_patterns,
        chart_patterns=chart_patterns,
        mtf=MultiTimeframeAnalysis(
            daily=TimeframeTrend(timeframe="daily", trend_direction="多頭", strength="中強"),
            weekly=TimeframeTrend(timeframe="weekly", trend_direction="多頭", strength="中"),
            monthly=TimeframeTrend(timeframe="monthly", trend_direction="盤整", strength="中"),
        ),
    )


def test_dashboard_tab_ai_disabled(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _DummySt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    _render_tab_ai(analysis=None, technical=_make_technical_summary(), ai_enabled=False)
    assert any("請啟用 AI 功能" in msg for msg in dummy.info_messages)


def test_dashboard_option_menu_entry() -> None:
    app_path = Path("src/ui/app.py")
    source = app_path.read_text(encoding="utf-8")
    assert "個股分析" in source


def test_dashboard_page_uses_text_input_on_change_for_enter() -> None:
    source = Path("src/ui/pages/dashboard.py").read_text(encoding="utf-8")
    assert "on_change" in source
    assert "_request_dashboard_analysis" in source


def test_dashboard_page_not_ready_payload_does_not_render_tabs(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _DummySt(symbol="2330", analyze_clicked=True)
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "render_stock_selector", lambda *args, **kwargs: dummy._symbol.strip().upper())
    monkeypatch.setattr(
        dashboard_module,
        "_build_dashboard_payload",
        lambda symbol, market="tw": {"symbol": symbol, "market": market, "ready": False, "error": "尚無本機日線資料"},
    )

    render_dashboard_page()

    assert dummy.tabs_called_count == 0
    assert any("尚無本機日線資料" in msg for msg in dummy.warning_messages)


def test_dashboard_page_refresh_quote_updates_session_payload(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    technical = _make_technical_summary()
    old_quote = RealtimeQuote(
        symbol="2330",
        name="台積電",
        price=100.0,
        change=0.0,
        change_pct=0.0,
        open=100.0,
        high=101.0,
        low=99.0,
        yesterday_close=100.0,
        volume=1000,
        timestamp="10:00:00",
    )
    payload = {
        "symbol": "2330",
        "market": "tw",
        "ready": True,
        "error": None,
        "daily_df": pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "symbol"]),
        "technical": technical,
        "quote": old_quote,
        "subject_name": "台積電",
        "analysis_time": "2026-05-11 14:35:20",
        "bid_ask": None,
        "chip": None,
        "candle_patterns": [],
        "chart_patterns": [],
        "multi_timeframe": MultiTimeframeAnalysis(
            daily=TimeframeTrend(timeframe="daily", trend_direction="盤整", strength="中"),
            weekly=TimeframeTrend(timeframe="weekly", trend_direction="盤整", strength="中"),
            monthly=TimeframeTrend(timeframe="monthly", trend_direction="盤整", strength="中"),
        ),
        "analysis": None,
        "ai_enabled": False,
    }

    dummy = _DummySt(
        symbol="2330",
        analyze_clicked=False,
        button_map={"dashboard_refresh_quote": True},
    )
    dummy.session_state["dashboard_payload"] = payload
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "render_stock_selector", lambda *args, **kwargs: dummy._symbol.strip().upper())

    new_quote = RealtimeQuote(
        symbol="2330",
        name="台積電",
        price=123.45,
        change=1.0,
        change_pct=0.8,
        open=122.0,
        high=124.0,
        low=121.0,
        yesterday_close=122.45,
        volume=2000,
        timestamp="10:05:00",
    )
    new_bid_ask = BidAskStructure(
        total_bid_vol=500,
        total_ask_vol=400,
        bid_ratio=0.56,
        ask_ratio=0.44,
        label="買盤較積極",
    )
    monkeypatch.setattr(
        dashboard_module,
        "_refresh_realtime_snapshot",
        lambda symbol, market="tw": (new_quote, new_bid_ask, None),
    )

    render_dashboard_page()

    updated = dummy.session_state["dashboard_payload"]
    assert updated["quote"].price == 123.45
    assert updated["bid_ask"].label == "買盤較積極"
    assert updated["subject_name"] == "台積電"
    assert updated["analysis_time"] == "2026-05-11 14:35:20"
    assert dummy.rerun_called_count == 1


def test_dashboard_page_renders_analysis_subject_and_time(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    payload = {
        "symbol": "2330",
        "market": "tw",
        "ready": True,
        "error": None,
        "daily_df": pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "symbol"]),
        "technical": _make_technical_summary(),
        "quote": None,
        "subject_name": "台積電",
        "analysis_time": "2026-05-11 14:35:20",
        "bid_ask": None,
        "chip": None,
        "candle_patterns": [],
        "chart_patterns": [],
        "multi_timeframe": MultiTimeframeAnalysis(
            daily=TimeframeTrend(timeframe="daily", trend_direction="盤整", strength="中"),
            weekly=TimeframeTrend(timeframe="weekly", trend_direction="盤整", strength="中"),
            monthly=TimeframeTrend(timeframe="monthly", trend_direction="盤整", strength="中"),
        ),
        "analysis": None,
        "ai_enabled": False,
    }
    dummy = _DummySt(symbol="2330", analyze_clicked=False)
    dummy.session_state["dashboard_payload"] = payload
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "render_stock_selector", lambda *args, **kwargs: dummy._symbol.strip().upper())

    render_dashboard_page()

    assert "台積電（2330）｜分析時間：2026-05-11 14:35:20" in dummy.caption_messages


def test_dashboard_payload_builds_multi_timeframe_from_date_column(monkeypatch, tmp_path) -> None:
    import src.ui.pages.dashboard as dashboard_module

    class _Realtime:
        @classmethod
        def from_config(cls):
            return cls()

        def fetch_quote(self, symbol: str):  # noqa: ANN201
            return RealtimeQuote(
                symbol=symbol,
                name="台積電",
                price=100.0,
                change=0.0,
                change_pct=0.0,
                open=100.0,
                high=101.0,
                low=99.0,
                yesterday_close=100.0,
                volume=1000,
                timestamp="10:00:00",
            )

        def fetch_bid_ask_structure(self, quote):  # noqa: ANN001, ANN201
            return None

    storage = ParquetStorage(data_dir=tmp_path)
    storage.save_daily("2330", _make_daily_df())
    monkeypatch.setattr(dashboard_module, "ParquetStorage", lambda: storage)
    monkeypatch.setattr(dashboard_module, "RealtimeFetcher", _Realtime)
    monkeypatch.setattr(dashboard_module, "st", _DummySt())
    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ai": {"enabled": False}, "ui": {"theme": "midnight_blue"}})
    monkeypatch.setattr(dashboard_module, "_format_analysis_time", lambda market="tw": "2026-05-11 14:35:20")
    monkeypatch.setattr(
        dashboard_module,
        "_prepare_daily_data_for_dashboard",
        lambda symbol, storage, market="tw": (storage.load_daily(symbol, market=market), None),
    )
    monkeypatch.setattr(
        dashboard_module,
        "_prepare_chip_data_for_dashboard",
        lambda symbol, storage: (None, pd.DataFrame(), None),
    )

    payload = _build_dashboard_payload("2330")

    assert payload["ready"] is True
    assert isinstance(payload["multi_timeframe"], MultiTimeframeAnalysis)
    assert payload["subject_name"] == "台積電"
    assert payload["analysis_time"] == "2026-05-11 14:35:20"


def test_dashboard_payload_us_uses_adjusted_daily_and_disables_realtime_and_chip(monkeypatch, tmp_path) -> None:
    import src.ui.pages.dashboard as dashboard_module

    storage = ParquetStorage(data_dir=tmp_path)
    raw_df = _make_daily_df(symbol="AAPL")
    adjusted_df = raw_df.copy()
    adjusted_df["close"] = adjusted_df["close"] + 100.0
    storage.save_daily("AAPL", raw_df, market="us")
    storage.save_adjusted("AAPL", adjusted_df, market="us")

    calls = {"realtime": 0, "chip": 0}

    class _Realtime:
        @classmethod
        def from_config(cls):
            calls["realtime"] += 1
            raise AssertionError("RealtimeFetcher should not be called for US dashboard")

    def _chip(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["chip"] += 1
        raise AssertionError("_prepare_chip_data_for_dashboard should not be called for US dashboard")

    monkeypatch.setattr(dashboard_module, "ParquetStorage", lambda: storage)
    monkeypatch.setattr(dashboard_module, "_sync_symbol_daily_data", lambda symbol, storage, market="tw": None)
    monkeypatch.setattr(dashboard_module, "RealtimeFetcher", _Realtime)
    monkeypatch.setattr(dashboard_module, "_prepare_chip_data_for_dashboard", _chip)
    monkeypatch.setattr(dashboard_module, "st", _DummySt())
    monkeypatch.setattr(
        dashboard_module,
        "get_config",
        lambda: {"ai": {"enabled": False}, "ui": {"theme": "midnight_blue"}},
    )

    payload = _build_dashboard_payload("AAPL", market="us")

    assert payload["ready"] is True
    assert payload["market"] == "us"
    assert payload["quote"] is None
    assert payload["chip"] is None
    assert payload["chip_error"] == "US-1 尚未支援美股籌碼資料。"
    assert float(payload["daily_df"]["close"].iloc[-1]) == float(adjusted_df["close"].iloc[-1])
    assert calls["realtime"] == 0
    assert calls["chip"] == 0


def test_build_recent_institutional_table_keeps_last_five_days() -> None:
    inst = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=7, freq="D"),
            "foreign_net": [1000, 2000, 3000, 4000, 5000, 6000, 7000],
            "trust_net": [0, 1000, 0, 1000, 0, 1000, 0],
            "dealer_net": [-1000, -1000, -1000, -1000, -1000, -1000, -1000],
        }
    )

    table = _build_recent_institutional_table(inst, n_days=5)

    assert len(table) == 5
    assert list(table.columns) == ["日期", "外資", "投信", "自營商"]
    assert table.iloc[-1]["外資"] == 7


def test_style_recent_institutional_table_applies_red_green_and_keeps_negative_sign() -> None:
    table = pd.DataFrame(
        {
            "日期": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "外資": [3, -2, 0],
            "投信": [0, 1, -1],
            "自營商": [-4, 0, 2],
        }
    )

    styled = _style_recent_institutional_table(table)

    assert styled._display_funcs[(0, 1)](table.iloc[0, 1]) == "3"
    assert styled._display_funcs[(1, 1)](table.iloc[1, 1]) == "-2"

    style_ctx = styled._compute().ctx
    assert ("color", "#dc2626") in style_ctx[(0, 1)]
    assert ("color", "#16a34a") in style_ctx[(1, 1)]
    assert (2, 1) not in style_ctx


def test_prepare_chip_data_returns_friendly_finmind_only_error(monkeypatch, tmp_path) -> None:
    import src.ui.pages.dashboard as dashboard_module

    class _BrokenFetcher:
        def fetch_institutional_incremental(self, symbol: str, storage):  # noqa: ANN001, ANN201
            raise RuntimeError("api timeout")

        def fetch_margin_incremental(self, symbol: str, storage):  # noqa: ANN001, ANN201
            return pd.DataFrame()

    monkeypatch.setattr(dashboard_module, "_build_chip_fetcher", lambda: _BrokenFetcher())

    chip, recent_df, chip_error = _prepare_chip_data_for_dashboard("2330", ParquetStorage(data_dir=tmp_path))

    assert chip is None
    assert recent_df.empty
    assert chip_error is not None
    assert "籌碼資料僅支援 FinMind，抓取失敗：" in chip_error


def test_sync_symbol_daily_data_fallback_when_primary_update_fails(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    calls: list[str] = []

    class _Fetcher:
        def __init__(self, source: str):
            self.source = source

    class _Maintenance:
        def __init__(self, *, fetcher, **kwargs):  # noqa: ANN003
            self.fetcher = fetcher

        def update_daily(self, symbol: str, market: str = "tw") -> None:
            calls.append(f"{self.fetcher.source}:{symbol}")
            if self.fetcher.source == "finmind":
                raise RuntimeError("primary update failed")

    class _Meta:
        def close(self) -> None:
            return None

    monkeypatch.setattr(dashboard_module, "DuckDBMeta", _Meta)
    monkeypatch.setattr(dashboard_module, "DataMaintenance", _Maintenance)
    monkeypatch.setattr(
        dashboard_module,
        "_build_fetchers_from_config",
        lambda market="tw": [("finmind", _Fetcher("finmind")), ("yfinance", _Fetcher("yfinance"))],
    )

    dashboard_module._sync_symbol_daily_data("2330", storage=object())  # type: ignore[arg-type]

    assert calls == ["finmind:2330", "yfinance:2330"]


# ---------------------------------------------------------------------------
# Phase 9-G: dashboard intraday snapshot tests
# ---------------------------------------------------------------------------

from src.data.fetcher import USIntradaySnapshot  # noqa: E402


def _make_intraday_snapshot(
    price: float = 155.0,
    previous_raw_close: float = 150.0,
    volume: int = 800000,
    ts: str = "2026-05-14 14:35:00",
    tz: str = "America/New_York",
) -> USIntradaySnapshot:
    change = price - previous_raw_close
    change_pct = change / previous_raw_close * 100.0
    timestamp = pd.Timestamp(ts).tz_localize(tz)
    return USIntradaySnapshot(
        symbol="AAPL",
        price=price,
        previous_raw_close=previous_raw_close,
        change=change,
        change_pct=change_pct,
        volume=volume,
        timestamp=timestamp,
    )


def _make_intraday_df(n: int = 5) -> pd.DataFrame:
    tz = "America/New_York"
    today = pd.Timestamp.now(tz=tz).date()
    timestamps = pd.date_range(f"{today} 09:30", periods=n, freq="1min", tz=tz)
    return pd.DataFrame({
        "date": timestamps,
        "open": [150.0 + i for i in range(n)],
        "high": [151.0 + i for i in range(n)],
        "low": [149.0 + i for i in range(n)],
        "close": [150.5 + i for i in range(n)],
        "volume": [100000 + i * 10000 for i in range(n)],
        "symbol": ["AAPL"] * n,
    })


def test_dashboard_us_intraday_snapshot_uses_latest_1m_close(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _MetricCaptureSt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ui": {"theme": "midnight_blue"}})

    snapshot = _make_intraday_snapshot(price=155.5, previous_raw_close=150.0)
    _render_tab_overview(
        quote=None,
        technical=_make_technical_summary(),
        df=_make_daily_df(symbol="AAPL", periods=80),
        market="us",
        intraday_snapshot=snapshot,
        intraday_df=_make_intraday_df(),
    )

    metric_map = dict(dummy.metrics)
    assert metric_map.get("近似盤中價") == "155.50"
    assert metric_map.get("狀態") == "盤中分K資料"


def test_dashboard_us_intraday_change_uses_previous_raw_close(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _MetricCaptureSt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ui": {"theme": "midnight_blue"}})

    # price=155.5, previous_raw_close=150.0 → change=+5.5, change_pct=+3.67%
    snapshot = _make_intraday_snapshot(price=155.5, previous_raw_close=150.0)
    _render_tab_overview(
        quote=None,
        technical=_make_technical_summary(),
        df=_make_daily_df(symbol="AAPL", periods=80),
        market="us",
        intraday_snapshot=snapshot,
    )

    metric_map = dict(dummy.metrics)
    assert metric_map.get("漲跌") == "+5.50"
    assert "3.67" in (metric_map.get("漲跌幅") or "")


def test_dashboard_us_intraday_volume_sums_today_1m_volume(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _MetricCaptureSt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ui": {"theme": "midnight_blue"}})

    snapshot = _make_intraday_snapshot(volume=1_234_567)
    _render_tab_overview(
        quote=None,
        technical=_make_technical_summary(),
        df=_make_daily_df(symbol="AAPL", periods=80),
        market="us",
        intraday_snapshot=snapshot,
    )

    metric_map = dict(dummy.metrics)
    assert "1,234,567" in (metric_map.get("成交量(shares)") or "")


def test_dashboard_us_intraday_shows_new_york_timestamp_and_research_caption(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _MetricCaptureSt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ui": {"theme": "midnight_blue"}})

    snapshot = _make_intraday_snapshot()
    _render_tab_overview(
        quote=None,
        technical=_make_technical_summary(),
        df=_make_daily_df(symbol="AAPL", periods=80),
        market="us",
        intraday_snapshot=snapshot,
    )

    # Must show NY timestamp info and research disclaimer caption
    captions = dummy.caption_messages
    assert any("紐約時間" in c for c in captions)
    assert any("可能延遲" in c and "研究分析" in c for c in captions)


def test_dashboard_us_intraday_falls_back_to_adjusted_daily_when_unavailable(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _MetricCaptureSt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ui": {"theme": "midnight_blue"}})

    # No intraday snapshot (None) — should show daily fallback
    _render_tab_overview(
        quote=None,
        technical=_make_technical_summary(),
        df=_make_daily_df(symbol="AAPL", periods=80),
        market="us",
        intraday_snapshot=None,
        intraday_error="非今日紐約交易日，已改用最新日線資料。",
    )

    metric_map = dict(dummy.metrics)
    # Must show daily fallback (收盤價) not intraday (近似盤中價)
    assert "收盤價" in metric_map
    assert "近似盤中價" not in metric_map
    assert metric_map.get("狀態") == "日線資料"
    assert any("目前無法取得美股盤中分 K" in m for m in dummy.info_messages)


def test_dashboard_us_intraday_does_not_show_bid_ask(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _MetricCaptureSt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ui": {"theme": "midnight_blue"}})

    snapshot = _make_intraday_snapshot()
    _render_tab_overview(
        quote=None,
        technical=_make_technical_summary(),
        df=_make_daily_df(symbol="AAPL", periods=80),
        market="us",
        intraday_snapshot=snapshot,
    )

    metric_labels = [label for label, _ in dummy.metrics]
    assert "買一" not in metric_labels
    assert "賣一" not in metric_labels


def test_dashboard_us_intraday_does_not_call_tw_realtime_fetcher(monkeypatch, tmp_path) -> None:
    import src.ui.pages.dashboard as dashboard_module

    storage = ParquetStorage(data_dir=tmp_path)
    raw_df = _make_daily_df(symbol="AAPL")
    adjusted_df = raw_df.copy()
    storage.save_daily("AAPL", raw_df, market="us")
    storage.save_adjusted("AAPL", adjusted_df, market="us")

    realtime_called = []

    class _Realtime:
        @classmethod
        def from_config(cls):
            realtime_called.append(True)
            raise AssertionError("RealtimeFetcher must not be called for US market (9-G)")

    monkeypatch.setattr(dashboard_module, "RealtimeFetcher", _Realtime)
    monkeypatch.setattr(dashboard_module, "ParquetStorage", lambda: storage)
    monkeypatch.setattr(dashboard_module, "_sync_symbol_daily_data", lambda symbol, storage, market="tw": None)
    monkeypatch.setattr(dashboard_module, "st", _DummySt())
    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ai": {"enabled": False}, "ui": {"theme": "midnight_blue"}})
    # Stub out intraday fetch to avoid real network call
    monkeypatch.setattr(
        dashboard_module,
        "_fetch_us_intraday_snapshot",
        lambda symbol, raw_daily: (pd.DataFrame(), None, "test stub"),
    )

    payload = _build_dashboard_payload("AAPL", market="us")

    assert not realtime_called
    assert payload["market"] == "us"


def test_dashboard_us_intraday_chart_uses_intraday_df_not_daily_patterns(monkeypatch) -> None:
    """9-G: intraday_df is rendered as a separate chart; daily pattern detection uses only daily df."""
    import src.ui.pages.dashboard as dashboard_module

    captured_figs = []

    class _CaptureSt(_DummySt):
        def plotly_chart(self, fig, **kwargs):  # noqa: ANN001
            captured_figs.append(fig)

    dummy = _CaptureSt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ui": {"theme": "midnight_blue"}})

    snapshot = _make_intraday_snapshot()
    intraday_df = _make_intraday_df(n=10)
    _render_tab_overview(
        quote=None,
        technical=_make_technical_summary(),
        df=_make_daily_df(symbol="AAPL", periods=80),
        market="us",
        intraday_snapshot=snapshot,
        intraday_df=intraday_df,
    )

    # There should be at least 2 charts: intraday and daily K
    assert len(captured_figs) >= 2
    # First chart should be intraday (title contains 1m or 分K)
    first_title = captured_figs[0].layout.title.text or ""
    assert "1m" in first_title or "分K" in first_title


# ---------------------------------------------------------------------------
# Regression: Bug 1 — DataFrame ambiguity in render_dashboard_page payload path
# ---------------------------------------------------------------------------

def test_render_dashboard_page_us_with_nonempty_intraday_df_does_not_crash(monkeypatch) -> None:
    """Regression: payload.get('intraday_df') or pd.DataFrame() raises ValueError
    when intraday_df is a non-empty DataFrame. Must use explicit is None check."""
    import src.ui.pages.dashboard as dashboard_module

    technical = _make_technical_summary()
    intraday_df = _make_intraday_df(n=5)   # non-empty — triggers the ambiguity bug
    snapshot = _make_intraday_snapshot()

    payload = {
        "symbol": "AAPL",
        "market": "us",
        "ready": True,
        "error": None,
        "daily_df": _make_daily_df(symbol="AAPL", periods=80),
        "technical": technical,
        "quote": None,
        "subject_name": "AAPL",
        "analysis_time": "2026-05-14 00:20:00",
        "bid_ask": None,
        "chip": None,
        "chip_recent_df": pd.DataFrame(),
        "chip_error": "US-1 尚未支援美股籌碼資料。",
        "candle_patterns": [],
        "chart_patterns": [],
        "multi_timeframe": MultiTimeframeAnalysis(
            daily=TimeframeTrend(timeframe="daily", trend_direction="多頭", strength="中強"),
            weekly=TimeframeTrend(timeframe="weekly", trend_direction="多頭", strength="中"),
            monthly=TimeframeTrend(timeframe="monthly", trend_direction="盤整", strength="中"),
        ),
        "analysis": None,
        "ai_enabled": False,
        "intraday_df": intraday_df,        # non-empty DataFrame
        "intraday_snapshot": snapshot,
        "intraday_error": None,
    }

    dummy = _DummySt(symbol="AAPL", analyze_clicked=False)
    dummy.session_state["dashboard_payload"] = payload
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(dashboard_module, "get_config", lambda: {"ui": {"theme": "midnight_blue"}})
    monkeypatch.setattr(dashboard_module, "render_stock_selector", lambda *args, **kwargs: "AAPL", raising=False)
    monkeypatch.setattr(dashboard_module, "_render_market_selector", lambda key_prefix: "us")
    monkeypatch.setattr(dashboard_module, "_input_dashboard_symbol", lambda *, market: "AAPL")

    # Must not raise ValueError: The truth value of a DataFrame is ambiguous
    render_dashboard_page()


# ---------------------------------------------------------------------------
# Regression: Bug 2 — previous_raw_close must exclude today's NY raw daily row
# ---------------------------------------------------------------------------

def test_fetch_us_intraday_snapshot_excludes_today_raw_daily(monkeypatch) -> None:
    """Regression: if raw daily contains today's NY date, previous_raw_close must be
    the last row strictly before today, not today's close.

    Scenario: raw daily close = [100, 104] where 104 is today's close.
    Intraday price = 105.
    Expected: previous_raw_close=100, change=5, change_pct=5%.
    Bug (before fix): previous_raw_close=104, change=1.
    """
    import src.ui.pages.dashboard as dashboard_module

    us_tz = "America/New_York"
    today = pd.Timestamp.now(tz=us_tz).date()
    yesterday = today - pd.Timedelta(days=1)

    raw_daily = pd.DataFrame({
        "date": pd.to_datetime([str(yesterday), str(today)]).tz_localize(us_tz),
        "open": [99.0, 103.0],
        "high": [101.0, 105.0],
        "low": [98.0, 102.0],
        "close": [100.0, 104.0],   # today's close = 104
        "volume": [1000, 2000],
        "symbol": ["AAPL", "AAPL"],
    })

    # Build a snapshot with latest_bar_date = today
    today_ts = pd.Timestamp(f"{today} 14:35:00", tz=us_tz)
    snapshot_raw = USIntradaySnapshot(
        symbol="AAPL",
        price=105.0,
        previous_raw_close=float("nan"),
        change=float("nan"),
        change_pct=float("nan"),
        volume=500000,
        timestamp=today_ts,
    )

    def _stub_fetch(symbol):  # noqa: ANN001
        return pd.DataFrame(), snapshot_raw, None

    monkeypatch.setattr(
        "src.ui.pages.dashboard.YFinanceFetcher",
        type("_FetcherStub", (), {
            "__init__": lambda self, market="us": None,
            "fetch_us_intraday": lambda self, symbol: _stub_fetch(symbol),
        }),
    )

    _, full_snapshot, error = dashboard_module._fetch_us_intraday_snapshot("AAPL", raw_daily)

    assert error is None
    assert full_snapshot is not None
    # previous_raw_close must be yesterday's close (100), NOT today's (104)
    assert full_snapshot.previous_raw_close == pytest.approx(100.0)
    assert full_snapshot.change == pytest.approx(5.0)
    assert full_snapshot.change_pct == pytest.approx(5.0)
