# KOC AI 量化交易系統開發規格書（shellpig 個人版）

## 修訂歷史

| 版本 | 日期 | 修訂說明 |
| :--- | :--- | :--- |
| **V1.0** | 2026/04/24 | 基於企業版 V3.0 規格書精簡而來。定位為個人研究工具，聚焦台股市場，純 Python 技術棧，含 AI 技術分析問答功能。 |
| **V1.1** | 2026/04/24 | Claude + Gemini 雙 AI Review 後更新。新增：時區規範（5.4）、數據維護模組（5.5）、`BacktesterBase` 抽象介面、`Account`/`SimpleAccount` 設計、Grid Search 參數優化（6.5）、`config.yaml` 配置管理、Notebook 範例說明。 |
| **V1.2** | 2026/04/25 | 事實性修正：(1) 台股漲跌停 ±15% → ±10%；(2) 修正台股交易時間描述（無午休，09:00–13:30 連續）；(3) 修正撮合假設與滑價模型衝突；(4) FinMind 免費層分K 限制描述；(5) KD↔STOCH 指標映射；(6) `on_bar` 介面 `portfolio`/`account` 命名統一；(7) 補 `.env.example` 範本檔；(8) Phase 1-D 前復權驗收條件嚴謹化；(9) 放寬 Phase 4-D AI 問答時間門檻；(10) §5.4 FinMind naive datetime 處理說明。 |

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
| **目標市場** | 台股、美股、加密貨幣 | **台股（.TW）為主** | 先深耕一個市場，驗證架構後再擴展 |
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

#### 4-D　端到端整合測試（Day 4-5）

**建置內容：** 從使用者輸入到最終回應的完整流程驗證

**驗收指標：**
- 輸入「2330 的 MACD 是否出現黃金交叉？」→ 回應含指標數值、解釋、免責聲明
- 輸入不存在的股票代碼（如「9999」）→ 友善錯誤訊息，不 crash
- 完整問答流程 < 30 秒（使用者體驗基準；含 LLM Tool Use 多輪往返、工具執行、最終 LLM 回應；不含首次冷啟動）

---

### 子階段總覽

| Phase | 子階段 | 工期 | 有 AI 輔助 |
| :--- | :--- | :--- | :--- |
| **1** 資料基礎建設 | 1-A → 1-D（4 段） | 7 天 | ✅ |
| **2** 向量化回測 | 2-A → 2-D（4 段） | 5 天 | ✅ |
| **3** 事件驅動引擎 | 3-A → 3-E（5 段） | 12 天 | ✅ |
| **4** AI 問答 + UI | 4-A → 4-D（4 段） | 5 天 | ✅ |
| **合計** | 17 個子階段 | **29 天（約 6-7 週）** | |

---

## 12. 費用估算

| 項目 | 費用 | 說明 |
| :--- | :--- | :--- |
| **FinMind API（免費層）** | 免費 | 每日 3,000 次請求；初期夠用 |
| **LLM API（AI 問答）** | 約 $1-5 USD/月 | 依 provider、模型與問答頻率而定 |
| **yfinance** | 免費 | 非官方 API，使用量大時有被封風險 |
| **Streamlit（本機）** | 免費 | 本機 localhost 運行 |
| **合計（初期）** | 約 $1-5 USD/月 | ≈ NT$30-150/月 |

**費用升級觸發條件：**
- 若 FinMind 免費層不足 → 升級付費方案（NT$300/月），可取得完整歷史分K
- 若 LLM API 費用過高 → 增加 prompt caching 優化、切換較便宜模型、或限制每日問答次數

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
*個人研究工具，技術棧：Python 3.12 + DuckDB + LLM Provider APIs + Streamlit。*

---

## 附錄 B：2026-04-26 架構決策補充

### B.1 未來擴充美股的邊界

目前版本仍以台股為唯一正式支援市場，不在本階段實作美股資料源、美股手續費模型、美股交易日曆或美股 UI 流程。

但為避免未來擴充時大幅重構，後續修改資料層與回測層時，應避免新增更多台股硬編碼。設計上先保留 `market` 概念，預設值為 `tw`，未來可擴充為 `us`。

建議逐步調整方向：

- 資料路徑由 `data/raw/tw/{symbol}` 漸進抽象為 `data/raw/{market}/{symbol}`。
- `symbol` 驗證需與 `market` 綁定，台股先採白名單格式，並禁止路徑穿越。
- 市場設定集中管理：timezone、currency、lot size、tick rule、tax rule、symbol suffix。
- 本階段只保留擴充接口，不宣稱已支援美股。

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
