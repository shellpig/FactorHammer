"""Data service — non-UI data management layer (Phase 10-A).

All functions return plain Python objects.
No Streamlit calls are made here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.core.config import get_config
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


@dataclass
class DataServiceError:
    code: str
    message: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_symbols(market: str = "tw") -> list[dict[str, Any]]:
    """Return metadata rows for the given market from DuckDB.

    Returns an empty list on error (callers may surface the error separately).
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

    if df.empty:
        return []

    return df.to_dict(orient="records")


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
            return DataServiceError(
                code="DELETE_PARTIAL",
                message=f"刪除部分失敗：{' | '.join(errors)}",
            )
        return True

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
