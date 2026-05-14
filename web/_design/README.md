# web/_design/ — 設計草稿暫存區

本目錄是 Claude Design 的工作區，存放尚未驗收完成的視覺稿、元件規劃、設計筆記。底線開頭，Next.js App Router 不會把它當作 route，build 時也不會被打包。

## 與 `web/src/` 的分工

| 目錄 | 性質 | 誰會寫 | 進 build |
|:---|:---|:---|:---|
| `web/src/` | 正式產品碼 | 實作端 Claude | ✅ |
| `web/_design/` | 設計草稿 | Claude Design | ❌ |

## 流程

每個頁面（10-C ~ 10-G）依「三輪交付」節奏使用本目錄：

1. **第 1 輪：靜態視覺稿**
   - 檔案：`{page}-mockup.tsx`（假資料寫死）
   - 用途：決定排版、字級、留白、顏色、Dark/Light 兩版

2. **第 2 輪：元件拆解**
   - 檔案：`{page}-components.md`
   - 用途：列出元件樹 + 對應的 shadcn/ui 元件 + props 介面

3. **第 3 輪：接真 API**
   - 動作：實作端把成品整理進 `web/src/app/{page}/page.tsx` + `web/src/components/{...}`，**並刪除本目錄對應的 `{page}-*` 草稿**

## 命名範例

```
web/_design/
├── README.md
├── dashboard-mockup.tsx       ← 10-D 第 1 輪
├── dashboard-components.md    ← 10-D 第 2 輪
├── data-mockup.tsx            ← 10-C 第 1 輪
└── ...
```

## 規則

- 不要在這裡放正式產品碼
- 第 3 輪驗收完成、內容遷入 `web/src/` 後，請刪除對應草稿
- 不要在這裡 import `web/src/` 以外的內部模組（避免循環依賴）
- 草稿期間可以用假資料、可以省略 error/loading 狀態，但要標註清楚
