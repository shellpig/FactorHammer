# 盤中看盤板（Intraday Watch Board）

手機上看的台股盤中技術面看板。電腦端每 5–8 分鐘跑一次腳本產生資料、重新發布 claude.ai Artifact 網頁；使用者在手機開網頁看，有問題回到 Claude 對話問。

- **網頁**：https://claude.ai/artifact/LR4QYReJjTELP87xex3y5d （私人，只有擁有者能開）
- **建立日期**：2026-09-30
- **位置**：QuantTraderV2 專案 `scripts/watch/`（使用專案 `.venv`、`src/` 模組與本機資料；不修改專案其他程式碼）

## 檔案

| 檔案 | 用途 |
|---|---|
| `build_watch.py` | 抓資料、算指標與事件，把資料嵌進模板輸出 `watch.html`；另存 `last_data.json` |
| `watch_template.html` | 網頁版面（純 HTML/CSS/JS，資料由 `/*__DATA__*/null` 置換） |
| `watch.html` | 產出的網頁，發布用 |
| `last_data.json` | 最近一次產出的完整資料（盤中回答問題時可直接讀） |
| `cache/daily_<代碼>_<日期>.csv` | 每檔「昨天以前」的日線快取；每天第一次執行才建立（會用到 FinMind 額度） |

## 產生資料

```powershell
cd C:\_work\AI_Work\Projects\QuantTraderV2\scripts\watch
C:\_work\AI_Work\Projects\QuantTraderV2\.venv\Scripts\python.exe build_watch.py --symbols 6182,2489,1476,2492,0050,2330 --out C:\_work\AI_Work\Projects\QuantTraderV2\scripts\watch\watch.html
```

參數：
- `--symbols`：逗號分隔代碼（最多 8 檔，順序即畫面順序）
- `--out`：輸出 HTML 路徑
- `--note`：頁首提示文字（盤中正式版不用傳）
- `--fresh-min`：重大事件閃爍分鐘數，預設 15（示範版曾用 999 讓收盤後也閃）

輸出最後一行形如：`ok 2026-10-01 10:12:03 trade_date=2026-10-01 [('6182', 133.0, 11), ...]`。
`trade_date` 不是今天 → 今天休市。第一次執行約 1–2 分鐘（建日線快取），之後每次約 20–40 秒。

## 資料來源

| 資料 | 來源 | 備註 |
|---|---|---|
| 現價、開高低、昨收、累積量、五檔 | TWSE MIS（專案 `src/data/realtime.py` 的 `RealtimeFetcher`） | 即時 |
| 1 分 K（走勢圖、VWAP、開盤區間、量比、5 分 KD/RSI、事件） | yfinance（上市 `.TW`、上櫃 `.TWO`，由 FinMind TaiwanStockInfo 判斷） | 可能延遲；缺 13:25–13:30 收盤集合競價，收盤後腳本會用官方收盤補最後一點 |
| 日線（均線、KD、MACD、壓力支撐） | 專案 `dashboard_service._prepare_daily_data` + `generate_technical_summary` | 只取今天以前的資料 |

## 網頁內容

- 頂部：更新時間、「追蹤設定」按鈕
- 總覽：每檔一行（現價、漲跌幅、VWAP 上/下、量比、最新事件）；點擊跳到卡片
- 卡片：報價、6 個指標（VWAP、開盤區間 30 分、量比、5 分 KD、5 分 RSI、日內位置）、走勢小圖、最新 3 事件；可展開：關鍵價位、若照現價收盤的日線指標、五檔、全部事件；名稱旁「↑ 回總覽」
- 顏色：台股慣例紅漲綠跌；深/淺色模式皆支援

### 事件規則（`detect_events`）

| 事件 | 規則 | 等級 |
|---|---|---|
| 突破/跌破開盤區間 | 09:30 後收盤突破 09:00–09:29 高/低點（各一次） | 一般 |
| 站上/跌破 VWAP | 超出 VWAP ±0.2% 連續 3 根，15 分鐘冷卻 | 一般 |
| 穿越關鍵價位 | 連續 2 根收盤超出價位 0.1%，同一價位 20 分鐘冷卻 | 見下 |
| 放量 | 5 分鐘量 ≥ 過去幾天同時段均量 3 倍，且 ≥ max(200 張, 20 日均量 2%)；15 分鐘冷卻 | ≥ 8 倍為重大 |
| 觸及漲停 / 鎖漲停 / 觸及跌停 | 依昨收與升降單位計算漲跌停價 | 重大 |

關鍵價位：昨高、昨低、MA5/10/20/60（昨日值）、專案的壓力/支撐（近 20/60 日高點、近期低點）。
- 壓力型（近 20/60 日高點，或其他 ≥ 昨收）向上 =「突破」、向下 =「跌回」；支撐型反之為「跌破」/「站回」。
- **重大**：「突破」或「跌破」且（屬近 20/60 日高點、近期低點，或 10 日內測試 ≥ 2 次）。
- 測試次數：過去 10 天最高價（壓力）或最低價（支撐）在價位 1% 內但收盤沒穿過的天數；昨高/昨低不計昨天本身。

### 總覽提示

- 當天最新一件重大事件（價格事件優先於放量）→ 整列底色 + 左色條 + 「★」行；發生後 `--fresh-min` 分鐘內外框閃爍
- 紅 = 偏多、綠 = 偏空、橘 = 放量
- 「收盤推算」有變化（KD 將黃金/死亡交叉、均線排列改變、MACD 柱狀體翻正/負）→ 橘字一行，不閃

## 追蹤清單（Artifact 資料庫）

- 網頁宣告 `capabilities: {db: {}}`，清單存在 `config/watchlist`：`{"symbols": [...], "updated_at": "..."}`
- 使用者在網頁「追蹤設定」新增/刪除（最多 8 檔，格式 `^\d{4,6}[A-Z]?$`），網頁即時寫入
- **每次更新前必須先讀這份清單**，用它當 `--symbols`
- 刪除立即從畫面消失；新增的顯示「等待下次更新」直到下一次產生資料
- 2026-09-30 初始值：6182、2489、1476、2492、0050、2330

## 盤中定時更新（建議另開 Sonnet 5.5 medium 對話）

每次更新只是固定步驟，不需要模型判斷；另開小上下文的對話最省用量，原對話保留給使用者問問題。

在新對話貼上（`/loop` 間隔 6 分鐘）：

```
/loop 6m 盤中看盤板更新，完整說明在 C:\_work\AI_Work\Projects\QuantTraderV2\scripts\watch\README.md。每次照做：
1. 現在若不是週一到週五 09:00–13:35（Asia/Taipei），不要做任何事；若已過 13:35，結束這個 loop。
2. 用 ArtifactData get 讀 url=https://claude.ai/artifact/LR4QYReJjTELP87xex3y5d collection=config doc_id=watchlist，取 symbols（沒有就用 6182,2489,1476,2492,0050,2330）。
3. 執行：cd C:\_work\AI_Work\Projects\QuantTraderV2\scripts\watch && C:\_work\AI_Work\Projects\QuantTraderV2\.venv\Scripts\python.exe build_watch.py --symbols <symbols 逗號分隔> --out C:\_work\AI_Work\Projects\QuantTraderV2\scripts\watch\watch.html
4. 輸出的 trade_date 不是今天 → 今天休市，不要發布並結束 loop。
5. 用 Artifact publish file_path=C:\_work\AI_Work\Projects\QuantTraderV2\scripts\watch\watch.html url=https://claude.ai/artifact/LR4QYReJjTELP87xex3y5d。不要傳 capabilities、不要傳 icon。
6. 只回一行：時間、各檔現價、有沒有新的重大事件。
```

注意：
- 新對話第一次發布前要先 `Artifact` `action: "read"` 這個網址一次（工具規定：沒讀過的 artifact 不能發布）
- 重新發布**不要傳 `capabilities`**：省略會保留 `db`；傳 `{}` 會清掉，追蹤清單功能就壞了
- 腳本失敗時回報錯誤就好，不要改程式

## 盤中回答使用者問題

1. 讀 `last_data.json`（最新一次產出）或重跑腳本取最新資料
2. 以技術面解讀狀況與風險；**不給買賣建議**（不是持牌投資顧問）

## 已知限制

- yfinance 分 K 可能延遲，且缺收盤集合競價；成交量比官方少約 3%
- 冷門股分鐘成交稀疏，圖上有空檔（例如 1476）
- 事件只從今天的 1 分 K 推算，沒有新聞/題材資料
- 需要電腦開著、更新用的對話開著；不支援休市日判斷以外的特殊日（如颱風假）自動處理，靠 trade_date 檢查
- 專案 FinMind 分鐘資料集（`TaiwanStockPriceMinute`）2026-09-30 試抓失敗，原因未查

## 變更紀錄

- 2026-09-30：建立。示範版用 9/30 收盤資料；加入回總覽按鈕、重大事件總覽提示（閃爍/變色）、追蹤設定（db）；檔案從暫存資料夾搬到 `C:\_work\AI_Work\Tools\watch\`，當天再搬進專案 `scripts/watch/`
