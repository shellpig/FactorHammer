"""Active ETF service — non-UI Active ETF management layer (Phase 16-A)."""

from __future__ import annotations

import datetime
import time
from typing import Any

import pandas as pd

from src.core.exceptions import FetcherError
from src.data.fetcher import ActiveEtfPremiumSnapshot, MoneyDjActiveEtfSource, TwseEtfNavSource
from src.data.storage import ParquetStorage, StorageError

import threading
from collections import defaultdict

# Process-level cache to avoid overloading MoneyDJ: {etf_code: last_fetch_timestamp}
_HOLDINGS_CACHE: dict[str, float] = {}
_CACHE_TTL_SECONDS = 60

# Phase 16-D sweep cache and per-ETF locks
_SWEEP_CACHE: dict[str, float] = {}
_ETF_LOCKS: dict[str, threading.Lock] = defaultdict(threading.Lock)
_PREMIUM_CACHE: dict[str, tuple[float, ActiveEtfPremiumSnapshot | None]] = {}



class ActiveEtfService:
    """Service layer for active ETF holding tracking."""

    def __init__(self, storage: ParquetStorage | None = None):
        self.storage = storage or ParquetStorage()

    def get_list(self) -> list[dict[str, str]]:
        """Return the active ETF list.

        Format: [{"code": "00981A", "name": "主動統一台股增長"}, ...]
        Uses cache-first logic. Returns an empty list on error.
        """
        # 1. Check metadata for list age
        meta = self.storage.load_active_etf_list_meta()
        fetched_at_str = meta.get("fetched_at")
        cache_valid = False

        if fetched_at_str:
            try:
                fetched_at = datetime.datetime.fromisoformat(fetched_at_str)
                # Cache is valid for 7 days
                if (datetime.datetime.now() - fetched_at).days < 7:
                    cache_valid = True
            except Exception:  # noqa: BLE001
                pass

        if cache_valid:
            df = self.storage.load_active_etf_list()
            if not df.empty:
                # Map etf_code -> code, etf_name -> name
                return [
                    {"code": str(row["etf_code"]), "name": str(row["etf_name"])}
                    for _, row in df.iterrows()
                ]

        # 2. Cache miss/stale - fetch from source
        try:
            source = MoneyDjActiveEtfSource()
            df = source.fetch_list()
            if not df.empty:
                # Save list and update metadata
                self.storage.save_active_etf_list(df)
                self.storage.save_active_etf_list_meta(
                    {"fetched_at": datetime.datetime.now().isoformat()}
                )
                return [
                    {"code": str(row["etf_code"]), "name": str(row["etf_name"])}
                    for _, row in df.iterrows()
                ]
        except Exception:  # noqa: BLE001
            # Swallow all exceptions, fallback to stale cache if available
            try:
                df = self.storage.load_active_etf_list()
                if not df.empty:
                    return [
                        {"code": str(row["etf_code"]), "name": str(row["etf_name"])}
                        for _, row in df.iterrows()
                    ]
            except Exception:  # noqa: BLE001
                pass

        return []

    def get_holdings_with_diff(self, etf_code: str) -> dict[str, Any]:
        """Fetch, save, and calculate holdings with difference from previous snapshot.

        This method is sync and coordinates fetching, storage, and diff calculation.
        """
        normalized_code = str(etf_code).strip().upper()
        premium = self.get_premium_snapshot(normalized_code)

        # Check process-level cache TTL
        now = time.time()
        last_fetch = _HOLDINGS_CACHE.get(normalized_code, 0.0)

        if now - last_fetch >= _CACHE_TTL_SECONDS:
            # TTL missed or expired, fetch from MoneyDJ and store under per-ETF lock
            with _ETF_LOCKS[normalized_code]:
                # Double check TTL under lock
                last_fetch = _HOLDINGS_CACHE.get(normalized_code, 0.0)
                if now - last_fetch >= _CACHE_TTL_SECONDS:
                    source = MoneyDjActiveEtfSource()
                    try:
                        snapshot_date, df = source.fetch_holdings(normalized_code)
                        self.storage.save_active_etf_holdings(normalized_code, snapshot_date, df)
                        # Update TTL cache
                        _HOLDINGS_CACHE[normalized_code] = time.time()
                    except FetcherError:
                        # Propagate FetcherError to let the API router return 4xx/5xx/etc.
                        raise
                    except Exception as exc:  # noqa: BLE001
                        raise FetcherError(f"Unexpected fetch failure for active ETF {normalized_code}: {exc}") from exc

        # 3. Read history dates and calculate differences
        dates = self.storage.load_active_etf_holdings_dates(normalized_code)
        if not dates:
            # Try loading cache list for name fallback
            etf_name = normalized_code
            for item in self.get_list():
                if item["code"] == normalized_code:
                    etf_name = item["name"]
                    break
            return {
                "etf_code": normalized_code,
                "etf_name": etf_name,
                "premium": premium,
                "latest_date": None,
                "previous_date": None,
                "has_previous": False,
                "holdings": [],
                "changes": {
                    "buys": [],
                    "sells": [],
                    "entries": [],
                    "exits": [],
                },
            }

        latest_date = dates[-1]
        previous_date = dates[-2] if len(dates) >= 2 else None
        has_previous = previous_date is not None

        # Load ETF name from active list cache if possible
        etf_name = normalized_code
        for item in self.get_list():
            if item["code"] == normalized_code:
                etf_name = item["name"]
                break

        # Load all holdings from storage
        all_holdings = self.storage.load_active_etf_holdings(normalized_code)
        latest_df = all_holdings[all_holdings["snapshot_date"] == latest_date].copy()

        if latest_df.empty:
            return {
                "etf_code": normalized_code,
                "etf_name": etf_name,
                "premium": premium,
                "latest_date": latest_date.strftime("%Y-%m-%d"),
                "previous_date": previous_date.strftime("%Y-%m-%d") if previous_date else None,
                "has_previous": has_previous,
                "holdings": [],
                "changes": {
                    "buys": [],
                    "sells": [],
                    "entries": [],
                    "exits": [],
                },
            }

        # Build join key for outer join
        # If holding_code is empty (cash/other), match on holding_name.
        latest_df["join_key"] = latest_df.apply(
            lambda r: r["holding_code"] if r["holding_code"] != "" else r["holding_name"],
            axis=1
        )

        if has_previous:
            prev_df = all_holdings[all_holdings["snapshot_date"] == previous_date].copy()
            if prev_df.empty:
                # Handle unexpected empty prev snapshot gracefully
                has_previous = False
                previous_date = None

        if has_previous:
            prev_df["join_key"] = prev_df.apply(
                lambda r: r["holding_code"] if r["holding_code"] != "" else r["holding_name"],
                axis=1
            )

            # Outer join to calculate diff
            merged = pd.merge(
                latest_df,
                prev_df,
                on="join_key",
                how="outer",
                suffixes=("_latest", "_prev")
            )

            # Fill keys
            merged["holding_code"] = merged["holding_code_latest"].fillna(merged["holding_code_prev"]).fillna("")
            merged["holding_name"] = merged["holding_name_latest"].fillna(merged["holding_name_prev"]).fillna("")

            shares_latest = merged["shares_latest"].fillna(0).astype("int64")
            shares_prev = merged["shares_prev"].fillna(0).astype("int64")
            merged["delta_shares"] = shares_latest - shares_prev

            # Classify changes
            # 1. buys: delta > 0 and present in both
            buys_mask = (merged["delta_shares"] > 0) & merged["shares_latest"].notna() & merged["shares_prev"].notna()
            # 2. sells: delta < 0 and present in both
            sells_mask = (merged["delta_shares"] < 0) & merged["shares_latest"].notna() & merged["shares_prev"].notna()
            # 3. entries: only in latest
            entries_mask = merged["shares_latest"].notna() & merged["shares_prev"].isna()
            # 4. exits: only in prev
            exits_mask = merged["shares_latest"].isna() & merged["shares_prev"].notna()

            buys_df = merged[buys_mask].copy()
            sells_df = merged[sells_mask].copy()
            entries_df = merged[entries_mask].copy()
            exits_df = merged[exits_mask].copy()

            # Helper to convert df to lists, sorting by |delta_shares| descending
            def to_change_list(df_part: pd.DataFrame) -> list[dict[str, Any]]:
                if df_part.empty:
                    return []
                df_part["abs_delta"] = df_part["delta_shares"].abs()
                df_sorted = df_part.sort_values("abs_delta", ascending=False)
                return [
                    {
                        "holding_code": str(r["holding_code"]),
                        "holding_name": str(r["holding_name"]),
                        "delta_shares": int(r["delta_shares"]),
                    }
                    for _, r in df_sorted.iterrows()
                ]

            buys = to_change_list(buys_df)
            sells = to_change_list(sells_df)
            entries = to_change_list(entries_df)
            exits = to_change_list(exits_df)

            # Build final holdings (latest only)
            latest_holdings_merged = merged[merged["shares_latest"].notna()].copy()
            # Sort by weight_pct descending
            latest_holdings_merged = latest_holdings_merged.sort_values("weight_pct_latest", ascending=False)

            holdings = []
            for rank, (_, row) in enumerate(latest_holdings_merged.iterrows(), 1):
                holdings.append({
                    "rank": rank,
                    "holding_code": str(row["holding_code"]),
                    "holding_name": str(row["holding_name"]),
                    "shares": int(row["shares_latest"]),
                    "weight_pct": float(row["weight_pct_latest"]),
                    "delta_shares": int(row["delta_shares"]),
                })

        else:
            # No previous snapshot to compare
            # Sort by weight_pct descending
            latest_df = latest_df.sort_values("weight_pct", ascending=False)
            holdings = []
            for rank, (_, row) in enumerate(latest_df.iterrows(), 1):
                holdings.append({
                    "rank": rank,
                    "holding_code": str(row["holding_code"]),
                    "holding_name": str(row["holding_name"]),
                    "shares": int(row["shares"]),
                    "weight_pct": float(row["weight_pct"]),
                    "delta_shares": None,
                })

            buys, sells, entries, exits = [], [], [], []

        return {
            "etf_code": normalized_code,
            "etf_name": etf_name,
            "premium": premium,
            "latest_date": latest_date.strftime("%Y-%m-%d"),
            "previous_date": previous_date.strftime("%Y-%m-%d") if previous_date else None,
            "has_previous": has_previous,
            "holdings": holdings,
            "changes": {
                "buys": buys,
                "sells": sells,
                "entries": entries,
                "exits": exits,
            },
        }

    def get_premium_snapshot(self, etf_code: str) -> dict[str, Any] | None:
        """Return TWSE NAV / premium-discount data for a single active ETF."""
        normalized_code = str(etf_code).strip().upper()
        now = time.time()
        cached = _PREMIUM_CACHE.get(normalized_code)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return self._premium_to_dict(cached[1])

        try:
            snapshot = TwseEtfNavSource().fetch_premium(normalized_code)
        except Exception:  # noqa: BLE001
            snapshot = None

        _PREMIUM_CACHE[normalized_code] = (time.time(), snapshot)
        return self._premium_to_dict(snapshot)

    @staticmethod
    def _premium_to_dict(snapshot: ActiveEtfPremiumSnapshot | None) -> dict[str, Any] | None:
        if snapshot is None:
            return None
        return {
            "etf_code": snapshot.etf_code,
            "etf_name": snapshot.etf_name,
            "market_price": snapshot.market_price,
            "estimated_nav": snapshot.estimated_nav,
            "premium_discount_pct": snapshot.premium_discount_pct,
            "previous_nav": snapshot.previous_nav,
            "data_date": snapshot.data_date,
            "data_time": snapshot.data_time,
            "source": snapshot.source,
        }

    def refresh_holdings_snapshot(self, etf_code: str, latest_close_date: datetime.date | None = None) -> None:
        """Gated holdings refresh (MoneyDJ fetch & save) for a single ETF.

        Only fetches if latest close date is newer than the latest local snapshot date.
        """
        normalized_code = str(etf_code).strip().upper()
        now = time.time()

        # Check process-level fetch cache
        if now - _HOLDINGS_CACHE.get(normalized_code, 0.0) < _CACHE_TTL_SECONDS:
            return

        with _ETF_LOCKS[normalized_code]:
            # Double check TTL under lock
            if now - _HOLDINGS_CACHE.get(normalized_code, 0.0) < _CACHE_TTL_SECONDS:
                return

            source = MoneyDjActiveEtfSource()
            # 1. Fetch latest close date from primary/fallback market source (no DB storage)
            if latest_close_date is None:
                latest_close_date = source.fetch_latest_close_date(normalized_code)

            if latest_close_date is None:
                return  # Skip if failed to query close date

            # 2. Load latest local snapshot date
            dates = self.storage.load_active_etf_holdings_dates(normalized_code)
            latest_snapshot_date = dates[-1] if dates else None

            # 3. Gating check
            if latest_snapshot_date is None or latest_close_date > latest_snapshot_date:
                try:
                    snapshot_date, df = source.fetch_holdings(normalized_code)
                    self.storage.save_active_etf_holdings(normalized_code, snapshot_date, df)
                    _HOLDINGS_CACHE[normalized_code] = time.time()
                except Exception:  # noqa: BLE001
                    raise

    def sweep_all(self, skip_code: str | None = None) -> None:
        """Sweep all active ETFs to fetch missing daily snapshots.

        Iterates through the active ETF list, gating each ETF by checking if
        latest_close_date > latest_snapshot_date. Skips skip_code and uses
        _SWEEP_CACHE for a 60s per-ETF cooling period.
        """
        import logging
        logger = logging.getLogger(__name__)

        normalized_skip = str(skip_code).strip().upper() if skip_code else None
        etfs = self.get_list()

        for idx, item in enumerate(etfs):
            code = item["code"]
            normalized_code = code.strip().upper()

            if normalized_skip and normalized_code == normalized_skip:
                continue

            # Check _SWEEP_CACHE (60s TTL)
            now = time.time()
            if now - _SWEEP_CACHE.get(normalized_code, 0.0) < 60.0:
                continue

            source = MoneyDjActiveEtfSource()
            # Query latest close date first
            try:
                latest_close_date = source.fetch_latest_close_date(normalized_code)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Sweep failed to fetch close date for {normalized_code}: {exc}")
                latest_close_date = None

            if latest_close_date is None:
                # Do NOT write _SWEEP_CACHE on failure so we can retry next time
                continue

            # Write sweep cache on successful query
            _SWEEP_CACHE[normalized_code] = time.time()

            # Compare and refresh
            dates = self.storage.load_active_etf_holdings_dates(normalized_code)
            latest_snapshot = dates[-1] if dates else None

            if latest_snapshot is None or latest_close_date > latest_snapshot:
                try:
                    self.refresh_holdings_snapshot(normalized_code, latest_close_date=latest_close_date)
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"Sweep failed to refresh holdings for {normalized_code}: {exc}")

            # Politeness delay
            if idx < len(etfs) - 1:
                time.sleep(1.0)
