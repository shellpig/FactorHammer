from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from src.core.constants import STANDARD_COLUMNS
from src.data.cleaner import DataCleaner
from src.data.maintenance import DataMaintenance
from src.data.storage import DuckDBMeta, ParquetStorage


def _make_daily(symbol: str, start: str, periods: int, close_base: float = 100.0) -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=periods, freq="D")
    return pd.DataFrame(
        {
            "date": idx,
            "open": [close_base + i for i in range(periods)],
            "high": [close_base + i + 1 for i in range(periods)],
            "low": [close_base + i - 1 for i in range(periods)],
            "close": [close_base + i for i in range(periods)],
            "volume": [1000] * periods,
            "symbol": [symbol] * periods,
        }
    )[STANDARD_COLUMNS]


class StubFetcher:
    def __init__(
        self,
        full_daily: pd.DataFrame,
        incremental_daily: pd.DataFrame | None,
        dividends: pd.DataFrame,
        splits: pd.DataFrame | None = None,
    ):
        self.full_daily = full_daily
        self.incremental_daily = incremental_daily
        self.dividends = dividends
        self.splits = splits if splits is not None else pd.DataFrame(columns=["date", "before_price", "after_price", "symbol"])

    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        if start <= "2000-01-01":
            return self.full_daily.copy(deep=True)

        if self.incremental_daily is None or self.incremental_daily.empty:
            return pd.DataFrame(columns=STANDARD_COLUMNS)

        out = self.incremental_daily.copy(deep=True)
        out["date"] = pd.to_datetime(out["date"])
        mask = (out["date"] >= pd.Timestamp(start)) & (out["date"] <= pd.Timestamp(end))
        return out.loc[mask, STANDARD_COLUMNS].reset_index(drop=True)

    def fetch_minute(self, symbol: str, start: str, end: str, freq: str = "1") -> pd.DataFrame:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        return self.dividends.copy(deep=True)

    def fetch_splits(self, symbol: str) -> pd.DataFrame:
        return self.splits.copy(deep=True)


def test_rebuild_symbol_saves_and_updates_meta(tmp_path) -> None:
    full_daily = _make_daily("2330", "2024-06-24", 4)
    dividends = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-06-26")],
            "cash_dividend": [5.0],
            "stock_dividend": [0.0],
            "symbol": ["2330"],
        }
    )
    fetcher = StubFetcher(full_daily=full_daily, incremental_daily=None, dividends=dividends)
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    report = maintenance.rebuild_symbol("2330")

    assert report.total_rows == len(full_daily)
    raw_saved = storage.load_daily("2330")
    adj_saved = storage.load_adjusted("2330")
    assert not raw_saved.empty
    assert not adj_saved.empty
    adj_saved_dates = pd.to_datetime(adj_saved["date"], errors="coerce")
    target_close = adj_saved.loc[adj_saved_dates.dt.strftime("%Y-%m-%d") == "2024-06-24", "close"].iloc[0]
    assert target_close != 100.0

    row = meta.get_meta("2330", "daily")
    assert row is not None
    assert row["row_count"] == len(raw_saved)


def test_rebuild_symbol_applies_split(tmp_path) -> None:
    full_daily = pd.DataFrame(
        {
            "date": pd.Series(pd.to_datetime(["2025-06-17", "2025-06-18", "2025-06-19"]).tz_localize("Asia/Taipei")).astype("datetime64[ns, Asia/Taipei]"),
            "open": [188.65, 47.16, 47.5],
            "high": [189.0, 48.0, 48.0],
            "low": [188.0, 46.5, 47.0],
            "close": [188.65, 47.16, 47.8],
            "volume": [1000, 1000, 1000],
            "symbol": ["0050", "0050", "0050"],
        }
    )[STANDARD_COLUMNS]
    splits = pd.DataFrame(
        {
            "date": pd.Series(pd.to_datetime(["2025-06-18"]).tz_localize("Asia/Taipei")).astype("datetime64[ns, Asia/Taipei]"),
            "before_price": [188.65],
            "after_price": [47.16],
            "symbol": ["0050"],
        }
    )

    fetcher = StubFetcher(
        full_daily=full_daily,
        incremental_daily=None,
        dividends=pd.DataFrame(),
        splits=splits,
    )
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    maintenance.rebuild_symbol("0050")

    adjusted = storage.load_adjusted("0050")
    split_saved = storage.load_splits("0050")
    assert not adjusted.empty
    assert not split_saved.empty
    adj_pre_close = adjusted.loc[pd.to_datetime(adjusted["date"]) == pd.Timestamp("2025-06-17", tz="Asia/Taipei"), "close"].iloc[0]
    adj_split_close = adjusted.loc[pd.to_datetime(adjusted["date"]) == pd.Timestamp("2025-06-18", tz="Asia/Taipei"), "close"].iloc[0]
    assert adj_pre_close == pytest.approx(adj_split_close, abs=0.01)


def test_rebuild_adj_factors_overwrites_adjusted(tmp_path) -> None:
    full_daily = _make_daily("2330", "2024-06-24", 4)
    dividends = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-06-26")],
            "cash_dividend": [5.0],
            "stock_dividend": [0.0],
            "symbol": ["2330"],
        }
    )
    fetcher = StubFetcher(full_daily=full_daily, incremental_daily=None, dividends=dividends)
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    storage.save_daily("2330", full_daily)
    maintenance.rebuild_adj_factors("2330")
    adjusted = storage.load_adjusted("2330")
    assert not adjusted.empty
    adjusted_dates = pd.to_datetime(adjusted["date"], errors="coerce")
    target_close = adjusted.loc[adjusted_dates.dt.strftime("%Y-%m-%d") == "2024-06-24", "close"].iloc[0]
    assert target_close != 100.0


def test_validate_data_returns_quality_report(tmp_path) -> None:
    raw = _make_daily("2330", "2024-01-01", 3)
    raw.loc[1, "close"] = -10.0

    fetcher = StubFetcher(full_daily=raw, incremental_daily=None, dividends=pd.DataFrame())
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)
    storage.save_daily("2330", raw)

    report = maintenance.validate_data("2330")
    assert report.negative_price_count >= 1


def test_list_stale_symbols(tmp_path) -> None:
    fetcher = StubFetcher(full_daily=pd.DataFrame(columns=STANDARD_COLUMNS), incremental_daily=None, dividends=pd.DataFrame())
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    meta.upsert_meta(
        symbol="2330",
        freq="daily",
        source="stub",
        first_date=pd.Timestamp("2024-01-01"),
        last_date=pd.Timestamp("2024-01-10"),
        row_count=10,
    )
    meta._conn.execute("UPDATE data_meta SET updated_at = TIMESTAMP '2000-01-01 00:00:00+00';")

    stale = maintenance.list_stale_symbols(days=7)
    assert any(item["symbol"] == "2330" for item in stale)


def test_update_daily_returns_added_rows(tmp_path) -> None:
    existing = _make_daily("2330", "2024-01-01", 2)
    incremental = _make_daily("2330", "2024-01-03", 2)
    fetcher = StubFetcher(full_daily=existing, incremental_daily=incremental, dividends=pd.DataFrame())
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    storage.save_daily("2330", existing)
    added = maintenance.update_daily("2330")
    merged = storage.load_daily("2330")

    assert added == 2
    assert len(merged) == 4
    assert pd.to_datetime(merged["date"]).max().date() >= datetime(2024, 1, 4).date()


def test_update_daily_rebuilds_adjusted_when_no_new_rows(tmp_path) -> None:
    existing = _make_daily("2330", "2024-06-24", 2)
    dividends = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-06-25")],
            "cash_dividend": [5.0],
            "stock_dividend": [0.0],
            "symbol": ["2330"],
        }
    )
    fetcher = StubFetcher(full_daily=existing, incremental_daily=pd.DataFrame(columns=STANDARD_COLUMNS), dividends=dividends)
    storage = ParquetStorage(data_dir=tmp_path / "data")
    meta = DuckDBMeta(db_path=str(tmp_path / "meta.duckdb"))
    cleaner = DataCleaner()
    maintenance = DataMaintenance(fetcher, storage, meta, cleaner)

    storage.save_daily("2330", existing)
    added = maintenance.update_daily("2330")

    adjusted = storage.load_adjusted("2330")
    assert added == 0
    assert not adjusted.empty
    adjusted_dates = pd.to_datetime(adjusted["date"], errors="coerce")
    adjusted_first = adjusted.loc[adjusted_dates.dt.strftime("%Y-%m-%d") == "2024-06-24", "close"].iloc[0]
    assert adjusted_first == pytest.approx(95.0)
