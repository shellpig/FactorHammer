"""Score the 起漲訊號 checklists (起漲訊號.md) for a list of TW symbols.

Usage (any cwd):
  C:\\_work\\AI_Work\\Projects\\QuantTraderV2\\.venv\\Scripts\\python.exe signals.py [2489,1802 ...] [--date 2026-10-07]

Without symbols, uses watchlist.json. Prints one row per symbol:
  A = 起漲前 1 天 (9 items), B = 起漲當天 (8 items), marks per item (✓/·), upside context
  (60d daily vol, historical +15%-in-15d rate after a >=5% day, distance to 52w high, RS20, foreign streak),
  and the backtested momentum columns (起漲訊號.md §3 / §7): 52w high, MA uptrend (today/prev), combo,
  同業新高 (industry peers at a 52w high, backtest universe), 投信5日% (5-day trust net / 20d avg volume).
Daily bars yfinance lacks after the backtest cache are filled from official TWSE/TPEx daily quotes.
Ranking follows 起漲訊號.md §3; this script only supplies the numbers.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import time
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
BT = CACHE / "bt"
FOREIGN_DAYS = 6  # foreign streak is counted back at most this many trading days
TRUST_DAYS = 5
PEER_MIN = 5                   # industries with fewer liquid stocks: 同業新高 not available (same as backtest)
MIN_VOL, MIN_PX = 300_000, 10  # backtest universe filter: 20d average volume (shares), close


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


def fetch_trust(d: date) -> dict | None:
    """Per-stock investment trust (投信) net shares: TWSE TWT44U + TPEx dailyTrade column 13.
    TWT44U lists only stocks the trusts traded; a missing stock = no trust trade."""
    j = pm._get(f"https://www.twse.com.tw/rwd/zh/fund/TWT44U?date={d:%Y%m%d}&response=json").json()
    twse = {r[1].strip(): pm._num(r[5]) for r in j.get("data") or []}
    j = pm._get(f"https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={d:%Y/%m/%d}&response=json").json()
    tpex = {r[0].strip(): pm._num(r[13]) for r in (j.get("tables") or [{}])[0].get("data") or []}
    return twse | tpex if twse and tpex else None


def trust_net(day: str) -> dict:
    """{code: net shares} for one trading day; cached in cache/bt/trust/ (shared with backtest_signals.py)."""
    p = BT / "trust" / f"{day}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    data = fetch_trust(date.fromisoformat(day)) or {}
    if data:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data), encoding="utf-8")
    return data


def day_quotes(day: str) -> dict:
    """{code: [open, high, low, close, volume shares]} for all TWSE + TPEx securities (official), plus "^TWII"
    (close only). Empty dict = no trading that day. Cached once the day has passed or has data."""
    p = CACHE / f"quotes_{day}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    out = {}
    j = pm._get(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={day.replace('-', '')}"
                "&type=ALLBUT0999&response=json").json()
    for tb in j.get("tables") or []:
        f = tb.get("fields") or []
        if "證券代號" in f and "收盤價" in f:
            cols = [f.index(k) for k in ("開盤價", "最高價", "最低價", "收盤價", "成交股數")]
            out |= {r[0].strip(): [pm._num(r[i]) for i in cols] for r in tb["data"]}
        elif "收盤指數" in f:
            out |= {"^TWII": [None, None, None, pm._num(r[1]), None] for r in tb.get("data") or []
                    if r[0] == "發行量加權股價指數"}
    if out:
        time.sleep(1)  # TWSE / TPEx block bursts
        j = pm._get(f"https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?date={day.replace('-', '/')}"
                    "&id=&response=json").json()
        out |= {r[0].strip(): [pm._num(r[i]) for i in (4, 5, 6, 2, 8)] for r in j["tables"][0]["data"]}
        out = {c: x for c, x in out.items() if c == "^TWII" or None not in x}
    if out or day < date.today().isoformat():
        CACHE.mkdir(exist_ok=True)
        p.write_text(json.dumps(out), encoding="utf-8")
    return out


def recent_days(start: str, end: str) -> list[str]:
    """Trading days in (start, end] per official daily quotes (weekdays without quotes = holidays)."""
    days = [x.strftime("%Y-%m-%d") for x in pd.bdate_range(pd.Timestamp(start) + pd.Timedelta(days=1), end)]
    return [x for x in days if day_quotes(x)]


def patch(d: pd.DataFrame, code: str, days: list[str]) -> pd.DataFrame:
    """Fill official OHLCV bars for `days` that yfinance lacks (missing row or NaN close)."""
    d = d.copy()
    for x in days:
        ts, q = pd.Timestamp(x), day_quotes(x).get(code)
        if q and (ts not in d.index or pd.isna(d.at[ts, "Close"])):
            d.loc[ts, ["Open", "High", "Low", "Close", "Volume"]] = q
    return d.sort_index()


def peer_highs(day: str, days: list[str]) -> tuple[dict, dict, dict]:
    """Liquid stocks of the backtest universe (cache/bt/*.parquet) closing at a 52-week high on `day`, per industry.
    Bars after each parquet's end come from official quotes. Returns ({industry: codes}, {industry: n}, {code: industry})."""
    ind = json.loads((BT / "industry.json").read_text(encoding="utf-8"))
    highs, size = {}, {}
    for p in BT.glob("[0-9]*.parquet"):
        c = p.stem
        if c not in ind:
            continue
        d = pd.read_parquet(p).dropna(subset=["Close"])
        d = d[d.index <= day]
        if d.empty:
            continue
        d = cut_unadjusted(patch(d, c, [x for x in days if pd.Timestamp(x) > d.index[-1]]))
        if len(d) < 201 or d.index[-1] != pd.Timestamp(day):
            continue
        if d.Volume.iloc[-20:].mean() < MIN_VOL or d.Close.iloc[-1] < MIN_PX:
            continue
        size[ind[c]] = size.get(ind[c], 0) + 1
        if d.Close.iloc[-1] > d.High.iloc[-251:-1].max():
            highs.setdefault(ind[c], set()).add(c)
    return highs, size, ind


def momentum(d: pd.DataFrame, ix: pd.Series, trust: list[float]) -> dict:
    """backtest_signals.py definitions on the evaluation day; trust: net shares over the last TRUST_DAYS days."""
    c, h, v = d.Close, d.High, d.Volume
    ma20, ma60 = c.rolling(20).mean(), c.rolling(60).mean()
    up = (c > ma20) & (c > ma60) & (ma20 > ma20.shift(5)) & (ma60 > ma60.shift(5))
    near52 = c.iloc[-1] / h.iloc[-250:].max()
    brk = (c.iloc[-1] / c.iloc[-2] >= 1.02 and v.iloc[-1] >= 1.3 * v.iloc[-6:-1].mean()
           and c.iloc[-1] >= c.iloc[-11:-1].max())
    ixd = ix[ix.index <= d.index[-1]]
    combo = brk and near52 >= 0.95 and bool(up.iloc[-2]) and ixd.iloc[-1] > ixd.iloc[-60:].mean()
    return {"near52": f"{near52 * 100:.0f}%", "創高": "✓" if c.iloc[-1] > h.iloc[-251:-1].max() else "·",
            "均多": f"{'✓' if up.iloc[-1] else '✗'}({'✓' if up.iloc[-2] else '✗'})", "組合": "✓" if combo else "·",
            "投信5日%": round(sum(trust) / v.iloc[-20:].mean() * 100, 1)}


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
    end = args.date or date.today().isoformat()
    base = pd.read_parquet(BT / "_TWII.parquet").index[-1].strftime("%Y-%m-%d")
    recent = recent_days(base, end)          # official trading days after the backtest cache
    for x in recent:
        tw = day_quotes(x).get("^TWII")
        if tw and pd.Timestamp(x) not in ix.index:
            ix.loc[pd.Timestamp(x)] = tw[3]
    ix = ix[ix.index <= end].sort_index()
    days = [x.strftime("%Y-%m-%d") for x in ix.index[-FOREIGN_DAYS:]]
    foreign = {day: foreign_net(day) for day in days}
    tdays = days[-TRUST_DAYS:]
    trust = {day: trust_net(day) for day in tdays}
    highs, size, ind = peer_highs(days[-1], recent)

    rows = []
    for code in codes:
        d = daily.get(code)
        if d is None:
            print(f"{code}: no daily data")
            continue
        d = patch(d, code, recent)
        d = cut_unadjusted(d[d.index <= ix.index[-1]])
        if len(d) < 30:
            print(f"{code}: not enough bars after split")
            continue
        nets = [(foreign[day].get(code) or {}).get("net") for day in days]
        nets = [None if n is None else n / 1000 for n in nets]
        name = next((foreign[day][code]["name"] for day in reversed(days) if code in foreign[day]), "")
        g = ind.get(code)
        peers = len(highs.get(g, set()) - {code}) if size.get(g, 0) >= PEER_MIN else "-"
        rows.append({"股": f"{code} {name}".strip(), **score(d, ix, nets),
                     **momentum(d, ix, [trust[day].get(code) or 0 for day in tdays]), "同業新高": peers, "產業": g or "-"})

    print(f"評估日 {ix.index[-1]:%Y-%m-%d}　A=起漲前1天(9，觀察用)　B=起漲當天(8)　定義見 起漲訊號.md")
    print("動能欄（§3 主排序）：near52=收盤/52週最高　均多=今日(前日)　組合=放量突破+收紅+near52≥95%+前日均多+大盤多頭　"
          f"同業新高=同產業其他流動股創52週新高檔數　投信5日%=近{TRUST_DAYS}日投信買賣超/20日均量")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print(pd.DataFrame(rows).set_index("股").to_string())


if __name__ == "__main__":
    main()
