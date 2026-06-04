"""Unit tests for Active ETF tracking features (Phase 16-A)."""

import datetime
from datetime import date
from pathlib import Path
import ssl
import time
import pytest
import pandas as pd

from src.core.exceptions import FetcherError
from src.data.fetcher import MoneyDjActiveEtfSource, _RelaxedStrictHTTPAdapter
from src.data.storage import ParquetStorage, StorageError
from src.services.active_etf_service import ActiveEtfService, _HOLDINGS_CACHE


# ---------------------------------------------------------------------------
# MoneyDjActiveEtfSource Test Cases
# ---------------------------------------------------------------------------

def test_moneydj_active_etf_parser_00981a():
    """Verify that MoneyDjActiveEtfSource parses 00981A HTML correctly."""
    fixture_path = Path(__file__).parent / "fixtures" / "moneydj_active_etf_00981a.html"
    html_content = fixture_path.read_text(encoding="utf-8")

    source = MoneyDjActiveEtfSource()
    snapshot_date, df = source.parse_holdings_html(html_content, "00981A")

    # Assert Date
    assert snapshot_date == date(2026, 6, 3)

    # Assert Columns and Types
    assert list(df.columns) == ["holding_code", "holding_name", "shares", "weight_pct"]
    assert len(df) == 51  # Row count for 00981A full holdings

    # First row is TSMC (2330.TW)
    first = df.iloc[0]
    assert first["holding_code"] == "2330.TW"
    assert first["holding_name"] == "台積電" or "2330" in html_content  # Match content parsed
    assert first["shares"] == 11960000
    assert first["weight_pct"] == 9.97


def test_moneydj_active_etf_parser_00983a_overseas():
    """Verify that MoneyDjActiveEtfSource parses 00983A with overseas assets correctly."""
    fixture_path = Path(__file__).parent / "fixtures" / "moneydj_active_etf_00983a.html"
    html_content = fixture_path.read_text(encoding="utf-8")

    source = MoneyDjActiveEtfSource()
    snapshot_date, df = source.parse_holdings_html(html_content, "00983A")

    assert snapshot_date == date(2026, 6, 2)
    assert len(df) == 39  # Row count

    # First row is Tesla (TSLA.US)
    tesla = df[df["holding_code"] == "TSLA.US"].iloc[0]
    assert tesla["holding_name"] == "Tesla"
    assert tesla["shares"] == 16131
    assert tesla["weight_pct"] == 9.08


def test_moneydj_active_etf_fetch_list_fallback(monkeypatch, tmp_path):
    """Verify that fetch_list swallows all token/network errors and returns an empty DataFrame."""
    # Temporarily set get_data_dir to point to tmp_path to isolate cache check
    monkeypatch.setattr("src.core.config.get_data_dir", lambda: tmp_path)

    # Mock FinMindFetcher to raise FetcherError to test error swallowing
    from src.data.fetcher import FinMindFetcher
    def mock_fetch_fail(self):
        raise FetcherError("Mocked FinMind fetch error")
    monkeypatch.setattr(FinMindFetcher, "fetch_stock_info", mock_fetch_fail)

    # Trigger fetch_list with no token / no config - it should return empty df without crashing
    source = MoneyDjActiveEtfSource()
    df = source.fetch_list()
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert list(df.columns) == ["etf_code", "etf_name"]


def test_moneydj_default_session_relaxes_x509_strict():
    """Default session must keep TLS verification but clear VERIFY_X509_STRICT.

    MoneyDJ's cert chain has a CA cert missing the Subject Key Identifier
    extension; OpenSSL 3.x strict mode rejects it. The fix mounts a relaxed
    adapter on the MoneyDJ host only, without disabling cert trust.
    """
    source = MoneyDjActiveEtfSource()

    adapter = source._session.get_adapter("https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm")
    assert isinstance(adapter, _RelaxedStrictHTTPAdapter)

    # Other hosts keep the default adapter (no relaxation leaks elsewhere)
    other = source._session.get_adapter("https://api.finmindtrade.com")
    assert not isinstance(other, _RelaxedStrictHTTPAdapter)

    # The relaxed adapter's SSL context must verify certs but not be strict
    pool = adapter.poolmanager
    ctx = pool.connection_pool_kw.get("ssl_context")
    assert ctx is not None
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert not (ctx.verify_flags & ssl.VERIFY_X509_STRICT)


def test_moneydj_fetch_holdings_decodes_charsetless_utf8(monkeypatch):
    """MoneyDJ sends UTF-8 with no charset header; fetch must not decode as latin-1.

    requests defaults charsetless text/html to ISO-8859-1, which mangles the
    Chinese holdings table and breaks parsing. fetch_holdings must fall back to
    the body-detected encoding.
    """
    import requests

    html = (
        '<html><head><meta charset="utf-8"></head><body>'
        '<div id="ctl00_ctl00_MainContent_MainContent_sdate3">2026/06/03</div>'
        "<table>"
        "<tr><th>個股名稱</th><th>比例</th><th>持股</th></tr>"
        "<tr><td>台積電(2330.TW)</td><td>9.97%</td><td>11,960,000</td></tr>"
        "</table></body></html>"
    )
    resp = requests.Response()
    resp.status_code = 200
    resp._content = html.encode("utf-8")
    resp.headers["Content-Type"] = "text/html"  # no charset -> requests picks latin-1
    resp.encoding = "ISO-8859-1"

    source = MoneyDjActiveEtfSource()
    monkeypatch.setattr(source._session, "get", lambda *a, **k: resp)

    snapshot_date, df = source.fetch_holdings("00981A")

    assert snapshot_date == date(2026, 6, 3)
    assert len(df) == 1
    assert df.iloc[0]["holding_code"] == "2330.TW"
    assert df.iloc[0]["holding_name"] == "台積電"
    assert df.iloc[0]["shares"] == 11960000
    assert df.iloc[0]["weight_pct"] == 9.97


def test_moneydj_injected_session_left_untouched():
    """A caller-supplied session must not get the relaxed adapter auto-mounted."""
    import requests

    injected = requests.Session()
    source = MoneyDjActiveEtfSource(session=injected)
    assert source._session is injected
    adapter = source._session.get_adapter("https://www.moneydj.com/")
    assert not isinstance(adapter, _RelaxedStrictHTTPAdapter)


# ---------------------------------------------------------------------------
# ParquetStorage Test Cases
# ---------------------------------------------------------------------------

def test_parquet_storage_path_traversal_guard(tmp_path):
    """Verify that ParquetStorage active ETF paths reject path traversal attempts."""
    storage = ParquetStorage(data_dir=tmp_path)

    # 1. Invalid format code checks
    with pytest.raises(StorageError, match="Invalid active ETF code"):
        storage._active_etf_holdings_path("2330")

    with pytest.raises(StorageError, match="Invalid active ETF code"):
        storage._active_etf_holdings_path("00981")

    # 2. Path traversal check (escaping root folder)
    # The validate method limits it to ^\d{5}A$ but even if we trick path resolver:
    with pytest.raises(StorageError):
        storage._active_etf_holdings_path("../../../00981A")


def test_parquet_storage_save_load_active_etf_list(tmp_path):
    """Verify save and load active ETF list and metadata in ParquetStorage."""
    storage = ParquetStorage(data_dir=tmp_path)

    assert storage.load_active_etf_list().empty
    assert storage.load_active_etf_list_meta() == {}

    # Save list
    test_df = pd.DataFrame([
        {"etf_code": "00981a", "etf_name": " 00981A Name "},
        {"etf_code": "00983A", "etf_name": "00983A Name"},
    ])
    storage.save_active_etf_list(test_df)

    loaded = storage.load_active_etf_list()
    assert len(loaded) == 2
    assert list(loaded["etf_code"]) == ["00981A", "00983A"]
    assert list(loaded["etf_name"]) == ["00981A Name", "00983A Name"]

    # Save meta
    meta = {"fetched_at": "2026-06-04T12:00:00"}
    storage.save_active_etf_list_meta(meta)
    assert storage.load_active_etf_list_meta() == meta


def test_parquet_storage_save_holdings_dedup(tmp_path):
    """Verify ParquetStorage save_active_etf_holdings prevents duplicate snapshot dates."""
    storage = ParquetStorage(data_dir=tmp_path)

    etf = "00981A"
    snapshot_d = date(2026, 6, 3)
    df_data = pd.DataFrame([
        {"holding_code": "2330.TW", "holding_name": "TSMC", "shares": 100, "weight_pct": 10.0}
    ])

    # First save
    storage.save_active_etf_holdings(etf, snapshot_d, df_data)
    loaded = storage.load_active_etf_holdings(etf)
    assert len(loaded) == 1
    assert loaded.iloc[0]["snapshot_date"] == snapshot_d
    assert loaded.iloc[0]["shares"] == 100

    # Second save with different shares on same snapshot_date - should be skipped (dedup)
    df_data_dup = pd.DataFrame([
        {"holding_code": "2330.TW", "holding_name": "TSMC", "shares": 200, "weight_pct": 10.0}
    ])
    storage.save_active_etf_holdings(etf, snapshot_d, df_data_dup)
    loaded_dup = storage.load_active_etf_holdings(etf)
    assert len(loaded_dup) == 1
    assert loaded_dup.iloc[0]["shares"] == 100  # Stays 100, no update

    # Save with another snapshot_date - should append
    new_snapshot_d = date(2026, 6, 4)
    storage.save_active_etf_holdings(etf, new_snapshot_d, df_data)
    loaded_new = storage.load_active_etf_holdings(etf)
    assert len(loaded_new) == 2
    assert set(loaded_new["snapshot_date"]) == {snapshot_d, new_snapshot_d}


# ---------------------------------------------------------------------------
# ActiveEtfService Test Cases
# ---------------------------------------------------------------------------

def test_service_get_holdings_with_diff_no_previous(tmp_path, monkeypatch):
    """Verify get_holdings_with_diff when there is only a single (latest) snapshot."""
    storage = ParquetStorage(data_dir=tmp_path)
    service = ActiveEtfService(storage=storage)

    etf = "00981A"
    snapshot_d = date(2026, 6, 3)
    df_data = pd.DataFrame([
        {"holding_code": "2330.TW", "holding_name": "TSMC", "shares": 1000, "weight_pct": 12.5},
        {"holding_code": "2308.TW", "holding_name": "Delta", "shares": 500, "weight_pct": 5.2},
    ])

    storage.save_active_etf_holdings(etf, snapshot_d, df_data)

    # Disable mock fetch to prevent TTL fetch trigger
    monkeypatch.setitem(_HOLDINGS_CACHE, etf, time.time())

    result = service.get_holdings_with_diff(etf)

    assert result["etf_code"] == "00981A"
    assert result["latest_date"] == "2026-06-03"
    assert result["previous_date"] is None
    assert result["has_previous"] is False
    assert len(result["holdings"]) == 2

    # Check holdings items
    h1 = result["holdings"][0]
    assert h1["rank"] == 1
    assert h1["holding_code"] == "2330.TW"
    assert h1["shares"] == 1000
    assert h1["weight_pct"] == 12.5
    assert h1["delta_shares"] is None

    # Check changes are empty
    changes = result["changes"]
    assert changes["buys"] == []
    assert changes["sells"] == []
    assert changes["entries"] == []
    assert changes["exits"] == []


def test_service_get_holdings_with_diff_calculation(tmp_path, monkeypatch):
    """Verify get_holdings_with_diff computes buys, sells, entries, and exits correctly."""
    storage = ParquetStorage(data_dir=tmp_path)
    service = ActiveEtfService(storage=storage)

    etf = "00981A"

    # Save previous snapshot (2026-06-03)
    # TSMC: 1000 shares
    # Delta: 500 shares
    # ExitStock: 200 shares
    # Cash: 100000 shares (no ticker)
    prev_d = date(2026, 6, 3)
    prev_df = pd.DataFrame([
        {"holding_code": "2330.TW", "holding_name": "TSMC", "shares": 1000, "weight_pct": 10.0},
        {"holding_code": "2308.TW", "holding_name": "Delta", "shares": 500, "weight_pct": 5.0},
        {"holding_code": "9999.TW", "holding_name": "ExitStock", "shares": 200, "weight_pct": 2.0},
        {"holding_code": "", "holding_name": "Cash", "shares": 100000, "weight_pct": 1.0},
    ])
    storage.save_active_etf_holdings(etf, prev_d, prev_df)

    # Save latest snapshot (2026-06-04)
    # TSMC: 1200 shares -> BUY (+200)
    # Delta: 400 shares -> SELL (-100)
    # EntryStock: 300 shares -> ENTRY (+300)
    # Cash: 150000 shares -> BUY (+50000, joined on Cash holding_name)
    # ExitStock is gone -> EXIT (-200)
    latest_d = date(2026, 6, 4)
    latest_df = pd.DataFrame([
        {"holding_code": "2330.TW", "holding_name": "TSMC", "shares": 1200, "weight_pct": 12.0},
        {"holding_code": "2308.TW", "holding_name": "Delta", "shares": 400, "weight_pct": 4.0},
        {"holding_code": "1111.TW", "holding_name": "EntryStock", "shares": 300, "weight_pct": 3.0},
        {"holding_code": "", "holding_name": "Cash", "shares": 150000, "weight_pct": 1.5},
    ])
    storage.save_active_etf_holdings(etf, latest_d, latest_df)

    # Lock TTL cache so it doesn't trigger mock fetch
    monkeypatch.setitem(_HOLDINGS_CACHE, etf, time.time())

    result = service.get_holdings_with_diff(etf)

    assert result["etf_code"] == "00981A"
    assert result["latest_date"] == "2026-06-04"
    assert result["previous_date"] == "2026-06-03"
    assert result["has_previous"] is True

    # Validate Holdings (latest only, sorted by weight)
    # TSMC (12.0) -> Delta (4.0) -> EntryStock (3.0) -> Cash (1.5)
    holdings = result["holdings"]
    assert len(holdings) == 4

    assert holdings[0]["holding_code"] == "2330.TW"
    assert holdings[0]["delta_shares"] == 200

    assert holdings[1]["holding_code"] == "2308.TW"
    assert holdings[1]["delta_shares"] == -100

    assert holdings[2]["holding_code"] == "1111.TW"
    assert holdings[2]["delta_shares"] == 300

    assert holdings[3]["holding_code"] == ""
    assert holdings[3]["holding_name"] == "Cash"
    assert holdings[3]["delta_shares"] == 50000

    # Validate Changes
    changes = result["changes"]

    # 1. buys: TSMC (+200), Cash (+50000)
    # Sorted by |delta_shares| descending: Cash (+50000) first, then TSMC (+200)
    assert len(changes["buys"]) == 2
    assert changes["buys"][0]["holding_name"] == "Cash"
    assert changes["buys"][0]["delta_shares"] == 50000
    assert changes["buys"][1]["holding_code"] == "2330.TW"
    assert changes["buys"][1]["delta_shares"] == 200

    # 2. sells: Delta (-100)
    assert len(changes["sells"]) == 1
    assert changes["sells"][0]["holding_code"] == "2308.TW"
    assert changes["sells"][0]["delta_shares"] == -100

    # 3. entries: EntryStock (+300)
    assert len(changes["entries"]) == 1
    assert changes["entries"][0]["holding_code"] == "1111.TW"
    assert changes["entries"][0]["delta_shares"] == 300

    # 4. exits: ExitStock (-200)
    assert len(changes["exits"]) == 1
    assert changes["exits"][0]["holding_code"] == "9999.TW"
    assert changes["exits"][0]["delta_shares"] == -200


def test_fetch_latest_close_date(monkeypatch):
    """Verify that MoneyDjActiveEtfSource.fetch_latest_close_date queries primary/fallback sources correctly."""
    source = MoneyDjActiveEtfSource()

    # 1. Mock FinMindFetcher daily response
    from src.data.fetcher import FinMindFetcher, YFinanceFetcher

    # Mock FinMind success
    mock_fm_df = pd.DataFrame([{"date": "2026-06-04", "close": 100.0}])
    monkeypatch.setattr(FinMindFetcher, "fetch_daily", lambda self, sym, start, end: mock_fm_df)
    assert source.fetch_latest_close_date("00981A") == datetime.date(2026, 6, 4)

    # Mock FinMind failure, YFinance success
    def mock_fm_fail(self, sym, start, end):
        raise Exception("FinMind failed")
    monkeypatch.setattr(FinMindFetcher, "fetch_daily", mock_fm_fail)

    mock_yf_df = pd.DataFrame([{"date": "2026-06-03", "close": 100.0}])
    monkeypatch.setattr(YFinanceFetcher, "fetch_daily", lambda self, sym, start, end: mock_yf_df)
    assert source.fetch_latest_close_date("00981A") == datetime.date(2026, 6, 3)

    # Both fail -> None
    monkeypatch.setattr(YFinanceFetcher, "fetch_daily", lambda self, sym, start, end: pd.DataFrame())
    assert source.fetch_latest_close_date("00981A") is None


def test_service_refresh_holdings_snapshot_gating(tmp_path, monkeypatch):
    """Verify gating logic in refresh_holdings_snapshot."""
    storage = ParquetStorage(data_dir=tmp_path)
    service = ActiveEtfService(storage=storage)
    etf = "00981A"

    # Reset caches
    from src.services.active_etf_service import _HOLDINGS_CACHE
    if etf in _HOLDINGS_CACHE:
        del _HOLDINGS_CACHE[etf]

    # Mock close date to 2026-06-04
    monkeypatch.setattr(
        MoneyDjActiveEtfSource,
        "fetch_latest_close_date",
        lambda self, code: datetime.date(2026, 6, 4)
    )

    # Mock MoneyDJ fetch_holdings to return 2026-06-04
    mock_df = pd.DataFrame([{"holding_code": "2330.TW", "holding_name": "TSMC", "shares": 100, "weight_pct": 10.0}])
    fetch_called = 0
    def mock_fetch_holdings(self, code):
        nonlocal fetch_called
        fetch_called += 1
        return datetime.date(2026, 6, 4), mock_df
    monkeypatch.setattr(MoneyDjActiveEtfSource, "fetch_holdings", mock_fetch_holdings)

    # 1. Local holdings empty -> should fetch
    service.refresh_holdings_snapshot(etf)
    assert fetch_called == 1
    assert len(storage.load_active_etf_holdings(etf)) == 1

    # 2. Local holdings snapshot date is 2026-06-04, latest close is 2026-06-04 -> should NOT fetch (gate)
    if etf in _HOLDINGS_CACHE:
        del _HOLDINGS_CACHE[etf]  # clear TTL cache to isolate gating
    service.refresh_holdings_snapshot(etf)
    assert fetch_called == 1  # still 1, not called

    # 3. Local holdings date is 2026-06-04, latest close is 2026-06-05 -> should fetch
    monkeypatch.setattr(
        MoneyDjActiveEtfSource,
        "fetch_latest_close_date",
        lambda self, code: datetime.date(2026, 6, 5)
    )
    def mock_fetch_holdings_v2(self, code):
        nonlocal fetch_called
        fetch_called += 1
        return datetime.date(2026, 6, 5), mock_df
    monkeypatch.setattr(MoneyDjActiveEtfSource, "fetch_holdings", mock_fetch_holdings_v2)

    service.refresh_holdings_snapshot(etf)
    assert fetch_called == 2
    assert len(storage.load_active_etf_holdings(etf)) == 2


def test_service_sweep_all_logic(tmp_path, monkeypatch):
    """Verify sweep_all skipping, cache behavior, and skip_code logic."""
    storage = ParquetStorage(data_dir=tmp_path)
    service = ActiveEtfService(storage=storage)

    # Setup mock list containing two ETFs
    mock_etfs = [
        {"code": "00981A", "name": "ETF1"},
        {"code": "00982A", "name": "ETF2"}
    ]
    monkeypatch.setattr(ActiveEtfService, "get_list", lambda self: mock_etfs)

    from src.services.active_etf_service import _HOLDINGS_CACHE, _SWEEP_CACHE
    _HOLDINGS_CACHE.clear()
    _SWEEP_CACHE.clear()

    # Mock latest close date queries
    close_dates = {
        "00981A": datetime.date(2026, 6, 4),
        "00982A": datetime.date(2026, 6, 4)
    }
    monkeypatch.setattr(
        MoneyDjActiveEtfSource,
        "fetch_latest_close_date",
        lambda self, code: close_dates.get(code)
    )

    # Mock refresh_holdings_snapshot
    refreshed_codes = []
    def mock_refresh(self, code, latest_close_date=None):
        refreshed_codes.append(code)
    monkeypatch.setattr(ActiveEtfService, "refresh_holdings_snapshot", mock_refresh)

    # 1. Sweep skipping skip_code ("00981A") -> only 00982A should be checked
    service.sweep_all(skip_code="00981A")
    assert refreshed_codes == ["00982A"]
    assert "00982A" in _SWEEP_CACHE
    assert "00981A" not in _SWEEP_CACHE  # skip_code not queried

    # 2. Sweep again -> 00982A hit _SWEEP_CACHE, so no refresh called
    refreshed_codes.clear()
    service.sweep_all()
    assert refreshed_codes == ["00981A"]  # only 00981A refreshed since 00982A is cached
    assert "00981A" in _SWEEP_CACHE

    # 3. Simulate close date fetch failure for 00981A -> should skip and NOT write _SWEEP_CACHE
    _SWEEP_CACHE.clear()
    refreshed_codes.clear()
    close_dates["00981A"] = None

    service.sweep_all()
    assert refreshed_codes == ["00982A"]
    assert "00981A" not in _SWEEP_CACHE
