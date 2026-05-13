# QuantTrader 專案簡報

本文件供新 session 快速了解專案全貌，取代逐份閱讀全部規格文件。需要深入某區段時，按行號索引讀取對應文件。

最後更新：2026-05-13

---

## 專案概述

台股量化交易研究工具（個人版），運行於 Windows 11 本機。聚焦研究與回測，不接實盤。三大核心功能：自動化台股資料管道、回測引擎（向量化 + 事件驅動）、AI 技術分析問答。

2026-05-13 Phase 9-A~9-F 自動化驗證全部完成（`89a4071` 已 push）：多市場基礎架構、美股日 K 資料管線、美股回測支援、美股技術分析儀表板、資料管理頁美股支援、Phase 9 整合回歸（428 passed）。9-F 手動驗收 12 項（9-F-1~9-F-12）待使用者執行。9-G 規格已追加：美股 yfinance 1m intraday 盤中快照與分 K 圖，使用最新 1 分 K close 作為近似盤中價，不做 WebSocket / 買一賣一 / 五檔 / tick。

## 技術棧

- Python 3.12+、套件管理 `uv`（`pyproject.toml`）
- 資料處理 pandas、技術指標 pandas-ta
- 台股資料 FinMind API + yfinance 備援；美股日 K 使用 yfinance（Phase 9-B）；9-G 規格追加美股 yfinance 1m intraday 盤中快照與分 K 圖
- 儲存 DuckDB + Parquet（零伺服器）
- UI Streamlit、圖表 Plotly
- AI LLM（OpenAI / Anthropic / Gemini，provider-neutral）
- 測試 pytest、虛擬環境 `.venv\Scripts\python.exe`

## 目錄結構

```
src/
├── core/           config.py, constants.py, exceptions.py, market.py, strategy_config.py
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
├── test_market.py, test_fetcher.py, test_storage.py, test_cleaner.py
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
  raw/us/{symbol}/       daily.parquet（Phase 9-B 已實作）
  processed/us/{symbol}/ adj_daily.parquet（Phase 9-B 已實作）
  backtest/              回測結果快照
  quant.duckdb           元資料
```

## 核心設計原則

1. **零設定啟動**：不依賴任何外部伺服器（無 PostgreSQL、無 Redis、無 Docker）。
2. **免費資料優先**：FinMind 免費層為主、yfinance 備援。一次性下載歷史 → Parquet 落地、日常增量更新。
3. **時區鐵律**：所有 datetime 必須 timezone-aware；台股使用 `Asia/Taipei`，美股使用 `America/New_York`（Phase 9-A 起由 `MarketSpec.timezone` 統一管理），禁止 naive datetime。
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
| 8-F | ✅ 完成 | 個股分析儀表板 UI：4 tab 總覽、籌碼與量價、型態與週期、AI 劇本；缺資料、重新整理報價、英文字母股票代碼、多週期資料欄位 regression 已補 |
| 8-G | ✅ 完成 | 新手友善說明文字：技術分析總覽 tooltip、K 棒型態詳細說明、量價結構 caption、籌碼術語解釋、壓力支撐概念、短線分數組成，已完成人工驗收 |
| 9-A | ✅ 完成 | 多市場基礎架構：`MarketSpec`、`market` context、storage/meta/maintenance market-aware、DuckDB meta migration、`assert_single_market`、symbol 正規化與路徑穿越防護 |
| 9-B | ✅ 完成 | 美股日 K 資料管線：yfinance daily、`BRK.B`→`BRK-B`、`America/New_York`、adjusted OHLC（price ratio）、split-adjusted volume（split-only factor）、`fetch_daily_with_adjusted`、US minute 拒絕、批次節流 |
| 9-C | ✅ 完成 | 美股回測支援：回測頁市場切換（單次/批次/參數掃描/WFA）、USD、1 股單位、`USCostCalculator`、DCA 不支援碎股 warning、台美 K 線顏色慣例 |
| 9-D | ✅ 完成 | 美股技術分析儀表板：市場切換、adjusted daily、技術面/K線/型態/AI 劇本；停用即時與籌碼；shares 顯示、紐約日期、AI 強制繁中輸出 |
| 9-E | ✅ 完成 | 資料管理頁美股支援：市場切換、yfinance 日 K 更新/重建、BRK.B 正規化、raw/adjusted 狀態、停用分 K 與籌碼 |
| 9-F | ⚠️ 自動驗證完成，手動驗收待做 | Phase 9 整合回歸與文件收束：全專案自動測試 428 passed；手動驗收 9-F-1~9-F-12 待使用者執行 |
| 9-G | 📋 規格已定，待實作 | 美股 yfinance 1m intraday 盤中快照與分 K 圖：最新 1 分 K close 作為近似盤中價、漲跌對前一紐約交易日 close、成交量為今日 1m volume 加總；不做 WebSocket、買一/賣一、五檔、tick、intraday 回測 |

## 當前待辦

見 `驗證後已知問題.md`（每次必讀）。

主線：Phase 9-A~9-F 自動化部分全部完成，已 push（`89a4071`）。9-F 手動驗收 12 項（9-F-1~9-F-12）待使用者執行。9-G 已完成規格文件追加，待後續實作。

2026-05-13 狀態：
- 最新 commit：`662507e docs: complete Phase 9-F document closure and brief update`（已 push 至 `origin/main`）。
- Phase 9-G 規格已寫入 `量化交易系統規格書_shellpig版.md`、`開發設計方針.md`、`測試指南.md` 並更新本 brief：使用 yfinance 1m intraday 補美股盤中快照與分 K 圖；總覽現價採最新 1 分 K close，漲跌 / 漲跌幅對前一紐約交易日 close，成交量採今日 regular session 1m volume 加總；若 intraday 不可用則降級 adjusted daily；不做 WebSocket、買一/賣一、五檔、tick、盤前盤後或 intraday 回測。
- Phase 9-C/9-D/9-E 已驗證完成；Phase 9-F 全專案自動回歸 428 passed，文件收束完成。
- Phase 9-C 驗證結果：`tests/test_cost.py tests/test_engine_vec.py tests/test_dca_backtest.py tests/test_backtest_page.py -m "not integration"` 為 42 passed；py_compile `src/backtest/cost.py src/backtest/_helpers.py src/backtest/dca.py src/backtest/batch.py src/backtest/sweep.py src/backtest/walk_forward.py src/ui/pages/backtest.py tests/test_cost.py tests/test_dca_backtest.py tests/test_backtest_page.py` 通過。
- Phase 9-C research tabs 回歸：`tests/test_batch.py tests/test_sweep.py tests/test_walk_forward.py tests/test_strategy_config.py tests/test_strategies.py -m "not integration"` 為 120 passed。
- Phase 9-C broader context 回歸：`tests/test_market.py tests/test_fetcher.py tests/test_storage.py tests/test_maintenance.py tests/test_cost.py tests/test_engine_vec.py tests/test_engine_event.py tests/test_consistency.py tests/test_dca_backtest.py tests/test_backtest_page.py tests/test_batch.py tests/test_sweep.py tests/test_walk_forward.py -m "not integration"` 為 194 passed, 6 deselected。
- 9-C 修改模組：`src/backtest/cost.py`（`TWCostCalculator` / `USCostCalculator` / `create_cost_calculator`）、`src/backtest/_helpers.py`（market-aware ETF/cost helper）、`src/backtest/dca.py`（美股 1 股 DCA、New York timezone）、`src/backtest/batch.py`、`src/backtest/sweep.py`、`src/backtest/walk_forward.py`（可注入 US cost calculator）、`src/ui/pages/backtest.py`（市場切換、US adjusted data、USD 顯示、DCA warning、台美 K 線顏色）。
- 9-C 新增/擴充測試：`tests/test_cost.py`（US cost model）、`tests/test_dca_backtest.py`（美股 DCA 1 股與月投入不足）、`tests/test_backtest_page.py`（US adjusted load、auto sync market、USD caption、DCA warning、不顯示「張」、caption 與 K 線顏色 market-aware）。
- Phase 9-D 驗證結果：`tests/test_technical_summary.py tests/test_pattern.py tests/test_advisor.py tests/test_dashboard_page.py -m "not integration"` 為 79 passed, 1 deselected；py_compile `src/ui/pages/dashboard.py src/ai/advisor.py src/analysis/technical_summary.py src/analysis/pattern.py tests/test_dashboard_page.py tests/test_advisor.py` 通過。
- Phase 9-D broader context 回歸：`tests/test_market.py tests/test_fetcher.py tests/test_storage.py tests/test_maintenance.py tests/test_cost.py tests/test_engine_vec.py tests/test_engine_event.py tests/test_consistency.py tests/test_dca_backtest.py tests/test_backtest_page.py tests/test_batch.py tests/test_sweep.py tests/test_walk_forward.py tests/test_technical_summary.py tests/test_pattern.py tests/test_advisor.py tests/test_dashboard_page.py -m "not integration"` 為 273 passed, 7 deselected。
- 9-D 修改模組：`src/ui/pages/dashboard.py`（dashboard 市場切換、美股 adjusted daily payload、停用 realtime/chip、shares 成交量、紐約日期 caption、美股即時刷新不支援提示）、`src/ai/advisor.py`（market-aware symbol 驗證、payload 帶 market/currency、prompt 強制繁中、AI tools 支援 market）。
- 9-D 新增/擴充測試：`tests/test_dashboard_page.py`（美股 adjusted daily、停用 realtime/chip、籌碼不支援提示、shares label、紐約日期 caption）、`tests/test_advisor.py`（美股 prompt 帶 market/currency/繁中硬約束、拒絕非 US-1 ticker、AI tool 接受美股 market context）。
- Phase 9-E 驗證結果：`tests/test_data_management_page.py tests/test_stock_selector.py tests/test_maintenance.py -m "not integration"` 為 23 passed；py_compile `src/ui/pages/data_management.py src/ui/stock_selector.py tests/test_data_management_page.py tests/test_stock_selector.py tests/test_maintenance.py` 通過。
- Phase 9-E broader context 回歸：`tests/test_market.py tests/test_fetcher.py tests/test_storage.py tests/test_maintenance.py tests/test_cost.py tests/test_engine_vec.py tests/test_engine_event.py tests/test_consistency.py tests/test_dca_backtest.py tests/test_backtest_page.py tests/test_batch.py tests/test_sweep.py tests/test_walk_forward.py tests/test_technical_summary.py tests/test_pattern.py tests/test_advisor.py tests/test_dashboard_page.py tests/test_data_management_page.py tests/test_stock_selector.py -m "not integration"` 為 284 passed, 7 deselected。
- 9-E 修改模組：`src/ui/pages/data_management.py`（資料管理頁市場切換、美股 yfinance-only fetcher、日 K 更新/重建 market 傳遞、分 K/籌碼不支援提示、raw daily / adjusted daily 本機狀態表、metadata market filter）、`src/ui/stock_selector.py`（market-aware stock selector，美股 ticker 輸入與 `BRK.B`→`BRK-B` 正規化）。
- 9-E 新增/擴充測試：`tests/test_data_management_page.py`（美股不支援訊息、update_daily market=us、yfinance-only、metadata market filter、raw/adjusted 狀態表、缺 adjusted 顯示、台股不顯示美股狀態表）、`tests/test_stock_selector.py`（美股 ticker 正規化與 invalid suffix uppercase fallback）。
- Phase 9-F 自動驗證結果：Phase 9 指定回歸 `tests/test_market.py tests/test_fetcher.py tests/test_storage.py tests/test_maintenance.py tests/test_cost.py tests/test_engine_vec.py tests/test_dca_backtest.py tests/test_backtest_page.py tests/test_technical_summary.py tests/test_pattern.py tests/test_advisor.py tests/test_dashboard_page.py -m "not integration"` 為 181 passed, 7 deselected。
- Phase 9-F data management / selector 回歸：`tests/test_data_management_page.py tests/test_stock_selector.py -m "not integration"` 為 11 passed。
- Phase 9-F 全專案非整合回歸：`tests/ -m "not integration"` 為 428 passed, 10 deselected。
- Phase 9-F 驗證備註：一般權限第一次跑 Phase 9 指定回歸與全專案回歸時，Windows/OneDrive `.pytest_tmp_*` 清理出現 `PermissionError: [WinError 5]`；依專案規則使用同一 venv、同一範圍 elevated 重跑後全部通過，判定為環境暫存目錄權限問題。

2026-05-12 狀態：
- 最新基準 commit：`75fee58 Add one-click install script and market core module`
- Phase 9-A 驗證結果：`tests/test_market.py tests/test_storage.py tests/test_maintenance.py -m "not integration"` 為 39 passed；py_compile `src/core/market.py src/data/storage.py src/data/maintenance.py` 通過
- Phase 9-B 驗證結果：`tests/test_fetcher.py tests/test_storage.py tests/test_maintenance.py -m "not integration"` 為 49 passed, 6 deselected（integration）；py_compile `src/data/fetcher.py src/data/maintenance.py` 通過
- 9-A 新增模組：`src/core/market.py`（MarketSpec、normalize_symbol、validate_symbol、assert_single_market）
- 9-A 修改模組：`src/data/storage.py`（normalize 函式群改 timezone 參數、DuckDB meta migration、market-aware 路徑）、`src/data/maintenance.py`（market 參數傳遞）
- 9-B 修改模組：`src/data/fetcher.py`（YFinanceFetcher market 參數、fetch_daily_with_adjusted、US adjusted bundle、split-only volume factor、US minute 拒絕）、`src/data/maintenance.py`（US adjusted bundle path、yfinance 批次節流）
- 9-A/9-B 新增測試：`tests/test_market.py`（11 tests）；`test_storage.py` 追加 5 tests（us path、unknown market、meta PK、migration）；`test_fetcher.py` 追加 12 tests（US ticker/tz/volume/adjusted/split/minute）；`test_maintenance.py` 追加 4 tests（US rebuild/update/throttle/rate-limit）
- storage.py 已完全移除 TAIPEI_TZ hardcode，改由 market timezone 動態決定；cleaner.py 無 timezone hardcode
- Phase 9 規格已納入審查重點：split-adjusted volume、禁止混合台美 DataFrame、yfinance 批次 request 至少 1 秒節流、美股 DCA 不支援碎股 warning、AI prompt 強制繁體中文

2026-05-11 狀態：
- Phase 9 規格已確認並寫入正式文件：US-1 範圍為美股日 K + 調整後價格 + 回測 + 技術分析；不做即時、籌碼、分 K、財報、期權、匯率換算。
- Phase 8 + 回測頁相關回歸：`tests/test_technical_summary.py tests/test_pattern.py tests/test_chip_analysis.py tests/test_realtime.py tests/test_advisor.py tests/test_dashboard_page.py tests/test_backtest_page.py -m "not integration"` 為 98 passed, 1 deselected。
- Realtime / dashboard 針對性回歸：`tests/test_realtime.py tests/test_dashboard_page.py -m "not integration"` 為 37 passed。
- `py_compile src\data\realtime.py src\ui\pages\dashboard.py` 通過；Phase 8 全範圍 py_compile 曾因 Windows/OneDrive `__pycache__` 權限擋住，elevated 重跑通過。
- 8-A 驗證結果：`tests/test_technical_summary.py` 13 passed
- 8-B 驗證結果：`tests/test_pattern.py` 15 passed
- 8-C 驗證結果：`tests/test_chip_analysis.py` 14 passed
- 8-D 驗證結果：`tests/test_realtime.py` 17 passed；新增非交易日 / 盤後即時報價時間判斷、`z="-"` 時不把買賣中間估算價塞進 `quote.price` 的 regression
- 8-E 驗證結果：`tests/test_advisor.py` 15 passed, 1 deselected（integration test 未跑）
- 8-F 驗證結果：`tests/test_dashboard_page.py` 19 passed；已覆蓋缺日線資料不 crash、重新整理報價更新 session payload 並 rerun、英文字母股票代碼、多週期 date 欄位 payload、盤中買一/賣一顯示、盤後收盤價/日成交量、近 5 日法人表格與籌碼抓取錯誤提示、輸入框 Enter 透過 form submit 穩定觸發分析、日線股數轉張顯示
- 8-G 驗證結果：`py_compile src\ui\pages\dashboard.py tests\test_dashboard_page.py` 通過；`tests/test_dashboard_page.py -m "not integration"` 為 27 passed；6 項人工驗收完成（tooltip hover、caption、K 棒詳細說明、日/週/月線說明）
- 回測頁 follow-up 驗證：`tests/test_backtest_page.py` 9 passed；已覆蓋回測載入前自動同步日線資料與 primary/fallback 資料源切換
- 8-F 手動驗收修正：日 K 線圖高度、支撐/壓力標註、拖曳平移、range slider、型態顯示、K 線 X 軸改 categorical 消除週末空隙
- Phase 8 後續修正：W 底 / M 頭同時偵測時改判為區間震盪；支撐/壓力改取近 20 日低點 / 近 60 日高點極值；資料管理頁支援 `00981A` 這類英文字母股票代碼；K 棒數量下拉；個股分析與回測自動補抓/更新日線；籌碼 tab 自動補抓並顯示近 5 交易日三大法人；盤中行情改顯示買一/賣一與盤中量，盤後顯示最新日線收盤價與日成交量；`RealtimeQuote.estimated_price` 獨立承載買賣中間估算價，`quote.price` 不再默默等於估算價；個股分析輸入框改用 form submit 支援 Enter；盤後日線成交量由股數轉張顯示
- 新增模組：`src/analysis/technical_summary.py`、`src/analysis/pattern.py`、`src/analysis/chip_analysis.py`、`src/data/realtime.py`、`src/ui/pages/dashboard.py`
- 修改模組：`src/data/fetcher.py`、`src/data/storage.py`、`src/data/realtime.py`、`src/core/constants.py`、`config.yaml`、`src/ui/app.py`、`src/ui/pages/dashboard.py`、`src/ui/pages/backtest.py`、`src/ui/pages/data_management.py`、`src/analysis/technical_summary.py`、`src/analysis/pattern.py`、`src/analysis/chip_analysis.py`
- 8-E 修改模組：`src/ai/advisor.py`、`src/core/exceptions.py`、`tests/test_advisor.py`
- 8-F / follow-up 測試模組：`tests/test_realtime.py`、`tests/test_dashboard_page.py`、`tests/test_backtest_page.py`、`tests/test_chip_analysis.py`

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

### 量化交易系統規格書_shellpig版.md（~2730 行）

| 區段 | 行範圍 | 何時讀 |
|:---|:---|:---|
| 修訂歷史 | 3-22 | 查版本變更，Phase 9 為 `V2.1` |
| 專案願景與目標 | 46-61 | 理解定位 |
| 技術語言與套件選型 | 63-90 | 技術決策參考 |
| 系統架構（四層架構圖） | 92-176 | 理解整體結構 |
| 資料來源規劃 | 178-222 | 修改 fetcher 時 |
| 資料品質與清洗（L1/L2/L3、時區） | 224-294 | 修改 cleaner / timezone 時 |
| 回測引擎規格 | 296-485 | 修改 backtest 時 |
| AI 技術分析模組 | 487-634 | 修改 ai/advisor 時 |
| 風控規格 | 636-649 | 風控相關 |
| 本機部署規格 | 651-747 | 環境設定 |
| 測試策略 | 749-770 | 測試方針 |
| Phase 1-4 開發計畫 | 772-951 | 查歷史 phase 規格 |
| Phase 5 回測體驗 | 953-1070 | 修改 DCA / 股價走勢 |
| Phase 6 UI/UX | 1072-1221 | 修改主題切換、設定頁與側邊欄 UI 小修 |
| Phase 7 策略擴充（7-A~7-D） | 1223-1932 | 策略、研究工作台、參數掃描、WFA |
| Phase 8 個股綜合分析儀表板（8-A~8-G） | 1934-2365 | 實作 analysis/ / realtime / dashboard / 說明文字時必讀 |
| **Phase 9 美股 US-1 / 9-G 支援** | **2368-2646** | **美股日 K、調整後價格、回測、技術分析、多市場架構、yfinance 1m intraday 盤中快照與分 K 圖時必讀** |
| 子階段總覽 | 2648-2663 | Phase 總覽 |
| 費用估算 | 2665-2681 | API / yfinance / US-2 資料源成本 |
| 附錄 A：免責聲明全文 | 2683-2702 | 免責聲明文案 |
| 附錄 B：架構決策補充 | 2704-2730 | 美股邊界與 AI provider 抽象 |

### 開發設計方針.md（~6273 行）

| 區段 | 行範圍 | 何時讀 |
|:---|:---|:---|
| 全域規範（型別、時區、測試、目錄） | 9-168 | 新 session 第一次實作前；Phase 9 起 timezone 改 market-aware |
| Phase 1 資料基礎建設 | 170-722 | 修改 data/ 時 |
| Phase 2 向量化回測 | 724-1196 | 修改 engine_vec / cost / metrics |
| Phase 3 事件驅動引擎 | 1198-1620 | 修改 engine_event / account / events |
| Phase 4 AI + Streamlit UI | 1622-2089 | 修改 ai/ / indicators/ / ui/ |
| 架構補充：市場與 AI Provider 抽象 | 2131-2228 | 市場抽象、Phase 9 US-1 邊界、AI provider 抽象 |
| Phase 6-A 主題切換 | 2232-2344 | 修改 themes.py / settings.py |
| Phase 6-B 設定頁與側邊欄 UI 小修 | 2346-2502 | 修改 app.py / themes.py / config.py / strategy_config.py / settings.py 時必讀 |
| Phase 7-A 策略擴充 | 2506-2964 | 實作新策略時必讀 |
| Phase 7-B 策略研究工作台 | 2966-3346 | 實作批次比較/K 線圖/overlay 時必讀 |
| Phase 7-C 參數掃描 | 3348-3738 | 實作參數掃描時必讀 |
| Phase 7-D Walk-Forward Analysis | 3740-4169 | 實作 WFA runner / UI tab 時必讀 |
| Phase 8-A~8-F 個股綜合分析儀表板 | 4171-5258 | 實作 analysis/ / realtime / dashboard 時必讀 |
| Phase 8-G 新手友善說明文字 | 5260-5683 | 實作儀表板說明文字時必讀 |
| **Phase 9 美股 US-1 / 9-G 支援** | **5685-6273** | **實作多市場基礎、美股資料管線、回測、dashboard、資料管理頁、美股 intraday snapshot 前必讀** |

### 測試指南.md（~2680 行）

| 區段 | 行範圍 | 何時讀 |
|:---|:---|:---|
| 環境準備 + 指令速查 | 9-89 | 首次跑測試 |
| Phase 1 測試 | 91-397 | 修改 data/ 時 |
| Phase 2 測試 | 400-660 | 修改 backtest 時 |
| Phase 3 測試 | 663-966 | 修改 events/account/engine_event 時 |
| Phase 4 測試 | 970-1217 | 修改 ai/indicators/UI 時 |
| Phase 6 測試 | 1219-1293 | 修改主題切換、設定頁與側邊欄時 |
| Phase 7-A 測試 | 1295-1495 | 新策略測試 |
| Phase 7-B 測試 | 1497-1584 | 批次比較測試 |
| Phase 7-C 測試 | 1586-1696 | 參數掃描測試 |
| Phase 7-D 測試 | 1698-1856 | Walk-Forward 測試 |
| Phase 7 全階段回歸 | 1858-1876 | Phase 7-D 完成後 |
| Phase 8 測試（8-A~8-F） | 1878-2126 | 個股分析儀表板測試 |
| **Phase 8-G 測試** | **2128-2174** | **儀表板說明文字測試** |
| Phase 8 全階段回歸 | 2176-2194 | Phase 8 完成後 |
| **Phase 9 測試（9-A~9-G）** | **2196-2599** | **美股 US-1 與 9-G intraday 實作與驗收時必讀** |
| 全專案最終回歸 | 2601-2639 | Phase 完成後 |
| 測試數量統計總覽 | 2641-2680 | 測試統計與 Phase 9 估算 |

### 驗證後已知問題.md（~785 行）

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
