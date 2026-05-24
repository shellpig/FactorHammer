"""Data service — non-UI data management layer (Phase 10-A).

All functions return plain Python objects.
No Streamlit calls are made here.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.core.config import get_config, get_data_dir
from src.core.market import normalize_market
from src.data.cleaner import DataCleaner
from src.data.fetcher import FinMindFetcher, IDataFetcher, YFinanceFetcher
from src.data.maintenance import DataMaintenance
from src.data.storage import DuckDBMeta, ParquetStorage


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SymbolStatus:
    """Status of a locally stored symbol."""

    symbol: str
    market: str
    data_type: str   # "raw_daily" | "adjusted_daily"
    available: bool
    row_count: int
    start_date: str   # "YYYY-MM-DD" or "-"
    end_date: str     # "YYYY-MM-DD" or "-"


@dataclass
class MaintenanceReport:
    """Result of a rebuild / update operation."""

    symbol: str
    market: str
    operation: str      # "update" | "rebuild"
    source: str
    rows_added: int
    success: bool
    error: str | None = None
    warnings: list[str] = field(default_factory=list)



@dataclass
class DataServiceError:
    code: str
    message: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_STOCK_INFO_CACHE_TTL_DAYS = 7


def _load_symbol_names(market: str) -> dict[str, str]:
    """Return {symbol: name} for the given market.

    TW: lazy-loads from FinMind TaiwanStockInfo, caches to
    ``data/stock_info_tw.parquet`` with a 7-day TTL.
    US: returns an empty dict (yfinance lookup deferred to a future phase).
    All errors are swallowed — callers fall back to symbol as name.
    """
    if market != "tw":
        return {}

    cache_path = get_data_dir() / "stock_info_tw.parquet"

    # Try warm cache first
    if cache_path.exists():
        try:
            mtime = datetime.datetime.fromtimestamp(cache_path.stat().st_mtime)
            age_days = (datetime.datetime.now() - mtime).days
            if age_days < _STOCK_INFO_CACHE_TTL_DAYS:
                df = pd.read_parquet(cache_path)
                if {"symbol", "name"}.issubset(df.columns):
                    return dict(zip(df["symbol"].astype(str), df["name"].astype(str)))
        except Exception:  # noqa: BLE001
            pass

    # Cache miss or stale — fetch from FinMind
    try:
        fetcher = FinMindFetcher()
        df = fetcher.fetch_stock_info()
        if not df.empty:
            df[["symbol", "name"]].to_parquet(cache_path, index=False)
            return dict(zip(df["symbol"].astype(str), df["name"].astype(str)))
    except Exception:  # noqa: BLE001
        pass

    return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_symbols(market: str = "tw") -> list[dict[str, Any]]:
    """Return metadata rows for the given market from DuckDB.

    Each row includes a ``name`` field (Chinese stock name for TW, symbol
    fallback for US).  Returns an empty list on error.
    """
    normalized_market = normalize_market(market)
    try:
        meta = DuckDBMeta()
        df = meta.list_all()
    except Exception:  # noqa: BLE001
        return []
    finally:
        try:
            meta.close()  # type: ignore[name-defined]
        except Exception:
            pass

    if "market" in df.columns:
        df = df[df["market"] == normalized_market].copy()

    # Bug 1 fix: de-duplicate by symbol so each ticker appears only once
    if not df.empty:
        df = df.drop_duplicates(subset=["symbol"], keep="first")

    if df.empty:
        return []

    rows = df.to_dict(orient="records")

    # Bug 2 fix: attach human-readable names
    names = _load_symbol_names(normalized_market)
    for row in rows:
        sym = str(row.get("symbol", ""))
        row["name"] = names.get(sym, sym)

    return rows


def get_symbol_status(symbol: str, market: str = "tw") -> list[SymbolStatus]:
    """Return raw + adjusted data status for a symbol."""
    normalized_market = normalize_market(market)
    storage = ParquetStorage()
    statuses: list[SymbolStatus] = []

    for data_type, loader in (
        ("raw_daily", lambda: storage.load_daily(symbol, market=normalized_market)),
        ("adjusted_daily", lambda: storage.load_adjusted(symbol, market=normalized_market)),
    ):
        try:
            df: pd.DataFrame = loader()  # type: ignore[operator]
        except Exception:  # noqa: BLE001
            df = pd.DataFrame()

        if df.empty:
            statuses.append(
                SymbolStatus(
                    symbol=symbol,
                    market=normalized_market,
                    data_type=data_type,
                    available=False,
                    row_count=0,
                    start_date="-",
                    end_date="-",
                )
            )
            continue

        dates = pd.to_datetime(df.get("date"), errors="coerce").dropna()
        statuses.append(
            SymbolStatus(
                symbol=symbol,
                market=normalized_market,
                data_type=data_type,
                available=True,
                row_count=int(len(df)),
                start_date=dates.min().strftime("%Y-%m-%d") if not dates.empty else "-",
                end_date=dates.max().strftime("%Y-%m-%d") if not dates.empty else "-",
            )
        )

    return statuses


def run_maintenance(
    symbol: str,
    *,
    rebuild: bool = False,
    market: str = "tw",
) -> MaintenanceReport | DataServiceError:
    """Run update or rebuild for a symbol.

    Returns ``MaintenanceReport`` on success or ``DataServiceError`` on failure.
    """
    normalized_market = normalize_market(market)
    storage = ParquetStorage()
    fetchers = _build_fetchers_from_config(market=normalized_market)

    if not fetchers:
        return DataServiceError(code="NO_SOURCE", message="No available data source. Details: n/a")

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
            if rebuild:
                maintenance.rebuild_symbol(symbol, market=normalized_market)
                return MaintenanceReport(
                    symbol=symbol,
                    market=normalized_market,
                    operation="rebuild",
                    source=source,
                    rows_added=-1,   # rebuild doesn't return added count
                    success=True,
                    warnings=maintenance.warnings,
                )
            else:
                added = maintenance.update_daily(symbol, market=normalized_market)
                return MaintenanceReport(
                    symbol=symbol,
                    market=normalized_market,
                    operation="update",
                    source=source,
                    rows_added=int(added),
                    success=True,
                    warnings=maintenance.warnings,
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{source}: {exc}")
        finally:
            meta.close()

    return DataServiceError(
        code="MAINTENANCE_FAILED",
        message=f"資料操作失敗：{' | '.join(errors)}",
    )


def delete_symbol_data(
    symbol: str,
    market: str = "tw",
) -> bool | DataServiceError:
    """Delete all local parquet data + DuckDB metadata for a symbol.

    Returns ``True`` on success or ``DataServiceError`` on failure.
    NOTE: Does NOT delete backtest results in data/backtest/.
    """
    normalized_market = normalize_market(market)
    storage = ParquetStorage()
    meta = DuckDBMeta()
    errors: list[str] = []

    try:
        # Remove parquet files
        try:
            storage.delete_symbol(symbol, market=normalized_market)
        except AttributeError:
            # ParquetStorage may not yet have delete_symbol — graceful fallback
            pass
        except Exception as exc:  # noqa: BLE001
            errors.append(f"parquet: {exc}")

        # Remove DuckDB metadata
        try:
            meta.delete_symbol(symbol, market=normalized_market)
        except AttributeError:
            pass
        except Exception as exc:  # noqa: BLE001
            errors.append(f"meta: {exc}")

        if errors:
            raw_detail = " | ".join(errors)
            hint = (
                "（檔案可能正被後端、Dashboard 或防毒程式使用，請關閉相關頁面後稍等幾秒再試）"
                if "WinError 5" in raw_detail or "Permission" in raw_detail
                else ""
            )
            return DataServiceError(
                code="DELETE_PARTIAL",
                message=f"刪除部分失敗：{raw_detail}{hint}",
            )
        return True

    finally:
        meta.close()


def refresh_shareholder_meeting_once_per_day(market: str = "tw") -> bool:
    """Refresh global TW shareholder meeting dataset once per day.

    This is a best-effort helper for data_update/data_rebuild job tail.
    Any failure is swallowed to avoid breaking the main daily pipeline.
    """
    normalized_market = normalize_market(market)
    if normalized_market != "tw":
        return False

    storage = ParquetStorage()
    meta = DuckDBMeta()
    try:
        fetchers = _build_fetchers_from_config(market=normalized_market)
        if not fetchers:
            return False
        _, fetcher = fetchers[0]
        maintenance = DataMaintenance(
            fetcher=fetcher,
            storage=storage,
            meta=meta,
            cleaner=DataCleaner(),
        )
        return maintenance.refresh_shareholder_meeting_once_per_day(market=normalized_market)
    except Exception:  # noqa: BLE001
        return False
    finally:
        meta.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_fetchers_from_config(market: str = "tw") -> list[tuple[str, IDataFetcher]]:
    normalized_market = normalize_market(market)
    cfg = get_config()
    data_section = cfg.get("data", {}) if isinstance(cfg, dict) else {}

    if normalized_market == "us":
        order = ["yfinance"]
    else:
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
