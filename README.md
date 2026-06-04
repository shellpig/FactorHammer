# FactorHammer (QuantTrader)

**English** | [繁體中文](./README_zh-TW.md) | [简体中文](./README_zh-CN.md)

![Python](https://img.shields.io/badge/PYTHON-3.12+-3776AB?logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/NODE.JS-22-339933?logo=node.js&logoColor=white)
![Next.js](https://img.shields.io/badge/NEXT.JS-15-000000?logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FASTAPI-009688?logo=fastapi&logoColor=white)
![Platform](https://img.shields.io/badge/PLATFORM-WINDOWS-0078D6?logo=windows&logoColor=white)
![Trading](https://img.shields.io/badge/TRADING-RESEARCH%20ONLY-red)

> A quantitative research tool for Taiwan / US (US-1) stocks · personal edition · runs locally on Windows · **no live trading**

For research, backtesting, and AI analysis only. The data pipeline, strategy development, batch sweeps, and walk-forward validation all run locally, with zero external server dependencies.

---

## ⚠️ Disclaimer

This is a personal research tool. It **does not constitute investment advice** and is not connected to any broker for live trading. All data comes from free public APIs (FinMind, yfinance, TWSE / TPEx OpenAPI, Goodinfo, etc.) and may be delayed, incomplete, or incorrect. You are solely responsible for any decisions made based on it.

---

## What It Does

| Area | Capabilities |
|---|---|
| Data pipeline | TW daily K / 1m intraday, institutional chips, margin trading, PER, monthly revenue, dividends, EPS, shareholder meetings; US (US-1) daily K / 1m |
| Active ETF tracking | Active Taiwan ETF list, MoneyDJ daily holdings snapshots, holding-level weight / share count, and buy / sell / entry / exit diffs |
| Technical analysis | pandas-ta indicator wrappers, candlestick patterns, chip analysis, technical summaries |
| Backtest engines | Vectorized (`generate_signals`) and event-driven (`on_bar`) engines running in parallel, with commission / slippage / tax models |
| Strategy library | MA Cross, RSI, KD, MACD, Bollinger Band, Bias, Donchian Breakout, DCA |
| Advanced research | Batch backtesting, parameter sweeps, walk-forward analysis |
| AI analysis | Provider-neutral (Anthropic / OpenAI / Gemini / DeepSeek); supports dashboard analysis and AI Q&A; disabled when not configured |
| Frontend | Next.js dashboard with candlestick charts, quote bar, backtest results, active ETF holdings, streaming AI Q&A, and a settings page |

---

## Tech Stack

- **Language / package management**: Python 3.12+ (managed by uv), Node.js 22 (portable, auto-installed)
- **Data layer**: DuckDB + Parquet (serverless, stored locally)
- **Data processing**: pandas, pandas-ta
- **Backend**: FastAPI, uvicorn, httpx, sse-starlette; SSE via `EventSourceResponse`
- **Frontend**: Next.js 15, React 19, TypeScript 5, Tailwind v4, SWR, Lightweight Charts, Radix UI, shadcn/ui pattern
- **AI**: Anthropic / OpenAI / Gemini / DeepSeek (provider-neutral)
- **Testing**: pytest, Vitest, Playwright

---

## Quick Start

**Requirements**: Windows 10 / 11.

### 1. Double-click `install.bat`

A one-time setup that automatically:

- Installs `uv` and runs `uv sync` to create `.venv`
- Downloads portable Node.js v22.11.0 into `tools\node\` (**does not touch the system environment**)
- Installs frontend dependencies (pnpm 11.1.1, frozen-lockfile)
- Creates `.env` from `.env.example`

### 2. Double-click `run_factorhammer.bat`

Starts FastAPI (:8000) + Next.js (:3000) and opens the browser at `/dashboard`.

On first launch a settings page appears where you can configure the AI provider and API keys in the UI (if left unconfigured, AI features are disabled while everything else works normally).

To shut down, press Ctrl+C in both windows or just close them.

---

## AI Features

AI is optional; without an API key, data management, analysis, and backtesting all work normally.

- **Provider**: supports Anthropic, OpenAI, Gemini, and DeepSeek; switch provider and model on the settings page.
- **API key management**: save and validate FinMind / Anthropic / OpenAI / Gemini / DeepSeek keys individually on the settings page.
- **Dashboard AI analysis**: the single-stock analysis page can generate an analysis summary using the currently selected provider.
- **AI Q&A**: the AI page supports SSE streaming responses, stop-streaming, and Markdown rendering.
- **Tool use**: AI Q&A can call local data tools to read daily K, technical indicators, support / resistance, and candlestick patterns based on the question; if daily data is missing, it auto-fetches / updates once through the existing data pipeline.

---

## Directory Structure (condensed)

```
src/
├── core/         config, constants, market, strategy_config
├── data/         fetcher, cleaner, storage, maintenance, realtime
├── backtest/     vectorized / event-driven engines, cost, metrics, report, batch, sweep, walk_forward
├── strategy/     StrategyBase + examples/ (MA, RSI, KD, MACD, Bollinger, Bias, Donchian, DCA)
├── analysis/     technical_summary, pattern, chip_analysis
├── indicators/   pandas-ta wrappers + alias mapping
├── ai/           advisor (LLM provider tool use)
└── services/     dashboard / backtest / data / config / active ETF service layer

api/              FastAPI backend (routers/, job_manager, deps)
web/              Next.js frontend (App Router)
tests/            pytest test suite
data/             (gitignored) DuckDB + Parquet local data
tools/node/       (gitignored) portable Node.js downloaded by install.bat
```

See `PROJECT_BRIEF.md` for the full directory and file reference.

---

## Documentation Guide

| Document | Purpose |
|---|---|
| [`PROJECT_BRIEF.md`](./PROJECT_BRIEF.md) | **Entry point for a new session**; architecture, progress, spec index |
| [`量化交易系統規格書_shellpig版.md`](./量化交易系統規格書_shellpig版.md) | Per-phase scope, API / UI contracts, acceptance criteria |
| [`開發設計方針.md`](./開發設計方針.md) | Implementation details, file locations, data contracts, class / function design |
| [`測試指南.md`](./測試指南.md) | Verification commands, test scope, manual acceptance checklist |
| [`驗證後已知問題.md`](./驗證後已知問題.md) | Open items, acceptance gaps, accepted boundary decisions |
| [`未涵蓋資料項目.md`](./未涵蓋資料項目.md) | Data items currently not fetched or stored |

The latest phase progress is maintained only in `PROJECT_BRIEF.md` to avoid content drift across two copies.

---

## Data Sources & Limitations

- **Taiwan stocks**: FinMind free tier as primary, yfinance as fallback; shareholder meetings via TWSE / TPEx OpenAPI; dividend policy uses the Goodinfo page as an ex-dividend fallback reference.
- **Active Taiwan ETFs**: MoneyDJ holdings pages for daily portfolio snapshots and adjacent-snapshot holding diffs.
- **US stocks**: yfinance (daily K + 1m intraday).
- **Timezone rule**: all datetimes are timezone-aware; TW uses `Asia/Taipei`, US uses `America/New_York`.
- **Update strategy**: download history once → land in Parquet; daily incremental updates handled by `data/maintenance.py`.
- **Not covered**: see [`未涵蓋資料項目.md`](./未涵蓋資料項目.md).

---

## Planned Features

The following are directions under consideration. They are not yet scheduled into formal phases, and their order and scope may change.

- **Portfolio / Watchlist**
  Let users build watchlists and holdings portfolios, recording cost and share count, and computing P&L, dividend income, and overall risk exposure — a portfolio-level view beyond single-stock analysis.

- **Backtest result archive & comparison center**
  Batch / sweep / walk-forward already exist; the next step is to centrally manage historical backtest results with tagging, favorites, cross-run comparison, and report export, so results don't get scattered and hard to trace.

- **Strategy template generator**
  Generate strategy scaffolds via UI or AI (combinations of moving averages, momentum, breakout, chip conditions, etc.) with basic tests auto-generated, lowering the barrier to writing a strategy from scratch.

- **AI analysis evaluation & anti-hallucination**
  Build a fixed question set to verify whether AI answers cite the correct local data, avoid bogus calculations, and honestly flag data gaps — moving AI Q&A from "usable" to "trustworthy".

- **More TW / US data items**
  For example financial-statement line items, shareholding dispersion, margin maintenance ratio, foreign-investor futures open interest. Starting with **market indices + sector indices** is recommended, since they directly improve the context for single-stock analysis.

- **Risk & money management module**
  Add max position limits, stop-loss, rebalancing, plus money-management research features such as Kelly / fixed fractional and drawdown control.

- **Security & privacy checks**
  Scan `.env`, API keys, the data directory, and logs for potential leakage of sensitive information.

---

## License

Released under the [MIT License](./LICENSE). For research and learning purposes only; **not for commercial use or live trading**, and provided without warranty.
