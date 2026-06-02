# FactorHammer（QuantTrader）

[English](./README.md) | [繁體中文](./README_zh-TW.md) | **简体中文**

![Python](https://img.shields.io/badge/PYTHON-3.12+-3776AB?logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/NODE.JS-22-339933?logo=node.js&logoColor=white)
![Next.js](https://img.shields.io/badge/NEXT.JS-15-000000?logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FASTAPI-009688?logo=fastapi&logoColor=white)
![Platform](https://img.shields.io/badge/PLATFORM-WINDOWS-0078D6?logo=windows&logoColor=white)
![Trading](https://img.shields.io/badge/TRADING-RESEARCH%20ONLY-red)

> 台股 / 美股 US-1 量化研究工具・个人版・Windows 本机・**不接实盘**

纯研究、回测、AI 分析用途。数据管线、策略开发、批量扫描与样本外验证皆在本机完成，零外部服务器依赖。

---

## ⚠️ 免责声明

本项目为个人研究工具，**不构成任何投资建议**，也不接任何券商实盘。所有数据来自公开免费 API（FinMind、yfinance、TWSE / TPEx OpenAPI、Goodinfo 等），可能存在延迟、遗漏或错误。使用者需自行承担依此进行任何决策的风险。

---

## 能做什么

| 范畴 | 功能 |
|---|---|
| 数据管线 | 台股日 K / 1m intraday、筹码、融资券、PER、月营收、股利、EPS、股东会；美股 US-1 日 K / 1m |
| 技术分析 | pandas-ta 指标封装、K 线形态、筹码分析、技术摘要 |
| 回测引擎 | 向量化（`generate_signals`）与事件驱动（`on_bar`）双引擎并行，含手续费 / 滑价 / 税费模型 |
| 策略库 | MA Cross、RSI、KD、MACD、Bollinger Band、Bias、Donchian Breakout、DCA |
| 进阶研究 | 批量回测（batch）、参数扫描（sweep）、样本外验证（walk-forward） |
| AI 分析 | Provider-neutral（Anthropic / OpenAI / Gemini / DeepSeek），支持 Dashboard 分析与 AI 问答；不设定则停用 |
| 前端 | Next.js dashboard，含 K 线、报价列、回测结果、流式 AI 问答、设定页 |

---

## 技术栈

- **语言 / 包管理**：Python 3.12+（uv 管理）、Node.js 22（portable，自动安装）
- **数据层**：DuckDB + Parquet（零服务器、本机落地）
- **数据处理**：pandas、pandas-ta
- **后端**：FastAPI、uvicorn、httpx、sse-starlette；SSE 走 `EventSourceResponse`
- **前端**：Next.js 15、React 19、TypeScript 5、Tailwind v4、SWR、Lightweight Charts、Radix UI、shadcn/ui pattern
- **AI**：Anthropic / OpenAI / Gemini / DeepSeek（provider-neutral）
- **测试**：pytest、Vitest、Playwright

---

## Quick Start

**前置要求**：Windows 10 / 11。

### 1. 双击 `install.bat`

一次性安装，自动完成：

- 安装 `uv` 并 `uv sync` 建立 `.venv`
- 下载 portable Node.js v22.11.0 到 `tools\node\`（**不污染系统环境**）
- 安装前端依赖（pnpm 11.1.1，frozen-lockfile）
- 从 `.env.example` 建立 `.env`

### 2. 双击 `run_factorhammer.bat`

自动启动 FastAPI（:8000）+ Next.js（:3000），并打开浏览器到 `/dashboard`。

首次进入会弹出设定页面，可在 UI 设定 AI Provider 与 API Key（不设定则 AI 功能停用，其它功能正常）。

关闭时把两个窗口 Ctrl+C 或直接关掉。

---

## AI 功能

AI 功能为可选；未设定 API Key 时，数据管理、分析与回测仍可正常使用。

- **Provider**：支持 Anthropic、OpenAI、Gemini、DeepSeek，可在设定页切换 provider 与 model。
- **API Key 管理**：设定页可分别保存与验证 FinMind / Anthropic / OpenAI / Gemini / DeepSeek key。
- **Dashboard AI 分析**：个股分析页可使用当前选定 provider 生成分析摘要。
- **AI 问答**：AI 页支持 SSE 流式回复、停止流式，以及 Markdown 显示。
- **Tool use**：AI 问答可调用本机数据工具，依问题读取日线、技术指标、支撑压力与 K 线形态；缺日线数据时会通过既有数据管线自动补抓 / 更新一次。

---

## 目录结构（精简）

```
src/
├── core/         config、constants、market、strategy_config
├── data/         fetcher、cleaner、storage、maintenance、realtime
├── backtest/     向量化 / 事件驱动引擎、cost、metrics、report、batch、sweep、walk_forward
├── strategy/     StrategyBase + examples/（MA、RSI、KD、MACD、Bollinger、Bias、Donchian、DCA）
├── analysis/     technical_summary、pattern、chip_analysis
├── indicators/   pandas-ta 封装 + 别名映射
├── ai/           advisor（LLM Provider Tool Use）
└── services/     dashboard / backtest / data / config 服务层

api/              FastAPI 后端（routers/、job_manager、deps）
web/              Next.js 前端（App Router）
tests/            pytest 测试套件
data/             (gitignore) DuckDB + Parquet 落地数据
tools/node/       (gitignore) install.bat 下载的 portable Node.js
```

完整目录与文件说明见 `PROJECT_BRIEF.md`。

---

## 文档导览

| 文档 | 用途 |
|---|---|
| [`PROJECT_BRIEF.md`](./PROJECT_BRIEF.md) | **新 session 入口**；架构、进度、规格索引 |
| [`量化交易系統規格書_shellpig版.md`](./量化交易系統規格書_shellpig版.md) | 各 Phase 范围、API / UI 合约、验收条件 |
| [`開發設計方針.md`](./開發設計方針.md) | 实作细节、文件位置、数据契约、类别 / 函数设计 |
| [`測試指南.md`](./測試指南.md) | 验证指令、测试范围、手动验收清单 |
| [`驗證後已知問題.md`](./驗證後已知問題.md) | 当前未完成项、验收缺口、已接受的边界决定 |
| [`未涵蓋資料項目.md`](./未涵蓋資料項目.md) | 当前不抓不存的数据项目 |

最新 Phase 进度只维护在 `PROJECT_BRIEF.md`，避免双份内容漂移。

---

## 数据来源与限制

- **台股**：FinMind 免费层为主、yfinance 备援；股东会走 TWSE / TPEx OpenAPI；股利政策以 Goodinfo 页作除息 fallback 参考。
- **美股**：yfinance（日 K + 1m intraday）。
- **时区铁律**：所有 datetime 皆 timezone-aware；台股 `Asia/Taipei`、美股 `America/New_York`。
- **更新策略**：一次性下载历史 → Parquet 落地；日常增量更新由 `data/maintenance.py` 处理。
- **未涵盖项目**：见 [`未涵蓋資料項目.md`](./未涵蓋資料項目.md)。

---

## 后续预计新增规格

以下为规划中的方向，尚未排入正式 Phase，顺序与范围可能调整。

- **Portfolio / Watchlist（观察清单与持股组合）**
  让使用者建立自选观察清单与持股组合，记录成本、张数，并计算损益、股利收入与整体风险暴露，作为单股分析之外的组合层视角。

- **回测结果保存与比较中心**
  目前已有 batch / sweep / walk-forward；下一步把历史回测结果集中管理，支持标签、收藏、跨次比较与报告导出，避免结果散落、难以回溯。

- **策略模板生成器**
  以 UI 或 AI 辅助生成策略骨架（均线、动能、突破、筹码条件等组合），并自动带出基本测试，降低从零撰写策略的门槛。

- **AI 分析评估与防幻觉机制**
  建立固定问题集，验证 AI 回答是否引用正确的本机数据、是否出现乱算、是否如实标明数据缺口；目标是把 AI 问答从「能用」推进到「可信」。

- **更多台股 / 美股数据项目**
  例如财报细项、股权分散、融资维持率、外资期货未平仓等。建议先从**大盘指数 + 类股指数**着手，因为它能直接改善单股分析的背景脉络。

- **风险与资金管理模块**
  纳入最大仓位限制、止损、再平衡，以及 Kelly / fixed fractional、drawdown 控制等资金管理研究功能。

- **安全与隐私检查**
  扫描 `.env`、API key、数据目录与 log，检查是否存在敏感信息泄漏风险。

---

## License

本项目以 [MIT License](./LICENSE) 释出。仅供研究与学习用途，**不得用于商业或实盘交易**；不附任何保固。
