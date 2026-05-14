"""Tests for Phase 10-D analysis/realtime/ai API endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from api.job_manager import get_job_manager
from src.ai.advisor import DashboardAnalysis, TradingScenario
from src.analysis.chip_analysis import ChipSummary
from src.analysis.pattern import CandlePattern, ChartPatternResult, MultiTimeframeAnalysis, TimeframeTrend
from src.analysis.technical_summary import PriceLevel, TechnicalSummary
from src.data.fetcher import USIntradaySnapshot
from src.data.realtime import BidAskStructure, RealtimeQuote
from src.services.dashboard_service import DashboardError, DashboardPayload

client = TestClient(app)


def _reset_job_manager() -> None:
    import api.job_manager as jm_module

    jm_module._job_manager = None


def _sample_payload(*, market: str = "tw") -> DashboardPayload:
    daily = pd.DataFrame(
        {
            "date": [
                pd.Timestamp("2026-05-12T00:00:00+08:00"),
                pd.Timestamp("2026-05-13T00:00:00+08:00"),
            ],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000, 1200],
            "symbol": ["2330", "2330"],
        }
    )
    technical = TechnicalSummary(
        trend_direction="多頭趨勢",
        ma_status="多頭排列",
        kd_status="K 80 / D 75",
        macd_status="正值收斂",
        volume_status="量能正常",
        volume_price_relation="價漲量增",
        short_term_score=0.62,
        short_term_label="中等偏多",
        short_term_components={"ma": 0.7, "kd": 0.6, "volume_price": 0.6, "breakout": 0.5},
        resistance_levels=[PriceLevel(value=110.0, label="近60日高點", kind="resistance")],
        support_levels=[PriceLevel(value=95.0, label="近期低點", kind="support")],
        volume_price_divergence="價量同步",
        ma_bias="+2.10%",
        chip_behavior="穩定",
        operation_observation="趨勢偏多",
    )
    quote = RealtimeQuote(
        symbol="2330",
        name="台積電",
        price=102.0,
        change=1.0,
        change_pct=0.99,
        open=101.0,
        high=103.0,
        low=100.0,
        yesterday_close=101.0,
        volume=1200,
        timestamp="2026-05-14T10:00:00+08:00",
        trade_date="2026-05-14",
        best_bid=[101.5],
        best_ask=[102.5],
        best_bid_vol=[100],
        best_ask_vol=[110],
    )
    chip = ChipSummary(
        foreign_net_n_days=100,
        trust_net_n_days=30,
        dealer_net_n_days=-20,
        foreign_label="買超 100 張",
        trust_label="買超 30 張",
        dealer_label="賣超 20 張",
        chip_concentration="穩定",
        chip_trend="偏多",
        chip_description="法人偏多",
        margin_balance_change=50,
        short_balance_change=-10,
    )
    mtf = MultiTimeframeAnalysis(
        daily=TimeframeTrend("daily", "多頭", "強"),
        weekly=TimeframeTrend("weekly", "多頭", "中強"),
        monthly=TimeframeTrend("monthly", "多頭", "強"),
    )
    analysis = DashboardAnalysis(
        industry_overview=["產業正向"],
        company_overview=["基本面穩定"],
        volume_price_analysis="量價健康",
        scenarios=[TradingScenario(name="開高走高", entry_range="100-102", stop_loss=98.0, target="108")],
        conclusion="偏多操作",
    )
    intraday_snapshot = USIntradaySnapshot(
        symbol="AAPL",
        price=190.0,
        previous_raw_close=188.0,
        change=2.0,
        change_pct=1.06,
        volume=123456,
        timestamp=datetime.fromisoformat("2026-05-14T09:40:00-04:00"),
        source="yfinance",
        interval="1m",
    )
    return DashboardPayload(
        symbol="2330" if market == "tw" else "AAPL",
        market=market,
        daily_df=daily,
        technical=technical,
        candle_patterns=[CandlePattern(name="長紅 K", detected=True, description="多方力道")],
        chart_patterns=[ChartPatternResult(pattern_type="W底（雙底）", formed=False, description="尚未形成")],
        multi_timeframe=mtf,
        ai_enabled=True,
        quote=quote if market == "tw" else None,
        bid_ask=BidAskStructure(100, 120, 0.45, 0.55, "賣壓較重") if market == "tw" else None,
        chip=chip if market == "tw" else None,
        chip_recent_df=pd.DataFrame([{"日期": "2026-05-13", "外資": 10, "投信": 2, "自營商": -1}]),
        chip_error=None if market == "tw" else "US-1 尚未支援美股籌碼資料。",
        intraday_df=pd.DataFrame([{"date": "2026-05-14T13:40:00+00:00", "open": 189.5, "high": 190.2, "low": 189.3, "close": 190.0, "volume": 1000, "symbol": "AAPL"}])
        if market == "us"
        else pd.DataFrame(),
        intraday_snapshot=intraday_snapshot if market == "us" else None,
        intraday_error=None,
        analysis=analysis,
        subject_name="台積電" if market == "tw" else "Apple",
        analysis_time="2026-05-14 10:00:00",
    )


@patch("api.routers.analysis.build_dashboard_payload")
def test_dashboard_payload_endpoint_returns_envelope(mock_build) -> None:
    _reset_job_manager()
    mock_build.return_value = _sample_payload(market="tw")
    resp = client.get("/api/dashboard/payload", params={"symbol": "2330", "market": "tw"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["symbol"] == "2330"
    assert isinstance(body["data"]["daily_df"], list)
    assert body["meta"]["market"] == "tw"


def test_dashboard_payload_endpoint_returns_409_when_write_lock_busy() -> None:
    _reset_job_manager()
    manager = get_job_manager()

    async def _hold_lock() -> None:
        await manager._write_lock.acquire()

    asyncio.run(_hold_lock())
    try:
        resp = client.get("/api/dashboard/payload", params={"symbol": "2330", "market": "tw"})
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"]["code"] == "WRITE_LOCK_BUSY"
    finally:
        manager.release_write_lock()


@patch("api.routers.analysis.build_dashboard_payload")
def test_analysis_section_technical(mock_build) -> None:
    mock_build.return_value = _sample_payload(market="tw")
    resp = client.get("/api/analysis/technical", params={"symbol": "2330", "market": "tw"})
    assert resp.status_code == 200
    assert resp.json()["data"]["trend_direction"] == "多頭趨勢"


@patch("api.routers.realtime.build_dashboard_payload")
def test_realtime_tw_endpoint(mock_build) -> None:
    mock_build.return_value = _sample_payload(market="tw")
    resp = client.get("/api/realtime/tw", params={"symbol": "2330"})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["quote"]["symbol"] == "2330"
    assert "bid_ask" in body


@patch("api.routers.realtime.build_dashboard_payload")
def test_realtime_us_intraday_endpoint(mock_build) -> None:
    mock_build.return_value = _sample_payload(market="us")
    resp = client.get("/api/realtime/us/intraday", params={"symbol": "AAPL"})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["intraday_snapshot"]["symbol"] == "AAPL"
    assert isinstance(body["intraday_df"], list)


@patch("api.routers.ai.build_dashboard_payload")
def test_ai_analyze_endpoint(mock_build) -> None:
    payload = _sample_payload(market="tw")
    payload.ai_enabled = True
    mock_build.return_value = payload
    resp = client.post("/api/ai/analyze", json={"symbol": "2330", "market": "tw"})
    assert resp.status_code == 200
    assert resp.json()["data"]["conclusion"] == "偏多操作"


@patch("api.routers.ai.build_dashboard_payload")
def test_ai_analyze_returns_503_when_disabled(mock_build) -> None:
    payload = _sample_payload(market="tw")
    payload.ai_enabled = False
    payload.analysis = None
    mock_build.return_value = payload
    resp = client.post("/api/ai/analyze", json={"symbol": "2330", "market": "tw"})
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"]["code"] == "AI_DISABLED"


@patch("api.routers.analysis.build_dashboard_payload")
def test_dashboard_payload_returns_400_on_service_error(mock_build) -> None:
    mock_build.return_value = DashboardError(code="FETCH_FAILED", message="boom")
    resp = client.get("/api/dashboard/payload", params={"symbol": "2330", "market": "tw"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "FETCH_FAILED"
