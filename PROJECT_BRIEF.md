# QuantTrader 專案簡報

本文件供新 session 快速了解專案全貌，取代逐份閱讀全部規格文件。需要深入某區段時，按行號索引讀取對應文件。

最後更新：2026-05-07

---

## 專案概述

台股量化交易研究工具（個人版），運行於 Windows 11 本機。聚焦研究與回測，不接實盤。三大核心功能：自動化台股資料管道、回測引擎（向量化 + 事件驅動）、AI 技術分析問答。

## 技術棧

- Python 3.12+、套件管理 `uv`（`pyproject.toml`）
- 資料處理 pandas、技術指標 pandas-ta
- 台股資料 FinMind API + yfinance 備援
- 儲存 DuckDB + Parquet（零伺服器）
- UI Streamlit、圖表 Plotly
- AI LLM（OpenAI / Anthropic / Gemini，provider-neutral）
- 測試 pytest、虛擬環境 `.venv\Scripts\python.exe`

## 目錄結構

```
src/
├── core/           config.py, constants.py, exceptions.py, strategy_config.py
├── data/           fetcher.py, cleaner.py, storage.py, maintenance.py
├── backtest/       base.py, engine_vec.py, engine_event.py, account.py,
│                   events.py, cost.py, metrics.py, report.py, dca.py
├── strategy/
│   ├── base.py     StrategyBase ABC
│   └── examples/   ma_cross.py, dca.py（Phase 7-A 將新增 6 個策略檔）
├── indicators/     calculator.py（pandas-ta 封裝 + 別名映射）
├── ai/             advisor.py（LLM Provider Tool Use）
└── ui/
    ├── app.py      Streamlit 主程式
    ├── themes.py   6 套主題定義
    └── pages/      backtest.py, data_management.py, ai_chat.py, settings.py

tests/
├── fixtures/       手工構造的 CSV 測試資料
├── test_fetcher.py, test_storage.py, test_cleaner.py
├── test_cost.py, test_metrics.py, test_report.py
├── test_engine_vec.py, test_engine_event.py, test_consistency.py
├── test_account.py, test_events.py
├── test_indicators.py, test_advisor.py
├── test_e2e.py, test_strategy_config.py
├── test_dca_backtest.py, test_maintenance.py
├── test_backtest_page.py, test_themes.py, test_config_ui_section.py

data/                （gitignore，執行時自動建立）
  raw/tw/{symbol}/       daily.parquet, minute.parquet
  processed/tw/{symbol}/ adj_daily.parquet
  backtest/              回測結果快照
  quant.duckdb           元資料
```

## 核心設計原則

1. **零設定啟動**：不依賴任何外部伺服器（無 PostgreSQL、無 Redis、無 Docker）。
2. **免費資料優先**：FinMind 免費層為主、yfinance 備援。一次性下載歷史 → Parquet 落地、日常增量更新。
3. **時區鐵律**：所有 datetime 必須 timezone-aware（`Asia/Taipei`），禁止 naive datetime。
4. **雙引擎並行**：`generate_signals`（向量化）與 `on_bar`（事件驅動）是並行設計，非可互換（已知設計決策，見已知問題）。
5. **策略即文件**：每個策略為獨立 Python 類別，透過 `config.yaml` 的 `strategies[]` preset 管理參數。
6. **AI 可選**：`config.yaml` 設定 `ai.enabled=false` 時，AI 功能關閉，不需要任何 API Key。

## 主要模型與介面

### StrategyBase（策略基類）

```python
class StrategyBase(ABC):
    def generate_signals(self, df: pd.DataFrame) -> pd.Series: ...  # 向量化引擎
    def on_bar(self, bar: BarEvent, account: Account) -> list[OrderEvent]: ...  # 事件驅動
    def reset_runtime_state(self) -> None: ...  # 狀態重置
```

### 現有策略

| 策略類別 | config type | 說明 |
|:---|:---|:---|
| `MACrossStrategy` | `moving_average_cross` | 雙均線交叉 |
| `DollarCostAveragingStrategy` | `dollar_cost_averaging` | 定期定額（專用回測流程） |

### 回測引擎

| 引擎 | 特點 |
|:---|:---|
| `VectorizedBacktester` | 向量化，用 signal +1/-1 驅動，引擎決定下單量 |
| `EventDrivenBacktester` | 事件驅動，策略回傳 OrderEvent，next-bar 成交 |

### IndicatorEngine 支援指標

KD、RSI_14、MACD、BBANDS_20、ATR_14、OBV、WILLR、EMA_12、EMA_26、MA_{n}、EMA_{n}。

### config.yaml 結構

```yaml
system:
  data_dir: ./data
  log_level: INFO
  timezone: Asia/Taipei
data:
  primary_source: finmind
  fallback_source: yfinance
backtest:
  commission_rate: 0.001425
  commission_discount: 0.6
  tax_rate: 0.003
  etf_tax_rate: 0.001
  slippage_ticks: 1
strategies:
  - name: MA20_MA60
    type: moving_average_cross
    params: { short_window: 20, long_window: 60 }
ai:
  enabled: true
  provider: anthropic
  model: claude-sonnet-4-20250514
ui:
  theme: arctic_light
  use_extras: true
  use_option_menu: true
```

## Phase 進度

| Phase | 狀態 | 概要 |
|:---|:---|:---|
| 1 | ✅ 完成 | 台股資料基礎建設（Fetcher、Cleaner L1-L3、Storage、Maintenance） |
| 2 | ✅ 完成 | 向量化回測引擎（Signal、Cost、Metrics、Tearsheet） |
| 3 | ✅ 完成 | 事件驅動引擎（Events、Account、EventLoop、雙引擎一致性） |
| 4 | ✅ 完成 | AI 問答 + Streamlit UI（AIAdvisor、IndicatorEngine、4 頁 UI、E2E） |
| 5 | ✅ 完成 | 回測體驗補充（5-A 股價走勢+EPS、5-B DCA+多策略 preset） |
| 6 | ✅ 完成 | UI/UX 強化（6-A 6 套主題切換） |
| 7-A | 📋 規格已寫 | 策略擴充：RSI、KD 交叉、MACD 交叉、布林通道、乖離率、Donchian 突破 + 中文 metadata |
| 7-B | 📋 規格已寫 | 策略研究工作台：批次比較、結果保存、UI tab 重構、K 線圖、Signal/Trade overlay、指標副圖 |
| 7-C | 📋 規格已寫 | 參數掃描與防過度最佳化：Grid Search、參數過濾、組合上限、樣本不足警告 |

## 當前待辦

見 `已知問題.md`（每次必讀）。

主線：Phase 1-6 全部完成。Phase 7-A/7-B/7-C 規格已寫入三份文件，待實作。實作順序：7-A → 7-B → 7-C。

2026-05-08 狀態：
- 最新 commit：`61ea6aa docs: align Phase 6-A theme names with implementation (V1.6)`
- 主分支 clean，無未提交變更
- 單元測試：136 passed, 8 deselected（integration）

已知設計限制：
- 兩引擎是不同典範（signal-based vs order-based），跨引擎只能比 per-share PnL
- 引擎不支援加倉/分批進出，維持「全進全出」
- `_calculate_order_quantity` sizing 未預留交易成本，邊界情況可能觸發 `Insufficient cash`

## 規格文件索引

### 量化交易系統規格書_shellpig版.md（~1590 行）

| 區段 | 行範圍 | 何時讀 |
|:---|:---|:---|
| 修訂歷史 | 1-15 | 查版本變更 |
| 專案願景與目標 | 41-56 | 理解定位 |
| 技術語言與套件選型 | 58-84 | 技術決策參考 |
| 系統架構（四層架構圖） | 87-169 | 理解整體結構 |
| 資料來源規劃 | 173-217 | 修改 fetcher 時 |
| 資料品質與清洗（L1/L2/L3、時區） | 219-289 | 修改 cleaner 時 |
| 回測引擎規格 | 291-480 | 修改 backtest 時 |
| AI 技術分析模組 | 482-629 | 修改 ai/advisor 時 |
| 風控規格 | 631-644 | 風控相關 |
| 本機部署規格 | 646-742 | 環境設定 |
| 測試策略 | 744-765 | 測試方針 |
| Phase 1-4 開發計畫 | 776-945 | 查歷史 phase 規格 |
| Phase 5 回測體驗 | 948-1064 | 修改 DCA / 股價走勢 |
| Phase 6 UI/UX | 1067-1126 | 修改主題切換 |
| **Phase 7-A 策略擴充** | **1130-1318** | **實作新策略時必讀** |
| **Phase 7-B 策略研究工作台** | **1320-1444** | **實作批次比較/K 線圖/overlay 時必讀** |
| **Phase 7-C 參數掃描** | **1446-1569** | **實作參數掃描時必讀** |
| 子階段總覽 + 費用估算 | 1571-1590 | 總覽 |

### 開發設計方針.md（~3400 行）

| 區段 | 行範圍 | 何時讀 |
|:---|:---|:---|
| 全域規範（型別、時區、測試、目錄） | 9-162 | 新 session 第一次實作前 |
| Phase 1 資料基礎建設 | 164-716 | 修改 data/ 時 |
| Phase 2 向量化回測 | 718-1190 | 修改 engine_vec / cost / metrics |
| Phase 3 事件驅動引擎 | 1192-1614 | 修改 engine_event / account / events |
| Phase 4 AI + Streamlit UI | 1616-2200 | 修改 ai/ / indicators/ / ui/ |
| Phase 6 主題切換 | 2203-2321 | 修改 themes.py / settings.py |
| **Phase 7-A 策略擴充** | **2325-2783** | **實作新策略時必讀** |
| **Phase 7-B 策略研究工作台** | **2785-3165** | **實作批次比較/K 線圖/overlay 時必讀** |
| **Phase 7-C 參數掃描** | **3167-3400** | **實作參數掃描時必讀** |

### 測試指南.md（~1710 行）

| 區段 | 行範圍 | 何時讀 |
|:---|:---|:---|
| 環境準備 + 指令速查 | 9-89 | 首次跑測試 |
| Phase 1 測試 | 91-397 | 修改 data/ 時 |
| Phase 2 測試 | 400-660 | 修改 backtest 時 |
| Phase 3 測試 | 663-966 | 修改 events/account/engine_event 時 |
| Phase 4 測試 | 970-1217 | 修改 ai/indicators/UI 時 |
| Phase 6 測試 | 1219-1252 | 修改主題切換時 |
| **Phase 7-A 測試** | **1256-1454** | **新策略測試** |
| **Phase 7-B 測試** | **1456-1543** | **批次比較測試** |
| **Phase 7-C 測試** | **1545-1636** | **參數掃描測試** |
| Phase 7 全階段回歸 | 1638-1656 | Phase 7 完成後 |
| 全專案回歸 + 測試統計 | 1658-1710 | Phase 完成後 |

### 已知問題.md（~420 行）

追蹤驗收中發現的問題。每筆含：位置、狀況、風險、處理階段。已處理的標記 `[✅ 已處理 @ commit]`。每次 session 開始時必讀。

### 未涵蓋資料項目.md

列管目前 fetcher / storage 不抓不存的資料（法人買賣超、融資融券、財報等）。策略需要這些資料時，需先回頭擴規格再走 Phase 1 管線。

## 測試速查

```powershell
# 全部單元測試（不含整合）
.\.venv\Scripts\python.exe -m pytest tests/ -v -m "not integration"

# 含整合測試
.\.venv\Scripts\python.exe -m pytest tests/ -v

# 指定測試檔
.\.venv\Scripts\python.exe -m pytest tests/test_engine_vec.py -v

# 覆蓋率
.\.venv\Scripts\python.exe -m pytest tests/ --cov=src --cov-report=term-missing -m "not integration"

# 啟動 Streamlit UI
.\.venv\Scripts\python.exe -m streamlit run src/ui/app.py
```

注意：Windows/OneDrive 路徑下 pytest 暫存目錄可能出現 `PermissionError: [WinError 5]`，視為環境問題，不影響測試結果。
