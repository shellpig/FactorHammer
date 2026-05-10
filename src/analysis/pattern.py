"""Pattern analysis module for Phase 8-B."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import pandas_ta as ta

_REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")

try:  # pragma: no cover - environment dependent
    import talib  # noqa: F401
    _HAS_TALIB = True
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    _HAS_TALIB = False


@dataclass
class CandlePattern:
    name: str
    detected: bool
    description: str


@dataclass
class ChartPatternResult:
    pattern_type: str
    formed: bool
    description: str
    key_points: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class TimeframeTrend:
    timeframe: str
    trend_direction: str
    strength: str


@dataclass
class MultiTimeframeAnalysis:
    daily: TimeframeTrend
    weekly: TimeframeTrend
    monthly: TimeframeTrend


def detect_candle_patterns(df: pd.DataFrame) -> list[CandlePattern]:
    """Detect daily candle patterns using pandas-ta + fallback rules."""
    _validate_input(df)

    if len(df) < 2:
        return _empty_candle_patterns()

    work = _numeric_ohlcv(df)
    last = work.iloc[-1]
    prev = work.iloc[-2]

    body = abs(last["close"] - last["open"])
    avg_body = _avg_body(work, lookback=20)
    upper_shadow = last["high"] - max(last["open"], last["close"])
    lower_shadow = min(last["open"], last["close"]) - last["low"]
    body_ref = max(body, 1e-9)

    long_red = bool(last["close"] > last["open"] and body > 2.0 * avg_body)
    long_black = bool(last["close"] < last["open"] and body > 2.0 * avg_body)
    upper_shadow_long = bool(upper_shadow > 2.0 * body_ref)
    lower_shadow_long = bool(lower_shadow > 2.0 * body_ref)

    doji = _detect_doji(work)
    hammer, hangingman = _detect_hammer_like(work)
    engulfing = _detect_engulfing(prev, last)
    morningstar, eveningstar = _detect_star_patterns(work)

    return [
        CandlePattern(name="長紅 K", detected=long_red, description="多方力道"),
        CandlePattern(name="長黑 K", detected=long_black, description="空方力道"),
        CandlePattern(name="十字線", detected=doji, description="多空拉鋸"),
        CandlePattern(name="錘子", detected=hammer, description="反轉訊號"),
        CandlePattern(name="吊人", detected=hangingman, description="反轉訊號"),
        CandlePattern(name="吞噬", detected=engulfing, description="反轉確認"),
        CandlePattern(name="晨星", detected=morningstar, description="強反轉"),
        CandlePattern(name="夜星", detected=eveningstar, description="強反轉"),
        CandlePattern(name="帶上影線", detected=upper_shadow_long, description="上檔壓力"),
        CandlePattern(name="帶下影線", detected=lower_shadow_long, description="下檔支撐"),
    ]


def detect_chart_pattern(
    df: pd.DataFrame,
    *,
    lookback_days: int = 60,
    tolerance_pct: float = 0.03,
) -> list[ChartPatternResult]:
    """Detect W-bottom and M-top chart patterns."""
    _validate_input(df)
    work = _numeric_ohlcv(df).tail(lookback_days).dropna(subset=["high", "low", "close"])
    if len(work) < 5:
        return [
            ChartPatternResult(
                pattern_type="W底（雙底）",
                formed=False,
                description="未形成標準W底型態",
            ),
            ChartPatternResult(
                pattern_type="M頭（雙頂）",
                formed=False,
                description="未形成標準M頭型態",
            ),
        ]

    w_pattern = _detect_w_bottom(work, tolerance_pct=tolerance_pct)
    m_pattern = _detect_m_top(work, tolerance_pct=tolerance_pct)

    if w_pattern.formed and m_pattern.formed:
        w_pattern = ChartPatternResult(
            pattern_type="W底（雙底）",
            formed=False,
            description="區間震盪，未形成標準W底型態",
        )
        m_pattern = ChartPatternResult(
            pattern_type="M頭（雙頂）",
            formed=False,
            description="區間震盪，未形成標準M頭型態",
        )

    return [w_pattern, m_pattern]


def analyze_multi_timeframe(df: pd.DataFrame) -> MultiTimeframeAnalysis:
    """Resample daily OHLCV to weekly/monthly and analyze trend strength."""
    _validate_input(df)
    daily = _numeric_ohlcv(df).sort_index()
    weekly = resample_ohlcv(daily, freq="W")
    monthly = resample_ohlcv(daily, freq="ME")

    return MultiTimeframeAnalysis(
        daily=_analyze_single_timeframe(daily, timeframe="daily"),
        weekly=_analyze_single_timeframe(weekly, timeframe="weekly"),
        monthly=_analyze_single_timeframe(monthly, timeframe="monthly"),
    )


def resample_ohlcv(df: pd.DataFrame, *, freq: str) -> pd.DataFrame:
    """Resample OHLCV using open=first/high=max/low=min/close=last/volume=sum."""
    if df.empty:
        return df.copy()
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    out = df.resample(freq).agg(agg)
    return out.dropna(subset=["open", "high", "low", "close"])


def _validate_input(df: pd.DataFrame) -> None:
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("df must be a non-empty DataFrame.")
    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"df missing required columns: {missing}")


def _numeric_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in _REQUIRED_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _avg_body(df: pd.DataFrame, *, lookback: int) -> float:
    body = (df["close"] - df["open"]).abs()
    trailing = body.tail(lookback)
    value = trailing.mean()
    if pd.isna(value) or float(value) <= 0:
        return 1e-9
    return float(value)


def _detect_doji(df: pd.DataFrame) -> bool:
    doji = ta.cdl_doji(df["open"], df["high"], df["low"], df["close"])
    if doji is None:
        return False
    value = pd.to_numeric(doji, errors="coerce").dropna()
    if value.empty:
        return False
    return bool(value.iloc[-1] != 0)


def _detect_hammer_like(df: pd.DataFrame) -> tuple[bool, bool]:
    last = df.iloc[-1]
    body = abs(last["close"] - last["open"])
    body_ref = max(body, 1e-9)
    upper_shadow = last["high"] - max(last["open"], last["close"])
    lower_shadow = min(last["open"], last["close"]) - last["low"]

    shape_match = bool(lower_shadow > 2.0 * body_ref and upper_shadow <= body_ref)
    if not shape_match:
        return False, False

    if _HAS_TALIB:
        talib_result = ta.cdl_pattern(df["open"], df["high"], df["low"], df["close"], name=["hammer", "hangingman"])
        if talib_result is not None and not talib_result.empty:
            hammer_col = _find_col(talib_result.columns, "CDL_HAMMER")
            hanging_col = _find_col(talib_result.columns, "CDL_HANGINGMAN")
            hammer = hammer_col is not None and float(talib_result[hammer_col].iloc[-1]) != 0.0
            hanging = hanging_col is not None and float(talib_result[hanging_col].iloc[-1]) != 0.0
            if hammer or hanging:
                return hammer, hanging

    recent = pd.to_numeric(df["close"], errors="coerce").tail(10).dropna()
    if len(recent) < 4:
        return True, False
    trend_delta = float(recent.iloc[-1] - recent.iloc[0])
    if trend_delta < 0:
        return True, False
    return False, True


def _detect_engulfing(prev: pd.Series, last: pd.Series) -> bool:
    prev_body_low = min(prev["open"], prev["close"])
    prev_body_high = max(prev["open"], prev["close"])
    last_body_low = min(last["open"], last["close"])
    last_body_high = max(last["open"], last["close"])

    bullish = (
        prev["close"] < prev["open"]
        and last["close"] > last["open"]
        and last_body_low <= prev_body_low
        and last_body_high >= prev_body_high
    )
    bearish = (
        prev["close"] > prev["open"]
        and last["close"] < last["open"]
        and last_body_low <= prev_body_low
        and last_body_high >= prev_body_high
    )
    return bool(bullish or bearish)


def _detect_star_patterns(df: pd.DataFrame) -> tuple[bool, bool]:
    if len(df) < 3:
        return False, False
    c1 = df.iloc[-3]
    c2 = df.iloc[-2]
    c3 = df.iloc[-1]

    body1 = abs(c1["close"] - c1["open"])
    body2 = abs(c2["close"] - c2["open"])
    body3 = abs(c3["close"] - c3["open"])
    body1_ref = max(body1, 1e-9)

    morningstar = (
        c1["close"] < c1["open"]
        and body2 < body1_ref * 0.6
        and c3["close"] > c3["open"]
        and c3["close"] >= (c1["open"] + c1["close"]) / 2.0
    )
    eveningstar = (
        c1["close"] > c1["open"]
        and body2 < body1_ref * 0.6
        and c3["close"] < c3["open"]
        and c3["close"] <= (c1["open"] + c1["close"]) / 2.0
    )
    return bool(morningstar), bool(eveningstar)


def _local_extrema(series: pd.Series, *, find_min: bool) -> list[int]:
    values = pd.to_numeric(series, errors="coerce").to_numpy()
    idxs: list[int] = []
    for i in range(1, len(values) - 1):
        left = values[i - 1]
        center = values[i]
        right = values[i + 1]
        if pd.isna(center) or pd.isna(left) or pd.isna(right):
            continue
        if find_min and center <= left and center <= right and (center < left or center < right):
            idxs.append(i)
        if not find_min and center >= left and center >= right and (center > left or center > right):
            idxs.append(i)
    return idxs


def _detect_w_bottom(df: pd.DataFrame, *, tolerance_pct: float) -> ChartPatternResult:
    lows = pd.to_numeric(df["low"], errors="coerce")
    highs = pd.to_numeric(df["high"], errors="coerce")
    min_idxs = _local_extrema(lows, find_min=True)

    best: tuple[int, int, float, float, float] | None = None
    for i in range(len(min_idxs)):
        for j in range(i + 1, len(min_idxs)):
            i1 = min_idxs[i]
            i2 = min_idxs[j]
            if i2 - i1 < 5:
                continue

            low1 = float(lows.iloc[i1])
            low2 = float(lows.iloc[i2])
            avg_low = (low1 + low2) / 2.0
            if avg_low <= 0:
                continue
            if abs(low1 - low2) / avg_low > tolerance_pct:
                continue

            mid_high = float(highs.iloc[i1 : i2 + 1].max())
            if mid_high <= avg_low * 1.03:
                continue
            best = (i1, i2, low1, low2, mid_high)

    if best is None:
        return ChartPatternResult(
            pattern_type="W底（雙底）",
            formed=False,
            description="未形成標準W底型態",
        )

    i1, i2, low1, low2, neckline = best
    return ChartPatternResult(
        pattern_type="W底（雙底）",
        formed=True,
        description="近60日形成標準W底型態",
        key_points=[
            ("低點1", low1),
            ("低點2", low2),
            ("頸線", neckline),
            ("索引區間", float(i2 - i1)),
        ],
    )


def _detect_m_top(df: pd.DataFrame, *, tolerance_pct: float) -> ChartPatternResult:
    highs = pd.to_numeric(df["high"], errors="coerce")
    lows = pd.to_numeric(df["low"], errors="coerce")
    max_idxs = _local_extrema(highs, find_min=False)

    best: tuple[int, int, float, float, float] | None = None
    for i in range(len(max_idxs)):
        for j in range(i + 1, len(max_idxs)):
            i1 = max_idxs[i]
            i2 = max_idxs[j]
            if i2 - i1 < 5:
                continue

            high1 = float(highs.iloc[i1])
            high2 = float(highs.iloc[i2])
            avg_high = (high1 + high2) / 2.0
            if avg_high <= 0:
                continue
            if abs(high1 - high2) / avg_high > tolerance_pct:
                continue

            mid_low = float(lows.iloc[i1 : i2 + 1].min())
            if mid_low >= avg_high * 0.97:
                continue
            best = (i1, i2, high1, high2, mid_low)

    if best is None:
        return ChartPatternResult(
            pattern_type="M頭（雙頂）",
            formed=False,
            description="未形成標準M頭型態",
        )

    i1, i2, high1, high2, neckline = best
    return ChartPatternResult(
        pattern_type="M頭（雙頂）",
        formed=True,
        description="近60日形成標準M頭型態",
        key_points=[
            ("高點1", high1),
            ("高點2", high2),
            ("頸線", neckline),
            ("索引區間", float(i2 - i1)),
        ],
    )


def _find_col(columns: pd.Index, prefix: str) -> str | None:
    pfx = prefix.upper()
    for col in columns:
        if str(col).upper().startswith(pfx):
            return str(col)
    return None


def _analyze_single_timeframe(df: pd.DataFrame, *, timeframe: str) -> TimeframeTrend:
    close = pd.to_numeric(df["close"], errors="coerce")
    ma5 = close.rolling(5, min_periods=5).mean().iloc[-1] if len(close) >= 5 else pd.NA
    ma20 = close.rolling(20, min_periods=20).mean().iloc[-1] if len(close) >= 20 else pd.NA
    ma60 = close.rolling(60, min_periods=60).mean().iloc[-1] if len(close) >= 60 else pd.NA

    trend = _determine_trend_simple(
        ma5=float(ma5) if pd.notna(ma5) else None,
        ma20=float(ma20) if pd.notna(ma20) else None,
        ma60=float(ma60) if pd.notna(ma60) else None,
    )
    rsi = ta.rsi(close, length=14)
    latest_rsi = None
    if rsi is not None:
        rsi_values = pd.to_numeric(rsi, errors="coerce").dropna()
        if not rsi_values.empty:
            latest_rsi = float(rsi_values.iloc[-1])
    strength = _determine_strength(trend=trend, rsi=latest_rsi)
    return TimeframeTrend(timeframe=timeframe, trend_direction=trend, strength=strength)


def _determine_trend_simple(ma5: float | None, ma20: float | None, ma60: float | None) -> str:
    if ma5 is None or ma20 is None:
        return "盤整"
    if ma60 is None:
        if ma5 > ma20:
            return "多頭"
        if ma5 < ma20:
            return "空頭"
        return "盤整"
    if ma5 > ma20 > ma60:
        return "多頭"
    if ma5 < ma20 < ma60:
        return "空頭"
    return "盤整"


def _determine_strength(*, trend: str, rsi: float | None) -> str:
    if rsi is None:
        return "中"
    if trend == "多頭" and rsi > 60:
        return "強"
    if trend == "多頭" and 50 <= rsi <= 60:
        return "中強"
    if trend == "空頭" or rsi < 40:
        return "弱"
    return "中"


def _empty_candle_patterns() -> list[CandlePattern]:
    return [
        CandlePattern(name="長紅 K", detected=False, description="多方力道"),
        CandlePattern(name="長黑 K", detected=False, description="空方力道"),
        CandlePattern(name="十字線", detected=False, description="多空拉鋸"),
        CandlePattern(name="錘子", detected=False, description="反轉訊號"),
        CandlePattern(name="吊人", detected=False, description="反轉訊號"),
        CandlePattern(name="吞噬", detected=False, description="反轉確認"),
        CandlePattern(name="晨星", detected=False, description="強反轉"),
        CandlePattern(name="夜星", detected=False, description="強反轉"),
        CandlePattern(name="帶上影線", detected=False, description="上檔壓力"),
        CandlePattern(name="帶下影線", detected=False, description="下檔支撐"),
    ]
