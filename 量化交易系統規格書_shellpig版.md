# KOC AI 量化交易系統開發規格書（shellpig 個人版）

## 修訂歷史

| 版本 | 日期 | 修訂說明 |
| :--- | :--- | :--- |
| **V1.0** | 2026/04/24 | 基於企業版 V3.0 規格書精簡而來。定位為個人研究工具，聚焦台股市場，純 Python 技術棧，含 AI 技術分析問答功能。 |
| **V1.1** | 2026/04/24 | Claude + Gemini 雙 AI Review 後更新。新增：時區規範（5.4）、數據維護模組（5.5）、`BacktesterBase` 抽象介面、`Account`/`SimpleAccount` 設計、Grid Search 參數優化（6.5）、`config.yaml` 配置管理、Notebook 範例說明。 |
| **V1.2** | 2026/04/25 | 事實性修正：(1) 台股漲跌停 ±15% → ±10%；(2) 修正台股交易時間描述（無午休，09:00–13:30 連續）；(3) 修正撮合假設與滑價模型衝突；(4) FinMind 免費層分K 限制描述；(5) KD↔STOCH 指標映射；(6) `on_bar` 介面 `portfolio`/`account` 命名統一；(7) 補 `.env.example` 範本檔；(8) Phase 1-D 前復權驗收條件嚴謹化；(9) 放寬 Phase 4-D AI 問答時間門檻；(10) §5.4 FinMind naive datetime 處理說明。 |
| **V1.3** | 2026/04/27 | 新增 Phase 5-A：回測頁個股股價走勢、週/月/季均線、買賣點標記、互動 tooltip，以及近 15 年季度 EPS + 年度 EPS 紀錄。 |
| **V1.4** | 2026/04/27 | 新增 Phase 5-B：定期定額策略、最小買入單位 1 股、多策略設定架構與策略參數保存格式。 |
| **V1.5** | 2026/04/30 | 新增 Phase 6（UI/UX 強化）章節與 Phase 6-A：執行期主題切換（light / dark / finance_green）、CSS 注入即時生效、`config.yaml` `ui` 區塊、可選的 `streamlit-extras` 與 `streamlit-option-menu` 元件庫整合。 |
| **V1.6** | 2026/04/30 | Phase 6-A 主題清單對齊實作：由原訂 3 套（`light` / `dark` / `finance_green`）擴充為 6 套（`arctic_light` / `obsidian_dark` / `finance_green` / `midnight_blue` / `cyberpunk` / `warm_sepia`）；預設主題與 fallback 改為 `arctic_light`；同步更新 Plotly template 對應表。 |
| **V1.7** | 2026/05/07 | 新增 Phase 7（策略擴充）章節與 Phase 7-A：6 種技術分析策略（RSI 超買超賣、KD 交叉、MACD 交叉、布林通道、乖離率、突破策略），含向量化 + 事件驅動雙介面、`strategy_config.py` preset 正規化、UI 回測頁分派。 |
| **V1.8** | 2026/05/08 | 新增 Phase 7-B（策略研究工作台）：批次策略比較、結果保存、UI tab 重構、K 線圖升級、Signal/Trade 雙層標記、策略指標副圖。新增 Phase 7-C（參數掃描與防過度最佳化）：Grid Search、參數驗證過濾、組合數限制、樣本不足警告、排序與 Top N。 |
| **V1.9** | 2026/05/09 | 新增 Phase 7-D（Walk-Forward Analysis）：單標的向量化 WFA、rolling IS/OOS 視窗、IS 參數掃描 + OOS 驗證、OOS 彙總績效、IS/OOS degradation、參數穩定性 CV、執行量上限、UI 中文說明規則與 CSV 匯出。 |
| **V1.10** | 2026/05/10 | Phase 7-D 驗收完成：7-D-1 核心引擎與 7-D-2 Walk-Forward tab、中文說明、回測次數預估、summary/window/stability table、CSV 匯出、Phase 7 回歸皆通過。 |
| **V1.11** | 2026/05/10 | 新增 Phase 6-B：設定頁與側邊欄 UI 小修。包含隱藏 Streamlit 自動頁面入口、預設外觀改為 `midnight_blue`、一般設定與策略設定儲存/恢復流程分離、策略類型選項補齊 8 種並顯示中文說明、每種策略提供一組預設 preset、已儲存 preset 可單獨清除。 |
| **V2.0** | 2026/05/10 | 新增 Phase 8（個股綜合分析儀表板）：8-A 技術面自動判讀引擎、8-B K 線型態辨識、8-C 籌碼分析管線、8-D 即時行情接入、8-E AI 綜合分析與操作劇本、8-F 儀表板 UI。新增 TWSE MIS 即時報價、FinMind 法人/融資融券管線、`src/analysis/` 模組群。 |
| **V2.1** | 2026/05/11 | 確認 Phase 9（美股 US-1 支援）規格：第一版只做美股日 K、調整後價格、回測與技術分析；不做即時行情、籌碼、分 K、匯率換算、財報與期權。新增多市場基礎、`market=us` 資料管線、USD 回測與既有 UI 市場切換規格。 |
| **V2.2** | 2026/05/13 | 新增 Phase 9-G：美股 yfinance 1m intraday 盤中快照與分 K 圖。使用最新 1 分 K close 作為近似盤中價，漲跌以該 raw 價格對前一紐約交易日 raw close 計算；新增專用 intraday API，不改 `fetch_minute(market="us")` 的 US-1 拒絕行為；不做 WebSocket、買一 / 賣一、五檔、逐筆或實盤級即時報價。 |
| **V2.3** | 2026/05/14 | 新增 Phase 10（前端架構重構）：從 Streamlit 遷移至 Next.js + FastAPI。10-A 服務層抽離 + FastAPI 後端骨架、10-B Next.js 前端骨架、10-C 資料管理頁、10-D 個股分析儀表板（Lightweight Charts）、10-E 回測研究工作台、10-F AI 問答頁、10-G 設定頁 + 全局整合、10-H 舊 UI 移除與收尾。新增 `src/services/`、`api/`、`web/` 目錄。 |
| **V2.4** | 2026/05/15 | Phase 10-F 拆分為 **10-F-1（UI shell + lock）** 與 **10-F-2（接 LLM）**：10-F-1 完整實作 AI 問答頁 UI（含免責聲明 gate + localStorage 持久、訊息泡泡與 Markdown 渲染 `react-markdown` + remark-gfm、Mock 逐字串流模擬未來 SSE token 動畫），但**不串接真實 LLM**；後端 `/api/ai/chat` 與 `/api/ai/status` 僅做最小骨架（chat 永遠回 `503 AI_DISABLED`、status 永遠回 `{ available: false, reason: "feature_locked" }`）；Sidebar AI 入口加「後續開放」灰色徽章；訊息歷史刷新即清不持久化。**設定頁的 AI 開關鎖死延至 10-G 一起做**（在 10-G 把 toggle 預設 disabled）。10-F-2 延後實作、時程不卡 10-G / 10-H，將補上 `AIAdvisor.stream_chat()` 三 adapter（Anthropic / OpenAI / Gemini）與真實 SSE。10-F-1 落地時 `pyproject.toml` 與 `web/package.json` package version 同步 bump 至 `0.2.0`（兩個 package version 從此對齊）。 |
| **V2.6** | 2026/05/15 | Phase 10-G 補完細部規格並正式拆為 **10-G-1（基礎設施先行）+ 10-G-2（設定頁主功能）**。**三項拍板決定**：(1) **主題系統** 從舊 Streamlit 6 套收斂為 Dark / Light 二選一（不移植），預設 dark、`next-themes` 留到 10-G-2 才裝、不接 system 自動偵測避免 K 線色閃動；(2) **策略 preset API** 改以 `name` 為主鍵：`POST /api/config/strategies`（upsert by name）+ `DELETE /api/config/strategies/{name}`（idempotent）+ `POST /api/config/strategies/restore`（復原 8 組預設）；payload `{ preset: {name, strategy, params, market} }`、錯誤碼 `INVALID_PRESET` 422；(3) **Toast 系統** 用 `sonner`（拔 `@radix-ui/react-toast`），預設右下、3 秒、success/error/info 三變體，封裝為 `useToast()` hook（介面與 10-E 已預設一致）；Error Boundary 只接 React 例外、API 錯誤一律走 toast。**10-G-1 提供 4 種全局元件供 10-E 4 段共用**：`useToast()` hook + `sonner Toaster`、`<ErrorBoundary>` + 預設 fallback、`CardSkeleton` / `ChartSkeleton` / `TableSkeleton` 三變體、`<CommandPalette>` + `useCommandPaletteEntry()` hook（cmdk 為底、Ctrl+K / Cmd+K / Esc / `/` 開啟並 focus input、頁面 + 股票搜尋）；同時把 10-C-2 既有 5 處 banner（全部更新 / 全部重建 / 新增 / 動作欄·更新 / DELETE）統一遷移為 toast。**10-G-2 設定頁四分區**：API key write-only（5 provider）+ 策略 preset CRUD（含重置預設）+ Dark/Light toggle + AI toggle disabled + tooltip。**10-E 合約收斂**：取消後 job 保持 `cancelled` 並可讀取 partial result；fetch/SSE/invalid JSON 走 toast + 頁內錯誤區，不交給 Error Boundary；CSV 匯出 query 由 `/api/jobs/{id}/result` 所在的 jobs router 負責；10-E-2 比較表定為 10 欄。**10-G-2 在所有 10-E 子階段驗收後才執行**；10-H 移至 10-G-2 之後。 |
| **V2.5** | 2026/05/15 | Phase 10-E 拆分為 **10-E-1（單次回測）/ 10-E-2（策略比較）/ 10-E-3（參數掃描）/ 10-E-4（Walk-Forward）** 四個子階段：四段共用 Job lifecycle + SSE 進度 + 取消、共用 K 線 + Markers chart 元件、共用 tearsheet 5 metric card；後端 dispatcher 比照 10-C-2 `_run_data_job` 樣板擴充。**明確不做老 Streamlit 的「歷史結果」tab**（Next.js SWR cache 後切頁狀態不會掉，迫切性降低）；**Heatmap 採「排名表 + 顏色背景」為主，僅當 sweep 為恰好 2 個參數時加 2D heatmap（自製 CSS Grid + Tailwind 色階，不引入 heatmap 套件）**；**多策略 equity curve 疊圖用 lightweight-charts 多個 LineSeries 同圖（不引入 Recharts）**；**WFA CSV 由後端產生 blob、前端 `<a download>` 觸發下載**。取消行為：服務層 `run_*_job` 在迴圈點檢查 `manager.get_job(job.id).status == "cancelled"` 後 break，比照 10-C-2 模式。**實作順序調整：10-G 將拆為 10-G-1（基礎設施先行：Toast 系統 + Error Boundary + Loading Skeleton + Command Palette）與 10-G-2（設定頁主功能），執行順序改為 10-G-1 → 10-E（4 段）→ 10-G-2 → 10-H；10-E 4 個子階段假設 10-G-1 已就位，job complete / cancel / error 通知統一走 toast、SSE 中載入態統一用 skeleton、頁面/股票導航支援 Command Palette。10-G-1 / 10-G-2 細部規格將於後續 V2.6 補上。** |
| **V2.7** | 2026/05/16 | **10-E 規格審查補丁**（12 項）：(1) `JobManager.finish_cancelled_job()` 新增（含 `cancel_job()` race condition 修正——只設 status、不關 queue）；(2) `GET /api/jobs/{id}/result` 擴充允許 cancelled + partial result；(3) 取消 `api/routers/backtest.py` 冗餘端點，前端直接用 `GET /api/config` 取 preset 清單；(4) `initial_capital` 預設 `1000000`，需新增為 `run_backtest_job()` 參數並注入引擎；(5) DCA 序列化映射補充（equity_curve / trades / metrics null 欄位）；(6) `sweep-defaults.ts` 完整內容 + `PARAM_TYPES` 型別表；(7) WFA 特化 `WfaProgress` interface 補充；(8) CSV blob 函式位置指定 `src/services/backtest_service.py`；(9) E2E Playwright 統一在 10-E-4 後撰寫；(10) **交易數量單位統一顯示「股」（shares），不做 1000 股→1 張轉換**（與舊 Streamlit 回測頁一致；「張」僅用於 10-D 儀表板的日成交量與籌碼顯示）；(11) 切換市場時 reset state（清空回測結果）；(12) DCA 批次比較 error message 明確定義為「DCA 不支援批次比較（請至單次回測使用）」。 |

---

## 0. 本文件與企業版 V3.0 的關係

本規格書（shellpig 版）是 `量化交易系統規格書_V3.0.md` 的**個人精簡版**，保留核心設計理念，移除所有對個人開發者不必要的複雜性。

### 主要差異對照表

| 功能/技術 | 企業版 V3.0 | shellpig 個人版 | 調整理由 |
| :--- | :--- | :--- | :--- |
| **執行語言** | Python + Rust | **純 Python** | 個人無 HFT 需求；Rust 學習曲線高，維護成本不合個人使用 |
| **跨語言通訊** | gRPC + Protobuf | **Python 函式呼叫** | 單一程式不需要微服務通訊層 |
| **回測顆粒度** | Tick / OrderBook | **分鐘K 事件驅動** | 台股免費歷史 Tick 資料幾乎不存在；分鐘K 已足夠絕大多數策略 |
| **時序資料庫** | TimescaleDB + Redis | **DuckDB + Parquet** | 零伺服器設定，單一 .db 檔，個人規模綽綽有餘 |
| **監控儀表板** | Prometheus + Grafana | **Streamlit 本機 UI** | 單機工具不需要監控基礎設施 |
| **容器化部署** | Docker + Kubernetes | **Python venv（uv）** | 個人單程式，無需容器編排 |
| **目標市場** | 台股、美股、加密貨幣 | **台股（.TW）為主；Phase 9 規劃美股 US-1（日 K 研究）** | 先深耕台股；美股第一版僅擴充研究、回測與技術分析，不接實盤 |
| **下單功能** | OMS/EMS 實盤 | **不接實盤（純研究）** | 個人版目標：研究、回測、AI 問答 |
| **演算法拆單** | TWAP / VWAP / Iceberg | **不需要** | 不接實盤 |
| **分級權限** | L1 / L2 / L3 | **不需要** | 個人單用戶 |
| **警報系統** | PagerDuty + 電話 | **Telegram Bot（選配）** | 個人工具不需要 on-call 機制 |

---

## 1. 專案願景與目標

**定位：** 個人量化交易研究工具，運行於 Windows 11 本機，不需要伺服器、不接實盤、不需團隊協作。

**三大核心功能：**
1. **自動化資料管道** — 定期抓取台股歷史 K 線（日K、分K）並存入本機資料庫
2. **回測引擎** — 支援向量化快速回測與分鐘K 事件驅動回測，自動生成績效報告
3. **AI 技術分析問答** — 以自然語言詢問技術分析問題，可選 ChatGPT / Claude / Gemini 等 LLM，自動查詢數據並給出分析

**設計原則：**
- **零設定啟動：** 不依賴任何外部伺服器（無 PostgreSQL、無 Redis、無 Docker）
- **免費資料優先：** 使用公開免費 API，必要時才升級付費方案
- **可讀性勝過效能：** 個人工具優先追求程式碼易讀，方便未來自行修改
- **策略即文件：** 每個策略為一個獨立 Python 類別，回測/模擬介面相同

---

## 2. 技術語言評估

### 為何個人版選擇純 Python

| 考量 | 說明 |
| :--- | :--- |
| **策略迭代速度** | Python 生態（Pandas、pandas-ta、matplotlib）讓策略邏輯 1 天內可驗證 |
| **效能是否足夠** | 台股個股日K 回測（5年、分鐘K）通常在 10 秒內完成，Python 速度足夠 |
| **若需加速** | 使用 `numba` JIT 或 `Polars`（Rust 底層）替代 Pandas，無需自己寫 Rust |
| **維護成本** | 單人維護，Python 程式碼易讀易改；Rust 需要額外處理記憶體、所有權等概念 |

**結論：個人版全程 Python，若未來效能真的成為瓶頸，再用 `numba` 或 `Polars` 局部優化即可。**

### 核心套件選型

| 類別 | 套件 | 說明 |
| :--- | :--- | :--- |
| **資料處理** | `pandas`, `polars` | 資料清洗、指標計算的主力 |
| **技術指標** | `pandas-ta` | 150+ 指標，一行呼叫（MA、RSI、MACD、KD、BBAND 等） |
| **台股資料** | `finmind`（FinMind SDK） | 日K、分K、財報、法人買賣超 |
| **歷史資料備援** | `yfinance` | 台股加 `.TW` 後綴可取得日K（Yahoo Finance） |
| **資料存儲** | `duckdb`, `pyarrow` | DuckDB 查詢 + Parquet 格式存儲 |
| **回測** | 自建（教育目的） | 理解底層運作；或 `vectorbt` 快速使用 |
| **AI 功能** | `openai`, `anthropic`, Gemini SDK/API | Provider-neutral Tool Use / Function Calling 模式 |
| **視覺化** | `plotly`, `streamlit` | 互動式圖表 + 本機 Web UI |
| **套件管理** | `uv` | 極速套件管理工具，取代 pip/conda |

---

## 3. 系統架構設計

### 3.1 四層架構圖

```
┌─────────────────────────────────────────────────────────────┐
│                      使用者介面層                             │
│  Streamlit Web UI (http://localhost:8501)                   │
│  ├── 資料管理頁面（查看/更新本機資料）                          │
│  ├── 回測頁面（設定策略參數、執行回測、查看 Tearsheet）           │
│  ├── AI 問答頁面（自然語言技術分析）                            │
│  └── 設定頁面（API Key、風控參數）                             │
└──────────────────────┬──────────────────────────────────────┘
                       │ Python 函式呼叫
┌──────────────────────▼──────────────────────────────────────┐
│                      應用邏輯層（純 Python）                   │
│  ├── DataManager       資料抓取、清洗、存儲排程                 │
│  ├── BacktestEngine    向量化 + 事件驅動兩種回測模式             │
│  ├── StrategyBase      策略基類，使用者繼承實作                  │
│  ├── IndicatorEngine   技術指標計算（pandas-ta 封裝）           │
│  ├── RiskManager       個人版簡化風控                          │
│  ├── AIAdvisor         LLM Provider Tool Use 整合             │
│  └── ReportGenerator  績效報告（Tearsheet）生成                │
└──────────────────────┬──────────────────────────────────────┘
                       │ DuckDB SQL / Parquet 讀取
┌──────────────────────▼──────────────────────────────────────┐
│                        資料層                                 │
│  data/                                                      │
│  ├── raw/tw/{symbol}/daily.parquet      台股日K（原始）        │
│  ├── raw/tw/{symbol}/minute.parquet     台股分K（原始）        │
│  ├── processed/tw/{symbol}/adj.parquet  除權息調整後           │
│  ├── backtest/                          回測結果快照            │
│  └── quant.duckdb                       元資料、績效歷史        │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP / REST API
┌──────────────────────▼──────────────────────────────────────┐
│                      外部資料源                               │
│  ├── FinMind API     台股日K/分K/財報/法人（免費層）             │
│  ├── TWSE Open Data  台灣證交所官方資料（完全免費，日K）          │
│  ├── yfinance        台股日K 備援（加 .TW 後綴）                │
│  └── LLM APIs        AI 分析功能（OpenAI/Anthropic/Gemini）    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 目錄結構

```
QuantTrader/
├── data/                     本機資料存儲（gitignore）
│   ├── raw/
│   ├── processed/
│   └── backtest/
├── src/
│   ├── data/
│   │   ├── fetcher.py        各資料源 Fetcher（含時區標準化）
│   │   ├── cleaner.py        資料品質處理（L1/L2/L3）
│   │   ├── storage.py        DuckDB / Parquet 存取
│   │   └── maintenance.py    歷史資料重建與維護指令
│   ├── backtest/
│   │   ├── base.py           Backtester 抽象介面
│   │   ├── engine_vec.py     向量化回測引擎（Pandas-based）
│   │   ├── engine_event.py   事件驅動回測引擎
│   │   ├── account.py        Account 抽象介面 + SimpleAccount 實作
│   │   ├── optimizer.py      Grid Search 參數優化
│   │   └── report.py         Tearsheet 生成
│   ├── strategy/
│   │   ├── base.py           StrategyBase 基類
│   │   └── examples/         範例策略
│   ├── indicators/
│   │   └── calculator.py     pandas-ta 封裝
│   ├── ai/
│   │   └── advisor.py        LLM Provider Tool Use 整合
│   └── ui/
│       └── app.py            Streamlit 主程式
├── tests/                    pytest 測試
├── notebooks/
│   ├── 01_data_exploration.ipynb      資料探索：讀取、繪圖、技術指標計算
│   └── 02_strategy_to_class.ipynb    從 Notebook 邏輯封裝成 StrategyBase 子類別的完整範例
├── config.yaml               策略參數與系統設定（進版本控制）
├── pyproject.toml            套件定義（uv 管理）
├── .env.example              API Keys 範本（進版本控制，僅含 key 名稱不含值）
└── .env                      API Keys 密鑰（不進版本控制）
```

---

## 4. 資料來源規劃

### 4.1 台股資料來源（免費策略）

| 資料源 | 類型 | 顆粒度 | 免費限制 | 主要用途 |
| :--- | :--- | :--- | :--- | :--- |
| **FinMind API** | REST | 日K、分K（1/5/15/30/60分） | 每日 3,000 次請求 | 主要資料源，含調整後價格 |
| **TWSE Open Data** | REST | 日K（盤後） | 無限制 | 備援；法人買賣、融資融券 |
| **yfinance** | Python 套件 | 日K、1分K（近60天） | 無官方限制（非官方） | 快速取樣；日K 備援 |

**FinMind 免費層限制說明：**
- 每日 API 請求上限 3,000 次（依資料集不同有上下浮動，以官方為準）
- 歷史分K（`TaiwanStockPriceMinute`）免費層**多數標的僅可取近 30 天**；1 年以上歷史分K 為付費贊助方案（約 NT$300/月）
- 若需要大量歷史分K（如 5 年 × 多標的）→ 升級付費方案，或退而使用日K + 自行建構 Bar
- 實際限制以 FinMind 官方文件為準（會隨時間調整），首次串接時應先以小範圍驗證可取得期間

**建議做法：** 一次性下載歷史資料存入 Parquet，日常更新只補抓最新幾天，大幅降低 API 用量。

### 4.2 資料 Fetcher 介面設計（Adapter 模式）

不同資料源的差異由 Fetcher 層吸收，上層邏輯統一使用 `DataManager`：

```python
class IDataFetcher(ABC):
    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame: ...
    def fetch_minute(self, symbol: str, start: str, end: str, freq: str = "1") -> pd.DataFrame: ...

class FinMindFetcher(IDataFetcher): ...
class TWFEFetcher(IDataFetcher): ...   # TWSE Open Data
class YFinanceFetcher(IDataFetcher): ...
```

標準化輸出欄位（所有 Fetcher 輸出相同格式）：

| 欄位 | 型別 | 說明 |
| :--- | :--- | :--- |
| `date` | `datetime64[ns]` | 時間戳（分K 含時分） |
| `open` | `float64` | 開盤價 |
| `high` | `float64` | 最高價 |
| `low` | `float64` | 最低價 |
| `close` | `float64` | 收盤價 |
| `volume` | `int64` | 成交量（股） |
| `symbol` | `str` | 股票代碼（如 `2330`） |

---

## 5. 資料品質與清洗規格

保留企業版三層概念，簡化實作複雜度。

### 5.1 L1 異常值處理

- 價格為負值或為 0 → 標記並移除
- 單筆 Bar 漲跌超過 ±10%（台股自 2015/06/01 起漲跌停幅度）→ 標記警告，人工確認
  - 例外：新上市 / 興櫃轉上市 / IPO 首五個交易日無漲跌幅限制，需在程式中以「上市日」白名單豁免
- 成交量為 0 → 保留（停牌日正常現象），但回測時跳過該交易日

### 5.2 L2 缺失值填補

- **日K 缺值：** 採用前向填充（Forward Fill），連續缺值超過 5 個交易日則標記停牌
- **分K 缺值：** 台股集中市場交易時間為 **09:00–13:30 連續交易（無午休）**，13:25–13:30 為收盤前最後 5 分鐘集合競價。非交易時段（13:30 後至次日 09:00 前）正常缺值不處理；盤中缺值（成交量 0 但有報價）前向填充
- **停牌日：** 自動識別（整日成交量 = 0 且持續），回測中自動跳過

### 5.3 L3 除權息調整

- 建立調整因子資料表（來源：FinMind 的 `StockDividend` 資料集）
- 提供**前復權**（回測用）與**原始價格**（看實際成本用）兩種模式切換
- **前復權** = 確保最新價格為基準，歷史價格向下調整，避免回測出現假突破

```python
def adjust_prices(df: pd.DataFrame, dividends: pd.DataFrame, method: str = "forward") -> pd.DataFrame:
    """
    method: "forward"（前復權，回測推薦）| "raw"（原始價格）
    """
```

### 5.4 時區規範（Timezone）

時區處理不規範是金融數據最常見的隱性 bug 來源，從專案第一天起即強制執行以下規範：

- **所有時間戳在從外部 API 讀取後，必須立即本地化至 `Asia/Taipei`（UTC+8）**
- 系統內部所有 `datetime` 物件均為 **timezone-aware**，禁止使用 naive datetime
- Parquet 存儲時保留時區資訊（pyarrow 原生支援）
- 未來若擴展至美股（ET）或加密貨幣（UTC），各資料源在進入統一資料層前即完成時區轉換

```python
import pandas as pd

TAIPEI_TZ = "Asia/Taipei"

def localize_to_taipei(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    """從 API 取得資料後立即呼叫，確保時區一致。

    注意：FinMind 等台股資料源回傳的 datetime 多為 naive 但語意上已是台北時間，
    必須使用 tz_localize（標記時區），而非 tz_convert（會誤認為 UTC 再轉換 +8 小時）。
    """
    if df[col].dt.tz is None:
        df[col] = df[col].dt.tz_localize(TAIPEI_TZ)
    else:
        df[col] = df[col].dt.tz_convert(TAIPEI_TZ)
    return df
```

### 5.5 數據維護模組（maintenance.py）

除了每日增量更新，當資料源邏輯變更或股票發生特殊企業行動（減資、股票分割）時，需要對特定標的進行**完整歷史資料重建**。

`src/data/maintenance.py` 提供以下指令：

| 指令 | 說明 |
| :--- | :--- |
| `rebuild_symbol(symbol)` | 重新下載並重算指定標的的完整歷史資料與調整因子 |
| `rebuild_adj_factors(symbol)` | 僅重算除權息調整因子，不重新下載原始資料 |
| `validate_data(symbol)` | 對指定標的執行完整的 L1/L2/L3 品質驗證，輸出報告 |
| `list_stale_symbols(days=7)` | 列出超過指定天數未更新的標的 |

---

## 6. 回測引擎規格

### 6.1 雙引擎架構

| 引擎類型 | 實作方式 | 適用場景 | 回測速度 |
| :--- | :--- | :--- | :--- |
| **向量化引擎** | Pandas 矩陣運算（自建，教育目的） | 策略早期快速海選、Grid Search 參數優化 | 極快（秒級） |
| **事件驅動引擎** | Python 迴圈逐 Bar 處理 | 上線模擬前最終驗證；含部位管理邏輯 | 較慢（分鐘級） |

**重要設計原則：策略類別同時支援兩種引擎，無需修改策略程式碼即可切換。**

#### Backtester 抽象介面

兩種引擎共同實作 `BacktesterBase` 介面，確保上層呼叫方式一致，並為未來整合 `vectorbt` 預留擴展點：

```python
class BacktesterBase(ABC):
    @abstractmethod
    def run(self, strategy: StrategyBase, data: pd.DataFrame) -> BacktestResult:
        """執行回測，回傳結果物件"""
        ...

# V1.0 實作
class VectorizedBacktester(BacktesterBase): ...   # Pandas-based，快速
class EventDrivenBacktester(BacktesterBase): ...   # 逐 Bar，貼近真實

# V2.0 預留（不在 V1 實作）
# class VectorbtBacktester(BacktesterBase): ...
```

### 6.2 事件驅動引擎設計

採用分鐘K 作為最小事件單位（`BarEvent`），而非 Tick。

#### 事件類型

```python
@dataclass
class BarEvent:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    freq: str  # "1min", "5min", "1day"

@dataclass
class OrderEvent:
    symbol: str
    order_type: str     # "MARKET" | "LIMIT"
    side: str           # "BUY" | "SELL"
    quantity: int
    price: float | None  # None 代表市價單

@dataclass
class FillEvent:
    symbol: str
    side: str
    quantity: int
    fill_price: float
    commission: float
    timestamp: datetime
```

#### 事件迴圈

```python
class EventDrivenEngine:
    def run(self, strategy: StrategyBase, data: pd.DataFrame) -> BacktestResult:
        for bar in self._iter_bars(data):
            bar_event = self._to_bar_event(bar)
            order_events = strategy.on_bar(bar_event, self.account)
            for order in order_events:
                fill = self._simulate_fill(order, bar_event)
                self.account.apply_fill(fill)
                strategy.on_fill(fill, self.account)
        return self._generate_result()
```

#### Account 抽象介面與 SimpleAccount 實作

`EventDrivenBacktester` 依賴抽象的 `Account` 介面，與資金管理的具體邏輯解耦：

```python
class Account(ABC):
    @abstractmethod
    def get_cash(self) -> float: ...
    @abstractmethod
    def get_position(self, symbol: str) -> int: ...
    @abstractmethod
    def apply_fill(self, fill: FillEvent) -> None: ...
    @abstractmethod
    def get_total_value(self, current_prices: dict[str, float]) -> float: ...

# V1.0：單一策略、單一帳戶
class SimpleAccount(Account):
    def __init__(self, initial_capital: float):
        self.cash = initial_capital
        self.positions: dict[str, int] = {}
        self.cost_basis: dict[str, float] = {}
    # ... 實作略

# V2.0 預留（不在 V1 實作）
# class PortfolioAccount(Account):
#     """支援多策略資金分配，含各策略子帳戶"""
```

#### 策略基類介面

```python
class StrategyBase(ABC):
    @abstractmethod
    def on_bar(self, bar: BarEvent, account: Account) -> list[OrderEvent]:
        """每根 K 線呼叫一次，回傳要執行的訂單列表"""
        ...

    def on_fill(self, fill: FillEvent, account: Account) -> None:
        """訂單成交後呼叫（可選覆寫）"""
        pass
```

### 6.3 市場摩擦模型（台股）

| 費用類型 | 費率 | 說明 |
| :--- | :--- | :--- |
| **手續費（買賣皆收）** | 0.1425% | 實際依券商折扣調整（常見 6 折 = 0.0855%） |
| **交易稅（賣出收）** | 0.3% | 台股固定稅率（ETF 為 0.1%） |
| **撮合假設** | 下根 K 線開盤價成交 | 訊號於 Bar t 收盤後產生，於 Bar t+1 開盤撮合，避免未來函數 |
| **滑價模型** | 固定 1 Tick | 在 Bar t+1 開盤價基礎上，買單 +1 Tick、賣單 -1 Tick |
| **Tick Size** | 依價位區間 | 台股 Tick 規則：< 10 元為 0.01；10–50 元為 0.05；50–100 元為 0.1；100–500 元為 0.5；500–1000 元為 1；≥ 1000 元為 5 |

### 6.4 績效評估報告（Tearsheet）

自動生成，包含以下指標：

**核心報酬指標：**
- 總報酬率、年化報酬率
- 最大回撤（Max Drawdown）及發生時間
- Sharpe Ratio（年化）、Sortino Ratio、Calmar Ratio

**交易統計：**
- 總交易次數、勝率、盈虧比（Profit Factor）
- 平均持倉時間、最大單筆虧損

**視覺化圖表：**
- 累積報酬曲線（含買賣進出場標記）
- 月度報酬熱力圖
- 回撤曲線
- 部位市值走勢

**進階驗證（選配）：**
- Walk-forward 測試（分訓練期/驗證期，防止過擬合）

### 6.5 參數優化（Grid Search）

當策略有可調整參數時（如均線週期、RSI 門檻值），使用內建的 Grid Search 自動化尋優，無需外部套件。

```python
class GridSearch:
    def run(
        self,
        strategy_class: type[StrategyBase],
        param_grid: dict[str, list],
        data: pd.DataFrame,
        metric: str = "sharpe_ratio"
    ) -> pd.DataFrame:
        """
        窮舉所有參數組合，回傳按指定指標排序的結果表。

        範例：
            gs = GridSearch()
            results = gs.run(
                strategy_class=MACrossStrategy,
                param_grid={"ma_short": [5, 10, 20], "ma_long": [30, 60, 90]},
                data=daily_df,
                metric="sharpe_ratio"
            )
        """
```

| 功能 | 說明 |
| :--- | :--- |
| **窮舉搜尋** | 測試所有參數組合（如 3×3 = 9 組），回傳完整結果表 |
| **排序指標** | 支援 `sharpe_ratio`、`max_drawdown`、`total_return` 等 |
| **過擬合警告** | 若最優參數組合在樣本外（Walk-forward）表現大幅下降，自動標記警告 |
| **V2+ 擴展** | 若參數維度增加至 5+ 維，可考慮引入 `optuna` 的貝氏優化替代窮舉 |

---

## 7. AI 技術分析模組

### 7.1 功能定位

使用者以**自然語言**提問，系統自動查詢數據、計算指標，由使用者選定的 LLM provider 生成分析報告。

AI 技術分析為**可選功能**，系統必須允許使用者完全關閉。關閉時，核心資料管道、回測、報表與 Streamlit 非 AI 頁面仍需正常運作，且不得要求設定任何 LLM API key。

**支援問題範例：**
- 「2330 現在的 RSI 是多少？是否超買？」
- 「台積電的 MACD 最近有沒有黃金交叉？」
- 「0050 的 60 日均線支撐強嗎？」
- 「幫我看一下 2412 最近一個月的技術面」

### 7.2 LLM Provider Tool Use 設計

採用 Function Calling / Tool Use 模式，讓 LLM 決定要查哪些資料，再整合結果生成自然語言回應。系統需支援 OpenAI / ChatGPT、Anthropic / Claude、Google / Gemini 三類 provider 的設定入口。

#### 功能開關

`config.yaml` 應提供 `ai.enabled`：

- `ai.enabled: false`：不初始化任何 LLM provider、不檢查 AI API key、不顯示可互動的 AI 問答流程。UI 可隱藏 AI 問答頁，或顯示「AI 功能已關閉」狀態頁。
- `ai.enabled: true`：依 `ai.provider` / `ai.model` 建立 provider adapter，並檢查選定 provider 對應的 API key。

預設建議為 `false`，讓專案可在沒有 AI API key、沒有網路 LLM 依賴的情況下完成資料與回測工作。

#### 定義給 LLM 的工具（Tools）

```python
tools = [
    {
        "name": "get_price_data",
        "description": "取得指定股票的歷史 K 線資料（日K 或分K）",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "台股代碼，如 '2330'"},
                "period": {"type": "string", "description": "時間範圍，如 '3mo'、'6mo'、'1y'"},
                "freq":   {"type": "string", "enum": ["daily", "60min", "30min", "5min"]}
            },
            "required": ["symbol", "period"]
        }
    },
    {
        "name": "calculate_indicators",
        "description": "計算技術指標",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol":     {"type": "string"},
                "indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "指標列表，如 ['RSI_14', 'MACD', 'BBANDS_20', 'KD', 'MA_5', 'MA_20', 'MA_60']"
                },
                "period":     {"type": "string"}
            },
            "required": ["symbol", "indicators"]
        }
    },
    {
        "name": "get_support_resistance",
        "description": "計算近期支撐與壓力位（基於近期高低點）",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol":    {"type": "string"},
                "lookback":  {"type": "integer", "description": "回溯交易日數，預設 60"}
            },
            "required": ["symbol"]
        }
    }
]
```

#### 呼叫流程

```
1. 使用者輸入問題
        ↓
2. LLM Provider API（帶入 tools 定義）
   → LLM 決定呼叫哪些工具、哪些參數
        ↓
3. 本機執行工具（查詢 DuckDB / 計算 pandas-ta 指標）
        ↓
4. 將工具回傳結果送回 LLM Provider API
        ↓
5. LLM 生成自然語言分析（附免責聲明）
        ↓
6. 顯示於 Streamlit UI
```

### 7.3 支援的技術指標清單

| 類別 | 指標 |
| :--- | :--- |
| **趨勢** | MA（5/10/20/60/120/240 日）、EMA、MACD（含柱狀圖與訊號線） |
| **動能** | RSI（14 日）、KD 隨機指標（9日）、Williams %R |
| **波動度** | Bollinger Bands（20日，±2σ）、ATR（14日） |
| **量能** | 成交量 MA（5/20 日）、OBV（能量潮）、量比 |
| **支撐壓力** | 近期高低點、均線糾結偵測 |

#### 指標別名映射表（IndicatorEngine 內部處理）

`pandas-ta` 的指標命名與台股慣用名不一致，`IndicatorEngine` 需維護對照表，讓 LLM Tool Use 可以使用台股慣用名：

| Tool Use 名稱（台股慣用） | pandas-ta 函式 | 輸出欄位 |
| :--- | :--- | :--- |
| `KD` | `ta.stoch(...)` | `STOCHk_9_3_3`（K 值）, `STOCHd_9_3_3`(D 值) |
| `MACD` | `ta.macd(...)` | `MACD_12_26_9`, `MACDh_12_26_9`, `MACDs_12_26_9` |
| `RSI_14` | `ta.rsi(length=14)` | `RSI_14` |
| `BBANDS_20` | `ta.bbands(length=20)` | `BBL_20_2.0`, `BBM_20_2.0`, `BBU_20_2.0` |
| `MA_{n}` | `ta.sma(length=n)` | `SMA_{n}` |

`IndicatorEngine.calculate(name)` 應先查映射表再呼叫對應 `pandas-ta` 函式，並將輸出欄位重新命名為 Tool Use 名稱以便 AI 引用。

### 7.4 免責聲明規範（重要）

AI 分析功能必須在設計層面落實免責聲明，而非只是 UI 角落的小字。

**系統層級：**
- 每次啟動工具時顯示免責聲明確認頁，使用者需點擊「我了解」後才能使用 AI 功能
- 每次 AI 回應的底部**自動附加**以下文字（不可省略）：

```
⚠️ 免責聲明：以上分析僅為技術指標數值的客觀陳述，不構成任何投資建議。
技術分析基於歷史數據，不保證未來走勢。AI 無法預測市場，所有投資決策
請自行判斷，並以券商官方行情為準。投資一定有風險，過去績效不代表未來報酬。
```

**LLM System Prompt 層級：**

```
你是一個台股技術分析助理。你的工作是：
1. 根據使用者提供的工具數據，客觀描述技術指標的現況
2. 解釋技術術語的含義
3. 說明常見的技術型態與歷史統計意義

你不應該：
- 明確建議使用者買進或賣出
- 預測股價未來走勢
- 給予資金配置建議

每次回應的最後，必須加上免責聲明。
```

---

## 8. 個人版風控規格

不需要企業版的三層完整防禦，但保留幾個關鍵的個人保護機制：

### 8.1 回測/模擬層風控

| 規則 | 說明 |
| :--- | :--- |
| **單日最大虧損上限** | 可在設定頁面自定義（如總資金 3%），達到後當日停止模擬下單 |
| **單筆最大倉位** | 限制單一標的佔總資金比例上限（預設 20%） |
| **Fat-finger 防護** | 若模擬訂單金額超過設定閾值（如 $100,000），系統跳出警告要求確認 |
| **最大回撤警報** | 策略回撤超過 10% 時，於 Streamlit UI 顯示醒目警告 |

---

## 9. 本機部署規格（Windows 11）

### 9.1 環境需求

| 項目 | 規格 |
| :--- | :--- |
| **作業系統** | Windows 11（原生，不需要 WSL） |
| **Python 版本** | Python 3.12+ |
| **套件管理** | `uv`（極速，取代 pip/conda） |
| **IDE** | VS Code + Python 擴充套件（推薦） |
| **不需要** | Docker、PostgreSQL、Redis、Rust Toolchain |

### 9.2 初始化步驟

```bash
# 安裝 uv（套件管理工具）
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 安裝套件（uv sync 會自動建立 .venv，無須先 uv venv）
uv sync

# 設定 API Keys（複製範本後填入）
copy .env.example .env
# 編輯 .env 填入 FINMIND_TOKEN 與選定 AI provider 的 API key

# 啟動 Streamlit UI
uv run streamlit run src/ui/app.py
```

### 9.3 配置管理（兩層分離）

**`.env`（不進版本控制）— 僅存放密鑰**

```
FINMIND_TOKEN=...                  # FinMind API Token（免費申請）
ANTHROPIC_API_KEY=sk-ant-...       # Claude API Key（選 Claude 時需要）
OPENAI_API_KEY=sk-...              # OpenAI / ChatGPT API Key（選 ChatGPT 時需要）
GEMINI_API_KEY=...                 # Gemini API Key（選 Gemini 時需要）
```

**安全規範：** `.env` 必須加入 `.gitignore`，絕對不可提交至版本控制。

---

**`config.yaml`（進版本控制）— 策略參數與系統設定**

```yaml
# 系統設定
system:
  data_dir: ./data
  log_level: INFO
  timezone: Asia/Taipei

# 回測預設參數
backtest:
  initial_capital: 1_000_000      # 初始資金（新台幣）
  commission_rate: 0.001425       # 手續費率（可依券商調整）
  commission_discount: 0.6        # 手續費折扣（6折）
  tax_rate: 0.003                 # 交易稅（一般股票）
  etf_tax_rate: 0.001             # 交易稅（ETF）
  slippage_ticks: 1               # 滑價 Ticks

# 風控預設值
risk:
  max_daily_loss_pct: 0.03        # 單日最大虧損 3%
  max_position_pct: 0.20          # 單標的最大倉位 20%
  max_drawdown_warning_pct: 0.10  # 回撤警告門檻 10%

# 資料來源優先順序
data:
  primary_source: finmind
  fallback_source: yfinance

# AI 技術分析（可完全關閉）
ai:
  enabled: false                 # false 時不要求任何 AI API key
  provider: anthropic            # openai | anthropic | gemini
  model: claude-...
  temperature: 0.2
  max_tokens: 4096
  timeout_seconds: 30
```

`config.yaml` 隨程式碼一起進入 Git，讓每次回測的參數設定都有跡可查，確保結果可重現。Streamlit UI 設定頁可覆蓋 `config.yaml` 的值進行臨時實驗，但不會寫回檔案（除非明確點擊「儲存為預設」）。

### 9.4 不需要的企業版基礎設施

以下元件在個人版**完全不需要安裝**：

- ❌ Docker Desktop
- ❌ Kubernetes
- ❌ PostgreSQL / TimescaleDB
- ❌ Redis
- ❌ Prometheus / Grafana
- ❌ Rust Toolchain

---

## 10. 測試策略

### 10.1 測試層級

| 測試類型 | 框架 | 覆蓋率目標 | 重點測試對象 |
| :--- | :--- | :--- | :--- |
| **單元測試** | `pytest` | > 70% | 指標計算、除權息調整、摩擦成本計算、風控規則 |
| **回測驗證測試** | `pytest` + 固定種子資料 | 必過 | 雙均線策略在已知數據集的結果是否可重現 |
| **資料品質測試** | `pytest` | > 60% | 異常值偵測、缺值填補邏輯 |

### 10.2 回測到模擬升階門檻

在把一個策略提升到「持續模擬監控」前，需通過以下自動化檢查：

| 指標 | 門檻值 |
| :--- | :--- |
| **樣本外測試（Walk-forward OOS）** | Sharpe Ratio > 1.0 |
| **最大回撤** | < 15%（寬鬆版，適合個人） |
| **交易筆數** | > 30 筆（統計顯著性基本要求） |
| **過擬合比率** | OOS Sharpe / IS Sharpe > 0.5 |

---

## 11. 四階段漸進式開發計畫

**總工期預估：約 6-7 週（業餘，每週 10-15 小時；有 AI 輔助）**
**子階段總數：17 個，每個子階段有獨立的進入條件與測試驗收指標**

> 每個子階段的退出條件（驗收指標）需全數通過，才能進入下一子階段。

---

### Phase 1：台股資料基礎建設（7 天）

#### 1-A　資料源連線驗證（Day 1）

**建置內容：** FinMind API wrapper、yfinance wrapper，連線與回傳格式測試

**驗收指標：**
- `test_finmind_connection()` → HTTP 200，回傳 DataFrame 非空
- `test_yfinance_2330()` → 取得 2330.TW 日K，欄位齊全（open/high/low/close/volume）
- 兩者輸出統一轉換為標準欄位格式，dtype 正確

#### 1-B　Parquet 存儲結構（Day 2）

**建置內容：** 存儲路徑規則（`data/raw/tw/{symbol}/daily.parquet`）、讀寫 Parquet、DuckDB 元資料表

**驗收指標：**
- 寫入 2330 日K → 讀出後與原始 DataFrame 完全相同（`pd.testing.assert_frame_equal`）
- DuckDB 元資料正確記錄「2330 日K 已下載至今日」
- 重複下載同一時段，不產生重複資料列

#### 1-C　資料品質檢核（Day 3）

**建置內容：** L1 異常值偵測（負價格、漲跌 > 15%、成交量 = 0）、L2 缺值前向填充

**驗收指標：**
- 注入已知壞資料（負價格、成交量 = 0、單日漲跌 > 15%）→ 確認全部被標記
- 注入連續 3 日缺值 → 前向填充正確，第 4 日值等於缺值前最後一筆
- 品質報告輸出每個標的的異常筆數統計

#### 1-D　除權息前復權調整（Day 4-7）

**建置內容：** 調整因子計算（來源 FinMind `StockDividend`）、前復權邏輯、原始/調整後資料分開存儲

**驗收指標：**
- 選已知除息日（如 2330 某次除息），調整後除息日前後收盤價連續無跳空
- 前復權的「最新除權息基準日之後」的價格不調整（基準日後若無新除權息，則最新收盤價 = 原始收盤價）
- 原始資料與調整後資料存於不同路徑，互不污染

---

### Phase 2：向量化回測引擎（5 天）

#### 2-A　訊號生成框架（Day 1-2）

**建置內容：** 策略訊號計算（雙均線為例），輸出 signal series（+1 買 / -1 賣 / 0 持平）

**驗收指標：**
- 手工計算已知資料集的 MA20/MA60 交叉日期 → signal 在正確日期翻轉
- signal 不在未來日期出現（Look-ahead Bias 檢查）
- signal 向量與原始 DataFrame 索引完全對齊

#### 2-B　市場摩擦成本計算（Day 2-3）

**建置內容：** 手續費（0.1425%）、交易稅（賣出 0.3%）、滑價（1 Tick）

**驗收指標：**
- 給定固定成交金額，計算出的手續費 + 稅與手算結果誤差 < 0.01 元
- 買進不收交易稅、賣出才收（單元測試分別驗證）
- ETF 交易稅正確套用 0.1%（而非 0.3%）

#### 2-C　績效指標計算（Day 3-4）

**建置內容：** Sharpe Ratio、MDD、Sortino、勝率、盈虧比

**驗收指標：**
- 全贏策略的 MDD = 0、勝率 = 100% → 驗證邊界條件
- 已知報酬序列（手算）與程式計算的 Sharpe Ratio 誤差 < 0.001
- MDD 的開始與結束日期標記正確

#### 2-D　Tearsheet 報告生成（Day 4-5）

**建置內容：** Plotly 累積報酬曲線、月度熱力圖、回撤曲線、績效數字摘要表

**驗收指標：**
- 給定已知回測結果，Tearsheet 能正常渲染（無 exception）
- 月度熱力圖每格數值與手算一致
- 報告能存成 HTML 檔並用瀏覽器正常開啟

---

### Phase 3：分鐘K 事件驅動回測引擎（12 天）

#### 3-A　事件資料結構定義（Day 1）

**建置內容：** `BarEvent`、`OrderEvent`、`FillEvent` dataclass，型別驗證

**驗收指標：**
- 錯誤型別輸入（price 傳入字串）→ 觸發 TypeError
- 各欄位預設值正確
- 可序列化為 dict（供 logging 使用）

#### 3-B　Portfolio 狀態管理（Day 2-4）

**建置內容：** 現金帳戶、持倉部位、未實現損益計算

**驗收指標：**
- 初始現金 100 萬，買入 1000 股 × 100 元 → 現金剩 100 萬 - 成交金額 - 手續費
- 賣出後持倉歸零、現金正確增加（含稅後）
- 未實現損益 = 持倉股數 × (當前價 - 成本價)，與手算一致

#### 3-C　事件迴圈核心（Day 4-7）

**建置內容：** 逐 Bar 迭代、事件觸發順序（Bar → 策略判斷 → Order → Fill）

**驗收指標：**
- 每根 K 線觸發恰好一次 `on_bar`（計數器驗證）
- `on_bar` 產生的 Order 在下根 K 線開盤才成交（防未來函數）
- 市價單以下根 K 線開盤價成交（驗證 FillEvent 的 fill_price）

#### 3-D　StrategyBase 與範例策略（Day 7-9）

**建置內容：** 抽象基類、雙均線分鐘版範例策略

**驗收指標：**
- 未實作 `on_bar` 的子類別，實例化時拋出 TypeError
- 範例策略在固定測試資料集上，進出場點與預期完全吻合
- 策略不需修改，可直接傳入向量化引擎執行

#### 3-E　雙引擎一致性驗證（Day 9-12）

**建置內容：** 同一策略跑向量化 vs 事件驅動，比對總報酬差異

**驗收指標：**
- 相同策略、相同資料 → 兩引擎總報酬偏差 < 1%
- 偏差來源可解釋（撮合假設不同）並記錄在測試說明中
- 偏差 > 1% 時測試自動失敗並輸出差異明細

---

### Phase 4：AI 技術分析問答 + Streamlit UI（5 天）

#### 4-A　LLM Provider Tool Use 基礎（Day 1-2）

**建置內容：** 三個工具定義（`get_price_data` / `calculate_indicators` / `get_support_resistance`）、工具呼叫解析

**驗收指標：**
- 輸入「2330 的 RSI」→ 選定 provider 呼叫正確工具（工具名稱記錄驗證）
- 工具回傳 mock 資料 → 選定 provider 能整合並生成回應
- 每次回應底部包含免責聲明文字（字串包含檢查）
- `ai.enabled: false` 時，`AIAdvisor` 不初始化 provider、不要求 API key，並回傳清楚的停用狀態或由 UI 阻止進入問答流程

#### 4-B　技術指標工具實作（Day 2-3）

**建置內容：** pandas-ta 封裝，對應 LLM Tool Use 定義的介面

**驗收指標：**
- `calculate_indicators("2330", ["RSI_14"])` → 回傳值介於 0-100
- `calculate_indicators("2330", ["MACD"])` → 回傳 macd、signal、histogram 三欄
- 傳入不存在的指標名稱 → 回傳清晰 error message，不 crash

#### 4-C　Streamlit UI 框架（Day 3-4）

**建置內容：** 多頁面架構（資料管理 / 回測 / AI 問答 / 設定）

**驗收指標：**
- `streamlit run src/ui/app.py` 無錯誤啟動，四個頁面皆可切換
- 設定頁能儲存 API Key 至 `.env`（輸入框遮罩，不明文顯示）
- 設定頁能切換 `ai.enabled`；關閉時 AI 問答頁不可發出 LLM API 呼叫，並清楚顯示停用狀態
- 回測頁輸入股票代碼 + 日期範圍 → 顯示 Tearsheet 圖表
- 回測頁績效摘要第一個欄位必須顯示「交易次數」，位置在「總報酬」左邊；若交易次數為 0，使用者能立即判斷績效全為 0 是因為策略未成交

#### 4-D　端到端整合測試（Day 4-5）

**建置內容：** 從使用者輸入到最終回應的完整流程驗證

**驗收指標：**
- 輸入「2330 的 MACD 是否出現黃金交叉？」→ 回應含指標數值、解釋、免責聲明
- 輸入不存在的股票代碼（如「9999」）→ 友善錯誤訊息，不 crash
- 完整問答流程 < 30 秒（使用者體驗基準；含 LLM Tool Use 多輪往返、工具執行、最終 LLM 回應；不含首次冷啟動）

---

### Phase 5：回測體驗與 UI 補充（彈性）

#### 5-A　回測頁股價走勢與 EPS 資訊（1-2 天）

**建置內容：** 在回測結果頁補充個股價格走勢、均線、買賣點與基本面 EPS 資訊，協助使用者同時判讀策略績效、股價環境與長期獲利能力。

**股價走勢圖規格：**
- 顯示該股票在本次回測日期區間內的股價走勢。
- 圖表至少包含收盤價、週線 MA5、月線 MA20、季線 MA60。
- 週線、月線、季線以日收盤價 rolling mean 計算：週線 = 5 日均線、月線 = 20 日均線、季線 = 60 日均線。
- 圖表需標記本次回測產生的買進點與賣出點，建議以不同顏色或不同 marker 形狀區分。
- 若前期資料不足以計算 MA5 / MA20 / MA60，該日期的均線值允許為空值，不得造成頁面錯誤。

**互動提示規格：**
- 滑鼠移動到走勢圖上時，顯示對應交易日的日期、收盤價、MA5、MA20、MA60。
- tooltip 範例欄位：
  - 日期
  - 收盤價
  - 週線 MA5
  - 月線 MA20
  - 季線 MA60
- 若該日期無某條均線資料，顯示空值或「尚無資料」。
- 若滑鼠位置落在非交易日，tooltip 對齊最近的有效交易日資料。

**EPS 紀錄規格：**
- 在同一個回測頁面新增「近 15 年 EPS 紀錄」區塊。
- 顯示該股票近 15 年可取得的 EPS 資料。
- EPS 表格需同時顯示季度 EPS 與年度 EPS 合計。
- 建議欄位：年度、Q1 EPS、Q2 EPS、Q3 EPS、Q4 EPS、年度 EPS。
- 最新年度若尚未完整公告，只顯示目前已取得的季度資料，年度 EPS 以已取得季度加總，不補值、不推估。
- 若某年度或某季度缺資料，顯示空值或「尚無資料」，不得造成頁面錯誤。

**驗收指標：**
- 回測頁輸入股票代碼與日期範圍後，除原有 Tearsheet 外，能顯示該股票回測期間的收盤價、MA5、MA20、MA60 走勢圖。
- 圖表上的買進點與賣出點能對應回測交易紀錄或訊號紀錄。
- 滑鼠移動到圖表上時，tooltip 能正確顯示該交易日的日期、收盤價、MA5、MA20、MA60。
- MA5 / MA20 / MA60 計算結果需與 pandas rolling mean 結果一致。
- EPS 區塊能顯示近 15 年季度 EPS 與年度 EPS 合計。
- 最新年度資料未滿四季時，只顯示已取得季度，年度 EPS 不做推估。
- 股價、均線、買賣點或 EPS 任一資料缺漏時，頁面需友善顯示空值或提示，不 crash。

#### 5-B　定期定額策略與多策略設定架構（2-3 天）

**建置內容：** 新增定期定額策略，並調整設定頁與設定檔結構，使系統可支援多種策略類型與各自不同的參數欄位。

**定期定額策略規格：**
- 新增策略類型：`dollar_cost_averaging`。
- 使用者可設定每月投入日、每月投入金額、最小買入單位、非交易日處理規則、買入價格欄位。
- 股票代碼、回測起始日、回測結束日屬於單次回測執行上下文，由回測頁輸入欄位決定，不保存為定期定額策略參數。
- 每月投入日以日期數字表示，例如每月 5 號、10 號、25 號。
- 若指定投入日不是交易日，改用該日之後的下一個有效交易日買入。
- 若指定投入日之後至月底都沒有可用交易日，該月略過。
- 買入價格初版使用買入日收盤價。
- 最小買入單位為 1 股，不使用小數股。
- 買入股數 = floor(可投入金額 / 買入日含成本單股價格)，不足 1 股時該次投入略過。
- 每次未用完的零頭現金保留在帳戶現金中，不強制併入下一期投入金額；下一期仍以設定的每月投入金額新增投入。
- 手續費與交易稅沿用既有回測設定；定期定額買進時只計算買進手續費，不計交易稅。

**回測上下文與策略參數分工：**
- `symbol`、`start_date`、`end_date` 以回測頁目前輸入值為準。
- 策略設定只保存可重用的策略參數，不得覆蓋本次回測頁輸入的 `symbol` / `start_date` / `end_date`。
- 同一組策略設定應可套用到不同股票與不同回測期間。
- 若未來策略 preset 支援保存預設股票或日期區間，只能作為 UI 預填值，不可覆蓋使用者本次回測輸入。

**定期定額回測輸出：**
- 回測績效摘要需顯示累積投入金額、目前市值、帳戶現金、未實現損益、總報酬率、累積買入股數、平均成本、投入次數。
- 交易紀錄表需顯示每次投入明細，建議欄位：日期、投入金額、買入價格、買入股數、手續費、實際花費、剩餘現金、累積股數、累積投入、平均成本。
- 若某月因資料不足、非交易日無可順延日、或投入金額不足 1 股而略過，需在交易紀錄或提示區保留可追蹤訊息。

**多策略設定架構：**
- 設定頁不得只綁定單一策略參數，需改成「策略類型 → 對應設定表單」的架構。
- 使用者可在設定頁選擇策略類型，例如均線交叉策略、定期定額策略。
- 不同策略類型顯示不同參數欄位。
- 設定檔需保存策略的 `name`、`type` 與 `params`，讓後續能新增更多策略而不破壞既有設定。
- 回測頁需能選擇一組策略設定並套用到回測流程。

**舊設定遷移規格：**
- 若 `config.yaml` 沒有 `strategies` 區塊，系統讀取設定時不得報錯。
- 系統需在記憶體中建立一組預設 `moving_average_cross` 策略，以維持既有 MA Cross 回測行為。
- 預設策略建議為 `MA20_MA60`，參數為 `short_window: 20`、`long_window: 60`。
- 此遷移採 lazy migration：啟動或讀取設定時不自動改寫 `config.yaml`，避免使用者未儲存設定就產生檔案 diff。
- 只有當使用者在設定頁儲存策略設定時，才將 `strategies[]` 寫回設定檔。
- 若未來偵測到舊版 `strategy:` 單策略區塊，需轉換為 `strategies[]` 中的一筆策略設定，並保留原本 `type` 與 `params`。

**建議設定格式：**
```yaml
strategies:
  - name: MA20_MA60
    type: moving_average_cross
    params:
      short_window: 20
      long_window: 60

  - name: Monthly_DCA
    type: dollar_cost_averaging
    params:
      monthly_day: 5
      monthly_amount: 10000
      min_buy_unit: 1
      non_trading_day_policy: next_trading_day
      buy_price_field: close
```

**驗收指標：**
- 設定頁可切換不同策略類型，且顯示對應參數欄位。
- 設定檔能保存至少一組均線交叉策略與一組定期定額策略。
- `config.yaml` 缺少 `strategies` 區塊時，系統仍能載入預設 MA Cross 策略並執行既有回測流程。
- 讀取設定時不得因 lazy migration 自動改寫 `config.yaml`；只有設定頁儲存時才寫回 `strategies[]`。
- 回測頁可選擇定期定額策略並執行回測。
- 回測頁輸入的 `symbol`、`start_date`、`end_date` 必須優先於任何策略 preset 預設值。
- 指定投入日為交易日時，系統於該日以收盤價買入。
- 指定投入日為非交易日時，系統順延至下一個有效交易日買入。
- 買入股數必須是整數股，且不得小於 1 股。
- 投入金額不足以買入 1 股時，該次投入略過並留下提示。
- 回測結果需正確顯示累積投入、累積股數、平均成本、目前市值、現金與總報酬率。
- 既有均線交叉策略設定與回測流程不得因新增多策略設定架構而失效。

---

### Phase 6：UI/UX 強化（彈性）

#### 6-A 主題切換與 UI 美化（1-2 天）

**建置內容：** 在設定頁新增「外觀主題」區塊，使用者可在執行期間切換 UI 主題（淺色 / 深色 / 金融綠），透過 CSS 注入即時生效，不需重啟 Streamlit。同時引入元件庫提升 KPI 卡片與側邊欄選單的視覺品質。

**主題架構規格：**
- 主題以 CSS 變數與 selector 定義，在 `src/ui/app.py` 載入後第一個 Streamlit 元件之前透過 `st.markdown(..., unsafe_allow_html=True)` 注入。
- 不依賴 `.streamlit/config.toml` 的 `[theme]` 區塊，因為 `config.toml` 需重啟才能生效。`config.toml` 只保留 `layout`、`runOnSave` 等基礎設定。
- 預設提供 6 套主題（V1.6 修訂後）：
  - `arctic_light`（預設淺色，北極白藍）
  - `obsidian_dark`（深色，Streamlit 預設黑）
  - `finance_green`（深底 + 金融綠強調色）
  - `midnight_blue`（深色海軍藍）
  - `cyberpunk`（黑底霓虹紅）
  - `warm_sepia`（淺色暖棕）
- 主題定義集中在 `src/ui/themes.py`，每套主題以 dict 形式提供調色盤（`background` / `surface` / `primary` / `text` / `muted`）與 `plotly_template` 欄位。

**設定保存規格：**
- `config.yaml` 新增 `ui` 區塊：
  ```yaml
  ui:
    theme: arctic_light     # arctic_light | obsidian_dark | finance_green | midnight_blue | cyberpunk | warm_sepia
    use_extras: true        # 啟用 streamlit-extras 元件
    use_option_menu: true   # 啟用 streamlit-option-menu 側邊欄
  ```
- 缺少 `ui` 區塊或缺少其中欄位時，系統採預設 `theme=arctic_light`、`use_extras=true`、`use_option_menu=true`，不報錯。
- 此設定採 lazy migration：啟動或讀取設定時不自動改寫 `config.yaml`；只在使用者於設定頁儲存時才寫回 `ui:` 區塊。
- 主題值未在合法清單內時，回退到 `arctic_light` 並在 UI 顯示警告。

**設定頁規格：**
- 在 `src/ui/pages/settings.py` 新增「外觀」區塊，提供：
  - 主題下拉選單（`arctic_light` / `obsidian_dark` / `finance_green` / `midnight_blue` / `cyberpunk` / `warm_sepia`）
  - 「使用 streamlit-extras 元件」開關
  - 「使用 option_menu 側邊欄」開關
- 「儲存」後同步寫入 `config.yaml` 的 `ui` 區塊並呼叫 `st.rerun()`，下一輪頁面渲染套用新主題，無需重啟 Streamlit。

**元件庫整合規格：**
- 新增可選依賴（pyproject.toml 不強制安裝；以 try/except import 偵測）：
  - `streamlit-extras`（提供 metric card、grid、colored_header）
  - `streamlit-option-menu`（提供帶圖示的側邊欄選單）
- 任一套件未安裝時，系統 fallback 到原生元件（`st.metric`、`st.radio`），不得 crash，並在啟動或設定頁顯示「未安裝 streamlit-extras / streamlit-option-menu，已退回原生元件」提示。
- 回測頁績效摘要（總報酬、年化報酬、最大回撤、Sharpe、交易次數等）在 `use_extras=true` 且套件已安裝時，改用 metric card 卡片化顯示。
- 側邊欄頁面切換在 `use_option_menu=true` 且套件已安裝時，改用 `option_menu` 取代 `st.radio`，否則維持 `st.radio`。

**主題與 Plotly 互動規格：**
- 主題切換不得影響 Plotly 圖表內部資料；圖表需依當前主題傳入對應 `template`：
  - `arctic_light` / `warm_sepia` → `plotly_white`
  - `obsidian_dark` / `finance_green` / `midnight_blue` / `cyberpunk` → `plotly_dark`
- 圖表底色（`paper_bgcolor` / `plot_bgcolor`）需與主題 `surface` 色一致，避免「白底圖表貼在深色頁面」破版。

**驗收指標：**
- 設定頁可選擇主題與兩個元件開關並儲存；切換後立即生效，不需重啟 Streamlit。
- 主題設定寫入 `config.yaml` 的 `ui` 區塊；其他原有區塊（`ai`、`risk`、`backtest`、`strategies`）不受影響。
- 缺少 `ui` 區塊時系統使用預設值並可正常啟動，不報錯。
- 6 套主題（`arctic_light` / `obsidian_dark` / `finance_green` / `midnight_blue` / `cyberpunk` / `warm_sepia`）皆能完整渲染四頁（資料管理、回測、AI 問答、設定），無破版、無 console 錯誤。
- Plotly 圖表（回測股價走勢、Tearsheet 權益曲線）在深色主題下底色一致且可讀。
- `streamlit-extras` 與 `streamlit-option-menu` 任一未安裝時，系統 fallback 到原生元件並顯示提示，不 crash。
- 既有功能（資料下載、回測、AI 問答、策略設定儲存讀取）行為與資料不因主題切換而異常。
- 主題值或元件開關設為非法值時，系統回退到預設並顯示警告，不中斷頁面。

#### 6-B 設定頁與側邊欄 UI 小修（0.5-1 天）

**建置內容：** 修正 6-A 後設定頁與側邊欄的可用性問題。此階段只調整 UI 與設定保存邏輯，不改資料管線、回測引擎、策略訊號語意或 AI 問答核心。

**側邊欄規格：**
- 左側 sidebar 只顯示 QuantTrader 自訂導覽區塊，不得同時顯示 Streamlit 自動產生的 multipage 導覽。
- 需移除或隱藏自動頁面入口：`app`、`ai chat`、`backtest`、`data management`、`settings`。
- 保留自訂選單區塊與四個功能頁面：`資料管理`、`回測`、`AI 問答`、`設定`。
- 若 AI 功能停用，`AI 問答` 頁仍可保留入口，但頁面內需清楚顯示停用狀態，不得發出 LLM API 呼叫。

**預設外觀規格：**
- 6-B 起，缺少 `ui.theme` 或 `ui` 區塊時，預設主題改為 `midnight_blue`。
- `config.yaml` 建議值：
  ```yaml
  ui:
    theme: midnight_blue   # arctic_light | obsidian_dark | finance_green | midnight_blue | cyberpunk | warm_sepia
    use_extras: true
    use_option_menu: true
  ```
- 若 `ui.theme` 為非法值，fallback 也改為 `midnight_blue`，並在 UI 顯示一次警告。

**設定頁儲存/恢復規格：**
- 設定頁需把「策略設定以外的設定」與「策略設定」分成兩組操作，避免使用者只想改外觀或 API key 時意外覆寫 `strategies[]`。
- 在「策略設定」區塊上方（目前位於「回測參數」之後）新增一般設定操作按鈕：
  - `儲存設定`：只儲存 `ui`、`ai`、`risk`、`backtest` 與 `.env` API keys；不得修改 `strategies[]` 或舊版 `strategy` 區塊。
  - `恢復設定預設值`：只恢復策略以外設定的預設值；不得清除或改寫任何已儲存策略 preset。
- 原策略區塊下方按鈕改名並限縮責任：
  - `儲存策略`：只新增或更新目前編輯的策略 preset，寫回 `config.yaml` 的 `strategies[]`；不得改寫 `ui`、`ai`、`risk`、`backtest` 或 `.env`。
  - `恢復策略預設值`：只把 `strategies[]` 恢復為 8 種策略各一組預設 preset；不得改寫其他設定。

**策略 preset 預設值：**
- `恢復策略預設值` 後，`strategies[]` 必須至少包含下列 8 筆：
  ```yaml
  strategies:
    - name: MA20_MA60
      type: moving_average_cross
      params: { short_window: 20, long_window: 60 }
    - name: 定期定額
      type: dollar_cost_averaging
      params: { monthly_day: 5, monthly_amount: 10000.0, min_buy_unit: 1, non_trading_day_policy: next_trading_day, buy_price_field: close }
    - name: RSI_14
      type: rsi
      params: { period: 14, oversold: 30.0, overbought: 70.0 }
    - name: KD_Cross
      type: kd_cross
      params: { k_period: 9, d_period: 3, smooth_k: 3 }
    - name: MACD_Cross
      type: macd_cross
      params: { fast: 12, slow: 26, signal: 9 }
    - name: BB_20
      type: bollinger_band
      params: { period: 20, std_dev: 2.0 }
    - name: BIAS_20
      type: bias
      params: { ma_period: 20, buy_bias: -10.0, sell_bias: 10.0 }
    - name: Donchian_20_10
      type: donchian_breakout
      params: { entry_period: 20, exit_period: 10 }
  ```
- 使用者可單獨刪除任何已儲存 preset；若刪到缺少某策略類型，下一次點 `恢復策略預設值` 必須重新建立完整 8 筆預設。

**策略類型選項規格：**
- 設定頁「策略類型」不得只列 `moving_average_cross` 與 `dollar_cost_averaging`，需補齊目前支援的 8 種策略類型。
- 選項顯示需與「編輯策略」欄位一致，格式為 `{type} ({中文說明})`：
  - `moving_average_cross (均線交叉)`
  - `dollar_cost_averaging (定期定額)`
  - `rsi (RSI 超買超賣)`
  - `kd_cross (KD 交叉)`
  - `macd_cross (MACD 交叉)`
  - `bollinger_band (布林通道)`
  - `bias (乖離率)`
  - `donchian_breakout (突破策略)`
- 選擇任一策略類型後，設定頁需顯示對應參數欄位並套用該策略的預設參數；不得因選到 7-A 新增策略而退回均線交叉或報「不支援」。

**單筆清除規格：**
- 「目前策略清單」中，每一筆已儲存 preset 前方需有清除按鈕。
- 點擊單筆清除只刪除該 preset，並立即寫回 `config.yaml` 的 `strategies[]`。
- 單筆清除不得修改其他 preset、不得修改策略以外設定、不得清除 `.env`。

**驗收指標：**
- 啟動 UI 後，左側 sidebar 不再出現 Streamlit 自動頁面入口，只保留 QuantTrader 自訂選單。
- `config.yaml` 缺少 `ui` 區塊時，UI 預設套用 `midnight_blue`。
- `儲存設定` / `恢復設定預設值` 只影響策略以外設定；`strategies[]` diff 不變。
- `儲存策略` / `恢復策略預設值` 只影響 `strategies[]`；`ui`、`ai`、`risk`、`backtest` 與 `.env` diff 不變。
- 「策略類型」可選 8 種策略，且每個選項都有中文括號說明。
- `恢復策略預設值` 後，每種策略類型至少各有一筆 preset。
- 單筆清除任一 preset 後，只有該 preset 被移除。

---

### Phase 7：策略擴充（彈性）

#### 7-A　六種技術分析策略（2-3 天）

**建置內容：** 新增 6 種台股常見技術分析策略，每種策略皆實作向量化（`generate_signals`）與事件驅動（`on_bar`）雙介面，可透過 `config.yaml` 的 `strategies[]` preset 設定參數，並在回測頁選擇執行。

**新增策略清單：**

| # | 策略類型 ID | 策略類別名稱 | 買進條件 | 賣出條件 | 預設參數 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `rsi` | `RSIStrategy` | RSI < `oversold` | RSI > `overbought` | `period=14, oversold=30, overbought=70` |
| 2 | `kd_cross` | `KDCrossStrategy` | K 線上穿 D 線 | K 線下穿 D 線 | `k_period=9, d_period=3, smooth_k=3` |
| 3 | `macd_cross` | `MACDCrossStrategy` | MACD 上穿 Signal 線 | MACD 下穿 Signal 線 | `fast=12, slow=26, signal=9` |
| 4 | `bollinger_band` | `BollingerBandStrategy` | 收盤價跌破下軌 | 收盤價突破上軌 | `period=20, std_dev=2.0` |
| 5 | `bias` | `BiasStrategy` | BIAS < `buy_bias`（偏離過深） | BIAS > `sell_bias`（偏離過高） | `ma_period=20, buy_bias=-10.0, sell_bias=10.0` |
| 6 | `donchian_breakout` | `DonchianBreakoutStrategy` | 收盤價突破 `entry_period` 日最高價 | 收盤價跌破 `exit_period` 日最低價 | `entry_period=20, exit_period=10` |

**策略邏輯詳細規格：**

**1. RSI 超買超賣（`rsi`）**
- 使用 Wilder RSI，以 `period` 日為計算週期。
- 當 RSI 從高位下穿 `oversold` 門檻時產生買進訊號（+1）。
- 當 RSI 從低位上穿 `overbought` 門檻時產生賣出訊號（-1）。
- RSI 尚未計算完成的 warm-up 期間，訊號為 0。

**2. KD 交叉（`kd_cross`）**
- 使用隨機指標 Stochastic Oscillator（K 值、D 值），參數為 `k_period`（回看期間）、`d_period`（D 值平滑期間）、`smooth_k`（K 值平滑期間）。
- 當 K 線從下方上穿 D 線時產生買進訊號（+1）。
- 當 K 線從上方下穿 D 線時產生賣出訊號（-1）。
- 指標尚未計算完成的 warm-up 期間，訊號為 0。

**3. MACD 交叉（`macd_cross`）**
- 使用 MACD 指標，參數為 `fast`（快線 EMA 週期）、`slow`（慢線 EMA 週期）、`signal`（訊號線 EMA 週期）。
- 當 MACD 線從下方上穿 Signal 線時產生買進訊號（+1）。
- 當 MACD 線從上方下穿 Signal 線時產生賣出訊號（-1）。
- 指標尚未計算完成的 warm-up 期間，訊號為 0。

**4. 布林通道（`bollinger_band`）**
- 使用布林通道，參數為 `period`（中軌 SMA 週期）、`std_dev`（標準差倍數）。
- 當收盤價從上方跌破下軌（Lower Band）時產生買進訊號（+1）。
- 當收盤價從下方突破上軌（Upper Band）時產生賣出訊號（-1）。
- 指標尚未計算完成的 warm-up 期間，訊號為 0。

**5. 乖離率（`bias`）**
- BIAS = (收盤價 - MA) / MA × 100（單位：百分比）。
- 使用 `ma_period` 日簡單移動平均線計算。
- 當 BIAS < `buy_bias`（例如 -10，代表股價低於均線 10%）時產生買進訊號（+1）。
- 當 BIAS > `sell_bias`（例如 10，代表股價高於均線 10%）時產生賣出訊號（-1）。
- MA 尚未計算完成的 warm-up 期間，訊號為 0。
- `buy_bias` 應為負數或零，`sell_bias` 應為正數或零，且 `buy_bias < sell_bias`。

**6. 突破策略 / Donchian Channel（`donchian_breakout`）**
- 當收盤價突破前 `entry_period` 日的最高價（不含當日）時產生買進訊號（+1）。
- 當收盤價跌破前 `exit_period` 日的最低價（不含當日）時產生賣出訊號（-1）。
- 最高/最低價使用 `high` / `low` 欄位計算。
- 回看期間不足時，訊號為 0。
- `entry_period` 與 `exit_period` 皆須為正整數。

**策略實作規格：**
- 所有新策略皆繼承 `StrategyBase`，實作 `generate_signals(df)` 與 `on_bar(bar, account)` 兩個方法。
- `generate_signals` 使用 pandas-ta 或 pandas 原生 rolling 計算指標，產生與 `df.index` 對齊的 `pd.Series`，值只有 `{-1, 0, +1}`。
- `on_bar` 在事件驅動模式下逐 bar 計算指標並判斷交叉/突破條件，回傳 `list[OrderEvent]`。
- `on_bar` 買進時以 `_BUY_INTENT_QUANTITY`（極大值）表達「全額買進」意圖，由執行層依實際成交價和帳戶現金決定最終可買股數。
- 每個策略實作 `reset_runtime_state()` 以清除 `on_bar` 的累計狀態（如歷史收盤價 list）。

**策略參數驗證規格：**
- 所有數值參數在 `__init__` 中驗證：必須為正數（period/window 類）或符合邏輯（buy_bias < sell_bias）。
- 不合法參數拋 `ValueError`，錯誤訊息包含參數名與限制。

**策略設定 preset 規格：**
- `strategy_config.py` 新增各策略類型的 `_normalize_*_params()` 函式，負責從 `config.yaml` preset 讀取並正規化參數。
- 建議 `config.yaml` preset 格式：
  ```yaml
  strategies:
    - name: RSI_14
      type: rsi
      params:
        period: 14
        oversold: 30
        overbought: 70

    - name: KD_Cross
      type: kd_cross
      params:
        k_period: 9
        d_period: 3
        smooth_k: 3

    - name: MACD_Cross
      type: macd_cross
      params:
        fast: 12
        slow: 26
        signal: 9

    - name: BB_20
      type: bollinger_band
      params:
        period: 20
        std_dev: 2.0

    - name: BIAS_20
      type: bias
      params:
        ma_period: 20
        buy_bias: -10.0
        sell_bias: 10.0

    - name: Donchian_20_10
      type: donchian_breakout
      params:
        entry_period: 20
        exit_period: 10
  ```

**策略中文 metadata 規格：**
- 在 `strategy_config.py` 新增 `STRATEGY_META` 字典，為所有 8 種策略類型（含既有 `moving_average_cross` 與 `dollar_cost_averaging`）提供中文 metadata。
- 每種策略類型的 metadata 包含以下欄位：

| 欄位 | 型別 | 說明 |
| :--- | :--- | :--- |
| `label` | `str` | 策略中文名稱，顯示在 UI 下拉選單 |
| `description` | `str` | 一句話策略說明 |
| `buy_hint` | `str` | 買進條件中文說明 |
| `sell_hint` | `str` | 賣出條件中文說明 |
| `param_labels` | `dict[str, str]` | 參數 key → 中文名稱對應 |

- 完整 metadata 定義：

| 策略類型 | label | description | buy_hint | sell_hint |
| :--- | :--- | :--- | :--- | :--- |
| `moving_average_cross` | 均線交叉 | 短均線上穿長均線買進，下穿賣出 | 短均線 > 長均線（黃金交叉） | 短均線 < 長均線（死亡交叉） |
| `dollar_cost_averaging` | 定期定額 | 每月固定日期以固定金額買入 | 每月指定日自動買入 | 不主動賣出（持有至回測結束） |
| `rsi` | RSI 超買超賣 | RSI 低於超賣線買進，高於超買線賣出 | RSI < 超賣門檻（如 30） | RSI > 超買門檻（如 70） |
| `kd_cross` | KD 交叉 | K 線上穿 D 線買進，下穿賣出 | K 線上穿 D 線（黃金交叉） | K 線下穿 D 線（死亡交叉） |
| `macd_cross` | MACD 交叉 | MACD 上穿訊號線買進，下穿賣出 | MACD 線上穿 Signal 線 | MACD 線下穿 Signal 線 |
| `bollinger_band` | 布林通道 | 跌破下軌買進，突破上軌賣出 | 收盤價跌破下軌（超跌反轉） | 收盤價突破上軌（超漲反轉） |
| `bias` | 乖離率 | 乖離率過低買進，過高賣出 | BIAS < 買進門檻（如 -10%） | BIAS > 賣出門檻（如 10%） |
| `donchian_breakout` | 突破策略 | 突破 N 日高點買進，跌破 M 日低點賣出 | 收盤價突破前 N 日最高價 | 收盤價跌破前 M 日最低價 |

- 參數中文名稱對應表：

| 策略類型 | 參數 key | 中文名稱 |
| :--- | :--- | :--- |
| `moving_average_cross` | `short_window` | 短均線週期 |
| `moving_average_cross` | `long_window` | 長均線週期 |
| `dollar_cost_averaging` | `monthly_day` | 每月投入日 |
| `dollar_cost_averaging` | `monthly_amount` | 每月投入金額 |
| `dollar_cost_averaging` | `min_buy_unit` | 最小買入單位（股） |
| `dollar_cost_averaging` | `non_trading_day_policy` | 非交易日處理 |
| `dollar_cost_averaging` | `buy_price_field` | 買入價格欄位 |
| `rsi` | `period` | RSI 週期 |
| `rsi` | `oversold` | 超賣門檻 |
| `rsi` | `overbought` | 超買門檻 |
| `kd_cross` | `k_period` | K 值回看期間 |
| `kd_cross` | `d_period` | D 值平滑期間 |
| `kd_cross` | `smooth_k` | K 值平滑期間 |
| `macd_cross` | `fast` | 快線 EMA 週期 |
| `macd_cross` | `slow` | 慢線 EMA 週期 |
| `macd_cross` | `signal` | 訊號線 EMA 週期 |
| `bollinger_band` | `period` | 中軌 SMA 週期 |
| `bollinger_band` | `std_dev` | 標準差倍數 |
| `bias` | `ma_period` | 均線週期 |
| `bias` | `buy_bias` | 買進乖離率門檻（%） |
| `bias` | `sell_bias` | 賣出乖離率門檻（%） |
| `donchian_breakout` | `entry_period` | 進場回看天數 |
| `donchian_breakout` | `exit_period` | 出場回看天數 |

**回測頁 UI 規格：**
- 回測頁的策略選擇下拉選單顯示 `{preset.name} ({STRATEGY_META[type].label})`，例如「MA20_MA60 (均線交叉)」。
- 選擇策略後，以 `st.caption` 顯示：
  - 策略說明（`description`）
  - 買進條件（`buy_hint`）與賣出條件（`sell_hint`）
  - 各參數值以中文名稱顯示，例如「短均線週期=20, 長均線週期=60」
- 各策略類型透過 `strategy_config.py` 正規化後，回測頁依 `type` 分派到對應策略類別。
- 所有新策略使用 `VectorizedBacktester` 或 `EventDrivenBacktester` 執行，結果顯示與既有 MA Cross 一致（Tearsheet + 股價走勢 + EPS）。

**驗收指標：**
- 6 個策略類別各自可透過 `generate_signals()` 產生正確的 `{-1, 0, +1}` 向量訊號。
- 6 個策略類別各自可透過 `on_bar()` 在事件驅動模式下產生正確的 `OrderEvent`。
- `strategy_config.py` 能正確正規化 6 種新策略類型的 preset 參數，不合法值回傳 `None`。
- `STRATEGY_META` 涵蓋全部 8 種策略類型，每種包含 `label`、`description`、`buy_hint`、`sell_hint`、`param_labels`。
- 回測頁策略選擇下拉選單顯示中文策略名稱，選擇後顯示中文買賣條件與參數說明。
- 回測頁可選擇任一新策略並成功執行回測，顯示 Tearsheet、股價走勢與 EPS。
- 既有策略（MA Cross、DCA）不受新增策略影響，且同步顯示中文 metadata。
- 所有策略的 warm-up 期間不產生虛假訊號。
- 不合法策略參數（負週期、buy_bias >= sell_bias 等）拋 `ValueError`。

---

#### 7-B　策略研究工作台（2-3 天）

**建置內容：** 批次策略比較、結果保存、回測頁 UI tab 重構、K 線圖升級（Candlestick）、Signal/Trade 雙層買賣標記、策略指標副圖。建立「批次跑多組回測 → 收集 metrics → 表格比較 → 選中結果展開圖表」的完整研究流程。

**7-B-1　批次策略比較**

- 新增 `src/backtest/batch.py`，提供 `run_strategy_batch()` 函式。
- 輸入：symbol、日期區間、初始資金、策略 preset 清單（來自 `config.yaml` 中所有已啟用的 strategies）。
- 對每個 preset 依序執行回測（預設使用 `VectorizedBacktester`），收集 `BacktestResult`。
- 回傳：每個策略的 summary row（dict）+ 原始 `BacktestResult` 物件，打包為 `BatchResult`。
- 某個策略回測失敗時（如 warm-up 不足、資料不足），記錄錯誤訊息並跳過，不中斷整個批次。

**BatchResult 資料結構：**

```python
@dataclass
class StrategyRunSummary:
    preset_name: str
    strategy_type: str
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    error: str | None           # 回測失敗時的錯誤訊息
    result: BacktestResult | None  # 回測成功時的完整結果

@dataclass
class BatchResult:
    symbol: str
    start_date: str
    end_date: str
    engine: str
    initial_capital: float
    summaries: list[StrategyRunSummary]
```

**比較表欄位：**

| 欄位 | 來源 | 說明 |
| :--- | :--- | :--- |
| 策略名稱 | `preset.name` | 顯示中文 label |
| 策略類型 | `preset.type` | 顯示 `STRATEGY_META[type].label` |
| 總報酬 | `BacktestResult.total_return` | 百分比格式 |
| 年化報酬 | `BacktestResult.annual_return` | 百分比格式 |
| 最大回撤 | `BacktestResult.max_drawdown` | 百分比格式 |
| Sharpe | `BacktestResult.sharpe_ratio` | 2 位小數 |
| 勝率 | `BacktestResult.win_rate` | 百分比格式 |
| Profit Factor | `BacktestResult.profit_factor` | 2 位小數，999.0 顯示 N/A |
| 交易次數 | `BacktestResult.total_trades` | 整數 |

**7-B-2　結果保存**

- 批次比較結果保存為 CSV 檔案，路徑：`data/backtest/strategy_comparisons/`。
- 檔名格式：`{symbol}_{start}_{end}_{timestamp}.csv`，例如 `2330_20230101_20260101_20260508T143022.csv`。
- CSV 欄位與比較表欄位一致，不含 `BacktestResult` 物件（僅 summary 數據）。
- UI 提供「匯出結果」按鈕，點選後存檔並顯示檔案路徑。
- 先 CSV 就好，不急著做資料庫 schema。

**7-B-3　UI tab 重構**

- 回測頁 `render()` 改為 `st.tabs` 結構，分三個 tab：
  - **單次回測**：現有回測流程（選策略 → 跑 → Tearsheet + 圖表），行為不變。
  - **策略比較**：選 symbol / 日期 → 一次跑全部 config 中的 preset → 顯示比較表 → 選中某列展開詳細圖表。
  - **歷史結果**：列出 `data/backtest/strategy_comparisons/` 下的 CSV 檔案，點選載入查看。
- 共用元件：symbol 輸入、日期選擇器抽成共用 helper，三個 tab 共享。
- 策略比較 tab 中，選中某列策略後，展開該策略的：
  - Tearsheet 摘要
  - K 線圖 + Signal/Trade overlay
  - 策略指標副圖

**7-B-4　K 線圖升級**

- 現有 `_render_price_panel()` 的收盤價折線圖（`go.Scatter`）升級為 K 線圖（`go.Candlestick`）。
- 使用 `price_df` 的 `open`、`high`、`low`、`close` 四個欄位。
- 保留既有的 MA5、MA20、MA60 均線疊圖。
- 若資料缺少 OHLC 欄位（如只有 close），降級回折線圖。
- K 線顏色：漲（close > open）紅色、跌（close < open）綠色（台股慣例）。

**7-B-5　Signal/Trade 雙層標記**

- 區分兩種標記，可同圖顯示或透過 toggle 切換：
  - **Signal marker**：策略在該 bar 產生 +1/-1 的原始訊號位置。形狀為菱形（diamond），顏色淺、半透明。
  - **Trade marker**：引擎實際成交的 entry/exit 位置（既有的買進/賣出三角形標記）。形狀為三角形（triangle-up/down），顏色實、不透明。
- Signal marker 資料來源：向量化引擎需回傳 `signals` Series（目前已在引擎內部計算，需暴露到 `BacktestResult`）。
- `BacktestResult` 新增可選欄位 `signals: pd.Series | None`，向量化引擎填入，事件驅動引擎填 `None`。
- 事件驅動引擎模式下，只顯示 Trade marker（因為 signal 和 trade 在事件驅動中是同一回事）。
- 用途：向量化引擎有 next-bar 成交語義，signal 和 trade 不在同一 bar，debug 假信號時兩者對照很有價值。

**7-B-6　策略指標副圖**

- 在 K 線圖下方新增指標副圖（Plotly subplot），顯示當前策略對應的技術指標。
- 副圖與主圖 X 軸對齊（共享 `xaxis`），支援 range slider 連動。
- 各策略類型的指標副圖內容：

| 策略類型 | 副圖內容 | 視覺元素 |
| :--- | :--- | :--- |
| `moving_average_cross` | 不需要獨立副圖 | MA 線已在主圖上，不另加副圖 |
| `dollar_cost_averaging` | 不需要副圖 | 無技術指標 |
| `rsi` | RSI 線 + 超買/超賣水平線 | RSI 曲線 + `overbought`/`oversold` 兩條水平虛線，區間填色 |
| `kd_cross` | K 線 + D 線 | 兩條曲線，交叉點可標記 |
| `macd_cross` | MACD 線 + Signal 線 + 柱狀圖（Histogram） | MACD/Signal 為曲線，Histogram 為柱狀圖（正綠負紅） |
| `bollinger_band` | 不需要獨立副圖 | 上軌/下軌/中軌畫在主圖上（與 K 線同座標軸） |
| `bias` | BIAS 曲線 + 買進/賣出門檻線 | BIAS 曲線 + `buy_bias`/`sell_bias` 兩條水平虛線 |
| `donchian_breakout` | 不需要獨立副圖 | Upper/Lower channel 畫在主圖上（與 K 線同座標軸） |

- 指標副圖只在「選中單一策略結果」時顯示（單次回測或策略比較中選定某列後）。
- 指標計算使用 `pandas_ta` 或 pandas rolling，與策略內部計算一致。

**驗收指標：**
- `run_strategy_batch()` 可對 8 個 preset 批次回測，每個回傳正確的 summary row。
- 某個策略失敗時不影響其餘策略的結果收集。
- 比較表 9 個欄位正確顯示，`profit_factor=999.0` 顯示為 N/A。
- 結果可匯出 CSV，檔案內容與表格一致。
- UI 三個 tab 可正常切換，互不干擾。
- 單次回測 tab 行為與 7-A 完全一致（不退化）。
- K 線圖顯示 OHLC candlestick，漲紅跌綠。
- Signal marker 和 Trade marker 可同圖顯示，hover 可區分兩者。
- 至少 RSI、MACD、BIAS 三種策略的指標副圖正確顯示。
- 布林通道和 Donchian channel 在主圖上疊加顯示。
- 歷史結果 tab 可載入並顯示之前匯出的 CSV。

---

#### 7-C　參數掃描與防過度最佳化（2-3 天）

**建置內容：** 在 7-B 的批次執行基礎上，新增單策略參數 Grid Search、不合法參數組合過濾、組合數上限控制、樣本不足警告、結果排序與 Top N 顯示。

**7-C-1　Grid Search 引擎**

- 新增 `src/backtest/sweep.py`，提供 `run_parameter_sweep()` 函式。
- 輸入：symbol、日期區間、初始資金、策略類型（單一 type）、參數掃描範圍（每個參數一組候選值）。
- 流程：
  1. 從參數候選值生成所有組合（Cartesian product）。
  2. 過濾不合法組合（見 7-C-2）。
  3. 檢查組合數是否超過上限（見 7-C-3）。
  4. 對每個合法組合建構策略 instance，執行回測（使用 `VectorizedBacktester`）。
  5. 收集每組的 summary metrics，打包回傳。
- 回傳 `SweepResult`：

```python
@dataclass
class SweepResult:
    symbol: str
    start_date: str
    end_date: str
    strategy_type: str
    total_combos: int            # 過濾前的總組合數
    valid_combos: int            # 過濾後的合法組合數
    results: list[SweepRunSummary]

@dataclass
class SweepRunSummary:
    params: dict[str, Any]       # 本次使用的參數組合
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    error: str | None
```

**參數掃描範例：**

| 策略類型 | 可掃描參數 | 範例輸入 |
| :--- | :--- | :--- |
| `moving_average_cross` | `short_window`, `long_window` | `5,10,20` × `40,60,120` |
| `rsi` | `period`, `oversold`, `overbought` | `7,14,21` × `20,30` × `70,80` |
| `kd_cross` | `k_period`, `d_period`, `smooth_k` | `9,14` × `3,5` × `3,5` |
| `macd_cross` | `fast`, `slow`, `signal` | `8,12` × `20,26` × `7,9` |
| `bollinger_band` | `period`, `std_dev` | `10,20,30` × `1.5,2.0,2.5` |
| `bias` | `ma_period`, `buy_bias`, `sell_bias` | `10,20,30` × `-15,-10,-5` × `5,10,15` |
| `donchian_breakout` | `entry_period`, `exit_period` | `10,20,55` × `5,10,20` |

**7-C-2　參數合法性過濾**

- 在生成組合後、跑回測前，自動過濾不合法的參數組合：

| 策略類型 | 過濾規則 |
| :--- | :--- |
| `moving_average_cross` | `short_window >= long_window` → 排除 |
| `rsi` | `oversold >= overbought` → 排除 |
| `macd_cross` | `fast >= slow` → 排除 |
| `bias` | `buy_bias >= sell_bias` → 排除 |
| 其餘策略 | 所有參數 `<= 0` → 排除 |

- 過濾規則複用各策略的 `_normalize_*_params()` 函式：呼叫後回傳 `None` 的組合即為不合法。
- 過濾後，在 UI 顯示「{total_combos} 組合中 {valid_combos} 個合法」。

**7-C-3　組合數上限控制**

- 預設上限：**200 組**合法組合。
- 在 UI 輸入參數後、點「開始掃描」前，即時計算合法組合數。
- 若超過上限：
  - 顯示 `st.warning("合法組合數 {valid_combos} 超過上限 200，請縮小參數範圍。")`。
  - 停用「開始掃描」按鈕，不允許執行。
- 上限值可在未來設定為 config 項目，目前硬寫。

**7-C-4　防過度最佳化守門**

- 結果表格中，針對潛在過度最佳化的結果加上視覺警告：
  - **交易次數過少**：`total_trades < 3` 的結果，在交易次數欄標註「⚠ 樣本不足」（黃色背景）。
  - **最大回撤過深**：`max_drawdown > 50%` 的結果，在最大回撤欄標註「⚠ 回撤過深」。
  - **Profit Factor 異常**：`profit_factor == 999.0`（sentinel 值）的結果，顯示 N/A 而非 999.0。
- 結果表格標題顯示「Top N 結果（依 {排序欄位}）」，不使用「最佳策略」、「最佳參數」等用語。
- 不自動宣稱任何組合是「最佳」，使用者自行判斷。

**7-C-5　結果排序與顯示**

- 掃描結果表格預設依 Sharpe Ratio 降序排列。
- 使用者可透過 `st.selectbox` 切換排序欄位：Sharpe、總報酬、年化報酬、最大回撤（升序）、勝率、Profit Factor。
- 顯示 Top 20 筆結果（可在 UI 上以 slider 調整顯示數量，上限 50）。
- 選中某列後，展開該參數組合的 Tearsheet 摘要 + K 線圖 + 指標副圖（複用 7-B 的圖表元件）。

**7-C-6　掃描結果保存**

- 掃描結果保存為 CSV，路徑：`data/backtest/parameter_sweeps/`。
- 檔名格式：`{symbol}_{strategy_type}_{timestamp}.csv`。
- CSV 欄位：各參數值 + 所有 metrics 欄位 + 警告欄位（`sample_warning: bool`）。
- UI 提供「匯出掃描結果」按鈕。

**7-C-7　UI 整合**

- 在 7-B 的回測頁 tabs 中新增第四個 tab：**參數掃描**。
- Tab 結構變更為：單次回測 / 策略比較 / 參數掃描 / 歷史結果。
- 參數掃描 tab 流程：
  1. 選擇 symbol、日期區間（共用元件）。
  2. 選擇策略類型（`st.selectbox`，列出所有非 DCA 的策略類型）。
  3. 根據選中的策略類型，動態顯示該策略的可掃描參數。
  4. 每個參數一個 `st.text_input`，輸入格式為逗號分隔值（如 `5,10,20`）。
  5. 即時顯示合法組合數與上限。
  6. 點「開始掃描」→ 顯示進度條 → 完成後顯示結果表格。
  7. 選中某列 → 展開圖表。
- DCA 策略不參與參數掃描（專用回測流程，不適合 grid search）。

**驗收指標：**
- `run_parameter_sweep()` 可對 MA Cross 的 `short_window=[5,10,20]` × `long_window=[40,60,120]` 完成掃描，正確排除 `short >= long` 的組合。
- 合法組合數超過 200 時，UI 阻止執行。
- `total_trades < 3` 的結果標註「⚠ 樣本不足」。
- 掃描結果可依不同欄位排序切換。
- 掃描結果可匯出 CSV。
- 選中某筆結果後，展開的圖表與該參數組合的回測結果一致。
- 參數掃描 tab 不影響其餘三個 tab 的功能。
- 不合法參數組合（如 RSI `oversold=80, overbought=30`）被自動過濾，不執行回測。

---

#### 7-D　Walk-Forward Analysis（3.5-5 天）

**建置內容：** 在 7-C 參數掃描基礎上，新增 Walk-Forward Analysis（WFA，滾動樣本外驗證）。系統將歷史資料切成多段 in-sample（IS，樣本內最佳化區間）與 out-of-sample（OOS，樣本外驗證區間），每段 IS 先執行參數掃描選出最佳參數，再將該參數套用到下一段 OOS 回測，用於檢查參數是否過度擬合單一歷史區間。

**狀態（2026-05-10）：** ✅ Phase 7-D 已驗收完成。7-D-1 核心引擎通過 `tests/test_walk_forward.py tests/test_sweep.py` = 62 passed, 1 warning；7-D-2 UI tab + 文件 + 回歸通過 py_compile、UI 規格補點驗收與 Phase 7 回歸 `tests/test_strategies.py tests/test_strategy_config.py tests/test_batch.py tests/test_sweep.py tests/test_walk_forward.py` = 116 passed, 1 warning。

**MVP 範圍：**

- 只支援單一 symbol，不做多標的 WFA。
- 只支援 `VectorizedBacktester`，不做 event-driven WFA。
- 只支援可參數掃描策略：`moving_average_cross`、`rsi`、`kd_cross`、`macd_cross`、`bollinger_band`、`bias`、`donchian_breakout`。
- 不支援 `dollar_cost_averaging`，DCA 屬專用回測流程，不適合 grid search + OOS 驗證。
- 採 rolling calendar window：固定 IS 長度向前滾動，不做 anchored expanding window。
- 不做 portfolio WFA、Monte Carlo、AI 自動解讀、walk-forward matrix、新資料源或新增策略。

**7-D-1　核心引擎（window splitter + runner + report + stability + CSV）**

核心引擎階段負責 WFA 的資料切割、IS 參數掃描、OOS 驗證、彙總報表、參數穩定性與 CSV 匯出，不包含 Streamlit UI。

**狀態（2026-05-09）：** ✅ 已驗證完成。`tests/test_walk_forward.py tests/test_sweep.py` 為 62 passed, 1 warning；第一次一般權限執行因 Windows temp 目錄權限導致 pytest `tmp_path` setup error，依專案規則 elevated 重跑同範圍後通過。`warning_count` 已補 regression test，確認 per-window warnings 與 unstable-parameter aggregate warnings 會一併計數。

**Rolling 視窗切割**

- 新增 `src/backtest/walk_forward.py`。
- 預設參數：

| 參數 | 預設 | 說明 |
| :--- | :--- | :--- |
| `is_months` | 12 | 用一年資料做樣本內最佳化 |
| `oos_months` | 6 | 用半年資料做樣本外驗證 |
| `step_months` | 6 | 每次向前滾動半年 |
| `max_windows` | 10 | MVP 硬上限，不提供 UI 調高 |
| `min_windows` | 3 | 少於 3 段則 WFA 可信度不足 |
| `max_combinations` | 200 | 沿用 7-C 參數掃描上限 |

- 最低資料長度公式：

```text
最低月數 = is_months + oos_months + (min_windows - 1) × step_months
```

- 以預設值計算：`12 + 6 + (3 - 1) × 6 = 30 個月`。
- UI 執行前必須檢查資料長度，不足時直接阻止執行，錯誤訊息：

```text
資料長度不足：目前資料僅 {actual} 個月，WFA 至少需要 {required} 個月（IS {is_months} + OOS {oos_months} + {min_windows - 1} 段步進 × {step_months}）。
```

**IS sweep + OOS 驗證**

- 每段 window 流程：
  1. 切出 IS data。
  2. 切出 OOS data。
  3. 以 IS data 呼叫 `run_parameter_sweep()`。
  4. 依 `optimize_metric` 選出 IS 最佳參數。
  5. 用最佳參數建立策略，對 OOS data 執行 `VectorizedBacktester`。
  6. 記錄 IS best result、OOS result、best params、warnings。
- 支援的最佳化指標限「越高越好」：
  - `total_return`
  - `annual_return`
  - `sharpe_ratio`
- 不納入 `profit_factor`：目前 metrics 層以 `999.0` 表示 sentinel，會誤導最佳參數選擇。
- 不納入 `max_drawdown`：屬「越低越好」指標，反向排序與 degradation 定義留待後續。
- 執行量預估：

```text
總回測次數 = window_count × combo_count
```

- UI 點「執行」前顯示：

```text
將進行 {windows} 段 × {combos} 組 = {total} 次回測
```

- 執行中顯示 `st.progress`，標示目前跑到第幾段視窗。
- 若資料可產生超過 10 段，MVP 只取最早 10 段或要求使用者縮短區間。

**WFA 結果模型**

```python
@dataclass(frozen=True)
class WalkForwardWindow:
    window_id: int
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp


@dataclass(frozen=True)
class WalkForwardWindowResult:
    window: WalkForwardWindow
    best_params: dict[str, Any] | None
    is_best: SweepRunSummary | None
    oos_result: BacktestResult | None
    degradation: float | None
    skipped: bool
    warnings: list[str]


@dataclass(frozen=True)
class WalkForwardSummary:
    strategy_type: str
    optimize_metric: str
    windows: list[WalkForwardWindowResult]
    total_window_count: int
    valid_window_count: int
    skipped_window_count: int
    aggregate: dict[str, Any]
    parameter_stability: dict[str, Any]
```

- `best_params`、`is_best`、`oos_result`、`degradation` 在 IS sweep 全部失敗時為 `None`。
- `skipped=True` 的視窗不計入 aggregate。
- `valid_window_count` 只計算 `skipped=False` 的視窗。

**WFA 指標與 degradation**

每段 window 明細至少包含：

| 欄位 | 說明 |
| :--- | :--- |
| `window_id` | 第幾段 |
| `is_start` / `is_end` | IS 日期範圍 |
| `oos_start` / `oos_end` | OOS 日期範圍 |
| `best_params` | IS 最佳參數 |
| `is_total_return` / `oos_total_return` | IS / OOS 總報酬 |
| `is_sharpe` / `oos_sharpe` | IS / OOS Sharpe |
| `oos_max_drawdown` | OOS 最大回撤 |
| `oos_total_trades` | OOS 交易次數 |
| `degradation` | IS 到 OOS 的績效衰退 |
| `warnings` | 樣本不足、掃描失敗等 |

彙總指標至少包含：

| 欄位 | 說明 |
| :--- | :--- |
| `total_window_count` | 產生的視窗總數 |
| `valid_window_count` | 成功且計入彙總的有效視窗數 |
| `skipped_window_count` | 被跳過的視窗數 |
| `oos_win_window_rate` | OOS 報酬為正的視窗比例 |
| `avg_oos_return` | 平均 OOS 報酬 |
| `median_oos_return` | OOS 報酬中位數 |
| `avg_oos_sharpe` | 平均 OOS Sharpe |
| `worst_oos_drawdown` | 最差 OOS 最大回撤 |
| `avg_degradation` | 平均 IS/OOS 衰退 |
| `parameter_stability_score` | 參數穩定性分數 |
| `warning_count` | 警告數 |

MVP degradation 採絕對差值：

```text
degradation = oos_metric - is_metric
```

- `degradation < 0` 表示 OOS 比 IS 差。
- 絕對差值在不同量級下可能誤導，例如 `IS Sharpe=5.0, OOS Sharpe=4.0` 與 `IS Sharpe=0.5, OOS Sharpe=-0.5` 都是 `-1.0`。比率型 degradation `(oos - is) / abs(is)` 列為 follow-up，MVP 不做。

**參數穩定性**

- 只使用有效 window 的最佳參數，跳過 sweep 失敗視窗。
- 對每個 numeric parameter 計算 `min`、`max`、`mean`、`median`、`std`、`cv`。
- 使用 Coefficient of Variation（CV）分類：

```python
cv = std / abs(mean)  # mean == 0 時直接判 unstable

if cv < 0.15:
    status = "stable"
elif cv < 0.40:
    status = "moderate"
else:
    status = "unstable"
```

- 任一參數為 `unstable` 時，UI 顯示：

```text
最佳參數在 WFA 視窗間變動過大（{param_name} CV={cv:.2f}），可能代表策略對參數高度敏感。
```

**警告與失敗處理**

| 條件 | 警告 | 行為 |
| :--- | :--- | :--- |
| WFA window 少於 3 段 | 視窗數過少，WFA 可信度有限 | 執行前阻止 |
| OOS trade 少於 3 筆 | OOS 交易樣本不足 | 該視窗標記警告，仍計入彙總 |
| 大多數 OOS 報酬為負 | 策略泛化能力不足 | 彙總層警告 |
| 平均 degradation 大幅為負 | IS 績效無法延續到 OOS | 彙總層警告 |
| 參數穩定性 unstable | 最佳參數跨視窗跳動過大 | 彙總層警告 |
| 某 window IS sweep 全部失敗 | 該視窗無法選出有效參數 | 跳過該視窗，不計入彙總 |
| 資料長度不足 | 無法產生足夠 WFA 視窗 | 執行前阻止 |

- window table 中對 sweep 失敗視窗標記「掃描失敗，跳過」。
- 若跳過後有效視窗數 `< min_windows`，觸發可信度不足警告。

**結果保存**

- WFA 結果保存為 CSV，路徑：`data/backtest/walk_forward/`。
- 檔名格式：`{symbol}_{strategy_type}_wfa_{timestamp}.csv`。
- 至少輸出兩份 CSV：
  - window summary CSV
  - parameter stability CSV
- CSV 需包含 window 範圍、best params、IS/OOS metrics、degradation、warnings、skipped flag。

**7-D-2　UI tab + 文件 + 回歸**

UI 階段負責回測頁 Walk-Forward tab、中文說明、執行前檢查、進度條、結果呈現、CSV 下載、文件更新與回歸驗收。

**狀態（2026-05-10）：** ✅ 已驗收完成。Walk-Forward tab 已新增；英文研究術語已補中文說明；回測次數預估已依日期區間、IS/OOS/Step 與合法參數組合數顯示；summary metrics、window table、parameter stability table、視窗警告詳情與 CSV 匯出入口已具備。Phase 7 回歸為 116 passed, 1 warning。

**UI 整合**

- 在回測頁新增「Walk-Forward」tab；不假設既有 tab 數固定。
- UI 主要顯示中文；必要英文研究術語需附中文說明：
  - Walk-Forward（滾動樣本外驗證）
  - In-sample / IS（樣本內最佳化區間）
  - Out-of-sample / OOS（樣本外驗證區間）
  - Optimize metric（最佳化指標）
  - Degradation（IS 到 OOS 績效衰退）
- 下拉選單、欄位標題、警告訊息若使用英文縮寫，旁邊需有中文 label、help text 或 tooltip。
- 表格欄位可保留英文資料欄名，但 UI 顯示名稱需附中文，例如 `oos_sharpe` 顯示為「OOS Sharpe（樣本外夏普值）」。
- 控制項：
  - 策略 preset / strategy type
  - 參數範圍輸入（沿用 7-C）
  - IS months（樣本內月份）
  - OOS months（樣本外月份）
  - Step months（滾動步進月份）
  - Optimize metric（最佳化指標）
  - Max combinations（最大參數組合數）
  - Run button
- 顯示區塊：
  1. Summary metrics（有效視窗數、OOS 勝率、平均 OOS return、平均 OOS Sharpe、最差 OOS drawdown、平均 degradation）
  2. Window table（IS/OOS 起訖、best params、IS/OOS metrics、warnings）
  3. 參數穩定性表（min / median / max / cv / status）
  4. CSV export（window summary、parameter stability）

**文件與回歸**

- 更新 `量化交易系統規格書_shellpig版.md`、`開發設計方針.md`、`測試指南.md`、`PROJECT_BRIEF.md`。
- 補手動驗收清單。
- 跑 Phase 7-D 指定測試與全非 integration 回歸。

**Follow-up（本 Phase 不做）：**

| 項目 | 說明 |
| :--- | :--- |
| Anchored expanding window | IS 起點固定、長度遞增 |
| Ratio-based degradation | `(oos - is) / abs(is)` 與絕對差並列 |
| `profit_factor` 納入 optimize metric | 需先解決 metrics 層 sentinel 999.0 |
| `max_drawdown` 納入 optimize metric | 需處理越低越好的反向邏輯 |
| Event-driven WFA | 目前只支援 Vectorized engine |
| 多標的 WFA | 留給 Phase 8 portfolio research |

**驗收指標：**

- 能對單一 symbol + 單一策略執行 WFA。
- 預設資料長度至少 30 個月才能產生 3 段 WFA；不足時 UI 阻止執行。
- 每段 IS 會跑參數掃描並選出最佳參數。
- 每段 OOS 會使用該段最佳參數重新回測。
- 報表清楚顯示 IS vs OOS degradation。
- 報表顯示參數穩定性，且 CV 門檻正確。
- OOS 交易過少、視窗過少、參數不穩定、sweep 失敗時會提示。
- sweep 全部失敗的視窗被跳過，不計入彙總。
- UI 有 Walk-Forward tab，英文術語均有中文說明。
- 結果可匯出 CSV。

---

### Phase 8：個股綜合分析儀表板（彈性）

#### 8-A　技術面自動判讀引擎（1-2 天）

**狀態（2026-05-10）：** ✅ 已驗收完成。`tests/test_technical_summary.py` = 13 passed。

**建置內容：** 把指標數值轉成人可讀的文字結論。給定一檔股票的日 K 資料，自動產出技術分析總覽（趨勢方向、MA 狀態、KD/MACD/量能判讀）、短線綜合分數（0~100%）、關鍵價位（壓力區/支撐區）、量價結構分析等文字化結論。

**專案定位更新：** Phase 8 加入即時報價與操作劇本後，專案定位修改為「研究、回測、盤中觀察，不接實盤下單」。

**設計決策：**

| 決策 | 選擇 | 理由 |
|:---|:---|:---|
| UI 框架 | Streamlit（維持現有） | 不重寫前端，工程量可控 |
| 排版策略 | Tab 分頁 + 滾動式 | Streamlit 無法單屏塞 12 面板；tab 分頁可讀性更好 |
| 即時行情 | TWSE MIS API | 免費、免 key、盤中即時（約 5-15 秒延遲） |
| 籌碼資料 | FinMind 免費層 | 三大法人買賣超可用；券商分點降級為法人替代 |
| 刷新機制 | 手動按鈕 | Streamlit auto-rerun 會重跑整頁分析 |
| K 線型態 | `pandas_ta.cdl_pattern(name=...)` + 自定規則 | 62 種型態可用 |
| config 結構 | 獨立 `realtime:` section | 語意清楚，未來擴充不會污染 `data:` |
| 籌碼更新時機 | 混合模式（on-demand + Parquet 落地 + 增量補抓） | 確保一定有資料，又避免頻繁打 API |
| W 底/M 頭偵測 | 保守策略（寧可漏報不要誤報） | 偵測不到時顯示「未形成標準型態」 |

**資料可信度等級：**

| 等級 | 定義 | 適用區塊 |
|:---|:---|:---|
| 精準資料 | 直接來自日 K、即時報價、法人/融資融券原始資料或可重現公式 | MA、KD、MACD、成交量、法人買賣超、融資融券餘額 |
| 規則估算 | 使用明確 rule-based 公式推導 | 支撐壓力、短線綜合分數、W 底/M 頭、量價結構 |
| 資料降級 | 缺少 tick、券商分點或真正內外盤資料時以替代資料近似 | 主力出貨警示、籌碼集中度、買賣力道估算 |
| AI 文字解讀 | AI 只根據已提供資料轉成中文分析，不得自行編造數字 | 公司/產業概況、隔日操作劇本、整體結論 |
| 資料不足 | 資料列數不足、API 失敗或 local cache 不完整 | 對應區塊顯示「資料不足」或降級提示 |

**依賴關係：**

```
8-A（技術面判讀）──┐
8-B（K線型態）  ──┤
                   ├──→ 8-E（AI分析）──→ 8-F（儀表板UI）──→ 8-G（新手說明）
8-C（籌碼管線）──┤
8-D（即時行情）──┘
```

8-A / 8-B / 8-C / 8-D 四條線互相獨立，可平行開發。8-E 依賴 8-A + 8-C，8-F 最後整合，8-G 在 8-F 基礎上加入新手友善說明文字。

**新增模組：** `src/analysis/technical_summary.py`

**輸入：** `pd.DataFrame`（日 K raw OHLCV）

價格尺度規則：
- K 線圖、即時價、支撐壓力、操作劇本價位一律使用 raw price。
- adjusted price 僅供長期報酬、除權息調整後趨勢比較使用。

**輸出：** `TechnicalSummary` dataclass：

| 區塊 | 欄位 | 說明 |
|:---|:---|:---|
| 技術分析總覽 | `trend_direction` | "多頭趨勢" / "空頭趨勢" / "盤整" |
| | `ma_status` | "多頭排列 (5>20>60)" / "空頭排列" / "糾結" |
| | `kd_status` | "KD 高檔鈍化" / "KD 黃金交叉" / ... |
| | `macd_status` | "正值收斂" / "負值擴張" / ... |
| | `volume_status` | "量能放大" / "量能略縮" / "爆量" |
| | `volume_price_relation` | "價漲量增" / "價漲量縮（短線整理）" / ... |
| 短線綜合分數 | `short_term_score` | 0.0~1.0 |
| | `short_term_label` | "強勢偏多" / "中等偏多" / "中性" / "偏空" |
| | `short_term_components` | `{"ma": 0.8, "kd": 0.6, ...}` |
| 關鍵價位 | `resistance_levels` | `list[PriceLevel]`（壓力區） |
| | `support_levels` | `list[PriceLevel]`（支撐區） |
| 量價結構 | `volume_price_divergence` | "量價背離：價漲量縮" / "量價同步" |
| | `ma_bias` | "與 MA20 乖離約 +4.61%，偏高" |
| | `chip_behavior` | 需 8-C 籌碼資料注入 |
| | `operation_observation` | 綜合觀察文字 |

**判讀規則（rule-based）：**

| 指標 | 判讀邏輯 |
|:---|:---|
| 趨勢方向 | MA5 > MA20 > MA60 → 多頭；反之空頭；交錯 → 盤整 |
| MA 狀態 | 三線排列順序 + 最新 close 相對位置 |
| KD 狀態 | K > 80 → 高檔鈍化；K < 20 → 低檔鈍化；K 上穿 D → 黃金交叉 |
| MACD 狀態 | DIF > 0 且 DIF > DEA → 正值擴張；DIF > 0 且 DIF < DEA → 正值收斂 |
| 量能狀態 | 今日量 vs 5 日均量：> 1.5x 放大、0.7x~1.5x 正常、< 0.7x 略縮 |
| 短線綜合分數 | MA 結構(30%) + KD 位置/交叉(25%) + 量價關係(25%) + 突破狀態(20%) |
| 壓力區 | 近 60 日最高價、近 20 日最高價（取不重複的 2 個） |
| 支撐區 | 近期低點、MA20、MA60（取最近的 2~3 個） |
| 乖離率 | `(close - MA20) / MA20 × 100%` |

**不使用 AI：** 純 rule-based template engine，`ai.enabled=false` 時照常運作。

**驗收指標：**
- 給定多頭排列 fixture，所有技術面欄位正確輸出多頭判讀
- 給定空頭排列 fixture，正確輸出空頭判讀
- 給定盤整 fixture，正確輸出盤整判讀
- 資料不足（< 60 bar）時不 crash，相關欄位標示資料不足
- 短線綜合分數在 0.0~1.0 範圍內

---

#### 8-B　K 線型態辨識（2-3 天）

**建置內容：** candlestick pattern 辨識 + 圖表型態偵測（W 底 / M 頭）+ 多週期分析（日 / 週 / 月趨勢）。

**新增模組：** `src/analysis/pattern.py`

**K 線型態表：**

| 型態 | 實作方式 | 判讀 |
|:---|:---|:---|
| 長紅 K / 長黑 K | 自定（body > 2× avg body） | 多方 / 空方力道 |
| 十字線 | `cdl_doji(open, high, low, close)` | 多空拉鋸 |
| 錘子 / 吊人 | `cdl_pattern(..., name=["hammer", "hangingman"])` | 反轉訊號 |
| 吞噬 | `cdl_pattern(..., name="engulfing")` | 反轉確認 |
| 晨星 / 夜星 | `cdl_pattern(..., name=["morningstar", "eveningstar"])` | 強反轉 |
| 帶上影線 / 下影線 | 自定（shadow > 2× body） | 上檔壓力 / 下檔支撐 |

**圖表型態偵測（保守策略）：**

| 型態 | 偵測演算法 |
|:---|:---|
| W 底（雙底） | 近 N 日找 2 個相近低點（誤差 < 3%），中間有反彈高點 |
| M 頭（雙頂） | 近 N 日找 2 個相近高點（誤差 < 3%），中間有回落低點 |
| 頭肩（選配） | 三峰結構，中間最高，兩側對稱（複雜度高，列為選配） |

偵測不到時明確標示「未形成標準 X 型態」，不硬套。

**多週期分析：** 將日 K resample 為週 K / 月 K，對每個週期分別跑趨勢判讀。`strength` 依據 MA 排列 + RSI 位置分為「強 / 中強 / 中 / 弱」。

**驗收指標：**
- pandas-ta `cdl_pattern` 正確辨識已知型態 fixture
- W 底/M 頭 fixture 正確偵測，非型態 fixture 正確標示「未形成」
- 多週期 resample 正確，週/月趨勢判讀符合預期
- 資料不足時不 crash

**狀態（2026-05-10）：** ✅ 已驗收完成。`tests/test_pattern.py` = 15 passed。

---

#### 8-C　籌碼分析管線（2-3 天）

**建置內容：** 三大法人買賣超 + 融資融券資料接入，產出籌碼分析摘要與籌碼集中度指標。

**新增管線：**

| 資料 | FinMind Dataset | 儲存 | 免費 |
|:---|:---|:---|:---|
| 三大法人買賣超 | `TaiwanStockInstitutionalInvestorsBuySell` | Parquet + DuckDB meta | ✅ |
| 融資融券 | `TaiwanStockMarginPurchaseShortSale` | Parquet + DuckDB meta | ✅ |

**Fetcher 擴充：**

- `fetch_institutional(symbol, start_date)` → 三大法人買賣超
  - FinMind 原始為 long format（每日每法人一筆 row），單位為**股**
  - `name` 值：`Foreign_Investor` / `Foreign_Dealer_Self` / `Investment_Trust` / `Dealer_self` / `Dealer_Hedging`
  - normalize 時 pivot 為 wide format：外資 = Foreign_Investor + Foreign_Dealer_Self；自營商 = Dealer_self + Dealer_Hedging
  - 回傳欄位：`date, foreign_buy, foreign_sell, foreign_net, trust_buy, trust_sell, trust_net, dealer_buy, dealer_sell, dealer_net, symbol`
- `fetch_margin(symbol, start_date)` → 融資融券
  - FinMind 原始為 wide format（每日一筆 row），單位為**張**
  - 回傳欄位：`date, margin_buy, margin_sell, margin_balance, short_buy, short_sell, short_balance, symbol`

**Storage 擴充：**

- `save_institutional()` / `load_institutional()` → `data/raw/tw/{symbol}/institutional.parquet`
- `save_margin()` / `load_margin()` → `data/raw/tw/{symbol}/margin.parquet`

**籌碼更新策略（混合模式）：** on-demand 為主（確保一定有資料），抓完後落地 Parquet。下次查同一檔時先檢查本地資料最後日期，只增量補抓缺少天數。maintenance 可批次更新已追蹤的股票清單。

**新增模組：** `src/analysis/chip_analysis.py`

**輸出：** `ChipSummary` dataclass，含三大法人近 N 日淨買賣（張）、籌碼集中度/趨勢（法人版估算）、融資融券餘額變化。

**資料單位規則：**
- 法人資料 storage 存股數，analysis/UI 顯示時 `// 1000` 轉張數
- 融資融券 storage 直接存張數
- UI 標籤必須寫清楚「法人版籌碼估算」

**驗收指標：**
- `fetch_institutional` 回傳 wide format，欄位與單位正確
- `fetch_margin` 回傳正確欄位
- 儲存/載入 round-trip 一致
- 增量補抓邏輯正確（本地有 30 天，只補抓之後的）
- ChipSummary 各欄位依規則填入

**狀態（2026-05-10）：** ✅ 已驗收完成。`tests/test_chip_analysis.py` = 14 passed。

---

#### 8-D　即時行情接入（1-2 天）

**建置內容：** TWSE MIS 公開 API 即時報價，產出頂部行情條與買賣力道估算。

**新增模組：** `src/data/realtime.py`

**API 端點（技術已確認）：** 只需一個端點 `mis.twse.com.tw`，用 `ex_ch` 的 `tse_` / `otc_` prefix 區分上市/上櫃。

| 市場 | `ex_ch` 格式 |
|:---|:---|
| 上市（tse） | `tse_{symbol}.tw` |
| 上櫃（otc） | `otc_{symbol}.tw` |

上市 / 上櫃判斷：FinMind `TaiwanStockInfo` 的 `type` 欄位（`twse` → `tse_`、`tpex` → `otc_`），啟動時載入一次快取。

**SSL 注意：** TWSE 憑證缺 Subject Key Identifier，僅可對 `mis.twse.com.tw` 單一 host scoped `verify=False`，不得全域關閉 TLS 驗證。

**TWSE API 欄位映射：**

| API key | 意義 | 解析方式 |
|:---|:---|:---|
| `c` | 股票代碼 | 直接取 |
| `n` | 股票名稱 | 直接取 |
| `z` | 成交價 | `float(z)`，`"-"` 時為無成交 |
| `y` | 昨收 | `float(y)` |
| `o` / `h` / `l` | 開盤/最高/最低 | `float()` |
| `v` | 累積成交量（張） | `int(v)` |
| `t` | 最後成交時間 | `"HH:MM:SS"` |
| `b` / `a` | 五檔買價/賣價 | `"_"` 分隔，filter 空字串 |
| `g` / `f` | 五檔買量/賣量 | `"_"` 分隔，filter 空字串 |

`change` 和 `change_pct` 由本地計算。

**快取策略：** 同一 symbol 在 `cache_ttl`（預設 10 秒）內重複查詢直接回 cache。

**config.yaml 新增：**

```yaml
realtime:
  cache_ttl: 10
  request_timeout: 5
```

**買賣力道估算：**
- 盤中：五檔買賣量總量比
- 盤後：`(close - open) / (high - low)` 近似
- UI 標示「買賣力道估算」或「多空力道估算」，不得直接標為「內外盤」

**盤後 fallback：** `is_market_open = False`，UI 顯示「盤後資料」標籤。

**驗收指標：**
- 上市/上櫃路由正確
- API 回傳正確解析（含 `"-"` 無成交處理）
- 快取在 TTL 內命中
- 盤後不 crash，正確標示

**狀態（2026-05-10）：** ✅ 已驗收完成。`tests/test_realtime.py` = 13 passed。

---

#### 8-E　AI 綜合分析與操作劇本（2-3 天）

**建置內容：** 用 AIAdvisor 生成產業/公司概況、量價結構增強版文字、隔日操作劇本（三情境）、整體結論。

**前提：** 依賴 8-A（技術面數據）+ 8-C（籌碼數據）。`ai.enabled=false` 時 8-E 不呼叫外部 AI；Dashboard 的 Tab 4 仍必須顯示，內容降級為「AI 功能未啟用」與 8-A 的 rule-based 結論，不得留空。

**AIAdvisor 擴充：**

新增 `generate_stock_dashboard_analysis()` tool-use function，輸入 TechnicalSummary + ChipSummary + 公司資料 + 近 60 日 OHLCV，輸出 `DashboardAnalysis`。

**輸出結構：**
- `industry_overview: list[str]` — 3-5 個 bullet points
- `company_overview: list[str]` — 3-5 個 bullet points
- `volume_price_analysis: str` — 2-3 句自然語言分析
- `scenarios: list[TradingScenario]` — 3 個情境（name / entry_range / stop_loss / target）
- `conclusion: str` — 1 句話總結

**Prompt 設計原則：**
- structured output（tool_use / JSON mode）
- 注入 8-A 技術面 + 8-C 籌碼摘要
- AI 不得自行編造數字，必須基於已提供數據
- 操作劇本價位必須基於 8-A 支撐壓力計算結果
- 劇本定位為「研究情境推演」，不使用「建議買進 / 必買 / 保證」語氣
- 每次輸出附短免責：非投資建議，僅供研究與風險控管參考

**降級策略：**

| 條件 | 行為 |
|:---|:---|
| `ai.enabled = false` | service 不呼叫 provider；UI catch 停用狀態並顯示「AI 功能未啟用」+ rule-based 結論 |
| AI 呼叫失敗 | UI catch 受控錯誤並顯示 `st.warning` + rule-based 結論 |
| 無籌碼資料 | 仍可運作，prompt 省略籌碼段 |

**驗收指標：**
- AI 回傳格式可解析為 DashboardAnalysis
- 操作劇本價位在合理範圍（基於支撐壓力）
- `ai.enabled=false` 時不 crash
- AI 失敗時降級正確

---

#### 8-F　個股儀表板 UI（3-4 天）

**建置內容：** 新增 `src/ui/pages/dashboard.py`，以 tab 分頁呈現個股綜合分析。

**頁面進入流程：**
1. 使用者輸入股票代碼
2. 點擊「分析」按鈕
3. 系統依序載入：日 K → 即時報價 → 技術面判讀 → 籌碼 → AI 分析
4. 以 tab 分頁呈現結果

**Tab 分頁規劃：**

| Tab | 內容 | 來源 |
|:---|:---|:---|
| Tab 1：總覽 | 頂部行情條、日 K 線圖 + MA + 支撐壓力、技術分析總覽、關鍵價位、短線綜合分數、「重新整理報價」按鈕 | 8-A + 8-D |
| Tab 2：籌碼與量價 | 法人近 5/10/20 日買賣超、籌碼集中度、融資融券、買賣力道、量價結構 | 8-C + 8-D + 8-A |
| Tab 3：型態與週期 | K 線型態表、W 底/M 頭分析、多週期分析 | 8-B |
| Tab 4：AI 劇本 | 產業/公司概況、量價分析、三情境操作劇本、整體結論 | 8-E |

`ai.enabled=false` 時 Tab 4 仍顯示但內容降級。

**排版原則：**
- 每個 tab 內 1~2 屏
- `st.columns` 2~3 欄排版
- `st.metric` 數字卡片
- 不注入大量 CSS hack

**側邊欄整合：** `option_menu` 新增「個股分析」入口，排在「回測」之後。

**主題相容：** 使用 `get_plotly_template()` 取得對應配色。

**驗收指標：**
- 輸入股票代碼 → 4 個 tab 皆正確渲染
- 即時報價正確顯示（盤中/盤後）
- AI 區塊降級正確
- 6 套主題皆相容
- 不影響現有回測/設定/AI 問答頁面

---

#### 8-G　新手友善說明文字（0.5-1 天）

**建置內容：** 在儀表板 UI 的所有 tab 中加入中文說明文字，讓股市新手也能理解每個指標、術語與分析結果的含義。不修改任何 analysis 模組或計算邏輯，純 UI 層文字新增。

**依賴：** 8-F（在 8-F 建好的儀表板上加說明）。

**設計原則：**

| 原則 | 說明 |
|:---|:---|
| 不影響進階使用者 | 說明文字使用 `st.metric(help=...)` tooltip 或 `st.caption`，不佔主要版面空間 |
| 集中管理 | 所有說明文字以 dict 常數集中在 `dashboard.py` 頂部，方便維護與翻譯 |
| 不改 analysis 模組 | 說明文字僅在 UI 層（`dashboard.py`），不擴充 dataclass 或修改計算邏輯 |
| 語氣中立 | 說明以教學為目的，不含任何投資建議語氣 |

**涵蓋範圍：**

**Tab 1 總覽：**

| 位置 | UI 元素 | 說明方式 | 說明內容摘要 |
|:---|:---|:---|:---|
| 技術分析總覽 — 趨勢方向 | `st.metric` | `help` tooltip | MA5/MA20/MA60 排列關係；多頭=短>中>長均；空頭反之；交錯=盤整。移動平均線概念簡介 |
| 技術分析總覽 — 均線狀態 | `st.metric` | `help` tooltip | 多頭排列/空頭排列/均線糾結各自的含義與市場訊號 |
| 技術分析總覽 — KD 狀態 | `st.metric` | `help` tooltip | KD（隨機指標）原理、K 與 D 值範圍 0~100、黃金交叉/死亡交叉定義、高低檔鈍化含義、本系統使用 K=9 D=3 smooth=3 |
| 技術分析總覽 — MACD 狀態 | `st.metric` | `help` tooltip | DIF（12日-26日 EMA 之差）與 DEA（DIF 的 9 日 EMA）定義、正值/負值擴張收斂的四種組合含義 |
| 技術分析總覽 — 量能狀態 | `st.metric` | `help` tooltip | 今日量 vs 近5日均量倍數；放大/正常/略縮/爆量門檻；量能是價格燃料的概念 |
| 技術分析總覽 — 量價關係 | `st.metric` | `help` tooltip | 價漲量增/價漲量縮/價跌量增/價跌量縮四種組合的市場訊號意義 |
| 壓力區 | 標題旁 | `st.caption` | 壓力區概念：股價向上可能遇到賣壓的價位；本系統取近60日/20日最高價 |
| 支撐區 | 標題旁 | `st.caption` | 支撐區概念：股價向下可能獲得買盤的價位；本系統取近期低點、MA20、MA60 |
| 短線綜合分數 | 進度條下方 | `st.caption` | 四面向加權公式：MA 結構 30% + KD 位置 25% + 量價關係 25% + 突破狀態 20%；分級含義：70% 以上強勢偏多、50% 以上且未滿 70% 中等偏多、30% 以上且未滿 50% 中性、未滿 30% 偏空 |

**Tab 2 籌碼與量價：**

| 位置 | UI 元素 | 說明方式 | 說明內容摘要 |
|:---|:---|:---|:---|
| 外資近N日 | `st.metric` | `help` tooltip | 外國機構投資人身份、台股最大法人、買超/賣超意義、含避險與 ETF 調倉 |
| 投信近N日 | `st.metric` | `help` tooltip | 投資信託公司（共同基金）身份、波段操作特性 |
| 自營商近N日 | `st.metric` | `help` tooltip | 券商自營部門、短線操作特性、含避險部位 |
| 籌碼集中度/趨勢 | 文字下方 | `st.caption` | 法人連續同向買入=集中（偏多）；連續同向賣出=分散（偏空）；交錯=穩定 |
| 融資餘額變化 | `st.metric` | `help` tooltip | 融資=借錢買股概念、散戶指標、融資大增而股價不漲為警訊 |
| 融券餘額變化 | `st.metric` | `help` tooltip | 融券=借股票賣（放空）概念、融券回補（軋空）可能推升股價 |
| 買賣力道估算 | `st.metric` | `help` tooltip | 五檔掛單量推算、掛單可撤銷限制、非精確內外盤統計 |
| 量價結構 — 第1行 | 量價背離/同步 | `st.caption` | 量價背離意義（動能不足或賣壓消退）、量價同步意義（趨勢可靠） |
| 量價結構 — 第2行 | MA20 乖離 | `st.caption` | 乖離率公式 (close-MA20)/MA20×100%、偏高/偏低門檻 ±3%、均值回歸概念 |
| 量價結構 — 第3行 | 操作觀察 | `st.caption` | 此文字為 rule-based 自動產生，非 AI 生成，不構成投資建議 |

**Tab 3 型態與週期：**

| 位置 | UI 元素 | 說明方式 | 說明內容摘要 |
|:---|:---|:---|:---|
| 10 種 K 棒型態 | 每個偵測到的型態 | `st.caption` | 詳細解釋該型態的形態特徵、偵測演算法、市場訊號含義（見下方詳表） |
| W 底/M 頭 | 型態結果下方 | `st.caption` | 雙底/雙頂的完整圖形解釋、頸線概念、目標價計算方式 |
| 日/週/月線趨勢 | `st.metric` | `help` tooltip | 各週期代表的時間尺度、resample 方式、趨勢一致性判讀 |
| 趨勢強度 | 標題區 | `st.caption` | 強度由 MA 排列 + RSI 綜合判斷的規則 |

**K 棒型態詳細說明對照表：**

| 型態 | 原有短說明 | 新增詳細說明 |
|:---|:---|:---|
| 長紅 K | 多方力道 | 當日實體超過近 20 日平均實體的 2 倍且為陽線（收盤 > 開盤）。代表多方佔明顯優勢，若出現在低檔可能暗示反轉向上 |
| 長黑 K | 空方力道 | 當日實體超過近 20 日平均實體的 2 倍且為陰線（收盤 < 開盤）。代表空方佔明顯優勢，若出現在高檔可能暗示反轉向下 |
| 十字線 | 多空拉鋸 | 開盤價與收盤價幾乎相同（實體極小），代表多空勢均力敵。出現在趨勢末端時常被視為反轉訊號，需配合後續走勢確認 |
| 錘子 | 反轉訊號 | 下影線超過實體 2 倍以上、上影線極短。出現在下跌趨勢中暗示下方有買盤接手，可能反轉向上，形態像一把錘子「打底」 |
| 吊人 | 反轉訊號 | 形態與錘子相同但出現在上漲趨勢中。暗示盤中有大幅下殺但收回，多方力道可能已在消耗，需警覺反轉風險 |
| 吞噬 | 反轉確認 | 今日 K 棒實體完全覆蓋前日實體。多頭吞噬（前陰後陽）暗示多方反攻；空頭吞噬（前陽後陰）暗示空方壓制，是較強的反轉確認 |
| 晨星 | 強反轉 | 三根 K 棒組合：長黑 → 小實體 → 長紅（收盤超過第一根中點）。出現在下跌趨勢中，暗示空方力竭、多方接手，強烈底部反轉 |
| 夜星 | 強反轉 | 晨星的反向型態：長紅 → 小實體 → 長黑。出現在上漲趨勢中，暗示多方力竭、空方介入，強烈頂部反轉 |
| 帶上影線 | 上檔壓力 | 上影線超過實體 2 倍以上。盤中買方推高股價後遇賣壓回落。上影線越長，上檔壓力越重，可能暗示短期高點 |
| 帶下影線 | 下檔支撐 | 下影線超過實體 2 倍以上。盤中賣方壓低後遇買盤接手回升。下影線越長，下檔支撐越強，可能暗示短期有底 |

**W 底/M 頭詳細說明：**

| 型態 | 詳細說明 |
|:---|:---|
| W 底（雙底） | 股價在相近價位形成兩個低點（誤差 < 3%），中間有反彈高點，形成 W 字形。突破頸線（兩低點間反彈高點）時確認型態成立。上漲目標約為頸線到低點距離的等幅上漲 |
| M 頭（雙頂） | 股價在相近價位形成兩個高點（誤差 < 3%），中間有回落低點，形成 M 字形。跌破頸線（兩高點間回落低點）時確認型態成立。下跌目標約為高點到頸線距離的等幅下跌 |

**不使用 AI：** 純 UI 層文字常數，`ai.enabled=false` 時照常運作。

**不修改 analysis 模組：** 所有說明文字集中在 `dashboard.py` 的常數 dict，不擴充 `TechnicalSummary`、`CandlePattern`、`ChipSummary` 等 dataclass。

**驗收指標：**
- 所有說明文字 dict 包含完整 key（不遺漏任何指標/型態）
- `_PATTERN_DETAILS` 所有型態說明皆為非空字串
- `st.metric(help=...)` tooltip 在 hover 時正確顯示
- `st.caption()` 在對應區塊下方正確顯示
- K 棒型態詳細說明在偵測到的型態旁正確顯示
- 現有 Phase 8 測試不受影響（不改 analysis 模組）
- 6 套主題下說明文字可讀

---

#### Phase 8 已知限制

| 限制 | 影響 | 降級方案 |
|:---|:---|:---|
| 無券商分點資料 | 主力追蹤精度降級 | 用三大法人淨買賣超替代 |
| 無 tick 資料 | 無法精確區分內外盤 | 五檔報價估算 + 日頻多空近似 |
| Streamlit 排版 | 無法單屏 12 面板 | Tab 分頁（4 tabs），每 tab 1~2 屏 |
| TWSE MIS API 穩定性 | 偶爾回應慢或被擋 | 快取 + 逾時 fallback 到日頻收盤 |
| AI 分析依賴外部 API | API key 缺失或額度用完 | 降級到純 rule-based |
| 操作劇本接近交易建議 | 可能誤解為實盤指令 | 明確標為研究情境推演 + 免責文字 |

---

### Phase 9：美股 US-1 支援

#### Phase 9 定位

Phase 9 的目標是把系統從「台股專用」擴充為「台股為主、可研究美股」的多市場架構。9-A 到 9-F 的第一版稱為 **US-1**，只支援美股日 K、調整後價格、回測與技術分析，不處理任何需要即時授權、交易所延遲規範或複雜跨幣別結算的功能。9-G 在 US-1 基礎上新增 **yfinance 1m intraday 盤中快照與分 K 圖**，定位為研究用途的近似盤中資料，不等同券商或交易所即時報價。

**US-1 正式支援：**

- 美股股票與 ETF：例如 `AAPL`、`MSFT`、`NVDA`、`SPY`、`QQQ`、`VOO`。
- 美股 class shares ticker：例如 UI 可接受 `BRK.B`，內部正規化為 `BRK-B`。
- 美股日 K raw data 與 adjusted daily data。
- 回測頁選擇美股後，可使用既有策略跑日線回測。
- 個股分析頁選擇美股後，可使用技術面總覽、K 線圖、型態辨識、多週期趨勢與 AI 劇本。
- 資料管理頁選擇美股後，可手動更新 / 重建日 K。

**US-1 明確不做：**

- 不做美股即時行情、盤前盤後即時、買一 / 賣一、五檔報價或 WebSocket。
- 不做美股分 K、tick、option、期貨或 crypto。
- 不做籌碼、法人、融資融券、券商分點或 short interest。
- 不做美股財報、基本面、產業分類或 ETF 成分股。
- 不做 USD/TWD 匯率換算，所有美股回測與報表均以 USD 呈現。
- 不做實盤下單與券商串接。
- 不支援非美股 suffix，例如 `.L`、`.TO`、`.HK`。

**9-G 擴充後仍明確不做：**

- 不做 WebSocket streaming。
- 不做買一 / 賣一、五檔、逐筆 tick 或 order book。
- 不宣稱 yfinance 1m close 是交易所正式即時成交價。
- 不做美股盤前 / 盤後分段分析；第一版只取 regular session，`prepost=False`。
- 不把美股 intraday 資料用於長期回測；yfinance intraday 歷史深度有限，僅供近期盤中分析與圖表。

#### Phase 9-A：多市場基礎架構

**目標：** 系統正式引入 `market` 概念，讓 `tw` 與 `us` 可以共用資料、回測與 UI 管線；台股既有流程必須維持預設且不退化。

**市場設定：**

| market | 顯示名稱 | timezone | currency | lot size | volume 顯示 | 主要資料源 |
|:---|:---|:---|:---|---:|:---|:---|
| `tw` | 台股 | `Asia/Taipei` | `TWD` | 1000 股 | 張 / 股依畫面語意 | FinMind + yfinance fallback |
| `us` | 美股 | `America/New_York` | `USD` | 1 股 | shares | yfinance |

**資料路徑：**

```text
data/raw/{market}/{symbol}/daily.parquet
data/raw/{market}/{symbol}/minute.parquet          # US-1 不使用
data/processed/{market}/{symbol}/adj_daily.parquet
```

**DuckDB metadata：**

`data_meta` 必須把 `market` 納入資料列與主鍵：

```sql
PRIMARY KEY (market, symbol, freq)
```

既有台股 metadata 若缺少 `market`，遷移時視為 `tw`。

**設計要求：**

- `market` 預設值仍為 `tw`，避免破壞既有呼叫。
- Storage、DataMaintenance、回測資料載入、資料管理頁與個股分析資料載入均需傳遞 `market`。
- timezone 不得再假設全系統只有 `Asia/Taipei`；所有 datetime 仍必須 timezone-aware。
- `symbol` 驗證必須與 `market` 綁定，並保留路徑穿越防護。
- 單一執行流程必須只存在一個明確 `market` context。回測頁單次 run、個股分析單次 payload、資料管理單次更新皆不得混合 `tw` 與 `us` DataFrame。
- US-1 不做跨市場 portfolio、跨市場 concat、跨市場 benchmark 或台美資料對齊。若未來需要跨市場比較，必須另開 phase，先定義統一 timezone / currency / calendar 對齊規則。

#### Phase 9-B：美股日 K 資料管線

**目標：** 美股日線可以透過 yfinance 抓取、清洗、存 raw、產生 adjusted daily，並支援增量更新與重建。

**資料源規格：**

- Provider：`yfinance`
- 支援顆粒度：daily only
- 不支援 minute；若 caller 對 `market="us"` 請求 minute，應回傳友善的 `NotImplementedError` / `FetcherError`，不得默默抓取不完整資料。
- yfinance 屬第三方非官方資料源，定位為個人研究用途，不保證商用品質或即時準確性。
- 美股批次更新需節流。DataMaintenance 或資料管理頁若一次更新多個 `market="us"` symbol，每個 yfinance request 間隔至少 1 秒，避免觸發 429 Too Many Requests 或短暫封鎖。

**Ticker 正規化：**

| 使用者輸入 | 內部 symbol |
|:---|:---|
| `aapl` | `AAPL` |
| `SPY` | `SPY` |
| `brk.b` | `BRK-B` |
| `BRK-B` | `BRK-B` |

第一版只允許美股常見 ticker 格式：英文字母、數字、單一 `-` 或單一 `.` class share 表示法。不得允許 `/`、`\`、`..`、絕對路徑或交易所 suffix。

**標準欄位：**

`STANDARD_COLUMNS` 不變：

| 欄位 | 型別 | 說明 |
|:---|:---|:---|
| `date` | timezone-aware datetime | 美股為 `America/New_York` 交易日 |
| `open` | float64 | 開盤價 |
| `high` | float64 | 最高價 |
| `low` | float64 | 最低價 |
| `close` | float64 | 收盤價 |
| `volume` | int64 | 成交股數 shares |
| `symbol` | str | 正規化 ticker |

**調整後價格：**

台股回測維持現有行為（使用 raw daily）。美股回測與技術分析預設使用 `processed/us/{symbol}/adj_daily.parquet`。調整方式：

```text
price_adjustment_ratio = Adj Close / Close
adjusted_open  = Open  * price_adjustment_ratio
adjusted_high  = High  * price_adjustment_ratio
adjusted_low   = Low   * price_adjustment_ratio
adjusted_close = Adj Close
```

**成交量調整：**

美股 adjusted daily 的 `volume` 必須使用 split-adjusted shares，避免拆股前成交量在 OBV、量能放大 / 縮小判讀中被低估。

成交量不可直接用 `Adj Close / Close` 反向調整，因為 `Adj Close` 可能包含股利調整，不一定只反映股票分割。正確規則是使用 split-only factor：

```text
adjusted_volume = raw_volume * cumulative_split_factor
```

或等價表示：

```text
adjusted_volume = raw_volume / split_only_price_ratio
```

其中 `cumulative_split_factor` / `split_only_price_ratio` 必須只來自 split events，不得混入 dividend adjustment。

若 yfinance 回傳資料缺少 `Adj Close` 或 `Close` 無法計算價格比例，則保存 raw OHLCV 作為 fallback，但 UI / log / 回傳狀態需標示「本次使用未調整價格」。若無法取得 split events 或無法確認 split factor，則不得宣稱 volume 已完成 split-adjust；所有 volume-dependent 指標與說明（OBV、量能放大 / 縮小、量價結構）必須顯示資料限制提示，或改用 raw volume 路徑並標示限制。

#### Phase 9-C：美股回測支援

**目標：** 回測頁可選擇美股市場，輸入美股 ticker，使用 adjusted daily 執行既有策略回測。

**UI 規格：**

- 既有回測頁新增 `市場` selector：`台股` / `美股`。
- 預設市場維持 `台股`。
- 選擇美股時，輸入提示改為 `AAPL / MSFT / SPY / BRK.B`。
- 美股資料不存在或過舊時，自動更新 `market="us"` 日 K。
- 報表幣別顯示 `USD`，不得顯示 `TWD` 或 `張`。
- 美股 DCA 介面需顯示提示：「US-1 DCA 最小買入單位為 1 整股，不支援碎股。若每月投入金額低於股價，該期可能不會買進。」

**成本模型：**

| 項目 | 台股 | 美股 US-1 |
|:---|:---|:---|
| 幣別 | TWD | USD |
| 最小交易單位 | 1000 股為一張；DCA 可 1 股 | 1 股 |
| tick size | 台股級距 | `0.01` |
| 證交稅 | 賣出課稅 | 0 |
| ETF 稅率 | 台股 ETF 特例 | 不另分 |
| 預設手續費 | config `commission_rate` + discount | 0（硬編碼） |

既有 `CostCalculator` 改名 `TWCostCalculator`，新增 `USCostCalculator` 與 `create_cost_calculator(market)` factory。US-1 美股成本參數（commission=0、tax=0、tick_size=0.01）硬編碼於 `USCostCalculator`，不開放 config.yaml 調整。若 US-2 需要支援券商分層費率或 SEC fee / TAF / ADR fee，再於 config.yaml 新增 `backtest.us` 區段。

**策略支援：**

既有日線策略可共用：MA、RSI、KD、MACD、BBANDS、BIAS、Donchian、DCA。若策略內存在台股交易單位或台股成本假設，需改為從市場設定讀取。

#### Phase 9-D：美股技術分析儀表板

**目標：** 既有個股分析頁可選美股，顯示純技術分析與 AI 劇本；台股專屬即時 / 籌碼功能在美股模式停用。

**美股模式啟用：**

- 技術面總覽
- 日 K 圖與 K 棒數量切換
- MA / KD / MACD / 量價結構
- K 線型態與 W 底 / M 頭
- 日 / 週 / 月多週期趨勢
- AI 綜合分析與操作劇本（若 AI enabled）

**美股模式停用：**

- TWSE MIS 即時行情
- 買一 / 賣一
- 盤中量
- 三大法人
- 融資融券
- 籌碼 tab 內容

美股成交量以 shares 顯示，不得轉換為台股「張」。美股畫面需標註日期以紐約交易日為準。

AI 劇本語言固定為繁體中文。即使市場為美股、ticker 為英文、幣別為 USD，`AIAdvisor` prompt 仍必須明確要求模型完全使用繁體中文輸出，建議在 prompt 結尾加入：

```text
You must reply entirely in Traditional Chinese (zh-TW).
```

#### Phase 9-E：資料管理頁美股支援

**目標：** 資料管理頁可選美股並手動更新 / 重建日 K。

**UI 規格：**

- 新增 `市場` selector。
- 台股模式維持現有日 K / 分 K / 籌碼相關能力。
- 美股模式只顯示日 K 更新 / 重建與資料狀態。
- 美股分 K 顯示停用提示：「US-1 尚未支援美股分 K」。
- 顯示資料來源、資料起訖日、筆數、最後更新時間、是否使用調整後價格。

#### Phase 9-F：整合回歸與文件收束

**目標：** Phase 9 完成後更新文件與測試指南，確認台股既有功能未退化，美股 US-1 功能可手動驗收。

**需更新文件：**

- `量化交易系統規格書_shellpig版.md`
- `開發設計方針.md`
- `測試指南.md`
- `PROJECT_BRIEF.md`（Phase 9 實作或驗收完成後再更新，不在規格討論稿先動）

**Phase 9 已知限制：**

| 限制 | 影響 | 降級方案 |
|:---|:---|:---|
| yfinance 非官方資料源 | 資料可能延遲、缺漏或欄位變動 | 明確標示研究用途；必要時 US-2 改接付費資料源 |
| yfinance request rate limit | 批次更新多檔美股可能觸發 429 或短暫封鎖 | 美股批次更新每檔間隔至少 1 秒；429 顯示外部資料源限制 |
| split factor 缺失 | adjusted volume 無法保證與 split-adjusted price 對齊，OBV / 量能判讀可能失真 | 不宣稱 volume 已 split-adjust；量能相關指標顯示資料限制提示 |
| US-1 不支援美股即時 | 9-A~9-F 個股分析無盤中價格 | 使用最新日 K 收盤資料；9-G 以 yfinance 1m close 補近似盤中價 |
| US-1 不支援美股分 K | 9-A~9-F 無法顯示 intraday 圖 | 9-G 顯示近期 yfinance 1m 分 K；仍不做 intraday 策略回測 |
| 不支援籌碼 / short interest | 美股分析缺少資金面 | 美股 dashboard 僅顯示技術面與 AI 劇本 |
| 不做匯率換算 | 無台幣資產總覽 | 報表全部以 USD 呈現 |
| 不做財報 / 基本面 | 無 EPS 或營收輔助 | 後續另開基本面資料 phase |

#### Phase 9-G：美股 yfinance 盤中快照與分 K 圖

**目標：** 個股分析頁在美股交易時間可顯示接近盤中的價格、漲跌、成交量與日內分 K 圖，不再只停留在前一個完整日 K 收盤價。

**資料源與語意：**

- Provider：`yfinance`
- 主要呼叫：`period="1d"`, `interval="1m"`, `prepost=False`, `auto_adjust=False`
- 支援 interval：第一版 UI 顯示 `1m`，可預留 `5m / 15m / 60m` 圖表切換，但不得把長期 intraday 回測納入 9-G。
- yfinance intraday 資料歷史深度受限，僅供近期盤中分析。
- timestamp 必須轉為 `America/New_York`，並保留 timezone-aware。
- 判斷 intraday 最新 bar 是否屬於「今日」時，一律以 `America/New_York` 當前日期為準，不得使用 UTC 日期或台北日期。
- UI 必須標示「美股盤中價使用 yfinance 最新 1 分 K 收盤價，可能延遲，僅供研究分析」或等價文案。

**API 決策：**

- 9-G 必須新增專用 intraday API，例如 `fetch_us_intraday(...)`。
- `fetch_minute(..., market="us")` 維持 US-1 拒絕行為，不因 9-G 改成允許。
- 原因：台股分 K 與美股 yfinance intraday 的資料來源、限制、cache 策略與語意不同，不應混用同一 public API。

**盤中行情顯示規則：**

| 欄位 | 9-G 顯示規則 |
|:---|:---|
| 現價 | 今日 regular session 最新一根 1m bar 的 raw `close` |
| 昨收 | 前一紐約交易日 raw daily `close` |
| 漲跌 | `intraday_raw_close - previous_raw_daily_close` |
| 漲跌幅 | `漲跌 / previous_raw_daily_close` |
| 成交量 | 今日 regular session 1m volume 加總，單位 shares；從 pandas 加總後明確 cast 成 Python `int` |
| 狀態 | `盤中分K資料` 或 `近似盤中價` |
| 時間 | 顯示最新 1m bar timestamp，標註紐約時間 |

盤中行情 metrics 必須使用 raw 尺度，因為 yfinance 1m intraday close 是 raw market price。不得用 raw intraday close 去對 adjusted daily close 計算漲跌，避免除息或調整因子造成漲跌幅失真。既有技術分析、日 K 圖與 AI 劇本預設仍可使用 adjusted daily。

若 1m intraday 抓取失敗、回傳空資料、非美股交易時間或最新 bar 非今日紐約交易日，dashboard 必須自動降級回 9-D 的 adjusted daily 顯示，並提示資料來源限制。

**分 K 圖：**

- 個股分析總覽 tab 新增日內分 K 圖，位置放在既有日 K 圖之前。
- 預設顯示今日 regular session 1m K。
- K 線圖 x 軸使用紐約時間，不轉台北時間。
- 盤中圖表只影響 dashboard 顯示；技術面 summary、型態辨識、多週期趨勢與 AI 劇本預設仍使用 adjusted daily。若 AI 要納入 intraday snapshot，需在 prompt payload 明確標示資料是 `intraday_snapshot`，不得與日 K close 混用。

**9-G 不做：**

- 不接 yfinance WebSocket。
- 不做買一 / 賣一、五檔或 order book。
- 不做 tick / 秒級資料。
- 不做 intraday 策略回測。
- 不將 intraday parquet 作為長期歷史資料庫；若需要落地，僅可保存近期 cache，並標明 yfinance 資料深度限制。
- 不做盤前 / 盤後分 K；`prepost=False`。

---

### 子階段總覽

| Phase | 子階段 | 工期 | 有 AI 輔助 |
| :--- | :--- | :--- | :--- |
| **1** 資料基礎建設 | 1-A → 1-D（4 段） | 7 天 | ✅ |
| **2** 向量化回測 | 2-A → 2-D（4 段） | 5 天 | ✅ |
| **3** 事件驅動引擎 | 3-A → 3-E（5 段） | 12 天 | ✅ |
| **4** AI 問答 + UI | 4-A → 4-D（4 段） | 5 天 | ✅ |
| **5** 回測體驗與 UI 補充 | 5-A → 5-B（2 段） | 3-5 天 | ✅ |
| **6** UI/UX 強化 | 6-A → 6-B（2 段） | 1.5-3 天 | ✅ |
| **7** 策略擴充 | 7-A → 7-D（4 段） | 9.5-14 天 | |
| **8** 個股綜合分析儀表板 | 8-A → 8-G（7 段） | 11.5-18 天 | ✅ |
| **9** 美股 US-1/9-G 支援 | 9-A → 9-G（7 段） | 9.5-15.5 天 | ✅ |
| **10** 前端架構重構 | 10-A → 10-H（8 段） | 15-25 天 | ✅ |
| **合計** | 47 個子階段 | **79-109.5 天（約 16-22 週）** | |

---

## 12. 費用估算

| 項目 | 費用 | 說明 |
| :--- | :--- | :--- |
| **FinMind API（免費層）** | 免費 | 每日 3,000 次請求；初期夠用 |
| **LLM API（AI 問答）** | 約 $1-5 USD/月 | 依 provider、模型與問答頻率而定 |
| **yfinance** | 免費 | 非官方 API；台股 fallback 與 Phase 9 美股 US-1 日 K 資料源，使用量大時有被封或欄位變動風險 |
| **美股付費資料源（US-2 以後可選）** | 暫不納入 | US-1 不採購；若 yfinance 品質不足，再評估 Polygon、Alpha Vantage 或其他供應商 |
| **Streamlit（本機）** | 免費 | 本機 localhost 運行；Phase 10-H 移除後不再使用 |
| **Next.js + FastAPI（本機）** | 免費 | Phase 10 起取代 Streamlit，本機 localhost 運行 |
| **合計（初期）** | 約 $1-5 USD/月 | ≈ NT$30-150/月 |

**費用升級觸發條件：**
- 若 FinMind 免費層不足 → 升級付費方案（NT$300/月），可取得完整歷史分K
- 若 LLM API 費用過高 → 增加 prompt caching 優化、切換較便宜模型、或限制每日問答次數
- 若美股資料品質或穩定性不足 → 另開 US-2，評估付費美股資料源（Polygon、Alpha Vantage 等）；US-1 既有功能不受影響，US-2 只擴充資料源與成本精度，不修改 US-1 已有流程；不得在 US-1 偷偷擴大資料商依賴

---

### Phase 10：前端架構重構 — Streamlit → Next.js

#### Phase 10 定位

Phase 10 將 UI 從 Streamlit 遷移至 Next.js (React) + FastAPI，解決 Streamlit 的根本限制：單欄流式佈局、手機體驗差、每次互動整頁重跑、互動性受限、Plotly 大量 K 線效能瓶頸。

**改版目標：**

1. **資訊密度提升** — 單頁同時呈現更多分析資訊，減少頁面切換
2. **手機可操作** — 手機瀏覽器可查看行情、檢視分析結果、瀏覽回測報告
3. **視覺品質** — 接近 TradingView / Bloomberg Terminal 的專業金融工具質感
4. **操作流暢** — 局部更新、即時回應、無整頁閃爍
5. **核心演算法不重寫** — `src/` 下分析、回測、資料、策略演算法完全保留；`src/ui/pages/` 中混雜的非渲染邏輯抽離至 `src/services/` 服務層

#### 技術選型

| 類別 | 選型 | 理由 |
|:---|:---|:---|
| 前端框架 | Next.js 15+ / React 19+ / TypeScript 5+ | 生態系最大、元件化、App Router layout 嵌套 |
| 樣式系統 | Tailwind CSS v4 | Mobile-first responsive、原子化、shadcn/ui 原生整合 |
| UI 元件庫 | shadcn/ui (Radix UI) | 直接複製原始碼可自訂、accessibility 合規、Dark/Light 原生 |
| 金融圖表 | Lightweight Charts (TradingView 開源) | Canvas 渲染效能高、十字線/多圖同步/觸控操作 |
| 輔助圖表 | Recharts | 非金融圖表（回測績效 bar chart 等） |
| 後端 API | FastAPI | async、自動 OpenAPI 文件、型別檢查 |
| 資料 fetching | SWR ≥2 | React data fetching + 快取 |
| 套件管理 | pnpm ≥9 | 比 npm 快；OneDrive 衝突時退回 npm |

**資料傳輸協定：**

| 場景 | 協定 |
|:---|:---|
| 一般查詢（技術分析、回測結果、設定讀寫） | REST JSON |
| 美股 / 台股行情輪詢 | REST JSON + 前端 polling (SWR) |
| 回測進度 | Server-Sent Events (SSE) |

#### 系統架構

```
使用者瀏覽器 (PC / 平板 / 手機)
  └── Next.js 前端 (web/, localhost:3000)
        │ HTTP REST / SSE
        ▼
      FastAPI 後端 (api/, localhost:8000)
        └── src/services/ 服務層（10-A 新增）
              └── src/ 核心模組（演算法不重寫）
                    └── DuckDB + Parquet (data/) + config.yaml
```

三者（Streamlit / FastAPI / Next.js）在 10-H 前可同時運行互不干擾。

#### 專案目錄規劃

Phase 10 新增三個主要目錄：

| 目錄 | 說明 |
|:---|:---|
| `src/services/` | 服務層：從 `src/ui/pages/` 抽離的非渲染邏輯（payload 組裝、自動補抓、回測資料同步、config 讀寫） |
| `api/` | FastAPI 後端 API 層：`main.py` + `deps.py` + `routers/`（analysis, backtest, data, ai, config, realtime, jobs） |
| `web/` | Next.js 前端：App Router、shadcn/ui 元件、Lightweight Charts 圖表、TypeScript 型別 |

新增測試目錄：`tests/test_services/`、`tests/test_api/`。

#### 子階段拆分

Phase 10 拆為 **10-A ~ 10-H** 八個子階段，每個可獨立驗證。

| 子階段 | 名稱 | 依賴 | 說明 |
|:---|:---|:---|:---|
| **10-A** | 服務層抽離 + FastAPI 後端骨架 | — | `src/services/` 抽離 4 個 service、FastAPI app + CORS + health + config + data/symbols + Job manager |
| **10-B** | Next.js 前端骨架 | scaffold 可平行；驗收依賴 10-A | 專案初始化、layout、sidebar、theme、routing、api-client、market-switcher、stock-selector |
| **10-C** | 資料管理頁 | 10-A, 10-B | 資料 CRUD API + 前端資料管理頁面 + DELETE 端點（新功能） |
| **10-D** | 個股分析儀表板 | 10-A, 10-B | K 線圖（Lightweight Charts）、技術分析、型態、籌碼、AI 劇本、聚合端點 |
| **10-E-1** | 單次回測 | 10-A, 10-B, **10-G-1** | 單次回測 Job + SSE、5 metric card tearsheet、K 線 + MA + buy/sell markers、equity curve、trades 表；建立 form / K 線 / tearsheet 元件供 10-E-2~4 重用；使用 10-G-1 的 toast / skeleton / error boundary / command palette |
| **10-E-2** | 策略比較（批次） | 10-E-1 | 批次比較 Job + SSE、比較表（10 欄）、多策略 equity 疊圖（lightweight-charts 多 LineSeries）、單列展開詳細結果（重用 10-E-1 tearsheet）；toast 通知完成 / 取消 / 失敗 |
| **10-E-3** | 參數掃描 | 10-E-2 | 參數掃描 Job + SSE（throttle）、排名表（含 sample_warning）、2D heatmap（僅 2 參數時）、組合數 ≤ 200 限制、取消按鈕；CSV 匯出；toast 通知完成 / 取消 |
| **10-E-4** | Walk-Forward Analysis | 10-E-3 | WFA Job + 巢狀 SSE（window × IS sweep）、Summary / Window / Stability 三表、Degradation 顯示、CSV 匯出；toast 通知完成 / 取消 / 資料不足錯誤 |
| **10-F-1** | AI 問答頁 UI shell（不接 LLM） | 10-A, 10-B | Chat UI 完成（免責聲明 gate / 訊息泡泡 / Markdown / Mock 逐字串流）；後端 `/api/ai/chat` 回 503、`/api/ai/status` 回 feature_locked；sidebar 加「後續開放」徽章；package version bump 至 `0.2.0` |
| **10-F-2** | AI 問答頁接 LLM（延後） | 10-F-1 | 補 `AIAdvisor.stream_chat()` Anthropic / OpenAI / Gemini 三 adapter；`POST /api/ai/chat` 改為真實 SSE token 串流；不卡 10-G / 10-H |
| **10-G-1** | 基礎設施先行（Toast / Error Boundary / Skeleton / Command Palette） | 10-A, 10-B, 10-C-2（既有 banner 來源）| 為 10-E 4 段預先建立全局元件：`sonner` toast 系統（拔 `@radix-ui/react-toast`）+ React Error Boundary + 3 種 Skeleton 變體 + `cmdk` Command Palette（頁面跳轉 + 股票搜尋）；10-C-2 既有 5 處 banner 全部改 toast |
| **10-E-1~4** | 回測工作台 4 段 | 10-G-1 | 見上表 |
| **10-G-2** | 設定頁主功能（API Key / 策略 preset / 主題 / AI toggle） | 10-G-1, 10-E（4 段全部驗收後） | SettingsPage 4 分區實作：API key write-only UI、策略 preset CRUD UI（搭配 `POST /api/config/strategies` upsert + `DELETE /api/config/strategies/{name}` + `POST /api/config/strategies/restore`）、Dark↔Light 主題切換（`next-themes`）、AI toggle disabled + tooltip |
| **10-H** | 舊 UI 移除與收尾 | 10-G-2 驗收後 | 移除 `src/ui/`、Streamlit 依賴、測試遷移檢查表、文件更新 |

10-A 與 10-B 的 scaffold 工作可同時進行；10-B 開發階段使用 mock data，最終驗收依賴 10-A。

#### 10-A：服務層抽離 + FastAPI 後端骨架

**服務層抽離（`src/services/`）：**

| 來源 | 目標 service | 關鍵函式 |
|:---|:---|:---|
| `src/ui/pages/dashboard.py` | `dashboard_service.py` | `build_dashboard_payload`、`prepare_daily_data`、`prepare_chip_data`、`fetch_us_intraday_snapshot` |
| `src/ui/pages/backtest.py` | `backtest_service.py` | `build_strategy`、`load_backtest_data`、`run_backtest_job` |
| `src/ui/pages/data_management.py` | `data_service.py` | `run_maintenance`、`get_symbol_status`、`list_symbols` |
| `src/ui/pages/settings.py` | `config_service.py` | `read_config`、`update_config`、`update_secrets`、`get_secrets_status` |

服務層函式回傳結果物件或錯誤物件，不直接操作 UI（不含 `st.error()`、`st.session_state` 等）。Streamlit 頁面與 API router 各自負責將結果轉成 UI 或 HTTP 回應。

**FastAPI 骨架：**

- `api/main.py`：FastAPI app 入口，CORS middleware（允許 `localhost:3000`）
- `api/deps.py`：共用依賴注入（Config、Storage）
- `api/routers/config.py`：`GET /api/config`、`PUT /api/config`、`PUT /api/config/secrets`
- `api/routers/data.py`：`GET /api/data/symbols?market=tw`
- `api/routers/jobs.py`：`POST /api/jobs`、`GET /api/jobs/{id}/events` (SSE)、`GET /api/jobs/{id}/result`、`POST /api/jobs/{id}/cancel`
- `api/job_manager.py`：in-memory Job manager（queue、狀態追蹤、寫入鎖、TTL 清除）
- `GET /api/health`：健康檢查

**Job manager 與 Write lock：**

個人單機使用，同時最多 1 個寫入型 job。所有回測 job 均視為寫入型（因 `load_backtest_data` 會 auto-sync 寫入 Parquet/DuckDB）。`DELETE /api/data/` 與 `GET /api/dashboard/payload` 也須取得 write lock。Lock 忙碌時立即回傳 `409 Conflict`。Job 結果 TTL 30 分鐘。

**驗收條件：**

1. `src/services/` 四個 service 建立完成
2. 舊 Streamlit UI 改為呼叫 `src/services/`，行為不變
3. `uvicorn api.main:app --reload` 啟動成功
4. `GET /api/health` 回傳 `{"status": "ok"}`
5. `GET /api/config` 回傳 config（不含 secrets）
6. `GET /api/data/symbols?market=tw` 回傳已存在的台股標的清單
7. Job lifecycle：`POST /api/jobs` → `GET .../events` SSE → `GET .../result`
8. `POST /api/jobs/{id}/cancel` 可取消 running job
9. 同時提交 2 個寫入型 job，第 2 個回傳 `409 Conflict`
10. 服務層測試 `tests/test_services/` 通過
11. API 端點測試 `tests/test_api/test_config_api.py`、`test_jobs_api.py` 通過

#### 10-B：Next.js 前端骨架

**產出：** `web/` 完整初始化（Next.js + Tailwind CSS + shadcn/ui）、Root layout（sidebar + theme provider）、5 個頁面路由空殼（dashboard / backtest / data / ai / settings）、`api-client.ts`、`market-switcher.tsx`、`stock-selector.tsx`。

**驗收條件：**

1. `pnpm dev` 啟動成功（localhost:3000）；OneDrive 衝突時 `.npmrc` 加 `package-import-method=copy`，仍失敗則改用 `npm`
2. 5 個頁面可透過 sidebar 切換，URL 對應正確
3. Dark / Light 主題切換即時生效
4. 手機寬度下 sidebar 收合為底部 tab bar
5. `api-client.ts` 可呼叫 10-A 的 `/api/health`
6. OneDrive 同步不報錯

#### 10-C：資料管理頁

10-C **拆為兩階段交付**：10-C-1 先做列表 + DELETE（不需擴充後端，全部 API 已實作），10-C-2 再補後端 Job dispatcher + 進度 SSE，落地更新 / 重建 / 新增。此拆分避免後端 `api/routers/jobs.py` 目前的 `NOT_IMPLEMENTED` gap 阻擋整體 UI 交付。

##### 10-C-1：列表 + DELETE（不需擴充後端）

**範圍：**
- 前端 [web/src/app/data/page.tsx](web/src/app/data/page.tsx) 對齊 [web/_design/data-mockup.tsx](web/_design/data-mockup.tsx) 視覺稿完整實作（含 Dark/Light）
- DELETE 確認 Dialog（**單步確認**：警示文案 + 取消／確認刪除兩顆按鈕；不需輸入代碼解鎖）

**對應後端 API（均已實作，10-C-1 不動）：**
- `GET /api/data/symbols?market={tw|us}` — 列表
- `GET /api/data/status/{market}/{symbol}` — 單一 symbol 的 raw + adjusted 狀態
- `DELETE /api/data/{market}/{symbol}` — 刪除本機 Parquet + DuckDB metadata（含 write lock 處理；被佔回 `409`；不存在回 `404`；不刪 `data/backtest/`）

**stage-2 功能的 UI 預留（10-C-1 須做）：**
- 「全部更新」「全部重建」「動作欄·更新」「+ 新增標的」四類按鈕：**顯示但 disabled + tooltip「Phase 10-C-2 開發中」**
- 視覺與 mockup 一致，使用者看得到完整 UI 也理解暫不能點

**狀態 badge 三態判定（前端依 `end_date` 計算）：**
- **最新**：`end_date == 最近交易日`
- **需更新**：`end_date 落後 1~5 交易日`
- **缺資料**：`end_date 落後 > 5 日` 或區間中有缺口（`row_count < expected`）

**美股顯示規則：**
- 單列顯示，名稱旁加 `raw+adj` 小型標記（不展開兩列）
- 切到美股顯示 callout：「美股僅支援日 K（資料來源：yfinance）；US-1 範圍不含分 K 與籌碼資料」

**驗收條件：**
1. 市場切換正確、列表完整顯示 **6 欄**（代碼 / 名稱 / 區間 / K 棒數 / 狀態 / 動作）。**「大小」(MB) 欄已從規格移除**：本機 parquet 檔案大小不影響使用者決策，徒增後端 `os.path.getsize` 與 race condition 風險，移除以縮 scope。**「名稱」欄目前以 symbol code 作 fallback**（後端 `list_symbols` 暫不補 name 欄；如需中文名稱呈現，後續另議）
2. 狀態 badge 三態正確著色
3. 美股 callout 與 `raw+adj` 標記到位
4. DELETE 流程：列按鈕 → 確認 Dialog（警示文案完整）→ 確認 → 列表 refresh + 成功 toast
5. stage-2 四類按鈕全 disabled，hover 顯示 tooltip
6. 對應前端 vitest 元件測試與後端 `test_data_api.py` 全綠

##### 10-C-2：更新 / 重建 / 新增（需擴充後端 Job dispatcher）

**新增 / 修改後端：**
- `api/job_manager.py`（或 `api/routers/jobs.py` 的 dispatcher 區塊）擴充支援：
  - `job.type == "data_update"` → 呼叫 `src.data.maintenance.update_daily`
  - `job.type == "data_rebuild"` → 呼叫 `src.data.maintenance.rebuild_symbol`
  - 批次模式：`params` 支援 `{ market: str, symbols?: list[str], all?: bool }`；給 `symbols` 跑指定清單、`all=true` 跑該市場全部
- 進度 SSE：每完成一個 symbol 推一筆 `event: progress`，全部結束推一筆 `event: result`

**SSE 訊息格式：**
```
event: progress
data: { "current": 3, "total": 10, "current_symbol": "2330", "status": "updating" }

event: progress
data: { "current": 3, "total": 10, "current_symbol": "2330", "status": "done" }

event: progress
data: { "current": 4, "total": 10, "current_symbol": "2317", "status": "failed", "error": "Network timeout" }

event: result
data: { "succeeded": ["2330", ...], "failed": [{ "symbol": "2317", "error": "..." }] }
```

**新增前端元件：**
- `web/src/components/data/AddSymbolDialog.tsx` — 「+ 新增標的」彈窗，**複用既有 `StockSelector` 元件**（代碼或名稱皆可輸入），送出後觸發 `data_update` job
- `web/src/components/data/RebuildConfirmDialog.tsx` — 「全部重建」二次確認 Dialog（破壞性操作，比照 DELETE 風格）
- `web/src/hooks/useDataJob.ts` — 接 SSE，回傳 `{ status, current, total, current_symbol, succeeded, failed }`

**失敗處理策略：**
- 批次中**單檔失敗**：跳過繼續其他 symbol、**不中斷整批**
- 全部完成後 toast 顯示：「成功 X 檔／失敗 N 檔：[2317, 0050]」

**動作欄·更新（單檔）：**
- 走相同的 `data_update` job、batch_size=1（`symbols=[該檔]`、`all` 不設）
- UI 進度條同樣顯示，但 current/total 都是 1，視覺更簡潔

**驗收條件：**
1. `POST /api/jobs` 帶 `type: "data_update"` / `"data_rebuild"` 不再回 `NOT_IMPLEMENTED`
2. 「全部更新」→ 單一全局進度條（顯示 X／Y）→ 結束 toast
3. 「全部重建」→ 二次確認 Dialog → 確認後執行
4. 「動作欄·更新」→ 單檔 SSE 流程（current=1, total=1）→ 完成 toast
5. 「+ 新增標的」→ 彈窗 → 輸入代碼或名稱（StockSelector）→ 送出 → 觸發 download → 完成後新代碼出現在列表
6. 批次中單檔失敗：其他 symbol 繼續處理，最終 toast 列出失敗代碼清單
7. 對應後端測試 `test_data_jobs_api.py` 全綠

#### 10-D：個股分析儀表板

改版核心頁面，用 Lightweight Charts 取代 Plotly。

**API 設計：**

- 聚合端點 `GET /api/dashboard/payload` — 頁面初載用，一次取得全部
- 細部端點 `GET /api/analysis/{technical|pattern|chip|daily}` — 局部刷新用
- `GET /api/realtime/{tw|us/intraday}` — 重新整理報價用
- `POST /api/ai/analyze` — AI 分析獨立觸發

**圖表實作：** K 線 + MA 疊加、成交量獨立圖、技術指標副圖（KD/RSI/MACD），全部時間軸同步。台股紅漲綠跌、美股綠漲紅跌。日 K 使用 business day string `"YYYY-MM-DD"`，美股 intraday 使用 `timestamp_utc` (UTC epoch 秒) + `exchange_tz`。

**Responsive 佈局：** PC ≥1280px 左右分欄（圖表 70% + 技術摘要面板），手機 <768px 全寬堆疊 + 底部 tab bar。

#### 10-E：回測研究工作台

10-E **拆為 4 個子階段交付**：10-E-1（單次）→ 10-E-2（批次）→ 10-E-3（掃描）→ 10-E-4（WFA）。每段獨立驗收。**10-E 開工前必須完成 10-G-1（基礎設施先行）**，4 段共用 10-G-1 的：

- **Toast 系統** — 所有 SSE job 的 complete / cancelled / error 統一走 toast（不再寫 inline banner）；10-C-2 既有的失敗清單 banner 也在 10-G-1 階段遷移為 toast
- **Error Boundary** — 整個 `BacktestPage` 用 Error Boundary 包住；只接 React render / lifecycle / hook 例外。fetch / SSE / invalid JSON 錯誤由 hook 設為 `status="error"`，顯示頁內錯誤區並走 toast
- **Loading Skeleton** — 載入態用 shadcn `Skeleton`：K 線 / equity / tearsheet 卡 / 表格各一份 skeleton 變體
- **Command Palette（Ctrl+K）** — 頁面跳轉支援「單次回測 / 策略比較 / 參數掃描 / Walk-Forward」四個 entry；股票搜尋已含

所有 4 段共用：

- **Job lifecycle**：`POST /api/jobs` → `GET /api/jobs/{id}/events`（SSE 進度）→ `GET /api/jobs/{id}/result`，比照 10-C-2 `_run_data_job` 模式
- **取消行為**：`POST /api/jobs/{id}/cancel`；服務層 `run_*_job` 在每個迴圈點檢查 `manager.get_job(job.id).status == "cancelled"` 後 break，最後以 `finish_cancelled_job(result=partial_result)` 保持 job status 為 `cancelled` 並保留已完成 partial result；`GET /api/jobs/{id}/result` 對 `complete` / `cancelled` 都可回傳 result（`cancelled` 且無 result 才回 409）
- **市場 / 貨幣 / 單位**：透過 `MarketSwitcher` 切換，前端 formatter 處理 USD vs TWD。**交易數量單位統一顯示「股」（shares）**，不做 1000 股 → 1 張的換算（與舊 Streamlit 回測頁一致；「張」僅用於 10-D 儀表板的日成交量與籌碼顯示）
- **初始資金預設值**：`initial_capital` 預設 `1000000`（前端 number input 預設值 + 後端缺省值皆為此值）
- **共用前端元件**：建立於 10-E-1，供 2~4 重用
  - `web/src/components/backtest/TearsheetCards.tsx` — 5 metric card（交易次數 / 總報酬率 / 年化報酬率 / 最大回撤 / Sharpe）
  - `web/src/components/backtest/CandleChartWithMarkers.tsx` — Lightweight Charts K 線 + MA 疊加 + buy/sell markers（綠 ↑ / 紅 ↓）
  - `web/src/components/backtest/EquityCurveChart.tsx` — Lightweight Charts 單線或多線 equity 圖
  - `web/src/components/backtest/TradesTable.tsx` — 交易明細表（shadcn Table，paginated）
  - `web/src/components/backtest/StrategyPresetSelect.tsx` — 策略 preset 下拉
  - `web/src/components/backtest/DateRangePicker.tsx` — 日期區間
  - `web/src/components/backtest/BacktestProgressBar.tsx` — 進度條（重用 10-C-2 `ProgressBar` 樣式）
- **明確不做**：老 Streamlit 第 5 個 tab「歷史結果」（Next.js SWR cache 後切頁狀態不會掉，迫切性降低；若日後有需要可在 10-H 後另議）
- **明確不做**：drawdown / monthly / summary 副圖（老頁面 plotly 三圖）；以 5 metric card 取代彙整

##### 10-E-1：單次回測

**範圍：**
- 前端 [web/src/app/backtest/page.tsx](web/src/app/backtest/page.tsx) 建立 4 tab 框架（單次 / 比較 / 掃描 / WFA），但 10-E-1 只實作「單次」tab
- 10-E-2~4 三個 tab 顯示為 disabled + tooltip「Phase 10-E-{N} 開發中」（比照 10-C-1 模式）

**後端：**
- `POST /api/jobs` 接 `type="backtest_run"`；params 如下表
- 服務層擴充 `src/services/backtest_service.py` 既有 `run_backtest_job()`，加入 cancellation token + 進度回呼
- Job dispatcher [api/routers/jobs.py](api/routers/jobs.py) 新增分支 `_run_backtest_run_job`
- 因單次回測極短（< 1 秒），SSE 只推 `running` → `complete`，**不分割多個 progress 事件**

**params schema：**
```json
{
  "market": "tw" | "us",
  "symbol": "2330" | "AAPL",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "strategy_preset_index": 0,
  "engine": "vectorized" | "event_driven",
  "initial_capital": 1000000
}
```
**`strategy_preset_index`** 指向 `config.yaml` 的 `strategies[]` 索引；前端 `StrategyPresetSelect` 透過 `GET /api/config` 取得 preset 清單後讓使用者挑選，送 index 給後端。

**result schema：**
```json
{
  "symbol": "2330",
  "market": "tw",
  "currency": "TWD",
  "engine": "vectorized",
  "strategy_type": "moving_average_cross",
  "strategy_params": { "short_window": 20, "long_window": 60 },
  "metrics": {
    "total_trades": 15,
    "total_return": 0.345,
    "annual_return": 0.0876,
    "max_drawdown": -0.182,
    "max_drawdown_start": "2022-04-21",
    "max_drawdown_end": "2022-10-13",
    "sharpe_ratio": 0.92,
    "win_rate": 0.467,
    "profit_factor": 1.85
  },
  "equity_curve": [
    { "date": "2020-01-02", "value": 1000000 },
    ...
  ],
  "trades": [
    { "entry_date": "2020-03-15", "exit_date": "2020-05-20", "side": "long",
      "entry_price": 285.5, "exit_price": 312.0, "shares": 1000,
      "pnl": 26500, "return_pct": 0.0928 },
    ...
  ],
  "price_data": [
    { "date": "2020-01-02", "open": 332, "high": 334, "low": 330, "close": 333,
      "volume": 27345000 },
    ...
  ],
  "signals": [
    { "date": "2020-03-15", "side": "buy", "price": 285.5 },
    { "date": "2020-05-20", "side": "sell", "price": 312.0 }
  ],
  "dca_warning": null
}
```

**Tearsheet 5 metric card：**
- 交易次數（整數，DCA 顯示「定期定額不適用」）
- 總報酬率（百分比，紅色 = 負）
- 年化報酬率（百分比，紅色 = 負）
- 最大回撤（百分比，永遠紅色或灰）
- Sharpe（小數兩位）
- 副標：「幣別：TWD」或「幣別：USD」

**K 線 + Markers：**
- 與 10-D `CandlestickChart` 同基底，加入 `series.setMarkers([{ time, position, color, shape, text }])`
- 買入：`position: "belowBar"`, `color: green`, `shape: "arrowUp"`, `text: "B"`
- 賣出：`position: "aboveBar"`, `color: red`, `shape: "arrowDown"`, `text: "S"`
- 台股紅漲綠跌、美股綠漲紅跌（重用 `--chart-up` / `--chart-down` CSS 變數）
- 顯示 MA 疊加（依 strategy_type 自動帶對應的 MA 線；無 MA 策略時不顯示）
- 預設視野最後 6 個月

**Equity curve：**
- 單線 `LineSeries`，X 軸與 K 線同期
- Hover tooltip 顯示日期 + equity 值

**Trades 表：**
- 6 欄：日期區間 / 方向 / 進場價 / 出場價 / 數量 / PnL（含 return_pct）
- shadcn `Table`，前端 sort 與 paginate（每頁 20 筆）
- 台股與美股交易數量統一顯示「股」（引擎回傳單位即為股，不轉換為張）

**驗收條件：**
1. 4 tab 框架建立，「單次回測」可用；10-E-2/3/4 tab disabled + tooltip
2. 表單：MarketSwitcher / StockSelector / DateRangePicker / EngineSelect / StrategyPresetSelect / 初始資金（number input）/ 開始回測按鈕
3. 送出後 `POST /api/jobs` 取得 job_id，SSE 顯示 running → complete；完成 < 5 秒
4. Tearsheet 5 metric card 顯示正確值與幣別
5. K 線顯示買賣點 markers，台股紅漲綠跌、美股綠漲紅跌
6. Equity curve 與 K 線時間軸對齊
7. Trades 表 sortable 與 paginated
8. DCA preset：顯示 `dca_warning`、無 trades 表、equity 用 DCA 結果替代
9. 取消按鈕：job 狀態變 `cancelled`；**Toast 顯示「回測已取消」**
10. 美股回測（AAPL）：USD 顯示、無「張」字、cost calculator 用 `USCostCalculator`
11. **Job complete 時 toast「回測完成」**；**Job error 時 toast 錯誤色 + 結果區域顯示 error.message**
12. **載入態 skeleton**：job running 期間，tearsheet / K 線 / equity / trades 四區各顯示對應 skeleton；SSE result 到後同步替換
13. **Error Boundary**：模擬 React render throw，主內容顯示 fallback「執行發生錯誤，請重試」，sidebar 不消失；SSE 中斷 / invalid JSON 改由結果區域顯示 error.message + toast
14. **Command Palette**：Ctrl+K 開啟後可看到「回測：單次 / 策略比較 / 參數掃描 / Walk-Forward」四個導航項
15. 對應後端測試 `test_backtest_api.py`（≥ 8 cases）+ 前端 vitest（≥ 5 檔 / ≥ 25 cases）全綠

##### 10-E-2：策略比較（批次）

**範圍：**
- 10-E-1 的「策略比較」tab 解 disable
- 後端服務層新增 `run_batch_backtest_job()`，包裝既有 `src/backtest/batch.py` `run_strategy_batch()`
- Job dispatcher 新增 `type="backtest_batch"` 分支

**params schema：**
```json
{
  "market": "tw" | "us",
  "symbol": "2330",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "strategy_preset_indices": [0, 1, 2, 3, 4, 5, 6, 7],
  "initial_capital": 1000000
}
```
- 預設全選 8 個 preset；前端可勾選子集
- DCA preset 視為「不支援批次比較」，後端回傳該 row `error="DCA 不支援批次比較（請至單次回測使用）"`，前端表格 row 數值欄顯示「—」+ 備註欄文案

**SSE 進度訊號：** 每完成一個策略推一筆 `progress`：
```
event: progress
data: { "current": 3, "total": 8, "current_preset_name": "RSI_14", "status": "running" }
event: progress
data: { "current": 3, "total": 8, "current_preset_name": "RSI_14", "status": "done" }
```

**result schema：**
```json
{
  "symbol": "2330", "market": "tw", "currency": "TWD",
  "start_date": "2020-01-01", "end_date": "2024-12-31",
  "initial_capital": 1000000,
  "summaries": [
    { "preset_name": "MA20_MA60", "strategy_type": "moving_average_cross",
      "total_return": 0.345, "annual_return": 0.0876, "max_drawdown": -0.182,
      "sharpe_ratio": 0.92, "win_rate": 0.467, "profit_factor": 1.85,
      "total_trades": 15, "error": null,
      "equity_curve": [...], "trades": [...], "signals": [...] },
    ...
  ]
}
```
- 每個 summary 包含完整 equity_curve / trades / signals（用於展開詳細）
- price_data 只附在 result 頂層一次（所有策略共用同一段股價）

**比較表（10 欄）：**
| 策略名稱 | 策略類型 | 總報酬 | 年化 | 最大回撤 | Sharpe | 勝率 | Profit Factor | 交易次數 | 備註 |
- shadcn `Table`，sortable
- 點 row → 展開區（lazy mount）顯示該策略的 tearsheet + K 線 + trades（複用 10-E-1 元件）

**多策略 equity 疊圖：**
- 一張 lightweight-charts，每個策略一條 `LineSeries`
- 顏色從預設 palette 取（最多 8 策略，色票需高對比）
- Legend 在圖下方或右上角
- Hover 同步十字線顯示所有策略當日 equity 值

**CSV 匯出按鈕：**
- `GET /api/jobs/{id}/result?format=csv` → 回 CSV blob（由 `api/routers/jobs.py` 既有 result endpoint 加 query 分支；後端產生，沿用 `save_batch_result_csv()` 邏輯）
- 前端 `<a download="batch_2330_20260515.csv">` 觸發下載

**驗收條件：**
1. 策略 multi-select 預設全選 8 個，可取消
2. 進度條顯示 `current / total preset_name`；**Skeleton 顯示在比較表 / 疊圖區域直到第一筆 progress 抵達**
3. 比較表顯示 10 欄、可排序、DCA row 顯示 error 備註
4. 多策略 equity 疊圖、十字線同步
5. 點 row 展開：tearsheet + K 線 + trades（複用 10-E-1 元件）
6. CSV 匯出；下載時 toast「已下載：batch_2330_20260515.csv」；job complete 時 toast「比較完成（N 成功 / M 失敗）」
7. 取消行為：跑到一半取消後，已完成的策略 result 仍保留、未跑的不在表中；**Toast「比較已取消（已完成 X/Y）」**
8. **Job error toast 錯誤色 + 結果區域顯示細節**
9. 對應後端測試 + 前端 vitest 全綠

##### 10-E-3：參數掃描

**範圍：**
- 10-E-1 的「參數掃描」tab 解 disable
- 後端服務層新增 `run_sweep_job()`，包裝既有 `src/backtest/sweep.py` `run_parameter_sweep()`
- Job dispatcher 新增 `type="backtest_sweep"` 分支
- `MAX_COMBOS = 200`（沿用既有常數）

**params schema：**
```json
{
  "market": "tw" | "us",
  "symbol": "2330",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "strategy_type": "moving_average_cross",
  "param_candidates": {
    "short_window": [5, 10, 20],
    "long_window": [40, 60, 120]
  },
  "initial_capital": 1000000
}
```
- 前端表單依 `strategy_type` 動態渲染參數輸入欄
- 每個參數一個 text input，使用者用逗號分隔輸入（`"5,10,20"`），前端 parse 後送 list
- 表單預設值取自既有 `_SWEEP_DEFAULTS`（移植到前端常數）
- 送出前前端 echo「總組合數 / 合法組合數 / 上限」訊息

**SSE 進度訊號 + throttle：**
- 每完成一個 combo 推一筆 progress
- **Throttle 規則**：若 `valid_combos > 50`，每 5 個 combo 才推一次（後端控制），UI 不會被 ≥1k 訊息淹沒
- 結束時推 `result` event

```
event: progress
data: { "current": 45, "total": 180, "current_params": { "short_window": 20, "long_window": 60 }, "status": "running" }
```

**result schema：**
```json
{
  "symbol": "2330", "market": "tw", "currency": "TWD",
  "strategy_type": "moving_average_cross",
  "start_date": "2020-01-01", "end_date": "2024-12-31",
  "total_combos": 200,
  "valid_combos": 180,
  "max_combos_limit": 200,
  "results": [
    { "params": { "short_window": 20, "long_window": 60 },
      "total_return": 0.345, "annual_return": 0.0876, "max_drawdown": -0.182,
      "sharpe_ratio": 0.92, "win_rate": 0.467, "profit_factor": 1.85,
      "total_trades": 15, "error": null, "sample_warning": false },
    ...
  ]
}
```
- 不包含完整 equity_curve / trades（資料量太大）；僅 metrics
- `sample_warning=true` 當 `total_trades < 3`

**前端視覺：**

1. **Top N 排名表**（預設 N=20）：
   - 欄位：排名 / 參數組合（多參數時用 chip 顯示）/ Sharpe / 總報酬 / 年化 / 最大回撤 / 勝率 / 交易次數 / 警告
   - sortable，預設按 Sharpe DESC
   - sample_warning 的 row 顯示警告 icon + tooltip「樣本數 < 3」
   - 點 row 不展開（不存個別 equity 資料）；如需詳細需回單次回測 tab 跑一次

2. **2D Heatmap**（僅當 `param_candidates` 恰好有 2 個 key 時顯示）：
   - 自製 CSS Grid + Tailwind 色階（綠 → 黃 → 紅 對應 Sharpe 高 → 低）
   - X / Y 軸為兩個參數值
   - cell hover 顯示 tooltip：完整 metrics
   - cell 點擊：複製該參數組合到剪貼簿（未來在單次回測 tab 貼上）
   - **不引入** Recharts / nivo / react-heatmap-grid 等套件
   - 3+ 參數時只顯示排名表

3. **CSV 匯出**：同 10-E-2 模式，後端產 blob

**驗收條件：**
1. 策略類型下拉切換時，參數輸入欄正確切換
2. 逗號分隔解析、預設值正確
3. 合法組合數提示與 200 上限警告（**> 200 時 toast 警告「合法組合數 N 超過上限 200」**）
4. 進度條顯示 `current / total`，> 50 組時 throttle 生效；**Skeleton 顯示在排名表 / heatmap 區域直到第一筆 progress**
5. 結果排名表（Top 20 預設）顯示、可排序、sample_warning 顯示警告 icon
6. 2 參數時顯示 heatmap，色階對應 Sharpe；3+ 參數時不顯示
7. 取消按鈕：跑到一半取消後，已完成的 combos result 仍保留；**Toast「掃描已取消（已完成 X/Y）」**
8. CSV 匯出；**完成 toast「掃描完成，共 N 個合法組合」**
9. 美股掃描（AAPL）：USD 與 cost calculator 正確
10. **Heatmap cell 點擊複製成功時 toast「參數已複製：short_window=20, long_window=60」**
11. 對應後端測試 + 前端 vitest 全綠

##### 10-E-4：Walk-Forward Analysis

**範圍：**
- 10-E-1 的「Walk-Forward」tab 解 disable
- 後端服務層新增 `run_walk_forward_job()`，包裝既有 `src/backtest/walk_forward.py` `run_walk_forward_analysis()`
- Job dispatcher 新增 `type="backtest_wfa"` 分支
- 沿用既有 `MAX_WFA_WINDOWS` / `MIN_WFA_WINDOWS` / `MAX_COMBOS` 常數

**params schema：**
```json
{
  "market": "tw" | "us",
  "symbol": "2330",
  "start_date": "2018-01-01",
  "end_date": "2024-12-31",
  "strategy_type": "moving_average_cross",
  "param_candidates": {
    "short_window": [5, 10, 20],
    "long_window": [40, 60, 120]
  },
  "is_months": 12,
  "oos_months": 3,
  "step_months": 3,
  "optimize_metric": "sharpe_ratio",
  "initial_capital": 1000000
}
```
- 表單在 10-E-3 基礎上加 IS / OOS / Step 月數 input 與 optimize_metric select
- 前端送出前估算「預估 N 段 × M 組合 = 最多 N×M 次回測」並顯示

**SSE 巢狀進度訊號：**
- 外層：每完成一個 window 推一筆 `window_progress`
- 內層：每完成一個 IS sweep combo 推一筆 `sweep_progress`（throttle 同 10-E-3）

```
event: window_progress
data: { "window_id": 2, "total_windows": 6, "phase": "is_sweep" }
event: sweep_progress
data: { "window_id": 2, "current": 45, "total": 180, "current_params": {...} }
event: window_progress
data: { "window_id": 2, "total_windows": 6, "phase": "oos_validate" }
event: window_progress
data: { "window_id": 2, "total_windows": 6, "phase": "done",
  "best_params": {...}, "oos_sharpe": 0.78 }
```

**result schema：**
```json
{
  "symbol": "2330", "market": "tw", "currency": "TWD",
  "strategy_type": "moving_average_cross",
  "optimize_metric": "sharpe_ratio",
  "total_window_count": 6,
  "valid_window_count": 6,
  "skipped_window_count": 0,
  "windows": [
    { "window_id": 1,
      "is_start": "2018-01-01", "is_end": "2018-12-31",
      "oos_start": "2019-01-01", "oos_end": "2019-03-31",
      "best_params": { "short_window": 20, "long_window": 60 },
      "is_metrics": { ... }, "oos_metrics": { ... },
      "degradation": -0.35, "skipped": false, "warnings": [] },
    ...
  ],
  "aggregate": {
    "oos_total_return": 0.42, "oos_annual_return": 0.072,
    "oos_max_drawdown": -0.15, "oos_sharpe_ratio": 0.65,
    "oos_win_rate": 0.51
  },
  "parameter_stability": {
    "params": {
      "short_window": { "values": [20, 20, 10, 20, 10, 20], "cv": 0.234 },
      "long_window": { "values": [60, 60, 120, 60, 60, 60], "cv": 0.298 }
    },
    "warning_count": 1
  }
}
```

**前端三表：**

1. **Summary（彙整）**：4-5 個 metric card（OOS 總報酬 / 年化 / 最大回撤 / Sharpe / 勝率）+ 額外「OOS / IS degradation 平均」chip

2. **Window 表**（每段視窗一行）：
   | # | IS 期 | OOS 期 | 最佳參數 | IS Sharpe | OOS Sharpe | Degradation | 警告 |
   - 以日期區間表示 IS / OOS
   - 最佳參數用 chip 群顯示
   - degradation 紅色 = 大幅退化

3. **Stability 表**（每參數一行）：
   | 參數名 | 各視窗的值 | CV（變異係數） | 穩定性 |
   - 各視窗的值用 chip group
   - CV 數字 + 穩定性標籤（< 0.2 = 穩定 / 0.2-0.5 = 中等 / > 0.5 = 不穩定）

**CSV 匯出：**
- 兩個 CSV 檔（沿用 `save_walk_forward_summary_csv()`）：
  - `wfa_window_{symbol}_{ts}.csv`：每段視窗一行
  - `wfa_stability_{symbol}_{ts}.csv`：每參數一行
- 後端 `GET /api/jobs/{id}/result?format=csv&part=window|stability` → 回 CSV blob（由 `api/routers/jobs.py` 既有 result endpoint 加 query 分支）
- 前端兩顆「匯出視窗表 CSV」/「匯出穩定性表 CSV」按鈕

**驗收條件：**
1. 表單 IS / OOS / Step 月數 + optimize_metric 下拉、預估視窗數顯示
2. 資料不足時前端顯示「需要 N 個月，目前 M 個月」警告，按鈕 disabled；**送出時若後端回 `INSUFFICIENT_DATA_FOR_WFA`，toast 錯誤色顯示**
3. 進度條：window N / total + 該 window 內的 sweep progress；**Skeleton 顯示在三表區域直到第一筆 window 完成**
4. Summary 5 card、Window 表、Stability 表全顯示
5. Degradation 紅色標示（< -0.3）
6. CV > 0.5 顯示「不穩定」標籤
7. 兩個 CSV 匯出按鈕都可下載；**下載觸發時 toast「CSV 已下載：wfa_window_2330_20260515.csv」**
8. 取消按鈕：跑到一半取消後，已完成的 windows 仍保留；**Toast「WFA 已取消（已完成 X/Y 段視窗）」**
9. 美股 WFA（AAPL）：USD、cost calculator 正確
10. **Job complete 時 toast「WFA 分析完成（N 段視窗）」**
11. 對應後端測試 + 前端 vitest 全綠

##### 10-E 實作前置修改（10-E-1 開工前必須完成）

以下 3 項為 10-E 的共用基礎設施修改，**必須在 10-E-1 實作前完成並驗證**：

1. **`JobManager.finish_cancelled_job()` 方法**：目前 [api/job_manager.py](api/job_manager.py) 尚未實作此方法。需新增（簽名見開發設計方針 §10-E），用於取消後保留 partial result 並關閉 SSE stream。
2. **`cancel_job()` 修改**：現有 `cancel_job()` 在設定 `status="cancelled"` 的同時會**立即關閉 event queue**，導致後續 service 迴圈 break 後推送的 partial result 無法送達。修改為：`cancel_job()` **只設 status，不關 queue**；改由 `finish_cancelled_job()` 統一關閉 queue。
3. **`GET /api/jobs/{id}/result` 允許 cancelled partial result**：現有 result endpoint 僅對 `status == "complete"` 回傳 result。需擴充：`status == "cancelled"` 且 `job.result` 存在時亦回傳 result（`meta.status` 帶 `"cancelled"`）；`cancelled` 且無 result 時回 409。

##### 10-E 策略 preset 端點

前端 `StrategyPresetSelect` 需要取得 preset 清單。**直接使用既有 `GET /api/config` 回傳的 `strategies[]` 陣列**（不另設 `/api/backtest/strategies` endpoint），避免冗餘端點。前端從 config response 取出 strategies 後顯示中文名稱，送回 `strategy_preset_index`。

##### 10-E 套件依賴（全段共用）

- **不引入新套件**：lightweight-charts（10-D 已用）、shadcn Table / Form / Select / Calendar / Tooltip / Dialog 均已存在於 web/
- **不引入** Recharts / nivo / react-heatmap-grid：批次 equity 疊圖用 lightweight-charts 多 LineSeries；heatmap 自製 CSS Grid

##### 10-E 通用錯誤碼

| 錯誤碼 | 觸發 | HTTP / Job error |
|:---|:---|:---|
| `INVALID_SYMBOL` | symbol 格式錯誤 | 422 |
| `NO_DATA` | 資料區間內無日線資料 | Job error |
| `NO_ADJUSTED_DATA` | 美股缺 adjusted 資料 | Job error |
| `INVALID_PARAMS` | 策略參數驗證失敗（如 short ≥ long） | Job error |
| `UNSUPPORTED_STRATEGY` | 不支援的 strategy_type | Job error |
| `OVER_MAX_COMBOS` | sweep / WFA 合法組合數 > 200 | 422 |
| `INSUFFICIENT_DATA_FOR_WFA` | 資料月數 < required_months | 422 |
| `JOB_CANCELLED` | 使用者取消 | Job status `cancelled`；若已有 partial result，`GET /api/jobs/{id}/result` 可回傳 |
| `WRITE_LOCK_BUSY` | 已有 backtest job 在跑 | 409 |

#### 10-F：AI 問答頁

10-F **拆為兩階段交付**：10-F-1 先做完整 UI shell 並把後端 chat 端點鎖死回 503（不接 LLM），10-F-2 才補上 `AIAdvisor.stream_chat()` 與真實 SSE token 串流。此拆分讓 AI 問答頁的視覺、訊息結構、免責聲明、Markdown 渲染、Mock token 動畫可先驗收完成，避開 LLM 串流 + tool use 的複雜度，並讓 10-G / 10-H 不必等 AI 功能落地就能往前推進。

##### 10-F-1：UI shell + 後端 lock（不接 LLM）

**範圍：**
- 前端 [web/src/app/ai/page.tsx](web/src/app/ai/page.tsx) 對齊 [web/_design/ai-chat.jsx](web/_design/ai-chat.jsx) 視覺稿完整實作（含 Dark/Light）
- **免責聲明 gate**：首次進入顯示「我了解」按鈕；接受後寫入 `localStorage`（key 命名 `ai_chat.disclaimer_accepted_v1`）持久；後續進頁不再顯示
- **訊息泡泡 + Markdown**：用 `react-markdown` + `remark-gfm` 渲染，支援 `**bold**`、`- list`、行內 code；user / assistant 兩種樣式（依 mockup 第 81-103 行）
- **Mock 逐字串流**：使用者送出 → 立即 push user message → 模擬 token by token 出現 assistant placeholder（每 20-40ms 一個 char，總長 < 5 秒），文案固定為「AI 串接尚未開放（這是 UI 預覽）。本訊息為模擬輸出，待 Phase 10-F-2 接上真實 LLM 後將改為串流逐字回應。」
- **訊息歷史**：純前端 React state，**刷新即清不持久化**（為與未來真 LLM 多輪對話保持一致，不引入 localStorage）
- **Header 狀態 chip**：顯示「AI · 未啟用」灰色 chip（不顯示 provider / model）
- **Sidebar AI 入口**：[web/src/components/sidebar.tsx](web/src/components/sidebar.tsx) 在「AI 問答」項目旁加灰色小徽章「後續開放」

**對應後端 API（新增最小骨架）：**
- `GET /api/ai/status` → `200 { available: false, reason: "feature_locked", message: "AI 功能尚未開放，將於後續版本啟用。" }`
- `POST /api/ai/chat` → `503 { error: { code: "AI_DISABLED", message: "AI 功能尚未開放。" } }`（不做 SSE）
- 既有 `POST /api/ai/analyze`（dashboard 隔日操作劇本用）保留現狀，AI off 時仍回 503

**設定頁 AI 鎖死的職責分工：**
- **不在 10-F-1 動設定頁**（目前仍是 Phase 10-B 留下的 placeholder shell）
- AI 開關 UI（toggle disabled + tooltip「AI 功能尚未開放」）與後端強制 `ai.enabled=false` 的 schema whitelist 一起留到 **10-G** 實作設定頁時處理
- 期間 `config.yaml` 維持 `ai.enabled: false` 預設值；使用者手動編檔仍可開，但前端任何 AI 路徑都會走「未啟用」分支（dashboard AI 劇本 503、chat 端點 503、status feature_locked）

**版號 bump：**
- 10-F-1 落地時 `pyproject.toml` 從 `0.1.0` → **`0.2.0`**
- `web/package.json` 從 `0.10.0` → **`0.2.0`**（與 py 對齊；放棄 Next.js scaffold 預設 0.10.0）
- 文件版號 → V2.4

**驗收條件：**
1. 進入 `/ai` 首次顯示免責聲明卡，點「我了解」後關閉並寫 `localStorage`；重新整理頁面不再顯示
2. Header 顯示「AI 問答」標題 + 副標 +「AI · 未啟用」灰色 chip
3. 輸入框可打字；按 Enter 或點送出後：user 泡泡立即出現、assistant 泡泡以逐字方式 push（20-40ms / char）出固定 placeholder 文案
4. Markdown 渲染：`**62.4**` 顯示粗體、`- 項目` 顯示清單
5. 訊息歷史保留在 state；F5 重整後清空
6. Sidebar「AI 問答」項目旁顯示灰色「後續開放」徽章
7. `GET /api/ai/status` 回 `feature_locked`、`POST /api/ai/chat` 回 503
8. 對應前端 vitest 元件測試與後端 `test_ai_api.py` 全綠（status / chat 503 / analyze AI off regression）

##### 10-F-2：接 LLM（延後實作）

**範圍：**
- `src/ai/advisor.py` 新增 `AIAdvisor.stream_chat(messages: list) -> AsyncIterator[str]`
- 三 adapter（`AnthropicAdapter` / `OpenAIAdapter` / `GeminiAdapter`）各自實作 `stream_complete()`
- `POST /api/ai/chat` 改為真實 SSE：`event: token data: {text: chunk}` 多筆 + `event: done data: {}`；error 時 `event: error data: {message: str}`
- `GET /api/ai/status` 改為依 `ai.enabled` + API key 設定動態回傳
- 前端 Mock chat hook 換成真實 EventSource / fetch ReadableStream
- 設定頁 AI toggle 解鎖（搭配 10-G 規格）

**已知待決問題（10-F-2 啟動時必須回答）：**
- Chat 模式是否啟用 tool use？（現有 `ask()` 跑 6 輪 tool；串流 + tool 是另一種典範）
- Messages payload 格式（OpenAI 標準 `[{role, content}]` 還是 provider-native？）
- 取消（abort）行為與 SSE error event 規格
- 多輪歷史是否在 10-F-2 改為 localStorage 持久化

**時程備註：**
- 10-F-2 **不卡 10-G / 10-H** 收尾；10-H 移除 `src/ui/` 時 `src/ai/advisor.py` 必須保留（10-F-2 與 dashboard analysis 都仍會用）

#### 10-G：設定頁 + 全局整合

10-G **拆為兩個子階段交付**：**10-G-1（基礎設施先行）→ 10-E（4 段）→ 10-G-2（設定頁主功能）**。10-G-1 的存在是為了讓 10-E 4 個 sub-stage 共用同一套 toast / skeleton / error boundary / command palette，避免每段各寫 inline banner 後再回頭重構。10-G-2 才做設定頁本身的主功能（API key / 策略 preset CRUD / 主題切換 / AI toggle）。

**Secrets 安全規則（10-G-2 適用）：** GET 永不回傳 API key 值；API key 只能透過 `PUT /api/config/secrets` write-only 寫入；`PUT /api/config` 走 schema whitelist；前端 API key 輸入框永遠為空，只顯示設定狀態。

##### 10-G-1：基礎設施（Toast / Error Boundary / Skeleton / Command Palette）

**範圍：** 提供 10-E 4 段所共同依賴的 4 種全局元件與 hook，並把 10-C-2 已落地的 banner 統一遷移為 toast；不動設定頁主功能（仍是 10-B 留下的 placeholder）。

**前置決定：**
- Toast 套件用 **`sonner`**（與規格 V2.3 寫的 shadcn Sonner 一致）；拔除 [web/package.json](web/package.json) 已裝但未使用的 `@radix-ui/react-toast`
- Toast 預設位置 **右下**、停留 **3 秒**，三個變體：**success / error / info**（與 [開發設計方針.md:7259-7273](開發設計方針.md:7259) 14 條 10-E toast 文案表對齊；Sonner 原生另支援 warning / loading / message，本階段不主動使用）
- Error Boundary **只接 React 例外**（render / lifecycle / hook 拋錯）；API 錯誤一律走 toast，不觸發 Error Boundary
- Command Palette 採 **`cmdk`** 套件（shadcn Command 預設底層），不自製
- 主題切換套件 **暫不裝**（`next-themes` 留到 10-G-2 真正做主題切換時再裝）；10-G-1 僅提供前述 4 種元件

**新增 / 修改檔案：**

| 檔案 | 動作 | 說明 |
|:---|:---|:---|
| `web/package.json` | 修改 | 新增 `sonner` 與 `cmdk`，移除 `@radix-ui/react-toast` |
| `web/src/components/providers.tsx` | 新增 | 全局 Provider wrapper（Sonner `<Toaster>` + CommandPalette mount + Theme provider 預留位） |
| `web/src/app/layout.tsx` | 修改 | 用 `<Providers>` 包住整個 app 樹 |
| `web/src/hooks/use-toast.ts` | 新增 | 封裝 `sonner` 為 `{ success, error, info, dismiss }` 介面（與 10-E 規格 [開發設計方針.md:6930](開發設計方針.md:6930) 對齊） |
| `web/src/components/error-boundary.tsx` | 新增 | React class 元件，接 `fallback` prop；附預設 fallback UI `<DefaultErrorFallback />` |
| `web/src/components/skeletons/index.tsx` | 新增 | 匯出 `CardSkeleton` / `ChartSkeleton` / `TableSkeleton` 三個 shadcn `Skeleton` 變體 |
| `web/src/components/command-palette.tsx` | 新增 | Command Palette 主元件（cmdk 包裝），Ctrl+K / Cmd+K 開啟、Esc 關閉、↑↓ 導航、Enter 觸發 |
| `web/src/hooks/use-command-palette.ts` | 新增 | 提供 `useCommandPaletteEntry({ id, label, action, group? })` hook（mount 時註冊、unmount 自動清除）與內部 store |
| `web/src/components/data/data-page-client.tsx` | 修改 | 把 10-C-2「全部更新 / 全部重建 / 新增 / 動作欄·更新 / DELETE」5 處 banner / inline 訊息全部改為 `useToast()` 呼叫 |
| `web/src/components/sidebar.tsx` | 修改 | 註冊 5 個頁面跳轉的 Command Palette entry（個股分析 / 資料管理 / 回測 / AI 問答 / 設定） |
| `web/src/components/stock-selector.tsx` | 修改 | 註冊「股票搜尋」群組 entry（資料來源走 `/api/data/symbols`） |
| `tests/test_api/` | （無新增） | 10-G-1 不動後端 |

**移除：**
- `@radix-ui/react-toast`（10-D 時為 Radix Tooltip 連帶裝入；Tooltip 在 `@radix-ui/react-tooltip` 不受影響）

**`useToast()` 介面合約：**

```typescript
// web/src/hooks/use-toast.ts
import { toast } from "sonner";

export type ToastApi = {
  success: (message: string, opts?: { duration?: number }) => void;
  error:   (message: string, opts?: { duration?: number }) => void;
  info:    (message: string, opts?: { duration?: number }) => void;
  dismiss: (id?: string | number) => void;
};

export function useToast(): ToastApi {
  return {
    success: (msg, opts) => toast.success(msg, { duration: opts?.duration ?? 3000 }),
    error:   (msg, opts) => toast.error(msg,   { duration: opts?.duration ?? 3000 }),
    info:    (msg, opts) => toast.info(msg,    { duration: opts?.duration ?? 3000 }),
    dismiss: (id) => toast.dismiss(id),
  };
}
```

**`<Toaster>` 設定：** `position="bottom-right"`、`duration={3000}`、`richColors`、`closeButton`。

**Error Boundary 行為：**
- 接 React render / lifecycle / hook 例外
- 不接：fetch 失敗、SSE 中斷、Promise rejection（這些走 toast）
- fallback UI 含「重置」按鈕，按下後呼叫 `resetErrorBoundary` 並 `router.refresh()`
- 開發模式下顯示 `error.stack`；production 只顯示 `error.message`

**Command Palette 規格：**
- 觸發：`Ctrl+K`（Windows / Linux）、`Cmd+K`（macOS）；Esc 關閉
- 內建 entries：
  - **頁面群組**：個股分析 / 資料管理 / 回測 / AI 問答 / 設定（由 Sidebar 在 mount 時註冊）
  - **股票搜尋群組**：使用者打字時 debounce 200ms 後查 `GET /api/data/symbols?market={current}&q={input}`（若後端不支援 `q`，則 client-side filter），最多顯示 10 筆，Enter 跳轉 `/dashboard?symbol={selected}`
- `useCommandPaletteEntry` lifecycle：mount 時 push、unmount 時 pop；同一 page mount 多次以 `id` 去重
- 視覺：shadcn Dialog overlay + Command 主體；fuzzy 比對用 cmdk 內建

**鍵盤快捷鍵約定：**
- `Ctrl+K` / `Cmd+K`：開啟 Command Palette
- `/`：聚焦 Command Palette（先開啟、自動 focus input）—— **採用「開啟並 focus」而非「聚焦頁內某個搜尋框」**；目前各頁的 StockSelector 不會被 `/` 觸發
- `Esc`：關閉 Command Palette / 關閉 Dialog（沿用 Radix 既有行為）

**驗收條件：**
1. 觸發 `useToast().success("測試")` 後右下角出現 3 秒綠色 toast
2. Provider 樹包住整個 app（任何 client component 都能呼叫 `useToast`）
3. React 元件刻意 throw 後 Error Boundary 顯示 fallback UI；點「重置」後頁面回正常
4. `CardSkeleton` / `ChartSkeleton` / `TableSkeleton` 三變體可獨立 import 並渲染
5. `Ctrl+K` 開啟 Palette；輸入頁面關鍵字後 ↑↓ 選擇、Enter 跳轉
6. `/` 開啟 Palette 並 focus input
7. 股票搜尋群組可搜到當前 market 的 symbol、Enter 跳轉 dashboard
8. 10-C-2 既有 5 處 banner 完全替換為 toast，inline banner 元件不再出現於 `data-page-client.tsx`（grep 確認）
9. `@radix-ui/react-toast` 從 `package.json` 移除；`pnpm install` 後 `node_modules` 不再含此套件
10. `web/` `tsc --noEmit` 0 errors；`pnpm test` 全綠（既有 + 10-G-1 新增測試）

**10-G-1 結束後尚未實作的 10-G-2 範圍：**
- API Key write-only UI 與 secrets 狀態顯示
- 策略 preset CRUD UI + 後端 `POST /api/config/strategies` / `DELETE /api/config/strategies/{name}` / `POST /api/config/strategies/restore`
- 主題切換 Dark↔Light（接 `next-themes`）
- AI toggle disabled + tooltip
- AI off 時 `/api/config` PUT 強制 `ai.enabled=false` 的 whitelist 加固

##### 10-G-2：設定頁主功能（API Key / 策略 preset / 主題 / AI toggle）

**前置：** 10-G-1 已驗收完成。

**範圍：** 把 [web/src/app/settings/page.tsx](web/src/app/settings/page.tsx) 從 placeholder 改為四分區的完整設定頁，並補上後端策略 preset 寫入端點。

**新增 / 修改檔案：**

| 檔案 | 動作 | 說明 |
|:---|:---|:---|
| `api/routers/config.py` | 修改 | 新增 `POST /api/config/strategies`（upsert by name）、`DELETE /api/config/strategies/{name}`、`POST /api/config/strategies/restore`；既有 GET 不變 |
| `src/services/config_service.py` | 修改 | 新增 `delete_strategy_preset_by_name(name)` 給端點用（既有 `upsert_strategy_preset` / `restore_strategy_defaults` 可直接重用） |
| `web/package.json` | 修改 | 新增 `next-themes` |
| `web/src/components/providers.tsx` | 修改 | 加入 `<ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>` |
| `web/src/app/settings/page.tsx` | 修改 | 完整四分區設定頁實作 |
| `web/src/components/settings/secrets-section.tsx` | 新增 | API Key 區（5 個 provider：openai / anthropic / gemini / finmind / google） |
| `web/src/components/settings/strategy-presets-section.tsx` | 新增 | 策略 preset 列表 + 新增 / 編輯 / 刪除 Dialog + 重置預設按鈕 |
| `web/src/components/settings/theme-section.tsx` | 新增 | Dark / Light 切換 toggle（搭配 `next-themes`） |
| `web/src/components/settings/ai-toggle-section.tsx` | 新增 | AI 開關 toggle（`disabled` 視 secrets 狀態 + 10-F-2 是否完成而定；目前永遠 disabled + tooltip「AI 功能尚未開放」） |
| `web/src/hooks/use-config.ts` | 新增 | SWR hook：讀 `/api/config`、`/api/config/secrets/status`、`/api/config/strategies` |
| `tests/test_api/test_config_api.py` | 修改 | 補 strategy preset 端點測試（POST upsert / DELETE by name / POST restore） |
| `tests/test_services/test_config_svc.py` | 修改 | 補 `delete_strategy_preset_by_name` 測試（含 name 不存在 idempotent） |

**主題系統收斂（與規格 [3438-3440](量化交易系統規格書_shellpig版.md:3438) 一致）：**
- 從舊 Streamlit 6 套主題收斂為 **Dark / Light 二選一**（不移植 6 套）
- shadcn/ui 原生 dark/light 雙模式，透過 `class="dark"` 切換
- K 線圖顏色依市場動態切換 CSS 變數 `--chart-up` / `--chart-down`（10-D 已實作，不變）
- 預設 `dark`；不接 `system` 自動偵測（`enableSystem={false}`），避免使用者 OS 主題切換時 K 線顏色閃動

**策略 preset 端點規格：**

| 方法 | 路徑 | Request Body | Response | 行為 |
|:---|:---|:---|:---|:---|
| GET | `/api/config/strategies` | — | `{ data: [{name, strategy, params, market}, ...], meta: {count: N} }` | 既有，不變 |
| POST | `/api/config/strategies` | `{ "preset": { name, strategy, params, market } }` | `201 { data: { upserted: true, name }, meta: {} }` | upsert by name；name 已存在則覆蓋 |
| DELETE | `/api/config/strategies/{name}` | — | `204` | idempotent；name 不存在仍回 204 |
| POST | `/api/config/strategies/restore` | — | `200 { data: { count: N }, meta: {} }` | 復原為 `DEFAULT_STRATEGY_PRESETS` |

**策略 preset JSON schema 範例：**

```json
{
  "name": "MA 20/60 台積電",
  "strategy": "moving_average_cross",
  "params": { "short_window": 20, "long_window": 60 },
  "market": "tw"
}
```

`strategy` 欄位接受值：`moving_average_cross` / `rsi` / `kd_cross` / `macd_cross` / `bollinger_band` / `bias` / `donchian_breakout` / `dollar_cost_averaging`（沿用 [src/core/strategy_config.py](src/core/strategy_config.py) 既有定義）。

**錯誤碼：**

| Code | HTTP | 觸發 |
|:---|:---|:---|
| `INVALID_PRESET` | 422 | `normalize_strategy_preset` 拋例外（缺欄、參數型別錯、strategy 不在 enum） |
| `UNKNOWN_PROVIDER` | 422 | `PUT /api/config/secrets` 帶不認得的 provider 名（既有錯誤碼，不變） |
| `WHITELIST_REJECTED` | 422 | `PUT /api/config` 帶不在 whitelist 的 key（既有，不變） |

**設定頁分區結構：**

```
SettingsPage
├── SecretsSection           — API Key 5 個 provider（openai/anthropic/gemini/finmind/google）
│   ├── 顯示「已設定 / 未設定」狀態
│   ├── 輸入框永遠為空（重新填寫即覆寫）
│   └── 「儲存」按鈕觸發 PUT /api/config/secrets
├── StrategyPresetsSection   — 策略 preset 列表
│   ├── 顯示既有 preset（name / strategy / params summary / market）
│   ├── 「新增」按鈕 → Dialog 輸入 preset → POST upsert
│   ├── 「編輯」按鈕 → Dialog 預填 → POST upsert 覆蓋
│   ├── 「刪除」按鈕 → 二次確認 → DELETE by name
│   └── 「重置預設」按鈕 → 二次確認 → POST restore
├── ThemeSection             — Dark / Light 切換
│   └── `next-themes` toggle（即時生效）
└── AiToggleSection          — AI 開關
    ├── `<Switch disabled>` + Tooltip「AI 功能尚未開放（等待 10-F-2）」
    └── 顯示目前後端 ai.enabled 狀態（read-only）
```

**API key 安全規則重申：**
- GET `/api/config` 回傳的 ai 區塊永遠 mask 為 `"***configured***"` 或不出現
- 前端 secrets 輸入框預設值為空字串、`autocomplete="off"`、`type="password"`
- 提交時送 `PUT /api/config/secrets`，後端寫 `.env`，**永不回傳 key 值**
- 狀態顯示透過 `GET /api/config/secrets/status` 得 boolean

**驗收條件：**
1. SettingsPage 顯示 4 個分區
2. **Secrets**：5 個 provider 輸入框與「已設定 / 未設定」狀態顯示；輸入後「儲存」觸發 PUT；toast「API Key 已更新」
3. **Strategy Preset**：列表顯示既有 preset；「新增」Dialog 輸入後 POST，toast「已新增策略：{name}」；「編輯」覆蓋同 name；「刪除」二次確認後 DELETE，toast「已刪除策略：{name}」；「重置預設」二次確認後 POST restore，toast「已重置為預設 8 組策略」
4. **Theme**：Dark / Light toggle 即時生效；切換時 toast 不出現（靜默切換）
5. **AI toggle**：永遠 disabled + tooltip「AI 功能尚未開放」；後端 `ai.enabled` 狀態顯示為 read-only chip
6. 後端 `POST /api/config/strategies` 帶 `preset.name = "MA 20/60"` 後 GET 可看到；再 POST 同 name 不同 params 是覆蓋而非新增
7. 後端 `DELETE /api/config/strategies/不存在` 仍回 204
8. 後端 `POST /api/config/strategies/restore` 回 200 並把 `config.yaml` `strategies` 段還原為 `DEFAULT_STRATEGY_PRESETS`
9. 後端 `POST /api/config/strategies` 帶不合法 preset（如 strategy 不在 enum）回 422 + `INVALID_PRESET`
10. API key 任何時候不出現在 GET 回傳；瀏覽器 DevTools network 無 key 明文
11. `web/` `tsc --noEmit` 0 errors；`pnpm test` 全綠；後端 `pytest tests/test_api/test_config_api.py tests/test_services/test_config_svc.py` 全綠

**10-G-2 結束後的範圍邊界：**
- 不做：i18n / 字體大小 / 緊湊模式 / 自訂主題色 / 鍵盤快捷鍵自訂
- 不做：策略 preset 拖曳排序、複製、匯入匯出（直接編 `config.yaml` 即可）

#### 10-H：舊 UI 移除與收尾

**前置條件：** 10-A ~ 10-G 全部通過人工驗收。

**測試遷移檢查表（不可跳過）：** 每個被刪的 Streamlit test case 必須先在 service 層/API/前端測試中有對應替代。

**動作：** 移除 `src/ui/`、Streamlit 依賴、`run_quanttrader.bat`、已有替代的 Streamlit 測試。更新文件。全專案回歸測試（測試總數不低於移除前）。

#### Phase 10 主題系統

從 6 套收斂為 2 套基礎主題（Dark 預設 + Light）+ 可選強調色。shadcn/ui 原生 dark/light 雙模式。K 線圖顏色依市場動態切換 CSS 變數 `--chart-up` / `--chart-down`。

#### Phase 10 Responsive 斷點

| 斷點 | 寬度 | 佈局策略 |
|:---|:---|:---|
| `sm` | ≥640px | 單欄，圖表全寬 |
| `md` | ≥768px | 雙欄開始出現 |
| `lg` | ≥1024px | Sidebar 固定展開 |
| `xl` | ≥1280px | 主要開發目標佈局 |
| `2xl` | ≥1536px | 三欄佈局 |

手機 (<768px)：底部 Tab Bar、K 線全寬 300px、DataTable 可滾動、Dialog 全螢幕 Sheet。觸控：pinch zoom、swipe、long press 十字線、最小觸控目標 44×44px。

#### Phase 10 明確不做

- 不做使用者認證/登入（個人工具）
- 不做雲端部署（維持零伺服器）
- 不做 PWA / 離線模式
- 不做 WebSocket（SSE 足夠）
- 不做 i18n（維持繁體中文）
- 不做 Server Components streaming（初期用 SWR）
- 不重寫核心演算法
- 不做 Docker 容器化
- 不做 CI/CD pipeline

#### Phase 10 風險

| 風險 | 緩解 |
|:---|:---|
| React/TypeScript 學習曲線 | shadcn/ui 現成元件 + AI 輔助 |
| Lightweight Charts API 差異 | 10-D 先做 PoC 驗證 |
| FastAPI 與 src/ import 整合 | 10-A 優先驗證 |
| OneDrive + Node.js 相容性 | `.npmrc` 設 `package-import-method=copy`；fallback npm |
| DuckDB 並發存取 | Job manager 限制同時 1 個寫入型 job |

---

## 附錄 A：免責聲明全文

本工具（shellpig 量化交易研究系統）為個人研究輔助工具，使用前請確認以下事項：

1. **非投資建議：** 本工具所有輸出，包含技術指標數值、AI 生成的分析文字、回測結果，均不構成任何形式的投資建議，不應作為買賣決策的唯一依據。

2. **歷史不代表未來：** 回測結果基於歷史市場數據，市場條件隨時可能改變，過去的績效表現不保證未來的報酬。

3. **AI 局限性：** AI 的分析基於提供的數值資料進行統計描述，AI 無法預測市場走向。分析中使用的技術術語（如「看漲」、「支撐」、「超買」）均為技術分析的慣用描述，非承諾或預測。

4. **資料準確性：** 本工具使用第三方資料源（FinMind、Yahoo Finance），不保證資料的即時性與百分之百準確性。重要交易決策請以券商官方行情系統為準。

5. **自負盈虧：** 使用者對自身的所有投資決策負完全責任，本工具開發者不承擔任何因使用本工具而導致的直接或間接投資損失。

---

*本規格書（shellpig 版）基於企業版 V3.0 精簡而來，由 Claude Sonnet 4.6 協助設計。*
*個人研究工具，技術棧：Python 3.12 + DuckDB + LLM Provider APIs + Streamlit（Phase 10 起遷移至 Next.js + FastAPI）。*

---

## 附錄 B：2026-04-26 架構決策補充

### B.1 美股擴充邊界

2026-04-26 的原始決策是「只保留 `market` 擴充接口，不宣稱已支援美股」。2026-05-11 規格討論後，決定將 Phase 9 規劃為 **美股 US-1 支援**，9-A 到 9-F 範圍嚴格限制為美股日 K、調整後價格、回測與技術分析。2026-05-13 追加 9-G：以 yfinance 1m intraday 補個股分析的近似盤中快照與分 K 圖。

Phase 9 之前的正式支援市場仍是台股。Phase 9 完成後，正式支援市場為：

- `tw`：台股完整既有功能。
- `us`：美股 US-1（日 K + adjusted daily + 回測 + 技術分析）；9-G 追加 yfinance 1m intraday 盤中快照與分 K 圖。

US-1 不等於完整美股平台。9-G 只補 yfinance 最新 1 分 K close 作為近似盤中價，仍不支援 WebSocket、買一 / 賣一、五檔、逐筆、籌碼、財報、期權、匯率換算或實盤。

為避免後續擴充時大幅重構，資料層與回測層必須停止新增台股硬編碼。設計上以 `market` 作為第一層分流，預設值仍為 `tw`。

建議逐步調整方向：

- 資料路徑由 `data/raw/tw/{symbol}` 漸進抽象為 `data/raw/{market}/{symbol}`。
- `symbol` 驗證需與 `market` 綁定，台股先採白名單格式，並禁止路徑穿越。
- 市場設定集中管理：timezone、currency、lot size、volume unit、tick rule、tax rule、price tick（詳見 Phase 9-A `MarketSpec`）。
- metadata 主鍵必須納入 `market`，避免 `2330` / `AAPL` 或未來同名 ticker 混用資料狀態。
- UI 不新增獨立美股頁，既有回測頁、個股分析頁與資料管理頁加市場切換。
- US-1 完成前，不得在 UI 暗示美股完整支援。

### B.2 AI 技術分析改為可選 LLM Provider

原規格以 Claude API 為主；後續應調整為 provider-neutral 的 AI 技術分析架構，至少支援下列 provider 的設定入口：

- OpenAI / ChatGPT
- Anthropic / Claude
- Google / Gemini

`AIAdvisor` 不應直接綁定單一 SDK，而應依賴共同介面，例如 `LLMProvider`。各 provider adapter 負責把本系統的工具呼叫格式轉換為各家 API 格式，再回傳統一的 `ToolCall` / `LLMResponse`。

建議設定格式：

```yaml
ai:
  enabled: false
  provider: anthropic   # openai | anthropic | gemini
  model: claude-...
  temperature: 0.2
  max_tokens: 4096
  timeout_seconds: 30
```

`enabled=false` 是合法且建議的預設狀態。此狀態下，系統不得因缺少 AI API key 而影響資料下載、清洗、回測、報表或非 AI UI 頁面。

`.env.example` 應保留下列 key 名稱：

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

模型清單變動頻繁，因此 UI 可提供常用模型下拉選單，但必須允許使用者手動輸入 model id。
