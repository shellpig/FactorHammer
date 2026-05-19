"""Tests for src/services/dividend_policy_service.py (Phase 11-D)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.services.dividend_policy_service import (
    _load_cache,
    extract_goodinfo_dividend_policy_from_html,
    fetch_goodinfo_dividend_policy_html,
    get_goodinfo_dividend_policy,
)

FIXTURE_HTML = (Path(__file__).parent.parent / "fixtures" / "goodinfo_dividend_policy_sample.html").read_text(
    encoding="utf-8"
)

TODAY_2026 = pd.Timestamp("2026-05-18", tz="Asia/Taipei")


# ---------------------------------------------------------------------------
# Parser tests (11-D-P1 ~ 11-D-P5)
# ---------------------------------------------------------------------------


def test_parser_extracts_year_cash_stock(tmp_path: Path) -> None:
    """11-D-P1: fixture HTML parses year, cash_dividend, stock_dividend."""
    df = extract_goodinfo_dividend_policy_from_html(FIXTURE_HTML)
    assert not df.empty
    assert set(df.columns) >= {"year", "cash_dividend", "stock_dividend"}
    assert 2026 in df["year"].values
    row = df[df["year"] == 2026].iloc[0]
    assert row["cash_dividend"] == pytest.approx(32.0)
    assert row["stock_dividend"] == pytest.approx(10.0)


def test_parser_multiindex_columns() -> None:
    """11-D-P2: MultiIndex columns are flattened, keywords still found."""
    html = """
    <table>
      <thead>
        <tr><th colspan="2">股利資訊</th></tr>
        <tr><th>股利發放期間</th><th>現金股利(元)</th><th>股票股利(元)</th></tr>
      </thead>
      <tbody>
        <tr><td>2025年</td><td>20.00</td><td>0.00</td></tr>
      </tbody>
    </table>
    """
    df = extract_goodinfo_dividend_policy_from_html(html)
    assert not df.empty
    assert 2025 in df["year"].values


def test_parser_normalizes_dashes_and_commas() -> None:
    """11-D-P3: dashes treated as null, comma numbers normalized."""
    html = """
    <table>
      <thead>
        <tr><th>股利發放期間</th><th>現金股利</th><th>股票股利</th></tr>
      </thead>
      <tbody>
        <tr><td>2024年</td><td>1,234.50</td><td>--</td></tr>
        <tr><td>2023年</td><td>-</td><td>5.00</td></tr>
      </tbody>
    </table>
    """
    df = extract_goodinfo_dividend_policy_from_html(html)
    assert 2024 in df["year"].values
    row_2024 = df[df["year"] == 2024].iloc[0]
    assert row_2024["cash_dividend"] == pytest.approx(1234.5)
    assert pd.isna(row_2024["stock_dividend"])
    row_2023 = df[df["year"] == 2023].iloc[0]
    assert pd.isna(row_2023["cash_dividend"])
    assert row_2023["stock_dividend"] == pytest.approx(5.0)


def test_parser_deduplicates_by_year_keeps_last() -> None:
    """11-D-P4: multiple tables merged, deduplicated by year, latest kept."""
    html = """
    <table>
      <thead><tr><th>股利發放期間</th><th>現金股利</th><th>股票股利</th></tr></thead>
      <tbody>
        <tr><td>2025年</td><td>10.00</td><td>0.00</td></tr>
      </tbody>
    </table>
    <table>
      <thead><tr><th>股利發放期間</th><th>現金股利</th><th>股票股利</th></tr></thead>
      <tbody>
        <tr><td>2025年</td><td>20.00</td><td>5.00</td></tr>
        <tr><td>2026年</td><td>30.00</td><td>0.00</td></tr>
      </tbody>
    </table>
    """
    df = extract_goodinfo_dividend_policy_from_html(html)
    assert df["year"].value_counts().max() == 1  # no duplicates
    row_2025 = df[df["year"] == 2025].iloc[0]
    # last occurrence wins
    assert row_2025["cash_dividend"] == pytest.approx(20.0)


def test_parser_no_matching_table_returns_empty() -> None:
    """11-D-P5: HTML with no dividend table returns empty DataFrame."""
    html = "<html><body><table><tr><th>標題</th><td>值</td></tr></table></body></html>"
    df = extract_goodinfo_dividend_policy_from_html(html)
    assert df.empty


def test_parser_strips_float_decimal_in_period_and_payment_raw() -> None:
    """When read_html infers a year-only column as float64, '2025' must not be
    rendered as '2025.0' in period / payment_raw (display-facing fields)."""
    html = """
    <table>
      <thead>
        <tr><th>股利發放期間</th><th>股利所屬期間</th><th>現金股利</th><th>股票股利</th></tr>
      </thead>
      <tbody>
        <tr><td>2026</td><td>2025</td><td>6.6</td><td>0</td></tr>
        <tr><td>2025</td><td>2024</td><td>5.296</td><td>0</td></tr>
      </tbody>
    </table>
    """
    df = extract_goodinfo_dividend_policy_from_html(html)
    for value in df["period"].dropna().tolist():
        assert not value.endswith(".0"), f"period must not carry float-decimal suffix: {value!r}"
    for value in df["payment_raw"].dropna().tolist():
        assert not value.endswith(".0"), f"payment_raw must not carry float-decimal suffix: {value!r}"


def test_service_selects_oldest_undetermined_goodinfo_period_2330() -> None:
    """Goodinfo detail rows: choose older unpaid period, not year total or newest unpaid period."""
    html = """
    <table>
      <thead>
        <tr>
          <th rowspan="3">股利發放期間</th>
          <th rowspan="3">股利所屬期間</th>
          <th colspan="6">股東股利 (元/股)</th>
        </tr>
        <tr>
          <th colspan="3">現金股利</th>
          <th colspan="3">股票股利</th>
        </tr>
        <tr>
          <th>盈餘</th><th>公積</th><th>合計</th>
          <th>盈餘</th><th>公積</th><th>合計</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>2026</td><td>-</td><td>19</td><td>0</td><td>19</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>未定</td><td>26Q1</td><td>7</td><td>0</td><td>7</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>未定</td><td>25Q4</td><td>6</td><td>0</td><td>6</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>3/17</td><td>25Q3</td><td>6</td><td>0</td><td>6</td><td>0</td><td>0</td><td>0</td></tr>
      </tbody>
    </table>
    """
    with (
        patch("src.services.dividend_policy_service._load_cache", return_value=None),
        patch("src.services.dividend_policy_service._save_cache"),
        patch(
            "src.services.dividend_policy_service.fetch_goodinfo_dividend_policy_html",
            return_value=html,
        ),
    ):
        result = get_goodinfo_dividend_policy("2330", today=TODAY_2026)

    assert result["status"] == "current_year"
    assert result["year"] == 2026
    assert result["period"] == "25Q4"
    assert result["payment_status"] == "undetermined"
    assert result["cash_dividend"] == pytest.approx(6.0)
    assert result["stock_dividend"] == pytest.approx(0.0)


def test_service_selects_undetermined_goodinfo_half_year_period_3293() -> None:
    html = """
    <table>
      <thead>
        <tr>
          <th rowspan="3">股利發放期間</th>
          <th rowspan="3">股利所屬期間</th>
          <th colspan="6">股東股利 (元/股)</th>
        </tr>
        <tr>
          <th colspan="3">現金股利</th>
          <th colspan="3">股票股利</th>
        </tr>
        <tr>
          <th>盈餘</th><th>公積</th><th>合計</th>
          <th>盈餘</th><th>公積</th><th>合計</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>2026</td><td>-</td><td>36</td><td>0</td><td>36</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>未定</td><td>25H2</td><td>36</td><td>0</td><td>36</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>無</td><td>25H1</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
      </tbody>
    </table>
    """
    with (
        patch("src.services.dividend_policy_service._load_cache", return_value=None),
        patch("src.services.dividend_policy_service._save_cache"),
        patch(
            "src.services.dividend_policy_service.fetch_goodinfo_dividend_policy_html",
            return_value=html,
        ),
    ):
        result = get_goodinfo_dividend_policy("3293", today=TODAY_2026)

    assert result["status"] == "current_year"
    assert result["year"] == 2026
    assert result["period"] == "25H2"
    assert result["payment_status"] == "undetermined"
    assert result["cash_dividend"] == pytest.approx(36.0)
    assert result["stock_dividend"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# No-undetermined → not_found (0050-like scenario)
# ---------------------------------------------------------------------------


def test_service_all_paid_returns_not_found_0050() -> None:
    """0050-like: all rows have payment dates (none undetermined) → not_found."""
    html = """
    <table>
      <thead>
        <tr>
          <th rowspan="3">股利發放期間</th>
          <th rowspan="3">股利所屬期間</th>
          <th colspan="3">現金股利</th>
          <th colspan="3">股票股利</th>
        </tr>
        <tr>
          <th>盈餘</th><th>公積</th><th>合計</th>
          <th>盈餘</th><th>公積</th><th>合計</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>2026</td><td>-</td><td>1</td><td>0</td><td>1</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>1/22</td><td>25H2</td><td>1</td><td>0</td><td>1</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>2025</td><td>-</td><td>3.06</td><td>0</td><td>3.06</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>7/21</td><td>25H1</td><td>0.36</td><td>0</td><td>0.36</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>1/17</td><td>24H2</td><td>2.7</td><td>0</td><td>2.7</td><td>0</td><td>0</td><td>0</td></tr>
      </tbody>
    </table>
    """
    with (
        patch("src.services.dividend_policy_service._load_cache", return_value=None),
        patch("src.services.dividend_policy_service._save_cache"),
        patch(
            "src.services.dividend_policy_service.fetch_goodinfo_dividend_policy_html",
            return_value=html,
        ),
    ):
        result = get_goodinfo_dividend_policy("0050", today=TODAY_2026)

    assert result["status"] == "not_found"


def test_service_future_payment_date_selected_00929() -> None:
    """00929-like: no undetermined, but 5/20 is a future date → pick it."""
    html = """
    <table>
      <thead>
        <tr>
          <th rowspan="3">股利發放期間</th>
          <th rowspan="3">股利所屬期間</th>
          <th colspan="6">股東股利 (元/股)</th>
        </tr>
        <tr>
          <th colspan="3">現金股利</th>
          <th colspan="3">股票股利</th>
        </tr>
        <tr>
          <th>盈餘</th><th>公積</th><th>合計</th>
          <th>盈餘</th><th>公積</th><th>合計</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>2026</td><td>-</td><td>0.57</td><td>0</td><td>0.57</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>5/20</td><td>26M04</td><td>0.13</td><td>0</td><td>0.13</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>4/21</td><td>26M03</td><td>0.13</td><td>0</td><td>0.13</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>3/18</td><td>26M02</td><td>0.11</td><td>0</td><td>0.11</td><td>0</td><td>0</td><td>0</td></tr>
      </tbody>
    </table>
    """
    with (
        patch("src.services.dividend_policy_service._load_cache", return_value=None),
        patch("src.services.dividend_policy_service._save_cache"),
        patch(
            "src.services.dividend_policy_service.fetch_goodinfo_dividend_policy_html",
            return_value=html,
        ),
    ):
        result = get_goodinfo_dividend_policy("00929", today=TODAY_2026)

    assert result["status"] == "current_year"
    assert result["period"] == "26M04"
    assert result["cash_dividend"] == pytest.approx(0.13)
    assert result["payment_date"] == "2026-05-20"


def test_service_selects_annual_only_table_3711() -> None:
    """3711-like: Goodinfo only has annual rows (no Q/H/M detail). The current-year
    row has 股利發放期間=2026 (bare year, no M/DD, no 未定) and 股利所屬期間=2025.
    Should be recognised as pending current-year dividend."""
    html = """
    <table>
      <thead>
        <tr>
          <th rowspan="3">股利發放期間</th>
          <th rowspan="3">股利所屬期間</th>
          <th colspan="6">股東股利 (元/股)</th>
        </tr>
        <tr>
          <th colspan="3">現金股利</th>
          <th colspan="3">股票股利</th>
        </tr>
        <tr>
          <th>盈餘</th><th>公積</th><th>合計</th>
          <th>盈餘</th><th>公積</th><th>合計</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>2026</td><td>2025</td><td>6.6</td><td>0</td><td>6.6</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>2025</td><td>2024</td><td>5.296</td><td>0</td><td>5.296</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>2024</td><td>2023</td><td>5.202</td><td>0</td><td>5.202</td><td>0</td><td>0</td><td>0</td></tr>
        <tr><td>2023</td><td>2022</td><td>8.793</td><td>0</td><td>8.793</td><td>0</td><td>0</td><td>0</td></tr>
      </tbody>
    </table>
    """
    with (
        patch("src.services.dividend_policy_service._load_cache", return_value=None),
        patch("src.services.dividend_policy_service._save_cache"),
        patch(
            "src.services.dividend_policy_service.fetch_goodinfo_dividend_policy_html",
            return_value=html,
        ),
    ):
        result = get_goodinfo_dividend_policy("3711", today=TODAY_2026)

    assert result["status"] == "current_year"
    assert result["year"] == 2026
    assert result["period"] == "2025"
    assert result["payment_status"] == "undetermined"
    assert result["payment_date"] is None
    assert result["cash_dividend"] == pytest.approx(6.6)
    assert result["stock_dividend"] == pytest.approx(0.0)


def test_service_annual_only_table_past_years_not_selected() -> None:
    """Annual-only table where the latest 股利發放期間 < today.year → not_found."""
    html = """
    <table>
      <thead>
        <tr>
          <th rowspan="3">股利發放期間</th>
          <th rowspan="3">股利所屬期間</th>
          <th colspan="3">現金股利</th>
        </tr>
        <tr>
          <th>盈餘</th><th>公積</th><th>合計</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>2025</td><td>2024</td><td>5.296</td><td>0</td><td>5.296</td></tr>
        <tr><td>2024</td><td>2023</td><td>5.202</td><td>0</td><td>5.202</td></tr>
      </tbody>
    </table>
    """
    with (
        patch("src.services.dividend_policy_service._load_cache", return_value=None),
        patch("src.services.dividend_policy_service._save_cache"),
        patch(
            "src.services.dividend_policy_service.fetch_goodinfo_dividend_policy_html",
            return_value=html,
        ),
    ):
        result = get_goodinfo_dividend_policy("0000", today=TODAY_2026)

    assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# Service tests (11-D-S1 ~ 11-D-S7)
# ---------------------------------------------------------------------------


def _make_service_mocks(has_cache: bool = False, cached_payload: dict | None = None):
    """Helper returning (mock_load_cache, mock_save_cache, mock_fetch)."""
    mock_load = MagicMock(return_value=cached_payload if has_cache else None)
    mock_save = MagicMock()
    return mock_load, mock_save


def test_service_current_year_no_undetermined_returns_not_found(tmp_path: Path) -> None:
    """11-D-S3: Goodinfo has current-year rows but none undetermined → not_found."""
    with (
        patch("src.services.dividend_policy_service._load_cache", return_value=None),
        patch("src.services.dividend_policy_service._save_cache"),
        patch(
            "src.services.dividend_policy_service.fetch_goodinfo_dividend_policy_html",
            return_value=FIXTURE_HTML,
        ),
    ):
        result = get_goodinfo_dividend_policy("3293", today=TODAY_2026)

    assert result["status"] == "not_found"


def test_service_stale_no_undetermined_returns_not_found(tmp_path: Path) -> None:
    """11-D-S4: Goodinfo latest year < today and no undetermined → not_found."""
    html_2025 = """
    <table>
      <thead><tr><th>股利發放期間</th><th>現金股利</th><th>股票股利</th></tr></thead>
      <tbody><tr><td>2025年</td><td>15.00</td><td>0.00</td></tr></tbody>
    </table>
    """
    with (
        patch("src.services.dividend_policy_service._load_cache", return_value=None),
        patch("src.services.dividend_policy_service._save_cache"),
        patch(
            "src.services.dividend_policy_service.fetch_goodinfo_dividend_policy_html",
            return_value=html_2025,
        ),
    ):
        result = get_goodinfo_dividend_policy("2330", today=TODAY_2026)

    assert result["status"] == "not_found"


def test_service_fetch_failed_returns_200_compatible_status() -> None:
    """11-D-S5: fetch/Playwright failure → status fetch_failed, no exception raised."""
    with (
        patch("src.services.dividend_policy_service._load_cache", return_value=None),
        patch("src.services.dividend_policy_service._save_cache"),
        patch(
            "src.services.dividend_policy_service.fetch_goodinfo_dividend_policy_html",
            side_effect=RuntimeError("playwright not installed"),
        ),
    ):
        result = get_goodinfo_dividend_policy("2330", today=TODAY_2026)

    assert result["status"] == "fetch_failed"
    assert "goodinfo.tw" in result["source_url"]


def test_service_stock_dividend_defaults_to_zero_when_absent() -> None:
    """11-D-S6: stock_dividend column missing → fallback 0.0."""
    html_no_stock = """
    <table>
      <thead>
        <tr><th>股利發放期間</th><th>股利所屬期間</th><th>現金股利</th></tr>
      </thead>
      <tbody>
        <tr><td>2026</td><td>-</td><td>20.00</td></tr>
        <tr><td>未定</td><td>25H2</td><td>10.00</td></tr>
      </tbody>
    </table>
    """
    with (
        patch("src.services.dividend_policy_service._load_cache", return_value=None),
        patch("src.services.dividend_policy_service._save_cache"),
        patch(
            "src.services.dividend_policy_service.fetch_goodinfo_dividend_policy_html",
            return_value=html_no_stock,
        ),
    ):
        result = get_goodinfo_dividend_policy("2330", today=TODAY_2026)

    assert result["status"] == "current_year"
    assert result["stock_dividend"] == pytest.approx(0.0)


def test_service_cache_hit_skips_fetch() -> None:
    """11-D-S7: cache hit → fetch is never called."""
    cached = {
        "status": "current_year",
        "year": 2026,
        "cash_dividend": 29.0,
        "stock_dividend": 0.0,
        "source_url": "https://goodinfo.tw/tw/StockDividendPolicy.asp?STOCK_ID=3293",
        "source_note": "此為網頁抓取資料，請自行前往來源確認",
    }
    mock_fetch = MagicMock()
    with (
        patch("src.services.dividend_policy_service._load_cache", return_value=cached),
        patch("src.services.dividend_policy_service.fetch_goodinfo_dividend_policy_html", mock_fetch),
    ):
        result = get_goodinfo_dividend_policy("3293", today=TODAY_2026)

    mock_fetch.assert_not_called()
    assert result["year"] == 2026


def test_service_not_found_when_no_table() -> None:
    """11-D-P5 via service: empty parse → not_found status."""
    html_empty = "<html><body><p>no table here</p></body></html>"
    with (
        patch("src.services.dividend_policy_service._load_cache", return_value=None),
        patch("src.services.dividend_policy_service._save_cache"),
        patch(
            "src.services.dividend_policy_service.fetch_goodinfo_dividend_policy_html",
            return_value=html_empty,
        ),
    ):
        result = get_goodinfo_dividend_policy("9999", today=TODAY_2026)

    assert result["status"] == "not_found"


def test_legacy_cache_without_schema_version_is_ignored(tmp_path: Path) -> None:
    """Old fetch_failed/not_found cache must not hide parser/fetcher fixes forever."""
    cache_dir = tmp_path / "cache" / "goodinfo_dividend_policy"
    cache_dir.mkdir(parents=True)
    (cache_dir / "2330_2026-05-18.json").write_text(
        json.dumps(
            {
                "status": "fetch_failed",
                "year": None,
                "cash_dividend": None,
                "stock_dividend": None,
                "source_url": "https://goodinfo.tw/tw/StockDividendPolicy.asp?STOCK_ID=2330",
                "source_note": "此為網頁抓取資料，請自行前往來源確認",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with patch("src.services.dividend_policy_service.get_data_dir", return_value=tmp_path):
        assert _load_cache("2330", TODAY_2026) is None


def test_fetch_html_uses_requests_before_playwright() -> None:
    """Goodinfo static HTML can be fetched without requiring Playwright in the venv."""
    response = MagicMock()
    response.text = "<html><table><tr><th>股利發放期間</th></tr></table></html>"
    response.apparent_encoding = "utf-8"
    response.raise_for_status.return_value = None
    session = MagicMock()
    session.get.return_value = response

    with patch("src.services.dividend_policy_service.requests.Session", return_value=session):
        html = fetch_goodinfo_dividend_policy_html("2330")

    assert "股利發放期間" in html
    session.get.assert_called_once()


def test_fetch_html_handles_goodinfo_client_key_reinit() -> None:
    init_response = MagicMock()
    init_response.text = """
    <script>
    arr[0] = '4.8'; arr[1] = '38079.6787363216'; arr[2] = '46968.5676252104';
    window.location.replace('StockDividendPolicy.asp?STOCK_ID=2330&REINIT=46160.4868171296');
    </script>
    """
    init_response.apparent_encoding = "utf-8"
    init_response.raise_for_status.return_value = None

    table_response = MagicMock()
    table_response.text = "<html><table><tr><th>股利發放期間</th><th>現金股利</th></tr></table></html>"
    table_response.apparent_encoding = "utf-8"
    table_response.raise_for_status.return_value = None

    session = MagicMock()
    session.get.side_effect = [init_response, table_response]

    with patch("src.services.dividend_policy_service.requests.Session", return_value=session):
        html = fetch_goodinfo_dividend_policy_html("2330")

    assert "股利發放期間" in html
    assert session.get.call_count == 2
    assert "REINIT=46160.4868171296" in session.get.call_args_list[1].args[0]
    session.cookies.set.assert_called_once()
