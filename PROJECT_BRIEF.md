# QuantTrader 專案簡報

本文件供新 session 快速了解專案全貌，取代逐份閱讀全部規格文件。需要深入某區段時，按行號索引讀取對應文件。

最後更新：2026-05-22

---

## 專案概述

台股 / 美股 US-1 量化交易研究工具（個人版），運行於 Windows 11 本機。聚焦資料管線、研究、回測與 AI 分析，不接實盤。

最新狀態見下方 **Phase 進度表**；過往階段細節請看 `git log` + `驗證後已知問題.md`。

- Phase 1–9 全部完成（含美股 US-1 / 9-G intraday）。
- Phase 10 全部完成（10-A ~ 10-H-2）；舊 Streamlit UI 已移除。
- Phase 11 11-A / 11-B / 11-C / 11-D 已完成並驗證通過；11-D Goodinfo 股利政策 fallback 已上線。
- Phase 11-E 已完成並驗證通過：純前端 UI/UX 收尾調整 8 項已上線，包含工具名稱改 `FactorHammer`、版號 build-time 注入、警示文字字色統一、股東會無資料文案修正、報價列改一排、K 線右側加「前收」、股東會編輯按鈕內聯、散戶多空比 placeholder 移除。
- Phase 12 12-A / 12-B / 12-C / 12-D 已完成；首次執行 Token Onboarding 與 Portable Runtime 重整已收束。
- Phase 13 13-A / 13-B 已完成並通過驗證：Dashboard 分析入口與日線定位整理、指標說明與數值呈現整理（壓力 / 支撐來源 label、近20日 / 近60日高點去重說明、台股成交量以日K股數語意呈現）。
- Phase 14 14-A 已完成並通過驗證：LAN / Tailscale 多裝置存取，採 proxy 同源方案（Next.js `rewrites()` 反代 `/api/*` 至 `127.0.0.1:8000`、uvicorn / `pnpm dev` 綁 `0.0.0.0`、api-client `BASE_URL` 預設空字串走相對路徑、CORS 不動、`NEXT_PUBLIC_API_URL` 保留 escape hatch）；順手把 Next.js dev indicator 搬到右上角避免遮 Mobile Tab Bar。
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
| 10-H-2 | ✅ 完成 | 實際移除與全專案回歸：刪 `src/ui/`、舊 Streamlit 啟動腳本、`pyproject.toml` streamlit 三套件、7 個 Streamlit pytest 檔；`src/ai/advisor.py` 保留（10-F-2 + dashboard analysis 仍使用）；`src/backtest/report.py` `_apply_theme` 去除 ui 依賴 |
| 11-A | ✅ 完成 | Dashboard 版面調整：chart 高度 400px → 300px；移除 K 線圖 KD / RSI / MACD 下方副圖但保留成交量；左欄 chart 下方新增兩塊、共 6 個 dashed placeholder panel；market=us 時 P11 下方兩塊隱藏；籌碼面板買賣力道與融資 / 融券壓成單行；關鍵價位小數顯示修正；使用者實機驗證通過 |
| 11-B | ✅ 完成 | 估值 / 獲利區塊：本益比、股價淨值比、殖利率、月營收、歷史除息本益比、同產業本益比 Modal；新增 PER / 月營收 fetcher，補 dividends / EPS storage + `data_meta`；P11 API namespace、service、frontend hooks / panels / Modal、同產業 PER cache + lock、US market 501 邊界與 route regression 已補；ETF 空資料說明、TTM PE 最近交易日價格、資料刪除 WinError 收尾皆已驗證完成 |
| 11-C | ✅ 完成 | 籌碼 / 事件區塊：法人持股成本、事件行事曆（除息 + 股東會）、股東會手動覆蓋 Modal；新增 TWSE / TPEx 股東會全市場資料源、獨立 metadata JSON、manual override CSV；股東會不進 `data_meta`；資料管理頁單檔刪除不動全市場股東會資料，`data_update` / `data_rebuild` 尾端只 refresh 一次；使用者已驗證完成 |
| 11-D | ✅ 完成 | Goodinfo 股利政策 fallback：事件行事曆無正式未來除息資料時，不再顯示去年資料推估的 `[預估]`，改抓 Goodinfo 股利政策表；只顯示「股利發放期間=未定」或日期落在未來的待發放明細與現金 / 股票股利；過期或失敗顯示查無今年股利資料；使用者已驗證通過 |
| 11-E | ✅ 完成 | UI/UX 收尾調整（純前端）：(1) Sidebar 工具名稱改 `FactorHammer`（不動 repo / package name）；(2) 名稱右下方版號 `v{version}`，build-time 從 `web/package.json` 注入；(3)「資料源未提供」字色改與「撈不到股東會資料」同黃色 token；(4) 股東會無資料文案改為「撈不到股東會資料，需要手動填入（或是ETF沒有股東會）」；(5) 報價列改一排，標籤 muted、數值原色、欄位以兩個全形空格分隔；(6) K 線右側加「前收」標籤，整組同色、漲紅跌綠、平盤灰；(7) 股東會編輯按鈕移到「事件行事曆」標題右側 8px 內聯；(8) 散戶多空比 placeholder 整塊移除；使用者已驗證完成 |
| 12-A | ✅ 完成 | Portable Node + install.bat 改版已完成：install.bat 5 步驟、portable Node v22.11.0 下載 + SHA-256 驗證、corepack 啟用 pnpm 11.1.1、舊 V2 啟動腳本改為 `run_factorhammer.bat` + PATH 注入 `tools\node\`、`web/package.json` 加 `packageManager`、`.gitignore` 加 `tools/`；乾淨環境 / 已有系統 Node / idempotent / 下載失敗等手動驗收已完成 |
| 12-B | ✅ 完成 | Backend Config API 擴充已實作並驗證完成：`POST /api/config/secrets/validate`、FinMind token 驗證改用 FinMind data endpoint、`_write_env` atomic helper（保留註解 / 空行 / 未知 keys、不 sort、寫 `.env.tmp` + `os.replace`）、`get_secrets_status` 空白 fallback bug 修正；既有 `PUT /api/config/secrets` regression 通過 |
| 12-C | ✅ 完成 | Frontend Token Setup Dialog 已實作並驗證完成：強制 block modal（無 X、ESC / overlay 都 preventDefault、儲存鈕灰至 FinMind 非空）、FinMind 申請連結、AI keys 選填折疊、SWR `mutate(() => true)` 全域 invalidate；不提供清空既有 AI key、不提供「先跳過」 |
| 12-D | ✅ 完成 | Verifier 文件收尾已完成：同步 12-A/B/C 狀態、檢查舊啟動腳本名殘留、更新現役啟動入口；Phase 12 整體完成 |
| 13-A | ✅ 完成 | Dashboard 分析入口與日線定位整理：移除「分析 / 即時更新」按鈕，Enter 成為唯一入口；同代碼 Enter 走 SWR `mutate()` 強制重跑 dashboard payload，後端維持 `_sync_symbol_daily_data → DataMaintenance.update_daily()` 路徑；台股 `intraday_df=[]` 隱藏 `分 K` tab，美股 intraday 仍顯示；自動測試 8 case + 手動驗收 1-7 全通過 |
| 13-B | ✅ 完成 | Dashboard 指標說明與數值呈現整理：壓力 / 支撐補來源 label，說明近20日 / 近60日高點過近會合併；台股報價列與 K 線 tooltip 成交量統一以日K股數語意呈現，避免 `quote.volume` 與 `daily_df.volume` 單位混淆；`formatTwDailyVolume()` 補前端測試，使用者已完成人工驗證 |
| 14-A | ✅ 完成 | LAN / Tailscale 多裝置存取：`run_factorhammer.bat` uvicorn 加 `--host 0.0.0.0`、`pnpm dev` 加 `-H 0.0.0.0`（pnpm 9+ 不需 `--` 分隔符）；`web/next.config.ts` 新增 `rewrites()` 反代 `/api/:path*` → `http://127.0.0.1:8000/api/:path*`、`devIndicators.position: top-right`（避免 Mobile Tab Bar 被遮）；`web/src/lib/api-client.ts` `BASE_URL` 預設值改為空字串；FastAPI CORS 不動；`NEXT_PUBLIC_API_URL` 保留為 escape hatch。Gate：tsc 0 errors、vitest 61 files / 407 tests pass（含 14-A 兩條 escape hatch / same-origin 新案）、pytest `tests/test_api` 120 passed；手動驗收 M1（PC 本機同源）、M2（rewrites 生效）、M3（同 Wi-Fi 手機）、M4（Tailscale）、M6（手機端 Token Setup Dialog onboarding）全通過，M5 自動測試已涵蓋故跳過 |

## 當前待辦

見 `驗證後已知問題.md`（每次必讀）。

主線：**Phase 1–14-A 全部完成並通過驗證。** 10-F-2（AI 問答接 LLM）延後，不卡主線。專案已完全遷移至 Next.js + FastAPI；Streamlit 程式碼與套件已從 codebase 移除。

2026-05-22 狀態（Phase 14-A 完成）：
- **P14-A 實作完成**：`run_factorhammer.bat` 後端 uvicorn 改綁 `--host 0.0.0.0`、前端 `pnpm dev -H 0.0.0.0`（規格原本寫 `-- -H 0.0.0.0`，實機跑 pnpm 11 + Next.js 15.3 時 `next dev` 會把 `--` 當 positional 並把 `-H` 誤判為 project directory 直接退出；驗證階段抓到後改為 `-H 0.0.0.0`，規格書 4788 / 設計方針 9889 / 9915 / 9921 四處同步修正並保留反例註解）；`web/next.config.ts` 加 `rewrites()` 把 `/api/:path*` 反代到 `http://127.0.0.1:8000/api/:path*`、另加 `devIndicators.position: "top-right"` 避免手機底部 Tab Bar 被 Next.js dev 浮動鈕遮擋；`web/src/lib/api-client.ts` `BASE_URL` 預設值由 `"http://localhost:8000"` 改為 `""` 走 same-origin proxy，保留 `NEXT_PUBLIC_API_URL` escape hatch；vitest 補兩條（`預設走 same-origin` / `接受 NEXT_PUBLIC_API_URL 覆蓋`）。
- **Gate**：`npx tsc --noEmit` 0 errors、`pnpm test -- --run` 61 files / 407 tests pass（13-B baseline 405 → +2 即 14-A 新案）、`pytest tests/test_api -m "not integration"` 120 passed in ~3s（CORS regression 無破壞）。手動驗收 M1（PC 同源 `localhost:3000`）、M2（`/api/data/symbols` proxy）、M3（同 Wi-Fi `192.168.18.5:3000` 手機載入 2330）、M4（Tailscale 跨網路）、M6（手機端 Token Setup Dialog 正常驗證 FinMind token）使用者皆已通過；M5（`NEXT_PUBLIC_API_URL` escape hatch）已由 vitest 自動測試涵蓋，手動驗收略過。
- **手機端剩餘觀察**：Next.js 15.3 dev mode 在手機 console 報 hydration mismatch（推測時間 / locale 格式相關，PC 端原本就存在）；屬 dev-only 行為，production build 不會跳 overlay，14-A 不處理，另票追蹤。
- **規格 / 設計方針 / 測試指南三份主文件**：14-A 段落於前一輪已寫入，本輪只同步修正 `pnpm dev` 指令寫法錯誤。

2026-05-21 狀態（Phase 13-B 完成）：
- **P12 狀態**：12-A / 12-B / 12-C / 12-D 已完成；現役啟動入口以 `run_factorhammer.bat` 為準。
- **P13-A 完成**：移除「分析」/「即時更新」按鈕、`submitSymbol` 同代碼分支呼叫 `void mutate()`、`ChartSection` 以 `payload.intraday_df.length > 0` 決定分K tab 顯示、minute→day fallback。Gate：`npx tsc --noEmit` 0 errors、`pnpm test -- --run` 61 files / 399 tests pass（含 13-A 8 case）；手動驗收 1-7（控制列只剩三件、看不到舊按鈕、新代碼 Enter 載入、同代碼 Enter Network 重發 `/api/dashboard/payload`、台股只剩日/週/月 K、週/月 K 切換不空白）使用者已通過。
- **P13-B 完成**：`LevelsPanel` 改為逐筆顯示壓力 / 支撐價格與來源 label，補近20日 / 近60日高點過近會合併說明；台股報價列改顯示「日K成交量」且優先取最新日K `daily_df.volume`，K 線 tooltip 非分K成交量套用日K股數語意 formatter；Gate：`npx tsc --noEmit` 0 errors、`pnpm test -- --run` 61 files / 405 tests pass；使用者已完成人工驗證。

過往驗證 recap（2026-05-10 ~ 2026-05-18）：
- Phase 6-C → 11-E 各子階段陸續完成並通過驗證；逐 phase 範圍 / 邊界決定 / 驗證結果見上方「Phase 進度表」、commit 訊息與 `驗證後已知問題.md`。
- 重要設計邊界（保留參考）：
  - P11-B 同產業 PER：cache miss 用 `ThreadPoolExecutor(max_workers=8)`、cache path `data/cache/industry_per/{slug(industry)}_{YYYY-MM-DD}.parquet`；個別 peer 失敗以 null 回傳。
  - P11-C 股東會：全市場單一 parquet，不進 `data_meta`，metadata 用 `shareholder_meeting.meta.json` 管 once-per-day；manual override 放 `data/manual/shareholder_meeting_override.csv`；單檔刪除不動全域股東會。
  - 10-G-2 主題系統：沿用既有自製 `theme-provider.tsx`（class="dark" + localStorage `qt-theme`），**未引入 `next-themes`**（與規格偏離但功能等價）。

已知設計限制：
- 兩引擎是不同典範（signal-based vs order-based），跨引擎只能比 per-share PnL
- 引擎不支援加倉/分批進出，維持「全進全出」
- 事件引擎已支援 pandas 新舊分鐘頻率 alias（`T` / `min` / `5min` / `H` / `h`）；短資料或無法推斷頻率時 fallback 到 `1day`

## 規格文件索引

### 量化交易系統規格書_shellpig版.md（~4909 行）

| 區段 | 行範圍 | 何時讀 |
|:---|:---|:---|
| 修訂歷史 | 3-31 | 查版本變更，最新為 `V3.3`（Phase 13 Dashboard 現有功能調整；含 13-A 分析入口與日線定位整理、13-B 指標說明與數值呈現整理） |
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
| **Phase 12 首次執行 Token Onboarding 與 Portable Runtime 重整（12-A~12-D）** | **4172-4592** | **install.bat 改版、portable Node v22.11.0、`run_factorhammer.bat`、`POST /api/config/secrets/validate` + FinMind 驗證、`_write_env` atomic helper 重構、Token Setup Dialog 強制 block modal、SWR mutate；實作 12-A/B/C 時必讀** |
| **Phase 13 Dashboard 現有功能調整（13-A~13-B）** | **4596-4731** | **Dashboard 分析入口與日線定位整理、同代碼 Enter 強制重跑 payload、隱藏無效分K、壓力 / 支撐來源說明、成交量日K股數語意統一時必讀** |
| **Phase 14 區網與遠端存取（14-A）** | **4735-4829** | **LAN / Tailscale 多裝置存取規格；含 proxy 同源 vs 環境變數 A/B 對照、`run_factorhammer.bat` host 改動、Next.js `rewrites()`、`api-client.ts` `BASE_URL` 預設值、CORS 不動的原因、安全模型、Tailscale 行為時必讀** |
| 子階段總覽 | 2666-2680 | Phase 總覽（含 Phase 11） |
| 費用估算 | 2685-2703 | API / yfinance / TWSE / TPEx / Next.js / US-2 資料源成本 |
| 10-E：回測研究工作台 | 2942-3387 | 實作 10-E-1~4、Job lifecycle、SSE、取消、CSV、toast/skeleton/error boundary/command palette 整合時必讀 |
| 10-G：設定頁 + 全局整合 | 3447-3649 | 實作 10-G-1 toast/error boundary/skeleton/command palette，或 10-G-2 settings/secrets/theme/strategy preset 時必讀 |
| 11-B：估值 / 獲利區塊 | 3871-3937 | 實作 PER / 月營收 / dividends / EPS 落地、valuation API、同產業 PER Modal 時必讀 |
| 11-C：籌碼 / 事件區塊 | 3938-4049 | 實作法人持股成本、股東會 TWSE/TPEx fetcher、manual override、event calendar、資料管理頁互動規則時必讀 |
| 11-E：UI/UX 收尾調整 | 4126-4170 | 實作工具名稱改 `FactorHammer`、版號 build-time 注入、警示文字字色統一、股東會無資料文案、報價列改一排、K 線右側加「前收」、編輯按鈕內聯、placeholder 移除時必讀 |
| 12-A：Portable Node + install.bat 改版 | 4231-4327 | 實作 install.bat 5 步驟、portable Node v22.11.0 + SHA-256、corepack/pnpm 啟用、舊 V2 啟動腳本改名為 `run_factorhammer.bat`、`web/package.json` packageManager、`.gitignore` 加 `tools/` 時必讀 |
| 12-B：Backend Config API 擴充 | 4328-4424 | 實作 `POST /api/config/secrets/validate` + FinMind 驗證流程、`_write_env` atomic + 保留註解 / 空行 / 未知 keys 共用 helper、`get_secrets_status` 空白 fallback bug 修正時必讀 |
| 12-C：Frontend Token Setup Dialog | 4425-4537 | 實作強制 block modal（不可 ESC / overlay 關）、FinMind 申請連結、AI keys 選填折疊、SWR `mutate(() => true)` 全域 invalidate 時必讀 |
| 12-D：Verifier 文件收尾 | 4538-4563 | verifier 角色執行；含舊啟動腳本名殘留檢測指令、文件同步檢查清單 |
| 13-A：Dashboard 分析入口與日線定位整理 | 4618-4665 | 移除「分析 / 即時更新」按鈕、Enter 唯一入口、同代碼 Enter 呼叫 SWR `mutate()`、隱藏無 intraday 資料的 `分 K` tab 時必讀 |
| 13-B：Dashboard 指標說明與數值呈現整理 | 4666-4713 | 壓力 / 支撐來源 label 或 tooltip、去重說明、成交量日K股數語意、避免即時報價量單位混淆時必讀 |
| 14-A：LAN / Tailscale 存取（proxy 同源） | 4754-4829 | 14-A 目標、proxy 同源 vs 環境變數 A/B 對照、CORS 不動的原因、必須動的四項、Phase 14-A 不做與風險時必讀 |
| 附錄 A：免責聲明全文 | 4832-4851 | 免責聲明文案 |
| 附錄 B：架構決策補充 | 4853-4909 | 美股邊界與 AI provider 抽象 |

### 開發設計方針.md（~10012 行）

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
| **Phase 13 Dashboard 現有功能調整** | **9619-9873** | **實作 P13 前必讀：13-A Enter 提交與同代碼 `mutate()`、分K tab 條件顯示；13-B 壓力 / 支撐來源說明、成交量 formatter 與報價列成交量來源規則** |
| **Phase 14 區網與遠端存取** | **9875-10012** | **實作 P14 前必讀：14-A `run_factorhammer.bat` 兩行改法、`next.config.ts` `rewrites()` 範例、`api-client.ts` `BASE_URL` 預設改空字串、CORS 不動的原因、`NEXT_PUBLIC_API_URL` escape hatch 去留** |
| 10-E 回測研究工作台 | 6920-7480 | 實作 backtest jobs、partial cancellation、CSV blob、共用 hook/元件時必讀 |
| 10-G 設定頁 + 全局整合 | 7649-8119 | 實作 toast、Error Boundary、Skeleton、Command Palette、settings/secrets/theme/preset CRUD 時必讀 |
| 11-B 資料層 / Service / API / 前端 | 8509-8705 | 實作 PER、monthly_revenue、dividends/EPS storage、valuation/monthly/dividend/industry PER API 與 panel 時必讀 |
| 11-C 股東會 / 事件 / 法人成本 | 8706-8880 | 實作 TWSEFetcher、shareholder_meeting parquet/meta、once-per-day guard、manual override、資料管理整合、event calendar 與 institutional cost 時必讀 |
| 11-D Goodinfo 股利政策 fallback | 8886-9075 | 實作 Goodinfo parser、每日 cache、event calendar fallback payload、前端「今年股利資料 / 查無今年股利資料」顯示時必讀 |
| 11-E UI/UX 收尾調整 | 9077-9170 | 實作 `next.config.ts` 注入 `NEXT_PUBLIC_APP_VERSION`、sidebar header 改名、quote header 改一排、K 線「前收」標籤、編輯按鈕內聯、placeholder 移除時必讀 |
| 12-A install.bat / Portable Node | 9190-9259 | install.bat 內部 5 步驟與 PATH 注入時機、portable Node 下載 / SHA-256 / 解壓扁平化、`run_factorhammer.bat` PATH 注入時必讀 |
| 12-B Config API 擴充 + `_write_env` 重構 | 9260-9449 | `validate_finmind_token` 完整程式碼、router endpoint 範例、共用 `_write_env` atomic helper、`get_secrets_status` bug 修法時必讀 |
| 12-C Token Setup Dialog 元件 | 9450-9608 | Dialog hooks 範例、儲存 handler、外部連結 JSX、`dashboard-page-client` 整合、既有測試 mock 調整時必讀 |
| 13-A Dashboard 分析入口與日線定位整理 | 9631-9755 | `DashboardPageClient` submitSymbol helper、同代碼 `mutate()`、移除按鈕與未用 icon import、`分 K` tab 依 `intraday_df.length` 顯示時必讀 |
| 13-B Dashboard 指標說明與數值呈現整理 | 9756-9866 | `LevelsPanel` label / tooltip、`formatTwDailyVolume()`、報價列成交量優先用最新日K `volume`、避免 `quote.volume` 單位混淆時必讀 |
| 14-A LAN / Tailscale 存取（proxy 同源） | 9879-10005 | `run_factorhammer.bat` uvicorn `--host 0.0.0.0` 與 `pnpm dev -H 0.0.0.0`、`next.config.ts` `rewrites()` + `devIndicators.position`、`api-client.ts` `BASE_URL` 改空字串、CORS 不動的原因、`NEXT_PUBLIC_API_URL` escape hatch、Tailscale 行為說明時必讀 |

### 測試指南.md（~4346 行）

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
| **Phase 13 測試（13-A~13-B）** | **4027-4141** | **Dashboard 現有功能調整測試；含移除按鈕、Enter 提示、新 / 同代碼 Enter 重新請求、分K tab 條件顯示、壓力 / 支撐來源、成交量日K股數語意** |
| **Phase 14 測試（14-A）** | **4143-4242** | **LAN / Tailscale 多裝置存取測試；含 vitest `api-client BASE_URL` 兩條新案例、`tests/test_api` regression、Playwright 不動、6 個手動驗收情境 14-A-M1 ~ M6（本機既有路徑、proxy rewrites 生效、同 Wi-Fi 手機、Tailscale 跨網路、`NEXT_PUBLIC_API_URL` escape hatch、Token Dialog 跨裝置）、Phase 14 完成 Gate** |
| 10-E 回測工作台測試 | 2786-2939 | 驗 10-E-1~4：backtest jobs、cancelled partial result、CSV、toast/skeleton/error panel |
| 10-G 設定頁 + 全局整合測試 | 3005-3092 | 驗 10-G-1 toast/error boundary/skeleton/command palette 與 10-G-2 settings |
| 11-E UI/UX 收尾調整測試 | 3696-3740 | 驗 11-E：sidebar 名稱 + 版號、警示文字字色、quote header 一排、K 線「前收」標籤、編輯按鈕位置、placeholder 移除 |
| 12-A 安裝腳本手動驗收 | 3777-3851 | 乾淨機器情境、已有系統 Node 機器、idempotent、下載失敗模擬、SHA-256 不符、pnpm 版本驗證、改名 / .gitignore |
| 12-B Config API 測試 | 3853-3922 | 14 條 router case + 12 條 service case；含 atomic / 保留性 / FinMind 三條路徑、既有 `PUT /api/config/secrets` regression |
| 12-C Token Setup Dialog 測試 | 3923-3994 | 16 條元件 case + 3 條整合 case + 10 點手動驗收；含強制 block、各錯誤訊息、SWR mutate、不清空既有 key |
| 13-A Dashboard 分析入口與日線定位整理測試 | 4037-4079 | 驗移除「分析 / 即時更新」、Enter 提示、新 / 同代碼 Enter 重新請求、無 intraday 隱藏分K、有 intraday 保留分K |
| 13-B Dashboard 指標說明與數值呈現整理測試 | 4080-4124 | 驗壓力 / 支撐來源 label 或 tooltip、去重說明、成交量 `2_379_159` 顯示為 `238萬股` 或完整股數、避免 `quote.volume` 單位混淆 |
| 14-A LAN / Tailscale 存取測試 | 4145-4242 | 驗 14-A：vitest `api-client BASE_URL` 預設空字串 + escape hatch、6 個手動驗收（本機既有路徑、proxy rewrites、同 Wi-Fi、Tailscale、`NEXT_PUBLIC_API_URL` 覆蓋、Token Dialog 跨裝置）、Phase 14 完成 Gate |
| 全專案最終回歸 | 4245-4285 | Phase 完成後 |
| 測試數量統計總覽 | 4287-4346 | 測試統計（含 Phase 11 估算；P12 屬腳本 + onboarding 類、P14 屬部署面，未計入測試數量總覽表） |

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

注意：`web/` 的 `pnpm build` 以使用者人工 PowerShell 執行結果為準。2026-05-18 已確認人工執行 `cd web; pnpm build` 可完整通過；但 Codex runner / agent shell 目前在 Windows 子程序鏈上不可靠，曾卡在 `next build` banner 後且 timeout 未能正確終止。後續 agent 驗證前端以 `npx tsc --noEmit` + `pnpm test -- --run` 為主要 gate；不要再由 agent 自動跑 `pnpm build`，除非使用者明確要求並接受可能卡住。

---

## 未來：打包成 Windows 安裝檔（規劃中，未動工）

目標：使用者下載一個檔 → 點擊安裝 → 點擊執行檔即可用。FINMIND_TOKEN 改由 app 首次執行偵測 `.env` 缺失時跳設定頁（非安裝期處理）。

> **與 Phase 12 的關係**：Phase 12 已先把「FINMIND_TOKEN 首次執行偵測 + 跳設定 modal」與「可攜式 Node v22.11.0 落到 `tools\node\`」兩塊雛形實作完成。未來 Inno Setup 打包階段可直接複用 P12 的 portable Node 結構與 onboarding modal，不必重做。P12 規格段落見「規格文件索引」內 Phase 12 索引行。

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
