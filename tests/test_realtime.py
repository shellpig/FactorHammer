from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from src.data.realtime import RealtimeFetcher, RealtimeQuote


@dataclass
class _DummyResponse:
    payload: dict

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class _DummySession:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[dict] = []

    def get(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.calls.append(kwargs)
        return _DummyResponse(payload=self.payload)


def _twse_payload(
    *,
    z: str = "101.5",
    y: str = "100.0",
    o: str = "99.0",
    h: str = "102.0",
    l: str = "98.0",
    v: str = "12345",
    t: str = "10:15:01",
    b: str = "101.5_101.0_100.5",
    a: str = "102.0_102.5_103.0",
    g: str = "200_180_160",
    f: str = "120_140_160",
    c: str = "2330",
    n: str = "台積電",
) -> dict:
    return {
        "msgArray": [
            {
                "c": c,
                "n": n,
                "z": z,
                "y": y,
                "o": o,
                "h": h,
                "l": l,
                "v": v,
                "t": t,
                "b": b,
                "a": a,
                "g": g,
                "f": f,
            }
        ]
    }


def test_parse_twse_response_normal() -> None:
    fetcher = RealtimeFetcher()
    quote = fetcher._parse_twse_response(_twse_payload())
    assert quote.symbol == "2330"
    assert quote.name == "台積電"
    assert quote.price == 101.5
    assert quote.yesterday_close == 100.0
    assert quote.open == 99.0
    assert quote.high == 102.0
    assert quote.low == 98.0
    assert quote.volume == 12345
    assert quote.timestamp == "10:15:01"


def test_parse_twse_response_no_trade() -> None:
    fetcher = RealtimeFetcher()
    quote = fetcher._parse_twse_response(_twse_payload(z="-", y="88.5"))
    assert quote.price == 88.5


def test_parse_five_levels() -> None:
    fetcher = RealtimeFetcher()
    quote = fetcher._parse_twse_response(_twse_payload())
    assert quote.best_bid == [101.5, 101.0, 100.5]
    assert quote.best_ask == [102.0, 102.5, 103.0]
    assert quote.best_bid_vol == [200, 180, 160]
    assert quote.best_ask_vol == [120, 140, 160]


def test_parse_five_levels_partial() -> None:
    fetcher = RealtimeFetcher()
    quote = fetcher._parse_twse_response(
        _twse_payload(
            b="101.5__-",
            a="102.0_",
            g="200__",
            f="_140",
        )
    )
    assert quote.best_bid == [101.5]
    assert quote.best_ask == [102.0]
    assert quote.best_bid_vol == [200]
    assert quote.best_ask_vol == [140]


def test_change_calculation() -> None:
    fetcher = RealtimeFetcher()
    quote = fetcher._parse_twse_response(_twse_payload(z="103.0", y="100.0"))
    assert quote.change == 3.0
    assert round(quote.change_pct, 4) == 3.0


def test_cache_hit_within_ttl() -> None:
    class _Clock:
        def __init__(self) -> None:
            self.t = 1000.0

        def __call__(self) -> float:
            return self.t

    clock = _Clock()
    fetcher = RealtimeFetcher(cache_ttl=10, clock=clock)
    calls = {"n": 0}

    def _fake_api(symbol: str):  # noqa: ARG001
        calls["n"] += 1
        return RealtimeQuote(
            symbol="2330",
            name="台積電",
            price=100.0,
            change=0.0,
            change_pct=0.0,
            open=100.0,
            high=100.0,
            low=100.0,
            yesterday_close=100.0,
            volume=1,
            timestamp="10:00:00",
        )

    fetcher._fetch_quote_from_api = _fake_api  # type: ignore[method-assign]

    _ = fetcher.fetch_quote("2330")
    clock.t = 1005.0
    _ = fetcher.fetch_quote("2330")
    assert calls["n"] == 1


def test_cache_miss_after_ttl() -> None:
    class _Clock:
        def __init__(self) -> None:
            self.t = 1000.0

        def __call__(self) -> float:
            return self.t

    clock = _Clock()
    fetcher = RealtimeFetcher(cache_ttl=10, clock=clock)
    calls = {"n": 0}

    def _fake_api(symbol: str):  # noqa: ARG001
        calls["n"] += 1
        return RealtimeQuote(
            symbol="2330",
            name="台積電",
            price=float(calls["n"]),
            change=0.0,
            change_pct=0.0,
            open=100.0,
            high=100.0,
            low=100.0,
            yesterday_close=100.0,
            volume=1,
            timestamp="10:00:00",
        )

    fetcher._fetch_quote_from_api = _fake_api  # type: ignore[method-assign]

    _ = fetcher.fetch_quote("2330")
    clock.t = 1011.0
    _ = fetcher.fetch_quote("2330")
    assert calls["n"] == 2


def test_market_map_tse() -> None:
    fetcher = RealtimeFetcher()
    fetcher._market_map = {"2330": "tse"}
    assert fetcher._build_ex_ch("2330") == "tse_2330.tw"


def test_market_map_otc() -> None:
    fetcher = RealtimeFetcher()
    fetcher._market_map = {"6547": "otc"}
    assert fetcher._build_ex_ch("6547") == "otc_6547.tw"


def test_market_map_fallback() -> None:
    fetcher = RealtimeFetcher()
    fetcher._market_map = {}
    fetcher.load_market_map = lambda: None  # type: ignore[method-assign]
    assert fetcher._build_ex_ch("9999") == "tse_9999.tw"


def test_bid_ask_structure_buy_dominant() -> None:
    fetcher = RealtimeFetcher()
    quote = RealtimeQuote(
        symbol="2330",
        name="台積電",
        price=101.0,
        change=1.0,
        change_pct=1.0,
        open=100.0,
        high=102.0,
        low=99.0,
        yesterday_close=100.0,
        volume=1000,
        timestamp="10:00:00",
        best_bid_vol=[400, 300, 200],
        best_ask_vol=[100, 100, 100],
    )
    out = fetcher.fetch_bid_ask_structure(quote)
    assert out.bid_ratio > 0.55
    assert out.label == "買盤較積極"


def test_bid_ask_structure_balanced() -> None:
    fetcher = RealtimeFetcher()
    quote = RealtimeQuote(
        symbol="2330",
        name="台積電",
        price=100.5,
        change=0.5,
        change_pct=0.5,
        open=100.0,
        high=101.0,
        low=99.0,
        yesterday_close=100.0,
        volume=1000,
        timestamp="10:00:00",
        best_bid_vol=[100, 100, 100],
        best_ask_vol=[100, 100, 100],
    )
    out = fetcher.fetch_bid_ask_structure(quote)
    assert out.label == "多空均衡"
    assert out.bid_ratio == 0.5


def test_is_market_open_detection() -> None:
    fetcher = RealtimeFetcher()
    trading_now = datetime(2026, 5, 11, 10, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    assert fetcher._is_market_open("09:00:00", now=trading_now) is True
    assert fetcher._is_market_open("13:30:00", now=trading_now) is True
    assert fetcher._is_market_open("08:59:59", now=trading_now) is False
    assert fetcher._is_market_open("13:30:01", now=trading_now) is False


def test_is_market_open_false_on_weekend_even_if_quote_time_is_intraday() -> None:
    fetcher = RealtimeFetcher()
    sunday_night = datetime(2026, 5, 10, 21, 17, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    assert fetcher._is_market_open("10:15:01", now=sunday_night) is False


def test_is_market_open_false_after_hours_even_if_quote_time_is_intraday() -> None:
    fetcher = RealtimeFetcher()
    weekday_night = datetime(2026, 5, 11, 21, 17, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    assert fetcher._is_market_open("10:15:01", now=weekday_night) is False
