"""Score the 起漲訊號 checklists (起漲訊號.md) for a list of TW symbols.

Usage (any cwd):
  C:\\_work\\AI_Work\\Projects\\QuantTraderV2\\.venv\\Scripts\\python.exe signals.py [2489,1802 ...] [--date 2026-10-07]

Without symbols, uses watchlist.json. Prints one row per symbol:
  A = 起漲前 1 天 (9 items), B = 起漲當天 (8 items), marks per item (✓/·), and upside context
  (60d daily vol, historical +15%-in-15d rate after a >=5% day, distance to 52w high, RS20, foreign streak).
Ranking is a judgment call (see 起漲訊號.md §3); this script only supplies the numbers.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import warnings
from datetime import date
from pathlib import Path

import pandas as pd
import pandas_ta as ta
import yfinance as yf

import premarket as pm

warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
FOREIGN_DAYS = 6  # foreign streak is counted back at most this many trading days


def load_daily(codes: list[str]) -> tuple[dict[str, pd.DataFrame], pd.Series]:
    """yfinance daily bars (split-adjusted) for each code, trying .TW then .TWO; plus ^TWII closes."""
    tickers = [f"{c}.TW" for c in codes] + [f"{c}.TWO" for c in codes] + ["^TWII"]
    raw = yf.download(tickers, period="3y", interval="1d", auto_adjust=False, progress=False, group_by="ticker")
    out = {}
    for c in codes:
        for t in (f"{c}.TW", f"{c}.TWO"):
            if t in raw.columns.get_level_values(0):
                d = raw[t].dropna(subset=["Close"])
                if len(d) > 30:
                    out[c] = d
                    break
    return out, raw["^TWII"]["Close"].dropna()


def foreign_net(day: str) -> dict:
    """{code: {"name", "net" (shares), ...}} for one trading day; cached."""
    for p in (CACHE / f"premarket_{day}.json", CACHE / f"foreign_{day}.json"):
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            return data.get("foreign", data) or {}
    data = pm.fetch_foreign(date.fromisoformat(day)) or {}
    if data:
        CACHE.mkdir(exist_ok=True)
        (CACHE / f"foreign_{day}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def score(d: pd.DataFrame, ix: pd.Series, nets: list[float]) -> dict:
    """d: daily bars up to the evaluation day; nets: foreign net (lots), oldest -> evaluation day."""
    c, h, l, v = d.Close, d.High, d.Low, d.Volume
    box = c.iloc[-11:-1]
    rng = h.iloc[-1] - l.iloc[-1]
    ma = {n: c.iloc[-n:].mean() for n in (5, 10, 20)}
    bb = ta.bbands(c, length=20)
    bw = (bb.iloc[:, 2] - bb.iloc[:, 0]) / bb.iloc[:, 1] * 100
    bw_rank = (bw.iloc[-60:] <= bw.iloc[-1]).mean() * 100 if bw.dropna().size >= 40 else math.nan
    st = ta.stoch(h, l, c, k=9, d=3, smooth_k=3)
    k, dd = st.iloc[:, 0], st.iloc[:, 1]
    streak = 0
    for n in reversed(nets):
        if n is None or n <= 0:
            break
        streak += 1

    chg = (c.iloc[-1] / c.iloc[-2] - 1) * 100
    boxp = (box.max() / box.min() - 1) * 100
    dry = v.iloc[-6:-1].mean() / v.iloc[-21:-1].mean()
    vr = v.iloc[-1] / v.iloc[-6:-1].mean()
    conv = (max(ma.values()) / min(ma.values()) - 1) * 100
    slope = (ma[20] / c.iloc[-25:-5].mean() - 1) * 100
    dtop = (c.iloc[-1] / box.max() - 1) * 100
    ixd = ix[ix.index <= d.index[-1]]
    rs20 = (c.iloc[-1] / c.iloc[-21] - ixd.iloc[-1] / ixd.iloc[-21]) * 100
    cpos = (c.iloc[-1] - l.iloc[-1]) / rng * 100 if rng else 50.0
    kd_cross = bool(k.iloc[-1] > dd.iloc[-1] and k.iloc[-2] <= dd.iloc[-2] + 3 and dd.iloc[-1] < 35)
    today_net = nets[-1] if nets else None

    a = [boxp <= 7, dry < 1, vr >= 1.3, bw_rank <= 20, conv <= 5, abs(slope) <= 3, abs(dtop) <= 4,
         streak >= 2, rs20 <= 0]
    b = [chg >= 2, boxp <= 6, dry < 1, vr >= 1.3, c.iloc[-1] >= box.max(), cpos >= 60, kd_cross,
         today_net is not None and today_net > 0]

    # upside context
    mx15 = pd.concat([h.shift(-i) for i in range(1, 16)], axis=1).max(axis=1)
    hit = (mx15 / c - 1 >= 0.15).iloc[:-15]
    big = ((c / c.shift() - 1) >= 0.05).iloc[:-15]
    cond = hit[big]
    return {
        "收": round(c.iloc[-1], 2), "漲%": round(chg, 1),
        "A前1天": f"{sum(a)}/9", "B當天": f"{sum(b)}/8",
        "A項": "".join("✓" if x else "·" for x in a), "B項": "".join("✓" if x else "·" for x in b),
        "日波動%": round((c / c.shift() - 1).iloc[-60:].std() * 100, 1),
        "大漲後15d≥15%": f"{cond.mean() * 100:.0f}%(n={cond.size})" if cond.size else "-",
        "距52週高%": round((h.iloc[-251:-1].max() / c.iloc[-1] - 1) * 100),
        "RS20": round(rs20, 1), "外資連買": streak,
        "外資合計張": round(sum(n for n in nets if n is not None)),
    }


def cut_unadjusted(d: pd.DataFrame) -> pd.DataFrame:
    """Drop bars before a >25% one-bar gap on >2x volume (split the source failed to adjust).
    yfinance normally adjusts splits; 25% avoids false hits when a missing bar merges two limit moves."""
    gap = (d.Close / d.Close.shift() - 1).abs()
    hit = (gap > 0.25) & (d.Volume > 2 * d.Volume.rolling(20).mean().shift())
    return d[d.index >= hit[hit].index[-1]] if hit.any() else d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("symbols", nargs="?", default="", help="comma separated, default watchlist.json")
    ap.add_argument("--date", default="", help="evaluation day YYYY-MM-DD (default: latest bar)")
    args = ap.parse_args()
    codes = [x.strip() for x in args.symbols.split(",") if x.strip()]
    if not codes:
        codes = json.loads((HERE / "watchlist.json").read_text(encoding="utf-8"))["symbols"]

    daily, ix = load_daily(codes)
    if args.date:
        ix = ix[ix.index <= args.date]
    days = [x.strftime("%Y-%m-%d") for x in ix.index[-FOREIGN_DAYS:]]
    foreign = {day: foreign_net(day) for day in days}

    rows = []
    for code in codes:
        d = daily.get(code)
        if d is None:
            print(f"{code}: no daily data")
            continue
        d = cut_unadjusted(d[d.index <= ix.index[-1]])
        if len(d) < 30:
            print(f"{code}: not enough bars after split")
            continue
        nets = [(foreign[day].get(code) or {}).get("net") for day in days]
        nets = [None if n is None else n / 1000 for n in nets]
        name = next((foreign[day][code]["name"] for day in reversed(days) if code in foreign[day]), "")
        rows.append({"股": f"{code} {name}".strip(), **score(d, ix, nets)})

    print(f"評估日 {ix.index[-1]:%Y-%m-%d}　A=起漲前1天(9)　B=起漲當天(8)　定義見 起漲訊號.md")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print(pd.DataFrame(rows).set_index("股").to_string())


if __name__ == "__main__":
    main()
