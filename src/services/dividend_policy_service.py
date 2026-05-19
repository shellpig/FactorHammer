"""Goodinfo 股利政策 fallback service (Phase 11-D).

Fetches Goodinfo dividend policy page when no official future ex-dividend
data is found in local parquet.  Results are cached per symbol per day so
that only one network fetch is attempted.

Playwright is an optional dependency — if it is not installed the service
gracefully returns status="fetch_failed" without raising.
"""

from __future__ import annotations

import io
import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.core.config import get_data_dir

_GOODINFO_URL_TEMPLATE = "https://goodinfo.tw/tw/StockDividendPolicy.asp?STOCK_ID={symbol}"
_SOURCE_NOTE = "此為網頁抓取資料，請自行前往來源確認"
_CACHE_SCHEMA_VERSION = 7
_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


def _cache_path(symbol: str, today: pd.Timestamp) -> Path:
    date_str = today.strftime("%Y-%m-%d")
    return get_data_dir() / "cache" / "goodinfo_dividend_policy" / f"{symbol}_{date_str}.json"


def _load_cache(symbol: str, today: pd.Timestamp) -> dict[str, Any] | None:
    path = _cache_path(symbol, today)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if payload.get("_schema_version") != _CACHE_SCHEMA_VERSION:
        return None
    payload.pop("_schema_version", None)
    return payload


def _save_cache(symbol: str, today: pd.Timestamp, payload: dict[str, Any]) -> None:
    path = _cache_path(symbol, today)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: write to temp then replace
    tmp = Path(tempfile.mktemp(dir=path.parent, prefix=f"{symbol}_", suffix=".json.tmp"))
    stored_payload = {"_schema_version": _CACHE_SCHEMA_VERSION, **payload}
    try:
        tmp.write_text(json.dumps(stored_payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _normalize_text(value: Any) -> str:
    text = str(value).replace("\u3000", " ").strip()
    # pandas read_html may infer integer-only columns as float64, turning a
    # cell like "2025" into "2025.0" after str(). Strip the trailing .0 so
    # period / payment_raw render cleanly and match year-only regexes.
    m = re.fullmatch(r"(-?\d+)\.0+", text)
    return m.group(1) if m else text


def _period_sort_key(value: Any) -> tuple[int, int, str]:
    text = _normalize_text(value).upper()
    match = re.search(r"(\d{2})([QH])([1-4])", text)
    if not match:
        return (9999, 99, text)
    year = int(match.group(1))
    kind = match.group(2)
    index = int(match.group(3))
    order = index if kind == "Q" else index * 2
    return (year, order, text)


def _parse_payment_date(raw: str, year: int) -> pd.Timestamp | None:
    """Parse 'M/DD' or 'MM/DD' from payment_raw into a date with the given year."""
    m = re.search(r"(\d{1,2})/(\d{1,2})", raw)
    if m is None:
        return None
    try:
        return pd.Timestamp(year=year, month=int(m.group(1)), day=int(m.group(2)), tz="Asia/Taipei")
    except (ValueError, OverflowError):
        return None


def _is_bare_year_payment(payment_raw: str) -> bool:
    """Detect payment_raw that contains only a 4-digit year (e.g. '2026' / '2026年')."""
    return re.fullmatch(r"\s*\d{4}\s*年?\s*", payment_raw) is not None


def _is_future_payment(payment_raw: str, year_in_row: int, today: pd.Timestamp) -> bool:
    """True when payment_raw describes a current/future pending dividend."""
    parsed = _parse_payment_date(payment_raw, year_in_row)
    if parsed is not None:
        return parsed >= today.normalize()
    # Annual-summary symbols (e.g. 3711) only show 股利發放期間 as bare year and
    # 股利所屬期間 as the fiscal year. When the dividend year is current/future
    # and no M/DD has been announced, treat it as a pending payment.
    if _is_bare_year_payment(payment_raw):
        return year_in_row >= today.year
    return False


def _find_first_column(columns: pd.Index, keywords: tuple[str, ...], *, exclude: tuple[str, ...] = ()) -> Any | None:
    for col in columns:
        text = str(col)
        if all(kw in text for kw in keywords) and not any(kw in text for kw in exclude):
            return col
    return None


def _find_dividend_column(columns: pd.Index, dividend_kind: str) -> Any | None:
    candidates = [col for col in columns if dividend_kind in str(col)]
    if not candidates:
        return None
    total = [col for col in candidates if "合計" in str(col)]
    return total[0] if total else candidates[0]


def _looks_like_goodinfo_table(html: str) -> bool:
    return any(keyword in html for keyword in ("股利發放期間", "現金股利", "股票股利", "股利政策"))


def _decode_response_text(response: requests.Response) -> str:
    if response.apparent_encoding:
        response.encoding = response.apparent_encoding
    return response.text


def _client_key_from_init_html(html: str) -> tuple[str, str] | None:
    reinit = re.search(r"REINIT=([0-9.]+)", html)
    values = re.findall(r"arr\[(\d+)\] = '([^']*)'", html)
    if reinit is None or not values:
        return None

    arr = [""] * 8
    for index, value in values:
        idx = int(index)
        if 0 <= idx < len(arr):
            arr[idx] = value

    # Goodinfo's initial JS stores browser timezone offset and Excel-style day.
    # Taiwan local machines use -480; this is enough for the CLIENT_KEY gate.
    timezone_offset_minutes = -480
    arr[3] = str(timezone_offset_minutes)
    arr[4] = str(time.time() / 86400 + 25569 - timezone_offset_minutes / 1440)
    for idx in (5, 6, 7):
        arr[idx] = arr[idx] or "0"
    return "|".join(arr), reinit.group(1)


def extract_goodinfo_dividend_policy_from_html(html: str) -> pd.DataFrame:
    """Parse Goodinfo dividend policy HTML and return a DataFrame with columns:
    year (int), cash_dividend (float | None), stock_dividend (float | None).

    Returns empty DataFrame when no usable table is found.
    """
    try:
        tables = pd.read_html(io.StringIO(html), flavor="lxml")
    except Exception:
        return pd.DataFrame(columns=["year", "cash_dividend", "stock_dividend"])

    frames: list[pd.DataFrame] = []
    for tbl in tables:
        # Flatten MultiIndex columns
        if isinstance(tbl.columns, pd.MultiIndex):
            tbl.columns = pd.Index([" ".join(str(c) for c in col).strip() for col in tbl.columns])

        col_str = " ".join(str(c) for c in tbl.columns)
        # Accept only tables that mention dividend-related keywords
        if not any(kw in col_str for kw in ("現金股利", "股票股利", "股利", "發放", "期間")):
            continue

        # Identify date/period columns. Goodinfo uses "股利發放期間" for payment status
        # and "股利所屬期間" for rows like 25Q4 / 25H2.
        year_col = _find_first_column(tbl.columns, ("股利", "發放", "期間")) or tbl.columns[0]
        period_col = _find_first_column(tbl.columns, ("股利", "所屬", "期間"))

        # Identify cash / stock dividend columns
        cash_col = _find_dividend_column(tbl.columns, "現金股利")
        stock_col = _find_dividend_column(tbl.columns, "股票股利")

        if cash_col is None and stock_col is None:
            continue

        def _clean_numeric(series: pd.Series) -> pd.Series:
            s = series.astype(str).str.replace(",", "", regex=False)
            s = s.str.replace(r"^-+$", "", regex=True)  # treat "-" / "--" as empty
            return pd.to_numeric(s, errors="coerce")

        def _extract_year(series: pd.Series) -> pd.Series:
            extracted = series.astype(str).str.extract(r"(\d{4})", expand=False)
            return pd.to_numeric(extracted, errors="coerce")

        frame = pd.DataFrame()
        payment_raw = tbl[year_col].map(_normalize_text)
        frame["year"] = _extract_year(tbl[year_col]).ffill()
        frame["period"] = tbl[period_col].map(_normalize_text) if period_col is not None else None
        frame["payment_status"] = payment_raw.map(lambda value: "undetermined" if "未定" in value else None)
        frame["payment_raw"] = payment_raw
        frame["cash_dividend"] = _clean_numeric(tbl[cash_col]) if cash_col is not None else None
        frame["stock_dividend"] = _clean_numeric(tbl[stock_col]) if stock_col is not None else None
        frame = frame.dropna(subset=["year"])
        frame["year"] = frame["year"].astype(int)
        frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=["year", "cash_dividend", "stock_dividend"])

    combined = pd.concat(frames, ignore_index=True)
    # Deduplicate by year: keep latest (last occurrence after sort)
    summary = combined[combined["period"].fillna("").isin(["", "-"])].copy()
    details = combined[~combined["period"].fillna("").isin(["", "-"])].copy()
    if summary.empty:
        summary = combined.copy()
    summary = summary.sort_values("year").drop_duplicates(subset=["year"], keep="last")
    combined = pd.concat([summary, details], ignore_index=True)
    return combined.reset_index(drop=True)


def fetch_goodinfo_dividend_policy_html(symbol: str) -> str:
    """Fetch Goodinfo dividend policy page HTML.

    Requests is tried first because the dividend policy table is server-rendered
    in normal cases. Playwright remains an optional fallback for page changes.
    """
    url = _GOODINFO_URL_TEMPLATE.format(symbol=symbol)

    try:
        session = requests.Session()
        response = session.get(url, timeout=15, headers=_REQUEST_HEADERS)
        response.raise_for_status()
        html = _decode_response_text(response)
        if _looks_like_goodinfo_table(html):
            return html

        init = _client_key_from_init_html(html)
        if init is not None:
            client_key, reinit = init
            session.cookies.set("CLIENT_KEY", client_key, domain="goodinfo.tw", path="/")
            separator = "&" if "?" in url else "?"
            response = session.get(f"{url}{separator}REINIT={reinit}", timeout=15, headers=_REQUEST_HEADERS)
            response.raise_for_status()
            html = _decode_response_text(response)
            if len(html) > 10_000 or _looks_like_goodinfo_table(html):
                return html
    except Exception:
        pass

    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError("playwright not installed") from exc

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "zh-TW,zh;q=0.9"})
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(1500)
            return page.content()
        finally:
            browser.close()


def get_goodinfo_dividend_policy(
    symbol: str,
    today: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Return Goodinfo dividend policy payload for a given symbol.

    Returned dict always has:
        status: "current_year" | "stale" | "not_found" | "fetch_failed"
        year: int | None
        cash_dividend: float | None
        stock_dividend: float | None
        source_url: str
        source_note: str
    """
    if today is None:
        today = pd.Timestamp.now(tz="Asia/Taipei")

    source_url = _GOODINFO_URL_TEMPLATE.format(symbol=symbol)

    def _result(
        status: str,
        year: int | None = None,
        cash: float | None = None,
        stock: float | None = None,
        period: str | None = None,
        payment_status: str | None = None,
        payment_date: str | None = None,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "year": year,
            "period": period,
            "payment_status": payment_status,
            "payment_date": payment_date,
            "cash_dividend": cash,
            "stock_dividend": stock,
            "source_url": source_url,
            "source_note": _SOURCE_NOTE,
        }

    cached = _load_cache(symbol, today)
    if cached is not None:
        return cached

    try:
        html = fetch_goodinfo_dividend_policy_html(symbol)
    except Exception:
        payload = _result("fetch_failed")
        return payload

    try:
        df = extract_goodinfo_dividend_policy_from_html(html)
    except Exception:
        payload = _result("fetch_failed")
        try:
            _save_cache(symbol, today, payload)
        except Exception:
            pass
        return payload

    if df.empty:
        payload = _result("not_found")
        try:
            _save_cache(symbol, today, payload)
        except Exception:
            pass
        return payload

    has_period = ~df["period"].fillna("").isin(["", "-"])
    has_dividend = (df["cash_dividend"].fillna(0) > 0) | (df["stock_dividend"].fillna(0) > 0)

    undetermined = df[
        (df["payment_status"] == "undetermined") & has_period & has_dividend
    ].copy()

    if not undetermined.empty:
        undetermined["_period_key"] = undetermined["period"].map(_period_sort_key)
        latest = undetermined.sort_values(["year", "_period_key"]).iloc[0]
    else:
        future_mask = has_period & has_dividend & df.apply(
            lambda r: _is_future_payment(str(r.get("payment_raw", "")), int(r["year"]), today),
            axis=1,
        )
        future = df[future_mask].copy()
        if not future.empty:
            future["_period_key"] = future["period"].map(_period_sort_key)
            latest = future.sort_values(["year", "_period_key"]).iloc[0]
        else:
            payload = _result("not_found")
            try:
                _save_cache(symbol, today, payload)
            except Exception:
                pass
            return payload
    year = int(latest["year"])
    period_val = latest.get("period")
    period = str(period_val) if pd.notna(period_val) and str(period_val).strip() not in ("", "-") else None
    payment_status_val = latest.get("payment_status")
    payment_status = (
        str(payment_status_val)
        if pd.notna(payment_status_val) and str(payment_status_val).strip()
        else None
    )
    cash = float(latest["cash_dividend"]) if pd.notna(latest["cash_dividend"]) else None
    stock_val = latest.get("stock_dividend")
    stock = float(stock_val) if pd.notna(stock_val) else 0.0

    parsed_date = _parse_payment_date(str(latest.get("payment_raw", "")), year)
    payment_date_str = parsed_date.strftime("%Y-%m-%d") if parsed_date is not None else None

    # Annual-summary rows have no M/DD — surface them as 未定 so the UI renders
    # "股利發放時間未定" instead of a blank countdown slot.
    if payment_status is None and parsed_date is None and _is_bare_year_payment(str(latest.get("payment_raw", ""))):
        payment_status = "undetermined"

    if year == today.year:
        payload = _result(
            "current_year",
            year=year,
            cash=cash,
            stock=stock,
            period=period,
            payment_status=payment_status,
            payment_date=payment_date_str,
        )
    else:
        payload = _result(
            "stale",
            year=year,
            cash=cash,
            stock=stock,
            period=period,
            payment_status=payment_status,
            payment_date=payment_date_str,
        )

    try:
        _save_cache(symbol, today, payload)
    except Exception:
        pass

    return payload
