# QuantTrader 專案簡報

本文件供新 session 快速了解專案全貌，取代逐份閱讀全部規格文件。需要深入某區段時，按行號索引讀取對應文件。

最後更新：2026-05-18

---

## 專案概述

台股 / 美股 US-1 量化交易研究工具（個人版），運行於 Windows 11 本機。聚焦資料管線、研究、回測與 AI 分析，不接實盤。

2026-05-18 Phase 11 規格已更新：11-D 從原先待定 / 散戶多空比 placeholder 改為 Goodinfo 股利政策 fallback，補強事件行事曆的「即將除息」顯示；若本機沒有正式未來除息資料，不再用上一筆除息日 + 1 年產生 `[預估]`，改查 Goodinfo 股利政策表。若表內有「股利發放期間=未定」的明細列，優先顯示較舊的待發放所屬期間，例如 `3293` 顯示 `25H2 現金股利 36`、`2330` 顯示 `25Q4 現金股利 6`，並提示使用者自行確認。11-C 已完成並驗證通過。

2026-05-17 Phase 11 規格已從草案正式寫入三份文件：`量化交易系統規格書_shellpig版.md`（V3.0）、`開發設計方針.md`、`測試指南.md`。Phase 11 擴充 dashboard 個股分析頁的基本面與事件資訊，拆為 11-A 版面 placeholder、11-B 估值 / 獲利、11-C 籌碼 / 事件、11-D Goodinfo 股利政策 fallback；執行順序固定 11-A → 11-B → 11-C → 11-D。11-A / 11-B / 11-C 已完成並驗證通過；11-B 後續發現的刪除 WinError、ETF 空資料說明與歷史除息 TTM PE 最近交易日價格修正也已驗證完成。

2026-05-14 Phase 10 規格已完成並寫入正式文件：前端架構從 Streamlit 遷移至 Next.js (React) + FastAPI，拆為 10-A~10-H 八個子階段。新增 `src/services/`（服務層）、`api/`（FastAPI 後端）、`web/`（Next.js 前端）。核心演算法不重寫。Phase 9-G（美股 intraday）為前置條件。

- Phase 1–9 全部完成（含美股 US-1 / 9-G intraday）。
- Phase 10 全部完成（10-A ~ 10-H-2）；舊 Streamlit UI 已移除。
- Phase 11 11-A / 11-B / 11-C / 11-D 已完成並驗證通過；11-D Goodinfo 股利政策 fallback 已上線。
- Phase 11-E 已完成並驗證通過：純前端 UI/UX 收尾調整 8 項已上線，包含工具名稱改 `FactorHammer`、版號 build-time 注入、警示文字字色統一、股東會無資料文案修正、報價列改一排、K 線右側加「前收」、股東會編輯按鈕內聯、散戶多空比 placeholder 移除。
- Phase 10-F-2（AI 問答接 LLM）延後，不卡主線。

## 技術棧

- **語言 / 套件管理：** Python 3.12+、uv（`pyproject.toml`）
- **資料處理：** pandas、pandas-ta
- **資料來源：** 台股 FinMind API + yfinance 備援；美股日 K / 1m intraday 使用 yfinance；Phase 11-C 股東會使用 TWSE / TPEx OpenAPI；Phase 11-D Goodinfo 股利政策頁作除息 fallback 參考
- **儲存：** DuckDB + Parquet（零伺服器）
- **後端：** FastAPI、uvicorn、httpx；SSE 以 FastAPI `StreamingResponse` 實作
- **前端：** Next.js 15+、React 19+、TypeScript 5+、Tailwind CSS v4、SWR、Lightweight Charts、Radix UI、sonner、cmdk、shadcn/ui pattern
- **舊 UI：** Streamlit 已於 Phase 10-H 移除；Plotly 僅保留於 `src/backtest/report.py` 報告生成
- **AI：** OpenAI / Anthropic / Gemini（provider-neutral）
- **測試：** pytest（固定 `.venv\Scripts\python.exe`）、Vitest、Playwright

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
└── services/       ★ Phase 10 新增：服務層（從 ui/pages/ 抽離的非渲染邏輯）
                    dashboard_service.py, backtest_service.py,
                    data_service.py, config_service.py

api/                 ★ Phase 10 新增：FastAPI 後端 API 層
├── main.py          FastAPI app 入口、CORS
├── deps.py          共用依賴注入
├── job_manager.py   in-memory Job manager（write lock、TTL）
└── routers/         analysis.py, backtest.py, data.py, ai.py,
                     config.py, realtime.py, jobs.py

web/                 ★ Phase 10 新增：Next.js 前端
├── src/app/         App Router（dashboard, backtest, data, ai, settings）
├── src/components/  共用元件（sidebar, charts/, metric-card, stock-selector, ...）
├── src/hooks/       use-stock-data.ts, use-backtest.ts, use-realtime.ts
├── src/lib/         api-client.ts, formatters.ts, utils.ts
└── src/types/       analysis.ts, backtest.ts, market.ts, config.ts

tests/
├── fixtures/       手工構造的 CSV 測試資料
├── test_market.py, test_fetcher.py, test_storage.py, test_cleaner.py
├── test_cost.py, test_metrics.py, test_report.py
├── test_engine_vec.py, test_engine_event.py, test_consistency.py
├── test_account.py, test_events.py
├── test_indicators.py, test_advisor.py
├── test_e2e.py, test_strategy_config.py
├── test_dca_backtest.py, test_maintenance.py
├── test_strategies.py, test_batch.py, test_sweep.py, test_walk_forward.py
├── test_technical_summary.py, test_pattern.py
├── test_chip_analysis.py, test_realtime.py
├── test_services/   ★ Phase 10 新增：服務層測試
│                    test_dashboard_svc.py, test_backtest_svc.py,
│                    test_data_svc.py, test_config_svc.py
└── test_api/        ★ Phase 10 新增：API 端點測試
                     test_config_api.py, test_jobs_api.py, test_data_api.py,
                     test_analysis_api.py, test_backtest_api.py, test_ai_api.py

data/                （gitignore，執行時自動建立）
  raw/tw/{symbol}/       daily.parquet, minute.parquet,
                         institutional.parquet, margin.parquet,
                         per.parquet, monthly_revenue.parquet,
                         dividends.parquet, eps.parquet（Phase 11-B 規格）
  raw/tw/                shareholder_meeting.parquet,
                         shareholder_meeting.meta.json（Phase 11-C 規格；不進 data_meta）
  manual/                shareholder_meeting_override.csv（Phase 11-C 規格）
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
  enabled: false
  provider: anthropic
  model: claude-sonnet-4-6
ui:
  theme: midnight_blue
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
| 9-F | ✅ 完成 | Phase 9 整合回歸與文件收束：全專案自動測試 428 passed；手動驗收 9-F-1~9-F-12 全數通過 |
| 9-G | ✅ 完成 | 美股 yfinance 1m intraday 盤中快照與分 K 圖：專用 `fetch_us_intraday` API、最新 1 分 K raw close 作為近似盤中價、漲跌對前一紐約交易日 raw close、今日判斷以紐約日期為準、成交量為今日 1m volume 加總、分 K 圖放日 K 圖前 |
| 10-A | ✅ 完成 | 服務層抽離 + FastAPI 後端骨架：`src/services/` 4 個 service、`api/` FastAPI app + CORS + health + config + data/symbols + Job manager（write lock、TTL）；舊 Streamlit UI 改呼叫 services 行為不變；服務層 44 passed + API 17 passed + 全專案 508 passed |
| 10-B | ✅ 完成 | Next.js 前端骨架：`web/` Next.js 15.3 + React 19 + TS 5 + Tailwind v4 + SWR + Lightweight Charts；Sidebar 5 頁導航（PC 左側 240px / Mobile 底部 Tab Bar）、Dark/Light 主題、api-client、市場切換、股票選擇器、4 型別檔、formatters；Vitest 33 passed + 全專案 508 passed；手動驗收 10-B-1~6 全數通過 |
| 10-C-1 | ✅ 完成 | 資料管理頁 stage-1（列表 + DELETE）：DataTable 顯示 **6 欄**（代碼 / 名稱 / 區間 / K 棒數 / 狀態 / 動作；「大小」欄已從規格移除）、單步確認 Dialog、三態 badge（fresh/stale/missing，基於 ISO-week businessDaysBetween）、美股 raw+adj 標記 + callout。stage-2 按鈕（全部更新/全部重建/動作欄·更新/+ 新增標的）皆 disabled + tooltip「Phase 10-C-2 開發中」。tsc 0 errors + vitest 61 pass（+27：StatusBadge 4 + DeleteConfirmDialog 8 + trading-calendar 13 + 既有 34）+ pytest 39 pass（+14：test_data_api.py）。**Known limitation**：「名稱」欄目前 fallback 至 symbol code（後端 `list_symbols` 暫不補 name 欄；若需中文名稱另議） |
| 10-C-2 | ✅ 完成 | 資料管理頁 stage-2（更新/重建/新增）：擴充 `api/routers/jobs.py` dispatcher 支援 `data_update` / `data_rebuild` job type（單檔 + all 批次模式、SSE progress + result event、單檔失敗不中斷整批、write lock 互斥）；前端 ProgressBar 全局進度條、RebuildConfirmDialog 二次確認、AddSymbolDialog（複用 StockSelector）、完成後 banner 列出 succeeded / failed 清單。tsc 0 errors + vitest **11 files / 87 tests pass**（10-C-2 補 3 檔 / 26 cases）+ pytest **52 passed**（+13 in `test_data_jobs_api.py`）。**邊界決定**：失敗清單用 banner 取代 toast，toast 系統留待 10-G 全局整合 |
| 10-D | ✅ 完成 | 個股分析儀表板（Lightweight Charts）：3 輪驗收完成（round-3 13 項基本修正 + round-4 6 項緊湊化 + round-5 三欄佈局 50:25:25）；K 線 + MA + KD/RSI/MACD 副圖、crosshair tooltip、S/R 壓力支撐線、Pattern 長描述 tooltip、Radix Tooltip；tsc 0 errors + vitest 34 pass + pytest 25 pass |
| 10-E-1 | ✅ 完成 | 單次回測：Job + SSE、5 metric card tearsheet、K 線 + MA + buy/sell markers、equity curve、trades 表；建立 form / K 線 / tearsheet 元件供 10-E-2~4 重用；使用 10-G-1 的 toast / skeleton / error boundary / command palette；pytest 9 passed + vitest 31 files / 202 tests passed + tsc 0 errors |
| 10-E-2 | ✅ 完成 | 策略比較（批次）：`backtest_batch` Job + per-preset SSE progress、10 欄比較表、多策略 equity 疊圖（lightweight-charts 多 LineSeries + crosshair tooltip）、row 展開重用 10-E-1 元件、CSV blob 匯出；pytest `test_backtest_api.py` 14 passed、API 回歸 73 passed、vitest 34 files / 214 tests passed、tsc 0 errors |
| 10-E-3 | ✅ 完成 | 參數掃描：Top N 排名表 + 2D heatmap（僅 2 參數，自製 CSS Grid）+ 進度 throttle + sample_warning |
| 10-E-4 | ✅ 完成 | Walk-Forward：Summary / Window / Stability 三表 + 巢狀 SSE 進度（window × IS sweep）+ 雙 CSV 匯出（window + stability）；`run_walk_forward_job` + `WalkForwardTab` + `WfaSummaryCards` + `WfaWindowTable` + `WfaStabilityTable`；pytest 26 passed + vitest 40 files / 252 tests passed + tsc 0 errors |
| 10-F-1 | ✅ 完成 | AI 問答頁 UI shell + 後端 lock（**不接 LLM**）：完整 chat UI、免責聲明 gate（localStorage `ai_chat.disclaimer_accepted_v1`）、`react-markdown` + remark-gfm、Mock 逐字串流（25ms / char）、訊息歷史刷新即清；`GET /api/ai/status` 回 `feature_locked`、`POST /api/ai/chat` 回 503；Sidebar AI 入口加灰色「後續開放」徽章；package version py + web + FastAPI 三處同步 bump 至 `0.2.0`；文件 V2.4。tsc 0 errors + vitest **17 files / 124 tests pass**（+31：disclaimer-gate 5 / message-bubble 10 / chat-page-client 8 / use-ai-status 3 / sidebar 5）+ pytest **test_api 59 passed**（+7 in `test_ai_api.py`） |
| 10-F-2 | ⏸ 延後 | AI 問答頁接 LLM：補 `AIAdvisor.stream_chat()` 三 adapter（Anthropic / OpenAI / Gemini）+ 真實 SSE token 串流；**不卡 10-G / 10-H** |
| 10-G-1 | ✅ 完成 | 基礎設施先行：新增 `sonner` toast + 10-C-2 banner 遷移、React Error Boundary（只接 render/lifecycle/hook 例外）、`CardSkeleton` / `ChartSkeleton` / `TableSkeleton`、`cmdk` Command Palette（頁面跳轉 + 股票搜尋）；移除 `@radix-ui/react-toast`；補 7 檔前端測試與單檔更新/新增失敗 toast regression。tsc 0 errors + vitest **24 files / 148 tests passed** |
| 10-G-2 | ✅ 完成 | 設定頁 4 分區：API key write-only UI（5 provider）、策略 preset CRUD（`POST/DELETE/restore` 三端點 + Dialog）、Dark↔Light 主題切換（沿用既有自製 `theme-provider.tsx`，**未引入 `next-themes`**，等價支援 `class="dark"` + localStorage）、AI toggle disabled + Radix Tooltip；pytest `test_config_api.py + test_config_svc.py` 28 passed（+6 strategy endpoints / +3 `delete_strategy_preset_by_name`）+ vitest **46 files / 290 tests passed**（+5 settings 元件測試 + use-config hook）+ tsc 0 errors |
| 10-H-1 | ✅ 完成 | 收尾前置補強：Playwright E2E smoke 5 spec（desktop + mobile 兩 project、共 48 case）、手機 <768px 底部 Tab Bar（`sidebar.tsx` 拆 Desktop / Mobile + `pb-14`）、`web/src/tests/lib/theme-vars.test.ts` 補 `test_themes.py` CSS 變數驗證；測試遷移檢查表 7 行全部打勾。順手 bug fix：`backtest_service.py` `load_backtest_data` tz-aware filter、`StrategyPresetSelect.tsx` API URL 加 `NEXT_PUBLIC_API_URL` 前綴、`uv.lock` 同步 0.2.0。Gate：pytest 588 passed / vitest 48 files / 307 tests / tsc 0 errors / Playwright 48 tests pass |
| 10-H-2 | ✅ 完成 | 實際移除與全專案回歸：刪 `src/ui/`、`run_quanttrader.bat`、`pyproject.toml` streamlit 三套件、7 個 Streamlit pytest 檔；`src/ai/advisor.py` 保留（10-F-2 + dashboard analysis 仍使用）；`src/backtest/report.py` `_apply_theme` 去除 ui 依賴 |
| 11-A | ✅ 完成 | Dashboard 版面調整：chart 高度 400px → 300px；移除 K 線圖 KD / RSI / MACD 下方副圖但保留成交量；左欄 chart 下方新增兩塊、共 6 個 dashed placeholder panel；market=us 時 P11 下方兩塊隱藏；籌碼面板買賣力道與融資 / 融券壓成單行；關鍵價位小數顯示修正；使用者實機驗證通過 |
| 11-B | ✅ 完成 | 估值 / 獲利區塊：本益比、股價淨值比、殖利率、月營收、歷史除息本益比、同產業本益比 Modal；新增 PER / 月營收 fetcher，補 dividends / EPS storage + `data_meta`；P11 API namespace、service、frontend hooks / panels / Modal、同產業 PER cache + lock、US market 501 邊界與 route regression 已補；ETF 空資料說明、TTM PE 最近交易日價格、資料刪除 WinError 收尾皆已驗證完成 |
| 11-C | ✅ 完成 | 籌碼 / 事件區塊：法人持股成本、事件行事曆（除息 + 股東會）、股東會手動覆蓋 Modal；新增 TWSE / TPEx 股東會全市場資料源、獨立 metadata JSON、manual override CSV；股東會不進 `data_meta`；資料管理頁單檔刪除不動全市場股東會資料，`data_update` / `data_rebuild` 尾端只 refresh 一次；使用者已驗證完成 |
| 11-D | ✅ 完成 | Goodinfo 股利政策 fallback：事件行事曆無正式未來除息資料時，不再顯示去年資料推估的 `[預估]`，改抓 Goodinfo 股利政策表；只顯示「股利發放期間=未定」或日期落在未來的待發放明細與現金 / 股票股利；過期或失敗顯示查無今年股利資料；使用者已驗證通過 |
| 11-E | ✅ 完成 | UI/UX 收尾調整（純前端）：(1) Sidebar 工具名稱改 `FactorHammer`（不動 repo / package name）；(2) 名稱右下方版號 `v{version}`，build-time 從 `web/package.json` 注入；(3)「資料源未提供」字色改與「撈不到股東會資料」同黃色 token；(4) 股東會無資料文案改為「撈不到股東會資料，需要手動填入（或是ETF沒有股東會）」；(5) 報價列改一排，標籤 muted、數值原色、欄位以兩個全形空格分隔；(6) K 線右側加「前收」標籤，整組同色、漲紅跌綠、平盤灰；(7) 股東會編輯按鈕移到「事件行事曆」標題右側 8px 內聯；(8) 散戶多空比 placeholder 整塊移除；使用者已驗證完成 |
| 12 | 📋 規格 | 首次執行 Token Onboarding 與 Portable Runtime 重整（規格已寫入規格書 / 開發設計方針 / 測試指南，實作未動工）：12-A install.bat 5 步驟 + portable Node v22.11.0 + SHA-256 + `run_factorhammer.bat` 改名 + `tools/` 加 .gitignore；12-B 擴充既有 `api/routers/config.py` 新增 `POST /api/config/secrets/validate` + FinMind 驗證 + `_write_env` 重構為共用 atomic helper（保留註解 / 空行 / 未知 keys / 不 sort）+ `get_secrets_status` 空白 fallback bug 修正；12-C 強制 block Token Setup Dialog（不可 ESC / overlay 關）+ FinMind 申請連結 + AI keys 選填折疊 + SWR 全域 mutate；12-D verifier 文件收尾 |

## 當前待辦

見 `驗證後已知問題.md`（每次必讀）。

主線：**Phase 1–11 11-A~11-E 全部完成（含 10-H-2 Streamlit 完整移除 + 全專案回歸、11-D Goodinfo 股利政策 fallback、11-E UI/UX 收尾調整皆已驗證通過）。Phase 12 規格已寫入三份主文件，待使用者下「實作 12-A」或同等指令動工。** 10-F-2（AI 問答接 LLM）延後，不卡主線。專案已完全遷移至 Next.js + FastAPI；Streamlit 程式碼與套件已從 codebase 移除。

2026-05-18 狀態（Phase 12 規格寫入）：
- **P12 規格已寫入三份主文件**：`量化交易系統規格書_shellpig版.md` 新增 ### Phase 12 段落（含定位、4 個子階段、共通規則、API 合約、UI 規格、不做、風險）；`開發設計方針.md` 新增 ## Phase 12 段落（含 `_write_env` 重構程式碼、`validate_finmind_token` 完整 service 函式、router endpoint 範例、Dialog hooks 範例、SWR mutate 整合）；`測試指南.md` 新增 ## Phase 12 測試段落（12-A 安裝腳本 8 點手動驗收、12-B 14 條 router + 12 條 service 自動測試、12-C 16 條元件 + 3 條整合 + 10 點手動驗收、Phase 12 完成 Gate）。
- **P12 規格四項拍板決定**：(1) endpoint 策略：擴充既有 `api/routers/config.py` 沿用 `GET /api/config/secrets/status`、新增 `POST /api/config/secrets/validate`，**不**改造既有 `PUT /api/config/secrets`；(2) angled `_write_env` 重構為共用 atomic helper，既有 `update_secrets` 受惠（保留註解 / 空行 / 未知 keys、不 sort、寫 `.env.tmp` + `os.replace`）；(3) modal 強制 block（無 X、ESC / overlay 都 preventDefault、儲存鈕灰至 FinMind 非空）；(4) Node 鎖死 v22.11.0 portable 落到 `tools\node\`，`.gitignore` 加 `tools/`，pnpm 鎖 `11.1.1`。
- **P12 範圍邊界**：FinMind 驗證採固定流程「驗證成功才寫 .env」，限流時回 502 讓使用者重試，**不**允許繞過驗證寫入；modal 不提供清空既有 AI key、不提供「先跳過」；既有 `PUT /api/config/secrets` 行為與測試不被破壞。
- **P12 角色拆分**：12-A / 12-B / 12-C 由 implementer 動代碼 + 測試 + 註解，**不動 .md 文件**；12-D 由 verifier 角色執行（規格書 / 開發設計方針 / 測試指南 / PROJECT_BRIEF 已於本批次同步。

2026-05-18 狀態（Phase 11-E 完成）：
- **P11-E 已完成並由使用者驗證通過**：純前端 UI/UX 收尾調整 8 項已上線，不動後端、不動 Python、不動 `pyproject.toml` / `package.json` 的 `name` 欄位、不更名 repo。版號透過 `next.config.ts` 讀 `web/package.json` 的 version 注入 `NEXT_PUBLIC_APP_VERSION`，build-time only，無 runtime API 呼叫。
- **P11-D 已完成並由使用者驗證通過**：Goodinfo 股利政策 fallback 上線；只顯示「股利發放期間=未定」或日期落在未來的待發放明細，避免誤把已發放的舊資料當未來除息；`fetch_failed` 不寫每日 cache、舊 schema cache 自動失效；requests-first 處理 `CLIENT_KEY` / `REINIT`，Playwright 為 optional fallback。
- **P11-C 已完成並由使用者驗證通過**：法人持股成本、事件行事曆、TWSE / TPEx 股東會全市場資料、獨立 `shareholder_meeting.meta.json`、manual override CSV、股東會手動編輯 Modal、資料管理頁 lifecycle / refresh 規則皆已落地。
- **P11-D 規格背景**：原「散戶多空比」先不做；11-D 改為 Goodinfo 股利政策 fallback，文件已同步更新 `量化交易系統規格書_shellpig版.md`、`開發設計方針.md`、`測試指南.md`；11-E 進一步將該 placeholder 整塊移除。

2026-05-17 狀態（Phase 11-B 完成）：
- **P11-B 已完成並驗證通過**：新增 PER / monthly revenue fetcher；補 per / monthly_revenue / dividends / eps storage roundtrip 與 `data_meta`；dashboard service 新增 valuation / monthly revenue / dividend history with PE / industry PER；API 新增 `/api/analysis/p11/valuation`、`monthly-revenue`、`dividend-history`、`industry-per` 並放在動態 route 前；前端新增 valuation / monthly revenue / dividend history panel 與同產業 PER Modal；US market 回 501，frontend 隱藏 P11 區塊。
- **P11-B 已修正驗證中發現的 4 個缺口**：industry PER response contract 改為 `median / mean / count / cached_at`；補 4 個 P11 component tests + tooltip coverage；PER / PBR / TTM 顯示與 tooltip 對齊規格；P11 資料補抓改 best-effort，不阻塞 daily pipeline。
- **P11-B 收尾問題已驗證完成**：資料管理頁刪除遇 Windows `ReadOnly` / `WinError 5` 的錯誤解析與刪除耐受性已處理；ETF（如 0056）不適用 PER / 月營收 / EPS 時改以明確文案說明；歷史除息 TTM PE 改用除息日同日或最近可用交易日 close，並標記實際使用的 `price_date`。
- **P11-B 驗證結果**：Python gate `tests/test_fetcher.py tests/test_storage.py tests/test_maintenance.py tests/test_services/test_dashboard_svc.py tests/test_api/test_analysis_api.py` 為 **94 passed, 8 deselected**；frontend `npx tsc --noEmit` 0 errors；P11 frontend targeted tests **6 files / 17 tests passed**；full vitest **49 files / 321 tests passed**。
- **P11-A 已完成並由使用者實機驗證通過**：Dashboard chart 高度改為 300px；TW 左欄 chart 下方新增 6 個 dashed placeholder；US market 隱藏 P11 下方區塊；K 線圖移除 KD / RSI / MACD 副圖並保留成交量；籌碼面板買賣力道與融資 / 融券壓成單行；關鍵價位面板恢復小數顯示。
- **P11 規格草案已正式寫入三份文件**：`量化交易系統規格書_shellpig版.md` 新增 V3.0 與 Phase 11 章節；`開發設計方針.md` 新增 Phase 11 實作設計；`測試指南.md` 新增 Phase 11 測試矩陣與 gate。
- **P11 執行順序**：11-A（版面 placeholder）→ 11-B（估值 / 獲利）→ 11-C（籌碼 / 事件）→ 11-D（Goodinfo 股利政策 fallback），不可並行。
- **P11 API 規則**：所有新 endpoint 掛 `/api/analysis/p11/*`，且需補 regression 防止被既有 `/api/analysis/{section}` 動態路由吃掉。
- **P11-B 邊界決定**：同產業 PER cache miss 使用 `ThreadPoolExecutor(max_workers=8)`，每個 worker 建立獨立 `FinMindFetcher`；cache path 為 `data/cache/industry_per/{slug(industry)}_{YYYY-MM-DD}.parquet`；個別 peer 失敗以 `per/pbr/dividend_yield=null` 回傳，不阻塞整體結果。
- **P11-C 股東會決策**：股東會是全市場單一 parquet，不進 `data_meta`，不用 sentinel symbol，不改 `DuckDBMeta` schema；使用 `data/raw/tw/shareholder_meeting.meta.json` 管 once-per-day guard，manual override 放 `data/manual/shareholder_meeting_override.csv`。資料管理頁單檔刪除只刪 per-symbol raw/processed/meta，不刪 shareholder meeting auto/meta/manual；`data_update` / `data_rebuild` 在 TW market 的 symbol loop 尾端最多 refresh 一次，US market 略過；乾淨重測需額外清全域股東會檔與 manual CSV。
- **P11 同產業 PER Modal UX**：採同步 REST + `ThreadPoolExecutor(max_workers=8)` + cache；cache miss 可能 8–25 秒，前端需用 skeleton + 半透明遮罩 + 中央「資料讀取中」訊息，完成後一次替換表格。

2026-05-16 狀態（10-H-1）：
- **10-H-1 實作 + 驗證完成**：實作於 worktree `claude/peaceful-dewdney-33117e`，驗證通過後以 fast-forward 合進 main（commit `e7c6af2` + `e5c8a09`），uv.lock 同步 0.2.0 以 cherry-pick 進 main（`d346d49`）。新增 `web/playwright.config.ts`（desktop-chromium 1280×800 + mobile-chromium Pixel 5 兩 project）；新增 5 個 e2e spec（`navigation` / `backtest-single` / `backtest-cancel` / `csv-download` / `mobile-tabbar`）；新增 `web/src/tests/lib/theme-vars.test.ts` + `web/src/tests/components/mobile-tabbar.test.tsx`；`web/src/components/sidebar.tsx` 拆 `DesktopSidebar` + `MobileTabBar`（fixed bottom h-14 + grid-cols-5）；`web/src/app/layout.tsx` 加 `pb-14 lg:pb-0`；`web/src/app/globals.css` 補 `--chart-up` / `--chart-down` 與 `.light` class。順手修：`load_backtest_data` tz-aware filter、`StrategyPresetSelect` API URL 加絕對前綴。驗證：pytest **588 passed**、vitest **48 files / 307 tests pass**、tsc 0 errors、Playwright **48 tests pass**（24 desktop + 24 mobile）。測試遷移檢查表 7 行全打勾（見 `驗證後已知問題.md` [P10-H-1]）。

2026-05-16 狀態：
- **10-E-3 實作 + 驗證完成**：後端 `backtest_sweep` dispatcher + `run_param_sweep_job()` + sweep CSV blob + progress throttle（>50 combos）+ `OVER_MAX_COMBOS` 422 + `sample_warning`（total_trades < 3）；前端新增 `SweepTab` / `ParamGridForm` / `SweepRankingTable` / `SweepHeatmap`（僅 2 參數時自製 CSS Grid 2D）+ `sweep-types` / `sweep-helpers` / `sweep-constants`；commit `4b39120`。驗證：pytest 6 個 sweep case 全綠（含 throttle / over_max / 非整數參數 / sample_warning / CSV blob）。
- **10-E-4 實作 + 驗證完成**：後端 `backtest_wfa` dispatcher + `run_walk_forward_job()` + 巢狀 SSE（`window_progress` × `sweep_progress`）+ `INSUFFICIENT_DATA_FOR_WFA` 422 + `build_wfa_window_csv_blob` / `build_wfa_stability_csv_blob` 雙 CSV；前端新增 `WalkForwardTab` / `WfaSummaryCards` / `WfaWindowTable` / `WfaStabilityTable`；commit `18fde89`。驗證：pytest `test_backtest_api.py` 26 passed（含 6 個 WFA case）；vitest 40 files / 252 tests passed；tsc 0 errors。
- **10-G-2 實作 + 驗證完成**：後端 `api/routers/config.py` 新增 `POST /api/config/strategies`（upsert by name）、`DELETE /api/config/strategies/{name}`（idempotent 204）、`POST /api/config/strategies/restore`；`config_service.py` 新增 `delete_strategy_preset_by_name()`。前端 `web/src/app/settings/page.tsx` + 6 個 settings 元件（`settings-page-client` / `secrets-section` / `strategy-presets-section` / `strategy-preset-dialog` / `theme-section` / `ai-toggle-section`）+ `use-config` SWR hook。**主題系統**：沿用既有自製 `theme-provider.tsx`（class="dark" + localStorage `qt-theme`），**未引入 `next-themes`**（與規格 L3553-3554 偏離，但功能等價，已於 brief 與 spec 註記）。**AI toggle**：Radix Tooltip + `disabled`，文案「AI 功能尚未開放」。**Secrets 安全**：GET 永不回傳 key 值（既有規約沿用）。驗證：pytest `test_config_api.py + test_config_svc.py` 28 passed（+6 strategy endpoints / +3 delete_by_name）；vitest 46 files / 290 tests passed（+5 settings 測試檔 + use-config hook）；tsc 0 errors。


- **10-E-1 實作 + 驗證完成**：後端 `job_manager.py` 新增 `finish_cancelled_job()` + 修正 `cancel_job()` race condition；`backtest_service.py` 新增 `initial_capital` 參數 + DCA 序列化；`jobs.py` 新增 `backtest_run` dispatcher + cancelled partial result 回傳。前端新增 `BacktestPageClient`（4-tab 框架，僅 Single 啟用）、`SingleRunTab`（表單 + 結果顯示）、`TearsheetCards` / `CandleChartWithMarkers` / `EquityCurveChart` / `TradesTable` / `StrategyPresetSelect` / `DateRangePicker` / `EngineSelect` / `BacktestProgressBar` 共 10 個元件；`use-backtest-job` hook（SSE + cancel + toast）。驗證：pytest **9/9 passed**（`test_backtest_api.py`）；vitest **31 files / 202 tests passed**（含 7 個 backtest 測試檔 53 cases）；`tsc --noEmit` 通過。
- **10-E-2 實作 + 驗證完成**：後端 `api/routers/jobs.py` 新增 `backtest_batch` dispatcher、per-preset SSE progress、cancelled partial result 保留、`GET /api/jobs/{id}/result?format=csv` CSV blob；`src/services/backtest_service.py` 新增 `run_batch_backtest_job()`、`build_batch_csv_blob()` 與 batch summary detail 序列化（`price_data` 只在 result 頂層帶一次）。前端解鎖策略比較 tab，新增 `BatchCompareTab` / `StrategyMultiSelect` / `ComparisonTable` / `MultiEquityChart` / `batch-types`；`use-backtest-job` 支援 `jobId` 與 callback options；批次頁含 FastAPI base URL 取 preset、多策略 equity crosshair tooltip、10 欄 sortable table、row 展開重用 tearsheet / K 線 / equity / trades、CSV 下載 toast、取消後 partial result 顯示。驗證：`test_backtest_api.py` **14 passed**（含 SSE per-preset progress）、`tests/test_api/` **73 passed**、10-E-2 前端 targeted vitest **3 files / 12 tests passed**、完整 vitest **34 files / 214 tests passed**、`tsc --noEmit` 與 `py_compile` 通過。
- **10-E 規格審查完成（V2.7 補丁）**：三份文件同步補充以下 12 項缺口，規格、設計方針、測試指南已更新：
  1. `JobManager.finish_cancelled_job()` 方法需在 10-E-1 開工前新增（目前缺失）
  2. `cancel_job()` 需修改為只設 status、不關 queue（避免 partial result 推送失敗的 race condition）
  3. `GET /api/jobs/{id}/result` 需允許 cancelled + partial result 回傳
  4. 取消 `api/routers/backtest.py` 新端點，改用既有 `GET /api/config` 取 preset 清單
  5. `initial_capital` 預設 1000000，需新增為 `run_backtest_job()` 參數
  6. 10-E-2 的 `price_data` 只在 result 頂層帶一次（各 summary 不重複）— 規格已正確，無需改
  7. DCA 序列化映射補充（equity_curve 從 records 派生、trades 空陣列、metrics 不適用欄位 null）
  8. `sweep-defaults.ts` 完整內容 + `PARAM_TYPES` 型別表（int/float 區分）
  9. WFA 特化 `WfaProgress` interface 補充
  10. CSV blob 函式位置明確指定放 `src/services/backtest_service.py`
  11. E2E Playwright 統一在 10-E-4 完成後撰寫
  12. 交易數量統一顯示「股」、不轉「張」（與舊 Streamlit 回測頁一致）；切換市場 reset state；DCA 批次 error message 定義

2026-05-15 狀態：
- 最新 commit 請以 `git log --oneline -1` 為準。
- **10-G-1 實作 + 驗證完成**：新增 `web/src/components/providers.tsx`、`error-boundary.tsx`、`command-palette.tsx`、`skeletons/index.tsx`、`hooks/use-toast.ts`、`hooks/use-command-palette.ts`；`layout.tsx` 接入 Providers；Sidebar 註冊 5 個頁面 command entry；StockSelector 註冊股票搜尋來源；資料管理頁 10-C-2 完成/錯誤 banner 改 toast，並補單檔更新失敗與新增標的失敗 toast regression。驗證：`.\node_modules\.bin\tsc.CMD --noEmit` 通過；`pnpm test` 為 **24 files / 148 tests passed**；聚焦 `data-page-client.test.tsx` 為 **7 passed**。
- **10-E 規格拆分為 4 段（V2.5，V2.6 收斂合約）**：10-E-1（單次）/ 10-E-2（批次）/ 10-E-3（掃描）/ 10-E-4（WFA），規格、設計方針、測試指南三份文件已同步更新。明確不做老 Streamlit「歷史結果」tab；10-E-2 比較表定為 **10 欄**；Heatmap 採排名表 + 2D 自製 CSS Grid（僅 2 參數時）；多策略 equity 疊圖用 lightweight-charts 多 LineSeries；WFA 雙 CSV（window + stability）由後端產 blob、前端 `<a download>` 下載；不引入新前端套件（無 Recharts / nivo / heatmap-grid）。取消後 job status 保持 `cancelled`，但 partial result 可由 `GET /api/jobs/{id}/result` 讀取；CSV 匯出 query 由 `api/routers/jobs.py` 的既有 result endpoint 處理；fetch / SSE / invalid JSON 走 toast + 頁內 error panel，不交給 Error Boundary。
- **10-G 規格拆分為 2 段（V2.6）**：10-G-1（基礎設施先行：`sonner` toast + 10-C-2 banner 遷移、Error Boundary、Loading Skeleton、Command Palette）與 10-G-2（設定頁主功能：API key write-only UI、策略 preset CRUD by name、Dark↔Light 主題切換、AI toggle disabled + tooltip）。執行順序為 **10-G-1 → 10-E-1 → 10-E-2 → 10-E-3 → 10-E-4 → 10-G-2 → 10-H**。10-G-1 不裝 `next-themes`，10-G-2 才裝；Error Boundary 只接 React render / lifecycle / hook 例外；API 錯誤一律走 toast。
- **9-F 手動驗收完成**：9-F-1~9-F-12 全數通過，Phase 9 全階段（含手動驗收）正式收束。
- **10-F-1 實作 + 驗收完成**：AI 問答頁 UI shell + 後端 lock（不接 LLM）。
  - 後端：`GET /api/ai/status` 回 `{ available: false, reason: "feature_locked" }`、`POST /api/ai/chat` 回 503 + `AI_DISABLED`；既有 `/api/ai/analyze` 不變。
  - 前端：disclaimer-gate（localStorage `ai_chat.disclaimer_accepted_v1` 持久）、message-bubble（`react-markdown` + `remark-gfm`、空內容顯示閃爍 cursor）、chat-input（Enter 送、空字串不送）、chat-page-client、use-mock-chat（25ms / char 逐字串流）、use-ai-status；Sidebar AI 入口加灰色「後續開放」徽章；Header「AI · 未啟用」灰 chip；訊息歷史純 React state 刷新即清。
  - 版號：`pyproject.toml` `0.1.0`→`0.2.0`、`web/package.json` `0.10.0`→`0.2.0`、`api/main.py` FastAPI `version` `0.10.0`→`0.2.0`，文件 V2.4。
  - 自動驗證：`tests/test_api/` 59 passed（+7 in `test_ai_api.py`）、`web/` `tsc --noEmit` 0 errors、`web/` vitest **17 files / 124 tests pass**（+31 cases：disclaimer-gate 5 / message-bubble 10 / chat-page-client 8 / use-ai-status 3 / sidebar 5）。
  - 手動驗收：10-F-1-1~10-F-1-8 全數通過。
- 10-F-2（接 LLM、SSE token 串流）延後實作，不卡 10-G / 10-H。

2026-05-14 狀態：
- 最新 commit 請以 `git log --oneline -1` 為準；本 brief 已改為不硬寫最新 hash，避免文件在 commit 後立即失真。
- **9-G 驗證完成**：美股 yfinance 1m intraday 盤中快照與分 K 圖已通過驗證，Phase 9 全階段結束。
- **10-A 驗證完成**：服務層抽離（`src/services/` 4 service）+ FastAPI 後端骨架（`api/`）；服務層 44 passed + API 17 passed + Streamlit 回歸 72 passed + 全專案 508 passed。舊 Streamlit UI 改呼叫 services 行為不變。
- **10-B 驗證完成**：Next.js 15.3 前端骨架（`web/`）；Sidebar 5 頁導航、Dark/Light 主題、api-client、市場切換、股票選擇器、型別檔、formatters；Vitest 33 passed（api-client 4 + formatters 16 + market-switcher 5 + stock-selector 6 + setup 2）；手動驗收 10-B-1~6 全數通過（dev server 啟動 1250ms、頁面切換、主題切換、375px 底部 Tab Bar、`/api/health` 連通、OneDrive 無 conflict）。
- Phase 10 規格已寫入 `量化交易系統規格書_shellpig版.md`（V2.3）、`開發設計方針.md`、`測試指南.md`：前端架構從 Streamlit 遷移至 Next.js + FastAPI，拆為 10-A~10-H 八個子階段。新增 `src/services/` 服務層、`api/` FastAPI 後端、`web/` Next.js 前端。技術選型 Next.js 15+ / React 19+ / TypeScript 5+ / Tailwind CSS v4 / shadcn/ui / Lightweight Charts / SWR / FastAPI。核心演算法不重寫。10-H 舊 UI 移除需通過測試遷移檢查表。
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

### 量化交易系統規格書_shellpig版.md（~4660 行）

| 區段 | 行範圍 | 何時讀 |
|:---|:---|:---|
| 修訂歷史 | 3-29 | 查版本變更，最新為 `V3.1`（Phase 11-E UI/UX 收尾調整；含工具名稱改 `FactorHammer`、版號 build-time 注入、報價列改一排、K 線右側加「前收」等 8 項） |
| 專案願景與目標 | 47-62 | 理解定位 |
| 技術語言與套件選型 | 64-91 | 技術決策參考 |
| 系統架構（四層架構圖） | 93-177 | 理解整體結構 |
| 資料來源規劃 | 179-223 | 修改 fetcher 時 |
| 資料品質與清洗（L1/L2/L3、時區） | 225-295 | 修改 cleaner / timezone 時 |
| 回測引擎規格 | 297-486 | 修改 backtest 時 |
| AI 技術分析模組 | 488-635 | 修改 ai/advisor 時 |
| 風控規格 | 637-650 | 風控相關 |
| 本機部署規格 | 652-748 | 環境設定 |
| 測試策略 | 750-771 | 測試方針 |
| Phase 1-4 開發計畫 | 773-952 | 查歷史 phase 規格 |
| Phase 5 回測體驗 | 954-1071 | 修改 DCA / 股價走勢 |
| Phase 6 UI/UX | 1073-1222 | 修改主題切換、設定頁與側邊欄 UI 小修 |
| Phase 7 策略擴充（7-A~7-D） | 1224-1933 | 策略、研究工作台、參數掃描、WFA |
| Phase 8 個股綜合分析儀表板（8-A~8-G） | 1935-2366 | 實作 analysis/ / realtime / dashboard / 說明文字時必讀 |
| Phase 9 美股 US-1 / 9-G 支援 | 2369-2693 | 美股日 K、調整後價格、回測、技術分析、多市場架構、yfinance 1m intraday 時必讀 |
| **Phase 10 前端架構重構（10-A~10-H）** | **2705-3756** | **Streamlit → Next.js + FastAPI 遷移、服務層抽離、API 設計、圖表、Responsive、主題系統時必讀。10-E / 10-G 細部規格詳於此區段** |
| **Phase 11 Dashboard 基本面與事件擴充（11-A~11-E）** | **3768-4170** | **Dashboard 新增估值/獲利與籌碼/事件資訊、UI/UX 收尾調整時必讀；含 `/api/analysis/p11/*` namespace、PER/月營收/dividends/EPS、股東會 metadata、同產業 PER Modal UX、Goodinfo 股利政策 fallback、11-E 名稱/版號/報價列/前收標籤/placeholder 移除等 8 項** |
| **Phase 12 首次執行 Token Onboarding 與 Portable Runtime 重整（12-A~12-D）** | **4172-4582** | **install.bat 改版、portable Node v22.11.0、`run_factorhammer.bat`、`POST /api/config/secrets/validate` + FinMind 驗證、`_write_env` atomic helper 重構、Token Setup Dialog 強制 block modal、SWR mutate；實作 12-A/B/C 時必讀** |
| 子階段總覽 | 2666-2680 | Phase 總覽（含 Phase 11） |
| 費用估算 | 2685-2703 | API / yfinance / TWSE / TPEx / Next.js / US-2 資料源成本 |
| 10-E：回測研究工作台 | 2942-3387 | 實作 10-E-1~4、Job lifecycle、SSE、取消、CSV、toast/skeleton/error boundary/command palette 整合時必讀 |
| 10-G：設定頁 + 全局整合 | 3447-3649 | 實作 10-G-1 toast/error boundary/skeleton/command palette，或 10-G-2 settings/secrets/theme/strategy preset 時必讀 |
| 11-B：估值 / 獲利區塊 | 3871-3937 | 實作 PER / 月營收 / dividends / EPS 落地、valuation API、同產業 PER Modal 時必讀 |
| 11-C：籌碼 / 事件區塊 | 3938-4049 | 實作法人持股成本、股東會 TWSE/TPEx fetcher、manual override、event calendar、資料管理頁互動規則時必讀 |
| 11-E：UI/UX 收尾調整 | 4126-4170 | 實作工具名稱改 `FactorHammer`、版號 build-time 注入、警示文字字色統一、股東會無資料文案、報價列改一排、K 線右側加「前收」、編輯按鈕內聯、placeholder 移除時必讀 |
| 12-A：Portable Node + install.bat 改版 | 4229-4325 | 實作 install.bat 5 步驟、portable Node v22.11.0 + SHA-256、corepack/pnpm 啟用、`run_quanttraderV2.bat` 改名為 `run_factorhammer.bat`、`web/package.json` packageManager、`.gitignore` 加 `tools/` 時必讀 |
| 12-B：Backend Config API 擴充 | 4326-4422 | 實作 `POST /api/config/secrets/validate` + FinMind 驗證流程、`_write_env` atomic + 保留註解 / 空行 / 未知 keys 共用 helper、`get_secrets_status` 空白 fallback bug 修正時必讀 |
| 12-C：Frontend Token Setup Dialog | 4423-4525 | 實作強制 block modal（不可 ESC / overlay 關）、FinMind 申請連結、AI keys 選填折疊、SWR `mutate(() => true)` 全域 invalidate 時必讀 |
| 12-D：Verifier 文件收尾 | 4526-4552 | verifier 角色執行；含全文件 `run_quanttraderV2.bat` 殘留檢測指令、文件同步檢查清單 |
| 附錄 A：免責聲明全文 | 4585-4604 | 免責聲明文案 |
| 附錄 B：架構決策補充 | 4606-4662 | 美股邊界與 AI provider 抽象 |

### 開發設計方針.md（~9615 行）

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
| Phase 9 美股 US-1 / 9-G 支援 | 5685-6290 | 實作多市場基礎、美股資料管線、回測、dashboard、資料管理頁、美股 intraday snapshot 前必讀 |
| **Phase 10 前端架構重構（10-A~10-H）** | **6293-8405** | **服務層抽離、FastAPI 骨架、Next.js 前端、API 端點、圖表元件、Job manager、config 安全、測試遷移檢查表實作時必讀。10-C / 10-E / 10-G 細部設計皆在此段** |
| **Phase 11 Dashboard 基本面與事件擴充** | **8406-9170** | **實作 P11 前必讀：11-A 前端 placeholder、11-B data/service/API/frontend、11-C TWSEFetcher/股東會 metadata/manual override/event calendar、資料管理整合、11-D Goodinfo 股利政策 fallback、11-E UI/UX 收尾調整** |
| **Phase 12 首次執行 Token Onboarding 與 Portable Runtime 重整** | **9174-9615** | **實作 P12 前必讀：12-A install.bat 內部結構與 portable Node 流程、12-B `_write_env` atomic helper + `validate_finmind_token` 程式碼、12-C Token Setup Dialog hooks 範例 + SWR mutate 整合、既有測試 mock 調整** |
| 10-E 回測研究工作台 | 6920-7480 | 實作 backtest jobs、partial cancellation、CSV blob、共用 hook/元件時必讀 |
| 10-G 設定頁 + 全局整合 | 7649-8119 | 實作 toast、Error Boundary、Skeleton、Command Palette、settings/secrets/theme/preset CRUD 時必讀 |
| 11-B 資料層 / Service / API / 前端 | 8509-8705 | 實作 PER、monthly_revenue、dividends/EPS storage、valuation/monthly/dividend/industry PER API 與 panel 時必讀 |
| 11-C 股東會 / 事件 / 法人成本 | 8706-8880 | 實作 TWSEFetcher、shareholder_meeting parquet/meta、once-per-day guard、manual override、資料管理整合、event calendar 與 institutional cost 時必讀 |
| 11-D Goodinfo 股利政策 fallback | 8886-9075 | 實作 Goodinfo parser、每日 cache、event calendar fallback payload、前端「今年股利資料 / 查無今年股利資料」顯示時必讀 |
| 11-E UI/UX 收尾調整 | 9077-9170 | 實作 `next.config.ts` 注入 `NEXT_PUBLIC_APP_VERSION`、sidebar header 改名、quote header 改一排、K 線「前收」標籤、編輯按鈕內聯、placeholder 移除時必讀 |
| 12-A install.bat / Portable Node | 9190-9259 | install.bat 內部 5 步驟與 PATH 注入時機、portable Node 下載 / SHA-256 / 解壓扁平化、`run_factorhammer.bat` PATH 注入時必讀 |
| 12-B Config API 擴充 + `_write_env` 重構 | 9260-9449 | `validate_finmind_token` 完整程式碼、router endpoint 範例、共用 `_write_env` atomic helper、`get_secrets_status` bug 修法時必讀 |
| 12-C Token Setup Dialog 元件 | 9450-9608 | Dialog hooks 範例、儲存 handler、外部連結 JSX、`dashboard-page-client` 整合、既有測試 mock 調整時必讀 |

### 測試指南.md（~4125 行）

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
| Phase 8-G 測試 | 2128-2174 | 儀表板說明文字測試 |
| Phase 8 全階段回歸 | 2176-2194 | Phase 8 完成後 |
| Phase 9 測試（9-A~9-G） | 2196-2603 | 美股 US-1 與 9-G intraday 實作與驗收時必讀 |
| **Phase 10 測試（10-A~10-H）** | **2606-3238** | **服務層、API 端點、前端 Vitest、E2E Playwright、測試遷移檢查表。10-E / 10-G 測試規格已拆段** |
| **Phase 11 測試（11-A~11-E）** | **3239-3765** | **P11 自動測試 / 手動驗收 / Gate；含 fetcher、storage、maintenance/job、service、API、frontend、namespace regression、股東會 metadata、資料管理互動測試、Goodinfo fallback 測試、11-E UI/UX 純前端測試** |
| **Phase 12 測試（12-A~12-D）** | **3768-4024** | **P12 安裝腳本 / Backend Config API / Frontend Token Dialog 測試；含 install.bat 乾淨機器手動驗收 8 點、`secrets/validate` router 14 case + service 12 case、Token Setup Dialog 16 case + 整合 3 case、onboarding 手動驗收 10 點、Phase 12 完成 Gate** |
| 10-E 回測工作台測試 | 2786-2939 | 驗 10-E-1~4：backtest jobs、cancelled partial result、CSV、toast/skeleton/error panel |
| 10-G 設定頁 + 全局整合測試 | 3005-3092 | 驗 10-G-1 toast/error boundary/skeleton/command palette 與 10-G-2 settings |
| 11-E UI/UX 收尾調整測試 | 3696-3740 | 驗 11-E：sidebar 名稱 + 版號、警示文字字色、quote header 一排、K 線「前收」標籤、編輯按鈕位置、placeholder 移除 |
| 12-A 安裝腳本手動驗收 | 3777-3851 | 乾淨機器情境、已有系統 Node 機器、idempotent、下載失敗模擬、SHA-256 不符、pnpm 版本驗證、改名 / .gitignore |
| 12-B Config API 測試 | 3853-3922 | 14 條 router case + 12 條 service case；含 atomic / 保留性 / FinMind 三條路徑、既有 `PUT /api/config/secrets` regression |
| 12-C Token Setup Dialog 測試 | 3923-3994 | 16 條元件 case + 3 條整合 case + 10 點手動驗收；含強制 block、各錯誤訊息、SWR mutate、不清空既有 key |
| 全專案最終回歸 | 4026-4067 | Phase 完成後 |
| 測試數量統計總覽 | 4068-4127 | 測試統計（含 Phase 11 估算；P12 屬腳本 + onboarding 類，未計入測試數量總覽表） |

### web/_design/ — 10-C 視覺設計稿（Phase 10-C 實作必讀）

10-C 資料管理頁的視覺、配色、版型、Dark/Light 兩版皆已產出於 `web/_design/`，10-C-1 / 10-C-2 實作前**必須先讀完此目錄**：

| 檔案 | 內容 | 用途 |
|:---|:---|:---|
| `web/_design/data-mockup.tsx`（~607 行） | 完整 TSX 視覺稿，含 Dark / Light 兩版、`TOKENS` 主題系統、假資料（6 檔台股 + 3 檔美股）、DELETE Dialog（單步確認版）、6 條「設計建議變更」JSX 註解 | 10-C-1 移植視覺、tokens、配色、佈局；10-C-2 也須沿用相同視覺系統 |
| `web/_design/data-1.jpg` | Dark 版列表頁截圖 | 視覺對照基準 |
| `web/_design/data-2.jpg` | Dark 版 DELETE Dialog 截圖 | DELETE 對話框視覺對照 |

實作守則：
- **不要** 直接 import `web/_design/data-mockup.tsx`（按 [web/_design/README.md](web/_design/README.md) 規則，`_design/` 不進 build）
- 將 mockup 內的視覺結構、tokens、配色搬到 `web/src/app/data/page.tsx` 與 `web/src/components/data/*`
- mockup 第 12-45 行 JSX 註解列了 6 條「設計建議變更」，多數已在規格決議：① 美股單列 + raw+adj 標記、② 全部重建二次確認（10-C-2）、③ 美股 callout、⑤ badge 三態閾值、⑥ 動作欄配色（更新藍 / 刪除紅）。④ 新增標的彈窗設計在 10-C-2 處理

### 驗證後已知問題.md（~785 行）

追蹤驗收中發現的問題。每筆含：位置、狀況、風險、處理階段。已處理的標記 `[✅ 已處理 @ commit]`。每次 session 開始時必讀。

### 未涵蓋資料項目.md

列管目前 fetcher / storage 不抓不存的資料。Phase 8 已接入法人買賣超與融資融券；Phase 11-B 已接入月營收、股利/除息、EPS 與 PER/PBR/殖利率資料層；Phase 11-C 已接入股東會與事件資料層；Phase 11-D 只用 Goodinfo 作事件行事曆 fallback 參考，不寫正式資料層。剩餘項目（財報細項、股權分散、散戶多空比、融資維持率、外資期貨未平倉、大盤指數等）仍需先擴規格再走管線。

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

# Phase 10+：啟動 FastAPI 後端
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000

# Phase 10+：啟動 Next.js 前端（在 web/ 目錄）
cd web && pnpm dev

# Phase 10+：服務層測試
.\.venv\Scripts\python.exe -m pytest tests/test_services/ -v -m "not integration"

# Phase 10+：API 端點測試
.\.venv\Scripts\python.exe -m pytest tests/test_api/ -v -m "not integration"

# Phase 10+：前端測試（在 web/ 目錄）
cd web && pnpm test

# Phase 10+：E2E smoke test（在 web/ 目錄）
cd web && pnpm exec playwright test
```

注意：Windows/OneDrive 路徑下 pytest 暫存目錄可能出現 `PermissionError: [WinError 5]`，視為環境問題，不影響測試結果。

---

## 未來：打包成 Windows 安裝檔（規劃中，未動工）

目標：使用者下載一個檔 → 點擊安裝 → 點擊執行檔即可用。FINMIND_TOKEN 改由 app 首次執行偵測 `.env` 缺失時跳設定頁（非安裝期處理）。

> **與 Phase 12 的關係**：Phase 12 已先把「FINMIND_TOKEN 首次執行偵測 + 跳設定 modal」與「可攜式 Node v22.11.0 落到 `tools\node\`」兩塊雛形實作完成（規格已寫入，實作待動工）。未來 Inno Setup 打包階段可直接複用 P12 的 portable Node 結構與 onboarding modal，不必重做。P12 規格段落見「規格文件索引」內 Phase 12 索引行。

**推薦方案**：Inno Setup 離線安裝包，內含可攜式 Python + 可攜式 Node（沿用 P12 `tools\node\` 結構） + 預下載 wheels + 預 build 前端。安裝到 `%LOCALAPPDATA%\QuantTrader\`（per-user，免 UAC）。Launcher 啟動 uvicorn + `node server.js`，開瀏覽器到 dashboard。

**注意事項**：
- `.venv` 有絕對路徑（`pyvenv.cfg`），不能直接打包搬移；必須在使用者機器上用 bundled wheels 重建
- 未簽章會觸發 SmartScreen 警告；code signing cert 約 USD 100–300/年
- `node_modules` 路徑長，需開 Windows LongPathsEnabled
- 解除安裝 / 重灌時 user data（`.env`、`data/`）必須保留

### 體積優化清單（從預估 ~1 GB 壓到 ~200 MB）

打包時依序套用，**現在不需要動程式碼**：

1. **Next.js standalone output**（最大效益，省 ~520 MB）
   - `web/next.config.ts` 加 `output: 'standalone'`
   - 已確認 web/ 無 middleware、無 API route、無 SSR-only feature，安全
   - 純 build-time 設定，dev / test / 寫程式 0 影響，要做安裝檔時再加
   - 打包腳本要多 copy `public/` 與 `.next/static/` 到 standalone 旁邊
2. **plotly 改 optional dependency**（省 ~20 MB）
   - 只 [src/backtest/report.py](src/backtest/report.py) 用到，改 lazy import
3. **剝 Python 套件 tests / `__pycache__` / `pyarrow/include/`**（省 ~60 MB）
4. **精簡 portable Node**（省 ~30 MB）
   - 只留 `node.exe`，刪 npm / npx / corepack
5. **python-build-standalone 用 `install_only` 變體**（省 ~10 MB）
6. **Inno Setup 壓縮**：`Compression=lzma2/ultra64` + `SolidCompression=yes`
7. **加分項**：移除 `docs/`、`舊文件/`、`web/_design/`、多餘 `*.md`

**進階選項（評估時再決定）**：
- 純靜態前端：`output: 'export'` + FastAPI `StaticFiles` 直接 serve，可完全拿掉 Node runtime（前提：web/ 仍維持無 server-only feature）
- Hybrid 線上安裝：Setup.exe ~50 MB，首次執行去 GitHub Release 抓 runtime bundle

建議分三階段：A. 可攜式 runtime 在乾淨 VM 跑通 → B. Inno Setup 包裝 + 捷徑 + 解除安裝 → C. Launcher 美化（系統匣、無黑視窗）
