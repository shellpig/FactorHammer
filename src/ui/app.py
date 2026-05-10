"""Streamlit entrypoint for QuantTrader UI."""

from __future__ import annotations

import warnings

import pandas as pd
import streamlit as st

warnings.filterwarnings(
    "ignore",
    message=r"The 'mode\.copy_on_write' option is deprecated\.",
    category=pd.errors.Pandas4Warning,
    module=r"pandas_ta(\..*)?$",
)

from src.core.config import get_config
from src.ui.pages import ai_chat, backtest, dashboard, data_management, settings
from src.ui.themes import get_theme, render_theme_css

try:
    from streamlit_option_menu import option_menu
    HAS_OPTION_MENU = True
except ImportError:
    HAS_OPTION_MENU = False


def main() -> None:
    st.set_page_config(page_title="QuantTrader", page_icon="📊", layout="wide")

    config = get_config()
    ui_section = config.get("ui", {}) if isinstance(config, dict) else {}
    theme_name = str(ui_section.get("theme", "midnight_blue")).strip()
    use_option_menu = bool(ui_section.get("use_option_menu", True))

    valid_theme_name, _ = get_theme(theme_name)
    if theme_name and theme_name != valid_theme_name:
        st.warning(f"未知的主題 '{theme_name}'，已回退至 '{valid_theme_name}'。")
    st.markdown(render_theme_css(valid_theme_name), unsafe_allow_html=True)

    ai_section = config.get("ai", {}) if isinstance(config, dict) else {}
    ai_enabled = bool(ai_section.get("enabled", False))

    st.sidebar.title("QuantTrader")
    st.sidebar.caption("台股量化研究工具")
    if ai_enabled:
        st.sidebar.success("AI 功能：啟用")
    else:
        st.sidebar.info("AI 功能：停用")

    if use_option_menu and HAS_OPTION_MENU:
        with st.sidebar:
            page_name = option_menu(
                "功能頁面",
                options=["資料管理", "回測", "個股分析", "AI 問答", "設定"],
                default_index=0,
            )
    else:
        page_name = st.sidebar.radio(
            "功能頁面",
            options=["資料管理", "回測", "個股分析", "AI 問答", "設定"],
            index=0,
        )

    if page_name == "資料管理":
        data_management.render()
    elif page_name == "回測":
        backtest.render()
    elif page_name == "個股分析":
        dashboard.render_dashboard_page()
    elif page_name == "AI 問答":
        ai_chat.render()
    else:
        settings.render()


if __name__ == "__main__":
    main()
