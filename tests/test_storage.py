from __future__ import annotations

import pandas as pd
import pytest

from src.core.constants import STANDARD_COLUMNS, TAIPEI_TZ
from src.core.exceptions import StorageError
from src.data.storage import DuckDBMeta, ParquetStorage


def _make_daily_df(symbol: str, start: str, periods: int, close_base: float = 100.0) -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=periods, freq="D", tz=TAIPEI_TZ)
    df = pd.DataFrame(
        {
            "date": pd.Series(idx).astype(f"datetime64[ns, {TAIPEI_TZ}]"),
            "open": [close_base + i for i in range(periods)],
            "high": [close_base + i + 1 for i in range(periods)],
            "low": [close_base + i - 1 for i in range(periods)],
            "close": [close_base + i + 0.5 for i in range(periods)],
            "volume": [1000 + i for i in range(periods)],
            "symbol": [symbol] * periods,
        }
    )
    return df[STANDARD_COLUMNS]


def _make_splits_df(symbol: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(pd.to_datetime(["2025-06-18", "2026-01-01"]).tz_localize(TAIPEI_TZ)).astype(f"datetime64[ns, {TAIPEI_TZ}]"),
            "before_price": [188.65, 120.0],
            "after_price": [47.16, 60.0],
            "symbol": [symbol, symbol],
        }
    )


def test_save_and_load_daily_roundtrip(tmp_path) -> None:
    storage = ParquetStorage(data_dir=tmp_path)
    source = _make_daily_df(symbol="2330", start="2025-01-01", periods=5)

    storage.save_daily("2330", source)
    loaded = storage.load_daily("2330")

    expected = source.sort_values("date").reset_index(drop=True)
    pd.testing.assert_frame_equal(loaded, expected)


def test_upsert_no_duplicates(tmp_path) -> None:
    storage = ParquetStorage(data_dir=tmp_path)
    first_batch = _make_daily_df(symbol="2330", start="2025-01-01", periods=10, close_base=100.0)
    second_batch = _make_daily_df(symbol="2330", start="2025-01-06", periods=8, close_base=1000.0)

    storage.save_daily("2330", first_batch)
    storage.save_daily("2330", second_batch)
    merged = storage.load_daily("2330")

    assert len(merged) == 13
    merged_by_date = merged.set_index("date")
    second_by_date = second_batch.set_index("date")
    for dt in second_by_date.index:
        assert merged_by_date.loc[dt, "close"] == second_by_date.loc[dt, "close"]


def test_load_nonexistent_returns_empty(tmp_path) -> None:
    storage = ParquetStorage(data_dir=tmp_path)
    loaded = storage.load_daily("9999")

    assert loaded.empty
    assert loaded.columns.tolist() == STANDARD_COLUMNS


def test_save_and_load_splits_roundtrip(tmp_path) -> None:
    storage = ParquetStorage(data_dir=tmp_path)
    source = _make_splits_df(symbol="0050")

    storage.save_splits("0050", source)
    loaded = storage.load_splits("0050")

    expected = source.sort_values("date").reset_index(drop=True)
    pd.testing.assert_frame_equal(loaded, expected)


@pytest.mark.parametrize(
    "symbol",
    ["..", "../escape", "..\\escape", "a/b", "a\\b", "/escape", "C:/escape", "C:\\escape", "C:escape"],
)
def test_storage_rejects_path_traversal_symbol(tmp_path, symbol: str) -> None:
    storage = ParquetStorage(data_dir=tmp_path)
    source = _make_daily_df(symbol="2330", start="2025-01-01", periods=1)
    safe_path = storage._daily_path("2330")
    safe_path.resolve().relative_to(tmp_path.resolve())

    with pytest.raises(StorageError):
        storage.save_daily(symbol, source)


def test_storage_uses_default_tw_market_path(tmp_path) -> None:
    storage = ParquetStorage(data_dir=tmp_path)
    source = _make_daily_df(symbol="2330", start="2025-01-01", periods=1)

    default_path = storage.save_daily("2330", source)
    explicit_tw_path = storage.save_daily("2330", source, market="tw")
    expected_path = (tmp_path / "raw" / "tw" / "2330" / "daily.parquet").resolve()

    assert default_path == expected_path
    assert explicit_tw_path == expected_path
    assert expected_path.exists()


def test_storage_rejects_unknown_market(tmp_path) -> None:
    storage = ParquetStorage(data_dir=tmp_path)
    source = _make_daily_df(symbol="2330", start="2025-01-01", periods=1)

    with pytest.raises(StorageError, match="Unsupported market"):
        storage.save_daily("2330", source, market="us")


def test_duckdb_meta_upsert_and_query() -> None:
    meta = DuckDBMeta(db_path=":memory:")
    first_date = pd.Timestamp("2025-01-01 09:00:00", tz=TAIPEI_TZ)
    last_date = pd.Timestamp("2025-01-31 13:30:00", tz=TAIPEI_TZ)

    meta.upsert_meta(
        symbol="2330",
        freq="daily",
        source="finmind",
        first_date=first_date,
        last_date=last_date,
        row_count=22,
    )
    row = meta.get_meta("2330", "daily")
    assert row is not None
    assert row["symbol"] == "2330"
    assert row["freq"] == "daily"
    assert row["source"] == "finmind"
    assert row["row_count"] == 22

    assert pd.Timestamp(row["first_date"]).tz_convert("UTC") == first_date.tz_convert("UTC")
    assert pd.Timestamp(row["last_date"]).tz_convert("UTC") == last_date.tz_convert("UTC")
    assert row["updated_at"] is not None


def test_duckdb_meta_upsert_overwrite() -> None:
    meta = DuckDBMeta(db_path=":memory:")

    meta.upsert_meta(
        symbol="2330",
        freq="daily",
        source="finmind",
        first_date=pd.Timestamp("2025-01-01 09:00:00", tz=TAIPEI_TZ),
        last_date=pd.Timestamp("2025-01-15 13:30:00", tz=TAIPEI_TZ),
        row_count=10,
    )
    meta.upsert_meta(
        symbol="2330",
        freq="daily",
        source="yfinance",
        first_date=pd.Timestamp("2025-01-01 09:00:00", tz=TAIPEI_TZ),
        last_date=pd.Timestamp("2025-01-31 13:30:00", tz=TAIPEI_TZ),
        row_count=20,
    )

    row = meta.get_meta("2330", "daily")
    assert row is not None
    assert row["source"] == "yfinance"
    assert row["row_count"] == 20
