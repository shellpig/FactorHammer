# Claude Design 協作說明

本文件供 Claude Design（負責視覺/UI 設計）在新 session 開始時閱讀，了解專案脈絡、邊界、交付物與協作節奏。實作端（另一個 Claude session）會依此文件接手你的設計成品。

最後更新：2026-05-14

---

## 0. 一句話定位

把一個原本用 Streamlit 拼出來的台股/美股量化研究工具，遷移成 Next.js + FastAPI 的「接近 TradingView / Bloomberg Terminal 質感」的本機 web app。**你只動 `web/`，不動演算法、不動服務層、不動 API contract。**

---

## 1. 目前進度

| Phase | 狀態 | 概要 |
|:---|:---|:---|
| 10-A | ✅ 完成 | 服務層 `src/services/` + FastAPI 後端 `api/`（含 Job manager、write lock、SSE） |
| 10-B | ✅ 完成 | Next.js 15 + React 19 + TS5 + Tailwind v4 + SWR + Lightweight Charts 骨架；Sidebar 5 頁導航、Dark/Light 主題、api-client、market-switcher、stock-selector |
| **10-C** | 📋 待做 | 資料管理頁（含 DELETE 確認對話框） |
| **10-D** | 📋 待做 | 個股分析儀表板（K 線 + 技術指標 + 型態 + 籌碼 + AI 劇本） |
| **10-E** | 📋 待做 | 回測研究工作台（單次/批次/掃描/WFA + Job + SSE） |
| **10-F** | 📋 待做 | AI 問答頁（SSE 串流） |
| **10-G** | 📋 待做 | 設定頁 + 全局整合（Command Palette / 快捷鍵 / Toast / Error Boundary） |
| **10-H** | 📋 待做 | 移除舊 Streamlit UI（前置：10-A~10-G 全部通過驗收） |

10-B 留下的是「能跑、能切頁、能換主題」的空殼。從 10-C 開始才是真的堆 UI、做圖表、做 Responsive。

---

## 2. 必讀上下文（請依序看）

開新 session 時，請先讀以下檔案再開始設計：

| 順序 | 檔案 | 範圍 | 為什麼 |
|:---|:---|:---|:---|
| 1 | `PROJECT_BRIEF.md` | 全部 | 專案全貌、目錄結構、Phase 進度 |
| 2 | `量化交易系統規格書_shellpig版.md` | L2696-2909 | Phase 10 完整規格（技術選型、Responsive、主題、明確不做） |
| 3 | `開發設計方針.md` | L6293-6844 | Phase 10 實作細節（API 端點、元件拆分、測試遷移） |
| 4 | `src/ui/pages/{dashboard,backtest,data_management,settings,ai_chat}.py` | 對應頁面 | 原 Streamlit 頁面長相、欄位、互動順序——**新版要保留同等資訊密度** |
| 5 | `src/services/{dashboard,backtest,data,config}_service.py` | 全部 | 後端會回什麼 payload、欄位型別 |
| 6 | `web/src/` | 全部 | 既有骨架（layout、sidebar、theme、api-client、型別檔），**不要砍掉重練** |

---

## 3. 技術棧（不可換）

| 類別 | 選型 |
|:---|:---|
| 前端 | Next.js 15+ / React 19+ / TypeScript 5+ |
| 樣式 | Tailwind CSS v4 |
| UI 元件 | shadcn/ui（Radix UI）—— 優先用既有元件，不要自己造輪 |
| 金融圖表 | Lightweight Charts（TradingView 開源） |
| 輔助圖表 | Recharts（非 K 線類） |
| 資料 fetching | SWR ≥2 |
| 套件管理 | pnpm ≥9（OneDrive 衝突時退回 npm） |
| 後端（不動） | FastAPI + Python 3.12 |
| 資料傳輸 | REST JSON / 行情 polling / 回測 SSE |

---

## 4. 鐵則（不可違反）

1. **核心演算法不動** — `src/core/`、`src/data/`、`src/backtest/`、`src/strategy/`、`src/analysis/`、`src/indicators/`、`src/ai/` 完全不碰。
2. **服務層不動** — `src/services/` 的函式簽名與回傳結構是 API contract 的一部分，要改先回來討論。
3. **API contract 不動** — `api/routers/` 的路徑、method、request/response schema 都以既有為準。前端對齊後端，不是反過來。
4. **既有骨架不重練** — `web/src/components/sidebar.tsx`、`theme-provider.tsx`、`market-switcher.tsx`、`stock-selector.tsx`、`lib/api-client.ts`、`lib/formatters.ts` 已通過手動驗收（10-B-1~6），擴充可以、砍掉不行。
5. **主題走 CSS 變數** — Dark/Light 兩套主題在 `web/src/app/globals.css` 用 CSS 變數定義。K 線顏色用 `--chart-up` / `--chart-down`（台股紅漲綠跌、美股綠漲紅跌——由前端依 `market` context 動態切變數）。不要硬寫色碼。
6. **手機可用** — <768px 必須能操作。Sidebar 改底部 Tab Bar、K 線全寬、Dialog 改全螢幕 Sheet、最小觸控目標 44×44px。
7. **繁體中文** — UI 文案、tooltip、錯誤訊息全部繁中。不做 i18n。
8. **不做的事**（規格書 L2888-2898）：認證、雲端、PWA、WebSocket、Server Components streaming、Docker、CI/CD。

---

## 5. Responsive 斷點

| 斷點 | 寬度 | 佈局 |
|:---|:---|:---|
| `sm` | ≥640px | 單欄，圖表全寬 |
| `md` | ≥768px | 雙欄開始出現 |
| `lg` | ≥1024px | Sidebar 固定展開 |
| `xl` | ≥1280px | **主要開發目標佈局** |
| `2xl` | ≥1536px | 三欄佈局 |

手機（<768px）：底部 Tab Bar、Dialog 全螢幕 Sheet、觸控支援 pinch zoom / swipe / long press。

---

## 6. 建議的協作節奏（每個頁面三輪交付）

不要一次交付完整頁面。每個頁面拆成三輪，每輪驗收後再走下一輪：

### 第 1 輪：靜態視覺稿
- 給我一張 TradingView / Bloomberg / 既有金融工具的參考圖（或描述風格）
- 產出 HTML/JSX mockup（假資料寫死）
- 決定排版、字級、留白、顏色、Dark/Light 兩版
- **驗收標準**：使用者看了視覺稿同意風格，再進下一輪

### 第 2 輪：元件拆解 + shadcn/ui 對齊
- 把 mockup 拆成 `web/src/components/` 下的元件
- 優先用 shadcn/ui 既有元件（Button、Card、Tabs、Dialog、Sheet、Table、DropdownMenu…）
- 元件命名對齊規格（如 `charts/candlestick-chart.tsx`、`metric-card.tsx`）
- **驗收標準**：元件清單列出、命名確認、shadcn/ui 對應確認

### 第 3 輪：接真 API
- 用 SWR hook 接後端 API（端點請見「7. API 對照表」）
- 加 loading skeleton、error boundary、空狀態
- 加 Vitest 元件測試（10-B 已建立 33 個測試樣板可參考 `web/src/tests/`）
- **驗收標準**：`pnpm dev` + 後端 `uvicorn` 跑起來頁面能用、Vitest 通過

---

## 7. API 對照表（10-C ~ 10-G）

### 10-C 資料管理頁
- `GET /api/data/symbols?market={tw|us}` — 已存在標的清單
- `POST /api/jobs`（type: `data_update` / `data_rebuild`）→ SSE 進度
- **`DELETE /api/data/{market}/{symbol}`**（新功能）— 需取 write lock、前端必須彈確認 Dialog

### 10-D 個股分析儀表板
- `GET /api/dashboard/payload?market={tw|us}&symbol={...}` — 聚合端點，頁面初載用
- `GET /api/analysis/{technical|pattern|chip|daily}` — 細部端點，局部刷新用
- `GET /api/realtime/{tw|us/intraday}` — 重新整理報價
- `POST /api/ai/analyze` — AI 分析獨立觸發

### 10-E 回測工作台
- `POST /api/jobs`（type: `backtest_single` / `backtest_batch` / `backtest_sweep` / `backtest_wfa`）
- `GET /api/jobs/{id}/events` — SSE 進度
- `GET /api/jobs/{id}/result` — 拿結果
- `POST /api/jobs/{id}/cancel` — 取消

### 10-F AI 問答
- `POST /api/ai/chat`（SSE 串流逐字回應）

### 10-G 設定
- `GET /api/config` — 讀設定（**永遠不回傳 secrets**）
- `PUT /api/config` — 寫設定（走 schema whitelist）
- `PUT /api/config/secrets` — write-only 寫 API key
- `GET /api/config/secrets/status` — 只回「有沒有設」，不回值

詳細 schema 請看 `api/routers/` 對應檔。

---

## 8. 各頁面重點提示

### 10-C 資料管理頁
- 對齊 `src/ui/pages/data_management.py` 的功能：市場切換、資料狀態表、新增標的、更新/重建、美股停用分 K/籌碼提示
- 新增：DELETE 對話框（雙重確認、明示「刪本機快取，可重新下載」）

### 10-D 個股分析儀表板（核心頁面，建議**第一個**做，視覺定調用）
- K 線 + MA 疊加、成交量獨立圖、技術指標副圖（KD/RSI/MACD）— 時間軸全部同步
- 日 K 用 business day string `"YYYY-MM-DD"`；美股 intraday 用 `timestamp_utc` (UTC epoch 秒) + `exchange_tz`
- 台股紅漲綠跌、美股綠漲紅跌
- PC ≥1280px：左右分欄（圖表 70% + 技術摘要面板）
- 手機 <768px：全寬堆疊 + 底部 tab bar
- AI 劇本三情境（看多/看空/區間）卡片化呈現

### 10-E 回測工作台
- 統一走 Job lifecycle（不要直接同步呼叫）
- 包含：tearsheet cards、equity curve、K 線 + 買賣點 overlay、heatmap（參數掃描）、WFA 表格 + CSV 匯出、取消按鈕

### 10-F AI 問答
- SSE 串流逐字顯示（不是等完整回應）
- AI disabled 時顯示「請至設定頁啟用 AI」引導

### 10-G 設定頁 + 全局整合
- **Secrets 安全**：API key 輸入框永遠為空，只顯示「已設定 / 未設定」狀態
- Command Palette（Ctrl+K）跳頁、改主題、改市場
- 全局：Toast、Error Boundary、Loading skeleton

---

## 9. 交付物格式建議

每輪交付請用以下其中一種：

- **靜態視覺稿輪**：純 JSX/TSX 檔（可放在 `web/src/app/{page}/page.tsx` 直接覆蓋，或 `web/_design/{page}-mockup.tsx` 暫存）
- **元件拆解輪**：寫一份 `_design/{page}-components.md` 列出元件樹 + 對應 shadcn/ui 元件 + props 介面
- **接 API 輪**：直接改 `web/src/app/{page}/page.tsx` + 在 `web/src/hooks/use-{...}.ts` 加 SWR hook

實作端 session 會幫你：
- 對齊既有骨架（不會讓你重練 sidebar/theme）
- 補 Vitest 元件測試
- 跑 `pnpm dev` + Playwright smoke + 後端 `pytest tests/test_api/` 確認沒打壞 contract
- 寫進 git commit

---

## 10. 邊界爭議怎麼辦

如果你發現「規格書這樣寫但好像不合理」、「服務層的 payload 缺欄位」、「想新增 API 端點」：
- **不要直接動服務層或 API**
- 在交付物裡列出「設計建議變更」清單（含理由）
- 回到主對話讓使用者裁決，由實作端決定是否回頭改服務層 / API

---

## 11. 第一步建議

**從 10-D 個股分析儀表板開始**（不是從 10-C）。理由：

- 10-D 是改版的核心頁面（規格書定位），元件最多：K 線、技術指標副圖、tab 切換、metric card、Responsive 雙欄、AI 劇本卡片
- 設計模式（顏色 token、字級階層、圖表風格、卡片留白、tab 樣式、Responsive 行為）在這裡定型後，10-C / 10-E / 10-F / 10-G 可直接沿用，整體視覺一致性最好
- 如果先做 10-C（範圍小）建立風格，到 10-D 時碰到圖表/雙欄佈局可能被迫翻盤，反而是浪費

10-D 第一輪請聚焦在「靜態視覺稿 + Dark/Light 兩版」，不要急著接 API。確定風格後再進第 2、3 輪。

例外：如果使用者明確指定先做別頁，以使用者指示為準。

---

## 附錄 A：開場 prompt 範本

### 10-D 第 1 輪（靜態視覺稿）

```
請先讀 CLAUDE_DESIGN_協作說明.md，然後我們從 10-D 開始。
這次只跑第 1 輪：靜態視覺稿 + Dark/Light 兩版，先不要拆元件、不要接 API。
```

可選加強版（若要明確指定風格參考）：

```
請先讀 CLAUDE_DESIGN_協作說明.md，然後我們從 10-D 開始。
這次只跑第 1 輪：靜態視覺稿 + Dark/Light 兩版，先不要拆元件、不要接 API。
風格參考：TradingView 個股頁 / Bloomberg Terminal，深色為主、資訊密度高、字級階層清楚。
```

交付物放 `web/_design/dashboard-mockup.tsx`（假資料寫死即可）。

### 第 2 輪（元件拆解）開場

```
10-D 第 1 輪視覺稿已驗收。請進第 2 輪：元件拆解 + shadcn/ui 對齊。
產出 web/_design/dashboard-components.md，列出元件樹、對應的 shadcn/ui 元件、props 介面。
優先用 shadcn/ui 既有元件，不要自己造輪。
```

### 第 3 輪（接 API）開場

```
10-D 第 2 輪元件規劃已驗收。請進第 3 輪：接真 API。
依 components.md 把元件實作進 web/src/components/，把 dashboard 頁實作進 web/src/app/dashboard/page.tsx。
用 SWR hook 接 GET /api/dashboard/payload，加 loading skeleton、error boundary、空狀態。
驗收後請刪掉 web/_design/dashboard-mockup.tsx 與 dashboard-components.md。
```
