from typing import Literal, TypedDict

ThemeName = Literal["obsidian_dark", "finance_green", "midnight_blue", "arctic_light", "cyberpunk", "warm_sepia"]

DEFAULT_THEME: ThemeName = "midnight_blue"

class ThemePalette(TypedDict):
    background: str
    surface: str
    primary: str
    text: str
    muted: str
    plotly_template: str

THEMES: dict[ThemeName, ThemePalette] = {
    "obsidian_dark": {
        "background": "#0E1117",
        "surface": "#262730",
        "primary": "#FF4B4B",
        "text": "#FAFAFA",
        "muted": "#A3A8B8",
        "plotly_template": "plotly_dark",
    },
    "finance_green": {
        "background": "#001100",
        "surface": "#002200",
        "primary": "#00FF00",
        "text": "#CCFFCC",
        "muted": "#559955",
        "plotly_template": "plotly_dark",
    },
    "midnight_blue": {
        "background": "#0F172A",
        "surface": "#1E293B",
        "primary": "#38BDF8",
        "text": "#F8FAFC",
        "muted": "#94A3B8",
        "plotly_template": "plotly_dark",
    },
    "arctic_light": {
        "background": "#ECEFF4",
        "surface": "#FFFFFF",
        "primary": "#5E81AC",
        "text": "#2E3440",
        "muted": "#4C566A",
        "plotly_template": "plotly_white",
    },
    "cyberpunk": {
        "background": "#050505",
        "surface": "#18181B",
        "primary": "#F43F5E",
        "text": "#FAFAFA",
        "muted": "#A1A1AA",
        "plotly_template": "plotly_dark",
    },
    "warm_sepia": {
        "background": "#FDF6E3",
        "surface": "#EEE8D5",
        "primary": "#CB4B16",
        "text": "#586E75",
        "muted": "#93A1A1",
        "plotly_template": "plotly_white",
    },
}

def get_theme(name: str) -> tuple[ThemeName, ThemePalette]:
    """回傳合法主題；未知值回退到 midnight_blue。"""
    if name in THEMES:
        return name, THEMES[name]  # type: ignore
    return DEFAULT_THEME, THEMES[DEFAULT_THEME]

def render_theme_css(name: str) -> str:
    """產生注入用的 <style> 字串，包含 CSS 變數與 Streamlit selector overrides。"""
    _, palette = get_theme(name)
    return f"""
<style>
    /* 隱藏 Streamlit 自動產生的 multipage 導覽 */
    [data-testid="stSidebarNav"] {{
        display: none !important;
    }}
    :root {{
        --primary-color: {palette["primary"]};
        --background-color: {palette["background"]};
        --secondary-background-color: {palette["surface"]};
        --text-color: {palette["text"]};
        --muted-text-color: {palette["muted"]};
    }}
    [data-testid="stAppViewContainer"] {{
        background-color: var(--background-color) !important;
        color: var(--text-color) !important;
    }}
    [data-testid="stSidebar"] {{
        background-color: var(--secondary-background-color) !important;
    }}
    [data-testid="stHeader"] {{
        background-color: transparent !important;
    }}

    /* 強制修改所有基礎文字與標題顏色，避免在淺色模式下變成白色 */
    [data-testid="stAppViewContainer"] h1,
    [data-testid="stAppViewContainer"] h2,
    [data-testid="stAppViewContainer"] h3,
    [data-testid="stAppViewContainer"] h4,
    [data-testid="stAppViewContainer"] h5,
    [data-testid="stAppViewContainer"] h6,
    [data-testid="stAppViewContainer"] p,
    [data-testid="stAppViewContainer"] span,
    [data-testid="stAppViewContainer"] label,
    [data-testid="stAppViewContainer"] li,
    .stMarkdown, .stText {{
        color: var(--text-color) !important;
    }}

    /* 針對輸入框與下拉選單背景作修正，確保文字不被同色背景吃掉 */
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    div[data-baseweb="select"] > div {{
        background-color: var(--secondary-background-color) !important;
        color: var(--text-color) !important;
    }}

    /* Metric Cards 覆寫 */
    div[data-testid="metric-container"] {{
        background-color: var(--secondary-background-color) !important;
        border-color: var(--secondary-background-color) !important;
    }}
    div[data-testid="stMetricLabel"] > div {{
        color: var(--muted-text-color) !important;
    }}
    div[data-testid="stMetricValue"] > div {{
        color: var(--text-color) !important;
    }}

    /* Button styling — 淺色主題用深色(text)背景確保對比 ≥4.5:1；深色主題用 primary
       加入 [data-testid="stAppViewContainer"] 前綴，specificity 高於廣域 span/p 規則 */
    [data-testid="stAppViewContainer"] .stButton > button {{
        background-color: {palette["text"] if palette["plotly_template"] == "plotly_white" else palette["primary"]} !important;
        border: 1px solid {palette["text"] if palette["plotly_template"] == "plotly_white" else palette["primary"]} !important;
    }}
    [data-testid="stAppViewContainer"] .stButton > button,
    [data-testid="stAppViewContainer"] .stButton > button p,
    [data-testid="stAppViewContainer"] .stButton > button span {{
        color: {palette["background"]} !important;
    }}
    [data-testid="stAppViewContainer"] .stButton > button:hover,
    [data-testid="stAppViewContainer"] .stButton > button:focus {{
        filter: brightness(1.15) !important;
    }}
</style>
"""
