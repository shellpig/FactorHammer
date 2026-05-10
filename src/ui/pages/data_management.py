"""Data management page."""

from __future__ import annotations

from dataclasses import asdict
import re

import pandas as pd
import streamlit as st

from src.core.config import get_config
from src.data.cleaner import DataCleaner
from src.data.fetcher import FinMindFetcher, IDataFetcher, YFinanceFetcher
from src.data.maintenance import DataMaintenance
from src.data.storage import DuckDBMeta, ParquetStorage

_TW_SYMBOL_PATTERN = re.compile(r"^[0-9A-Z]{4,6}$")


def render() -> None:
    st.title("資料管理")
    st.caption("管理本機歷史資料、更新與重建。")

    symbol = st.text_input("股票代碼", value="2330").strip().upper()

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        do_refresh = st.button("重新整理列表", width="stretch")
    with col2:
        do_update = st.button("更新", type="primary", width="stretch")
    with col3:
        do_rebuild = st.button("重建", width="stretch")

    if do_update or do_rebuild:
        if not _TW_SYMBOL_PATTERN.fullmatch(symbol):
            st.error("請輸入有效的台股代碼（4~6 位英數字）。")
        else:
            _run_maintenance(symbol=symbol, rebuild=do_rebuild)

    if do_refresh or True:
        _render_meta_table()


def _run_maintenance(symbol: str, rebuild: bool) -> None:
    progress = st.progress(0, text="準備中...")
    try:
        progress.progress(10, text="初始化元件...")
        fetcher = _build_fetcher()
        storage = ParquetStorage()
        meta = DuckDBMeta()
        cleaner = DataCleaner()
        maintenance = DataMaintenance(fetcher=fetcher, storage=storage, meta=meta, cleaner=cleaner)

        if rebuild:
            progress.progress(40, text=f"重建 {symbol} 資料中...")
            report = maintenance.rebuild_symbol(symbol)
            progress.progress(100, text="完成")
            st.success(f"{symbol} 重建完成。")
            st.json(asdict(report), expanded=False)
        else:
            progress.progress(40, text=f"更新 {symbol} 日K中...")
            added = maintenance.update_daily(symbol)
            progress.progress(100, text="完成")
            st.success(f"{symbol} 更新完成，新增 {added} 筆。")
    except Exception as exc:  # noqa: BLE001
        st.error(f"資料操作失敗：{exc}")
    finally:
        try:
            meta.close()  # type: ignore[name-defined]
        except Exception:
            pass


def _render_meta_table() -> None:
    try:
        meta = DuckDBMeta()
        df = meta.list_all()
    except Exception as exc:  # noqa: BLE001
        st.error(f"讀取 metadata 失敗：{exc}")
        return
    finally:
        try:
            meta.close()  # type: ignore[name-defined]
        except Exception:
            pass

    if df.empty:
        st.info("目前尚無資料。可輸入代碼後按「更新」下載。")
        return

    out = df.copy()
    for col in ("first_date", "last_date", "updated_at"):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce")
    st.dataframe(out, width="stretch")


def _build_fetcher() -> IDataFetcher:
    cfg = get_config()
    data_section = cfg.get("data", {}) if isinstance(cfg, dict) else {}
    primary = str(data_section.get("primary_source", "finmind")).strip().lower()
    fallback = str(data_section.get("fallback_source", "yfinance")).strip().lower()
    order = [primary, fallback]

    errors: list[str] = []
    for source in order:
        try:
            if source == "finmind":
                return FinMindFetcher()
            if source == "yfinance":
                return YFinanceFetcher()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{source}: {exc}")

    raise RuntimeError(f"No available data source. Details: {' | '.join(errors) if errors else 'n/a'}")


if __name__ == "__main__":
    render()
