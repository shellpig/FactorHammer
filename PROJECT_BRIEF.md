# QuantTrader 專案簡報

本文件供新 session 快速了解專案全貌，取代逐份閱讀全部規格文件。需要深入某區段時，按行號索引讀取對應文件。

最後更新：2026-05-10

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
├── data/           fetcher.py, cleaner.py, storage.py, maintenance.py, realtime.py
├── backtest/       base.py, engine_vec.py, engine_event.py, account.py,
│                   events.py, cost.py, metrics.py, report.py, dca.py,
│                   batch.py, sweep.py, walk_forward.py, _helpers.py
├── strategy/
│   ├── base.py     StrategyBase ABC
│   └── examples/   ma_cross.py, dca.py, rsi.py, kd_cross.py,
│                   macd_cross.py, bollinger_band.py, bias.py,
│                   donchian_breakout.py
├── analysis/       technical_summary.py, pattern.py, chip_analysis.py
├── indicators/     calculator.py（pandas-ta 封裝 + 別名映射）
├── ai/             advisor.py（LLM Provider Tool Use）
└── ui/
    ├── app.py      Streamlit 主程式
    ├── themes.py   6 套主題定義
    └── pages/      backtest.py, dashboard.py, data_management.py,
                    ai_chat.py, settings.py

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
├── test_strategies.py, test_batch.py, test_sweep.py, test_walk_forward.py
├── test_technical_summary.py, test_pattern.py
├── test_chip_analysis.py, test_realtime.py, test_dashboard_page.py

data/                （gitignore，執行時自動建立）
  raw/tw/{symbol}/       daily.parquet, minute.parquet,
                         institutional.parquet, margin.parquet
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
| `RSIStrategy` | `rsi` | RSI 超買超賣 |
| `KDCrossStrategy` | `kd_cross` | KD 黃金/死亡交叉 |
| `MACDCrossStrategy` | `macd_cross` | MACD DIF/DEA 交叉 |
| `BollingerBandStrategy` | `bollinger_band` | 布林通道上下緣反轉 |
| `BiasStrategy` | `bias` | 乖離率均值回歸 |
| `DonchianBreakoutStrategy` | `donchian_breakout` | Donchian 高低通道突破 |

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
  initial_capital: 1000000.0
strategies:              # 8 種 preset，詳見 config.yaml
  - name: 定期定額
    type: dollar_cost_averaging
    params: { monthly_day: 5, monthly_amount: 10000.0, ... }
  - name: RSI_14
    type: rsi
    params: { period: 14, oversold: 30.0, overbought: 70.0 }
  - name: KD_Cross / MACD_Cross / BB_20 / BIAS_20 / Donchian_20_10
    ...
  - name: MA20_MA60
    type: moving_average_cross
    params: { short_window: 20, long_window: 60 }
ai:
  enabled: true
  provider: anthropic
  model: claude-sonnet-4-6
ui:
  theme: warm_sepia
  use_extras: true
  use_option_menu: true
realtime:
  cache_ttl: 10
  request_timeout: 5
risk:
  max_daily_loss_pct: 0.03
  max_position_pct: 0.2
  max_drawdown_warning_pct: 0.1
```

## Phase 進度

| Phase | 狀態 | 概要 |
|:---|:---|:---|
| 1 | ✅ 完成 | 台股資料基礎建設（Fetcher、Cleaner L1-L3、Storage、Maintenance） |
| 2 | ✅ 完成 | 向量化回測引擎（Signal、Cost、Metrics、Tearsheet） |
| 3 | ✅ 完成 | 事件驅動引擎（Events、Account、EventLoop、雙引擎一致性） |
| 4 | ✅ 完成 | AI 問答 + Streamlit UI（AIAdvisor、IndicatorEngine、4 頁 UI、E2E） |
| 5 | ✅ 完成 | 回測體驗補充（5-A 股價走勢+EPS、5-B DCA+多策略 preset） |
| 6-A | ✅ 完成 | UI/UX 強化：6 套主題切換、metric card、option_menu 側邊欄 |
| 6-B | ✅ 完成 | 設定頁與側邊欄 UI 小修：隱藏 Streamlit 自動頁面入口、預設 `midnight_blue`、設定/策略儲存分離、8 種策略 preset 與單筆清除 |
| 6-C | ✅ 完成 | 回測頁 UI 細節整理：日期欄位排列、策略比較備註欄、WFA session state hotfix、主題對比與 Plotly 文字可讀性 |
| 7-A | ✅ 完成 | 策略擴充：RSI、KD 交叉、MACD 交叉、布林通道、乖離率、Donchian 突破 + 中文 metadata |
| 7-B | ✅ 完成 | 策略研究工作台：批次比較、結果保存、UI tab 重構、K 線圖、Signal/Trade overlay、指標副圖 |
| 7-C | ✅ 完成 | 參數掃描與防過度最佳化：Grid Search、參數過濾、組合上限、樣本不足警告 |
| 7-D | ✅ 完成 | Walk-Forward Analysis：核心引擎、Walk-Forward tab、中文說明、回測次數預估、進度條、summary/window/stability table、CSV 匯出已驗收 |
| 8-A | ✅ 完成 | 技術面自動判讀引擎：TechnicalSummary dataclass、趨勢/MA/KD/MACD/量能判讀、短線綜合分數、關鍵價位、量價結構分析 |
| 8-B | ✅ 完成 | K線型態辨識：CandlePattern/ChartPatternResult/TimeframeTrend dataclass、10種K線型態、W底M頭偵測、多週期趨勢分析 |
| 8-C | ✅ 完成 | 籌碼分析管線：ChipSummary dataclass、三大法人pivot+加總、融資融券、增量補抓、籌碼集中度判讀 |
| 8-D | ✅ 完成 | 即時行情接入：RealtimeQuote/BidAskStructure dataclass、TWSE MIS API 解析、tse/otc 路由、快取、買賣力道估算 |
| 8-E | ✅ 完成 | AI 綜合分析與操作劇本：DashboardAnalysis/TradingScenario dataclass、structured JSON 輸出、三情境劇本、AI disabled/error 降級例外 |
| 8-F | ✅ 單元驗證完成 | 個股分析儀表板 UI：4 tab 總覽、籌碼與量價、型態與週期、AI 劇本；缺資料與重新整理報價 regression 已補 |

## 當前待辦

見 `驗證後已知問題.md`（每次必讀）。

主線：Phase 8-A/B/C/D/E 已完成驗收；Phase 8-F 單元驗證完成，下一步補 8-F 手動驗收與 Phase 8 回歸。

2026-05-10 狀態：
- 8-A 驗證結果：`tests/test_technical_summary.py` 13 passed, 0.72s
- 8-B 驗證結果：`tests/test_pattern.py` 15 passed, 0.69s
- 8-C 驗證結果：`tests/test_chip_analysis.py` 14 passed, 0.66s
- 8-D 驗證結果：`tests/test_realtime.py` 13 passed, 0.20s
- 8-E 驗證結果：`tests/test_advisor.py` 15 passed, 1 skipped（缺 anthropic API key 的 integration test）
- 8-F 驗證結果：`tests/test_dashboard_page.py` 8 passed, 0.94s；已覆蓋缺日線資料不 crash、重新整理報價更新 session payload 並 rerun
- 新增模組：`src/analysis/technical_summary.py`、`src/analysis/pattern.py`、`src/analysis/chip_analysis.py`、`src/data/realtime.py`、`src/ui/pages/dashboard.py`
- 修改模組：`src/data/fetcher.py`、`src/data/storage.py`、`src/core/constants.py`、`config.yaml`（+realtime section）、`src/ui/app.py`
- 8-E 修改模組：`src/ai/advisor.py`、`src/core/exceptions.py`、`tests/test_advisor.py`
- 8-F 測試模組：`tests/test_dashboard_page.py`

2026-05-10 狀態：
- Phase 8-D 基準 commit：`3fa5322 Complete Phase 8-D implementation and verification`
- 已完成實作測試統計：191 個單元測試、7 個 integration 測試、65 項手動驗收項目（Phase 1-7-D）
- 7-D-1 驗證結果：`tests/test_walk_forward.py tests/test_sweep.py` 為 62 passed, 1 warning（第一次因 Windows temp 權限失敗，elevated 重跑通過）
- 7-D-1 已補 `warning_count` regression test：`test_warning_count_includes_per_window_and_unstable_param`
- 7-D-2 驗收結果：Walk-Forward tab、英文術語中文說明、實際 window 回測次數預估、summary/window/stability table、CSV 匯出入口已驗收
- Phase 7-D 完成回歸：`tests/test_strategies.py tests/test_strategy_config.py tests/test_batch.py tests/test_sweep.py tests/test_walk_forward.py` 為 116 passed, 1 warning（elevated 重跑通過）
- Phase 6-B 已完成設定頁與側邊欄 UI 驗證；`use_container_width` deprecation warning 已處理。`pandas-ta` 對 pandas 4.0 的相容 warning 屬第三方套件根因，仍保留為追蹤限制。
- Phase 6-C 已完成回測頁 UI 驗證與收尾：日期欄位排列、策略比較備註欄、WFA `wfa_symbol` session state hotfix、`midnight_blue` metric card、`warm_sepia` / `arctic_light` Plotly 文字、`arctic_light` 清除按鈕對比皆已更新至 `驗證後已知問題.md`。
- Phase 6-C 相關驗證：`py_compile src\ui\themes.py src\ui\pages\backtest.py src\ui\pages\settings.py src\backtest\report.py` 通過；`tests/test_themes.py tests/test_config_ui_section.py tests/test_settings_page.py tests/test_backtest_page.py tests/test_report.py -v` 為 22 passed（elevated 重跑通過）。

已知設計限制：
- 兩引擎是不同典範（signal-based vs order-based），跨引擎只能比 per-share PnL
- 引擎不支援加倉/分批進出，維持「全進全出」
- 事件引擎已支援 pandas 新舊分鐘頻率 alias（`T` / `min` / `5min` / `H` / `h`）；短資料或無法推斷頻率時 fallback 到 `1day`

## 規格文件索引

### 量化交易系統規格書_shellpig版.md（~2366 行）

| 區段 | 行範圍 | 何時讀 |
|:---|:---|:---|
| 修訂歷史 | 1-19 | 查版本變更 |
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
| Phase 6 UI/UX | 1070-1219 | 修改主題切換、設定頁與側邊欄 UI 小修 |
| Phase 7-A 策略擴充 | 1221-1410 | 實作新策略時必讀 |
| Phase 7-B 策略研究工作台 | 1411-1536 | 實作批次比較/K 線圖/overlay 時必讀 |
| Phase 7-C 參數掃描 | 1537-1661 | 實作參數掃描時必讀 |
| Phase 7-D Walk-Forward Analysis | 1662-1930 | 實作 WFA / OOS 驗證時必讀 |
| **Phase 8 個股綜合分析儀表板** | **1933-2264** | **實作個股分析儀表板時必讀** |
| 子階段總覽 + 費用估算 | 2266-2320 | 總覽 |

### 開發設計方針.md（~5231 行）

| 區段 | 行範圍 | 何時讀 |
|:---|:---|:---|
| 全域規範（型別、時區、測試、目錄） | 9-162 | 新 session 第一次實作前 |
| Phase 1 資料基礎建設 | 164-716 | 修改 data/ 時 |
| Phase 2 向量化回測 | 718-1190 | 修改 engine_vec / cost / metrics |
| Phase 3 事件驅動引擎 | 1192-1614 | 修改 engine_event / account / events |
| Phase 4 AI + Streamlit UI | 1616-2200 | 修改 ai/ / indicators/ / ui/ |
| Phase 6-A 主題切換 | 2207-2321 | 修改 themes.py / settings.py |
| Phase 6-B 設定頁與側邊欄 UI 小修 | 2323-2479 | 修改 app.py / themes.py / config.py / strategy_config.py / settings.py 時必讀 |
| Phase 7-A 策略擴充 | 2481-2943 | 實作新策略時必讀 |
| Phase 7-B 策略研究工作台 | 2945-3325 | 實作批次比較/K 線圖/overlay 時必讀 |
| Phase 7-C 參數掃描 | 3327-3717 | 實作參數掃描時必讀 |
| Phase 7-D Walk-Forward Analysis | 3719-4145 | 實作 WFA runner / UI tab 時必讀 |
| **Phase 8 個股綜合分析儀表板** | **4148-5231** | **實作 analysis/ / realtime / dashboard 時必讀** |

### 測試指南.md（~2219 行）

| 區段 | 行範圍 | 何時讀 |
|:---|:---|:---|
| 環境準備 + 指令速查 | 9-89 | 首次跑測試 |
| Phase 1 測試 | 91-397 | 修改 data/ 時 |
| Phase 2 測試 | 400-660 | 修改 backtest 時 |
| Phase 3 測試 | 663-966 | 修改 events/account/engine_event 時 |
| Phase 4 測試 | 970-1217 | 修改 ai/indicators/UI 時 |
| Phase 6 測試 | 1219-1291 | 修改主題切換、設定頁與側邊欄時 |
| Phase 7-A 測試 | 1295-1495 | 新策略測試 |
| Phase 7-B 測試 | 1497-1584 | 批次比較測試 |
| Phase 7-C 測試 | 1586-1677 | 參數掃描測試 |
| Phase 7-D 測試 | 1698-1856 | Walk-Forward 測試 |
| Phase 7 全階段回歸 | 1858-1876 | Phase 7-D 完成後 |
| **Phase 8 測試** | **1878-2143** | **個股分析儀表板測試** |
| Phase 8 全階段回歸 | 2126-2143 | Phase 8 完成後 |
| 全專案回歸 + 測試統計 | 2146-2219 | Phase 完成後 |

### 驗證後已知問題.md（~737 行）

追蹤驗收中發現的問題。每筆含：位置、狀況、風險、處理階段。已處理的標記 `[✅ 已處理 @ commit]`。每次 session 開始時必讀。

### 未涵蓋資料項目.md

列管目前 fetcher / storage 不抓不存的資料。Phase 8 已接入法人買賣超與融資融券；剩餘項目（財報、股權分散等）仍需先擴規格再走管線。

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
