# FactorHammer（QuantTrader）

![Python](https://img.shields.io/badge/PYTHON-3.12+-3776AB?logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/NODE.JS-22-339933?logo=node.js&logoColor=white)
![Next.js](https://img.shields.io/badge/NEXT.JS-15-000000?logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FASTAPI-009688?logo=fastapi&logoColor=white)
![Platform](https://img.shields.io/badge/PLATFORM-WINDOWS-0078D6?logo=windows&logoColor=white)
![Trading](https://img.shields.io/badge/TRADING-RESEARCH%20ONLY-red)

> 台股 / 美股 US-1 量化研究工具・個人版・Windows 本機・**不接實盤**

純研究、回測、AI 分析用途。資料管線、策略開發、批次掃描與走樣外驗證皆在本機完成，零外部伺服器依賴。

---

## ⚠️ 免責聲明

本專案為個人研究工具，**不構成任何投資建議**，也不接任何券商實盤。所有資料來自公開免費 API（FinMind、yfinance、TWSE / TPEx OpenAPI、Goodinfo 等），可能存在延遲、遺漏或錯誤。使用者需自行承擔依此進行任何決策的風險。

---

## 能做什麼

| 範疇 | 功能 |
|---|---|
| 資料管線 | 台股日 K / 1m intraday、籌碼、融資券、PER、月營收、股利、EPS、股東會；美股 US-1 日 K / 1m |
| 技術分析 | pandas-ta 指標封裝、K 線形態、籌碼分析、技術摘要 |
| 回測引擎 | 向量化（`generate_signals`）與事件驅動（`on_bar`）雙引擎並行，含手續費 / 滑價 / 稅費模型 |
| 策略庫 | MA Cross、RSI、KD、MACD、Bollinger Band、Bias、Donchian Breakout、DCA |
| 進階研究 | 批次回測（batch）、參數掃描（sweep）、走樣外驗證（walk-forward） |
| AI 分析 | Provider-neutral（OpenAI / Anthropic / Gemini），可在 UI 設定；不設定則停用 |
| 前端 | Next.js dashboard，含 K 線、報價列、回測結果、AI 問答、設定頁 |

---

## 技術棧

- **語言 / 套件管理**：Python 3.12+（uv 管理）、Node.js 22（portable，自動安裝）
- **資料層**：DuckDB + Parquet（零伺服器、本機落地）
- **資料處理**：pandas、pandas-ta
- **後端**：FastAPI、uvicorn、httpx；SSE 走 `StreamingResponse`
- **前端**：Next.js 15、React 19、TypeScript 5、Tailwind v4、SWR、Lightweight Charts、Radix UI、shadcn/ui pattern
- **AI**：OpenAI / Anthropic / Gemini（provider-neutral）
- **測試**：pytest、Vitest、Playwright

---

## Quick Start

**前置要求**：Windows 10 / 11。

### 1. 雙擊 `install.bat`

一次性安裝，自動完成：

- 安裝 `uv` 並 `uv sync` 建立 `.venv`
- 下載 portable Node.js v22.11.0 到 `tools\node\`（**不污染系統環境**）
- 安裝前端套件（pnpm 11.1.1，frozen-lockfile）
- 從 `.env.example` 建立 `.env`

### 2. 雙擊 `run_factorhammer.bat`

自動啟動 FastAPI（:8000）+ Next.js（:3000），並開啟瀏覽器到 `/dashboard`。

首次進入會跳出設定頁面，可在 UI 設定 AI Provider 與 API Key（不設定則 AI 功能停用，其它功能正常）。

關閉時把兩個視窗 Ctrl+C 或直接關掉。

---

## 目錄結構（精簡）

```
src/
├── core/         config、constants、market、strategy_config
├── data/         fetcher、cleaner、storage、maintenance、realtime
├── backtest/     向量化 / 事件驅動引擎、cost、metrics、report、batch、sweep、walk_forward
├── strategy/     StrategyBase + examples/（MA、RSI、KD、MACD、Bollinger、Bias、Donchian、DCA）
├── analysis/     technical_summary、pattern、chip_analysis
├── indicators/   pandas-ta 封裝 + 別名映射
├── ai/           advisor（LLM Provider Tool Use）
└── services/     dashboard / backtest / data / config 服務層

api/              FastAPI 後端（routers/、job_manager、deps）
web/              Next.js 前端（App Router）
tests/            pytest 測試套件
data/             (gitignore) DuckDB + Parquet 落地資料
tools/node/       (gitignore) install.bat 下載的 portable Node.js
```

完整目錄與檔案說明見 `PROJECT_BRIEF.md`。

---

## 文件導覽

| 文件 | 用途 |
|---|---|
| [`PROJECT_BRIEF.md`](./PROJECT_BRIEF.md) | **新 session 入口**；架構、進度、規格索引 |
| [`量化交易系統規格書_shellpig版.md`](./量化交易系統規格書_shellpig版.md) | 各 Phase 範圍、API / UI 合約、驗收條件 |
| [`開發設計方針.md`](./開發設計方針.md) | 實作細節、檔案位置、資料契約、類別 / 函式設計 |
| [`測試指南.md`](./測試指南.md) | 驗證指令、測試範圍、手動驗收清單 |
| [`驗證後已知問題.md`](./驗證後已知問題.md) | 當前未完成項、驗收缺口、已接受的邊界決定 |
| [`未涵蓋資料項目.md`](./未涵蓋資料項目.md) | 目前不抓不存的資料項目 |

最新 Phase 進度只維護在 `PROJECT_BRIEF.md`，避免雙份內容漂移。

---

## 資料來源與限制

- **台股**：FinMind 免費層為主、yfinance 備援；股東會走 TWSE / TPEx OpenAPI；股利政策以 Goodinfo 頁作除息 fallback 參考。
- **美股**：yfinance（日 K + 1m intraday）。
- **時區鐵律**：所有 datetime 皆 timezone-aware；台股 `Asia/Taipei`、美股 `America/New_York`。
- **更新策略**：一次性下載歷史 → Parquet 落地；日常增量更新由 `data/maintenance.py` 處理。
- **未涵蓋項目**：見 [`未涵蓋資料項目.md`](./未涵蓋資料項目.md)。

---

## License

個人專案，無保固。僅供研究與學習用途，**不得用於商業或實盤交易**。
