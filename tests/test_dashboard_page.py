from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.technical_summary import PriceLevel, TechnicalSummary
from src.analysis.pattern import MultiTimeframeAnalysis, TimeframeTrend
from src.data.realtime import BidAskStructure, RealtimeQuote
from src.ui.pages.dashboard import (
    _render_tab_ai,
    _render_tab_chip,
    _render_tab_overview,
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
        self.tabs_called_count = 0
        self.rerun_called_count = 0

    def title(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def caption(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def text_input(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        return self._symbol

    def button(self, *args, **kwargs) -> bool:  # noqa: ANN002, ANN003
        key = str(kwargs.get("key", ""))
        if key in self._button_map:
            return bool(self._button_map[key])
        return self._analyze_clicked

    def info(self, message: str, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.info_messages.append(message)

    def warning(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        if args:
            self.warning_messages.append(str(args[0]))
        return None

    def subheader(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def columns(self, n: int, *args, **kwargs):  # noqa: ANN002, ANN003
        return [_DummyCtx() for _ in range(n)]

    def markdown(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

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


def test_dashboard_page_imports() -> None:
    from src.ui.pages.dashboard import render_dashboard_page as imported  # noqa: PLC0415

    assert callable(imported)


def test_dashboard_page_render_no_symbol(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _DummySt(symbol="", analyze_clicked=False)
    monkeypatch.setattr(dashboard_module, "st", dummy)
    render_dashboard_page()
    assert any("請先輸入股票代碼" in msg for msg in dummy.info_messages)


def test_dashboard_tab_overview_renders(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    monkeypatch.setattr(dashboard_module, "st", _DummySt())
    _render_tab_overview(
        quote=None,
        technical=_make_technical_summary(),
        df=pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "symbol"]),
    )


def test_dashboard_tab_chip_no_data(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _DummySt()
    monkeypatch.setattr(dashboard_module, "st", dummy)
    _render_tab_chip(chip=None, bid_ask=None, technical=_make_technical_summary())
    assert any("尚未載入籌碼資料" in msg for msg in dummy.info_messages)


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


def test_dashboard_page_not_ready_payload_does_not_render_tabs(monkeypatch) -> None:
    import src.ui.pages.dashboard as dashboard_module

    dummy = _DummySt(symbol="2330", analyze_clicked=True)
    monkeypatch.setattr(dashboard_module, "st", dummy)
    monkeypatch.setattr(
        dashboard_module,
        "_build_dashboard_payload",
        lambda symbol: {"symbol": symbol, "ready": False, "error": "尚無本機日線資料"},
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
        "ready": True,
        "error": None,
        "daily_df": pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "symbol"]),
        "technical": technical,
        "quote": old_quote,
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
        lambda symbol: (new_quote, new_bid_ask, None),
    )

    render_dashboard_page()

    updated = dummy.session_state["dashboard_payload"]
    assert updated["quote"].price == 123.45
    assert updated["bid_ask"].label == "買盤較積極"
    assert dummy.rerun_called_count == 1
