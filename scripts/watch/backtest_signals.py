"""Event-study backtest of the 起漲訊號 checklists (起漲訊號.md §1) on locally cached daily bars.

Usage (any cwd):
  ...\\.venv\\Scripts\\python.exe backtest_signals.py fetch 6234,5460,...   # yfinance ~3y daily -> cache/bt/ (skips cached)
  ...\\.venv\\Scripts\\python.exe backtest_signals.py fetch --random 40 --seed 1  # + random liquid uncached stocks
  ...\\.venv\\Scripts\\python.exe backtest_signals.py foreign               # per-day foreign net -> cache/bt/foreign/ (~40 min, resumable)
  ...\\.venv\\Scripts\\python.exe backtest_signals.py run                   # score every cached stock-day and report
  ...\\.venv\\Scripts\\python.exe backtest_signals.py run --only refine|bd|breadth|pullback [--since YYYY-MM-DD]

Phase 1: technical items only (A8 / B8 foreign items excluded) -> A out of 8, B out of 7.
Phase 2 (when cache/bt/foreign/ has data): adds A8 / B8 and reports on the covered days.
Signal day t (close) -> entry at open of t+1 -> outcomes over t+1..t+15, compared with every liquid stock-day.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pandas_ta as ta
import yfinance as yf

import premarket as pm
from signals import HERE, cut_unadjusted

warnings.filterwarnings("ignore")
BT = HERE / "cache" / "bt"
FDIR = BT / "foreign"
TDIR = BT / "trust"
FOREIGN_SLEEP = 3.0           # seconds between days (2 requests each); TWSE blocks bursts
START = "2023-07-01"          # ~60 bars warm-up before the first scored day
FIRST = "2023-10-01"
OOS = "2025-10-08"            # last year = out-of-sample (thresholds were picked from 2026 samples)
HOLD, HIT, STOP, COST = 15, 0.15, -0.07, 0.006
MIN_VOL, MIN_PX = 300_000, 10  # 20d average volume (shares), close
DEDUP = 10                    # same stock re-triggering within this many bars counts once
A_MIN, B_MIN = 6, 6           # = A 7/9, B 7/8 if the foreign item were met
A_NAMES = ["A1箱型窄", "A2之前量縮", "A3量先放出", "A4波動壓縮", "A5均線糾結", "A6月線走平", "A7貼近箱頂", "A9尚未發動"]
B_NAMES = ["B1收紅", "B2箱型窄", "B3之前量縮", "B4放量", "B5收過箱頂", "B6收在高檔", "B7KD低檔交叉"]


def fetch(codes: list[str]) -> None:
    BT.mkdir(parents=True, exist_ok=True)
    todo = [c for c in codes if not (BT / f"{c}.parquet").exists()]
    for c in sorted(set(codes) - set(todo)):
        print(f"{c}: cached")
    if not todo:
        return
    tickers = [f"{c}.TW" for c in todo] + [f"{c}.TWO" for c in todo] + ["^TWII"]
    raw = yf.download(tickers, start=START, interval="1d", auto_adjust=False, progress=False, group_by="ticker")
    for c in todo:
        for t in (f"{c}.TW", f"{c}.TWO"):
            d = raw[t].dropna(subset=["Close"]) if t in raw.columns.get_level_values(0) else None
            if d is not None and len(d) > 30:
                d.to_parquet(BT / f"{c}.parquet")
                print(f"{c}: {t} {len(d)} bars {d.index[0]:%Y-%m-%d}~{d.index[-1]:%Y-%m-%d}")
                break
        else:
            print(f"{c}: no data")
    raw["^TWII"].dropna(subset=["Close"]).to_parquet(BT / "_TWII.parquet")


def universe(day: str, liquid: bool = True) -> list[str]:
    """Listed + OTC common stocks; liquid=True keeps that day's volume >= MIN_VOL and close >= MIN_PX (proxy for
    the 20d filter). liquid=False keeps all, so stocks illiquid *now* but liquid in the past are not dropped."""
    ymd = day.replace("-", "")
    j = pm._get(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ymd}&type=ALLBUT0999&response=json").json()
    t = next(t for t in j["tables"] if "證券代號" in (t.get("fields") or []))
    rows = [(r[0], pm._num(r[2]), pm._num(r[8])) for r in t["data"]]
    j = pm._get(f"https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?date={day.replace('-', '/')}&response=json").json()
    rows += [(r[0], pm._num(r[8]), pm._num(r[2])) for r in j["tables"][0]["data"]]
    return sorted(c for c, v, px in rows if re.fullmatch(r"[1-9]\d{3}", c)
                  and (not liquid or (v and px and v >= MIN_VOL and px >= MIN_PX)))


def _foreign(d: date) -> dict | None:
    data = pm.fetch_foreign(d)
    return {c: x["net"] for c, x in data.items()} if data else None


def _trust(d: date) -> dict | None:
    """Per-stock investment trust (投信) net shares: TWSE TWT44U + TPEx dailyTrade column 13.
    TWT44U lists only stocks the trusts traded; a missing stock = no trust trade."""
    j = pm._get(f"https://www.twse.com.tw/rwd/zh/fund/TWT44U?date={d:%Y%m%d}&response=json").json()
    twse = {r[1].strip(): pm._num(r[5]) for r in j.get("data") or []}
    j = pm._get(f"https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={d:%Y/%m/%d}&response=json").json()
    tpex = {r[0].strip(): pm._num(r[13]) for r in (j.get("tables") or [{}])[0].get("data") or []}
    return twse | tpex if twse and tpex else None


def _local_foreign(day: str) -> dict | None:
    """Foreign data already cached by premarket.py / signals.py."""
    for p in (HERE / "cache" / f"premarket_{day}.json", HERE / "cache" / f"foreign_{day}.json"):
        if p.exists():
            j = json.loads(p.read_text(encoding="utf-8"))
            data = j.get("foreign", j)
            return {c: x["net"] for c, x in data.items()} if data else None
    return None


INST = {"foreign": (FDIR, _foreign, _local_foreign), "trust": (TDIR, _trust, lambda day: None)}


def inst_fetch(kind: str) -> None:
    """Per-day institutional net (shares) for all TWSE/TPEx stocks -> cache/bt/<kind>/<day>.json; resumable."""
    out, fetcher, local = INST[kind]
    out.mkdir(parents=True, exist_ok=True)
    start = pd.Timestamp(FIRST) - pd.Timedelta(days=40)   # 投信首買 looks back 20 bars
    days = [x.strftime("%Y-%m-%d") for x in pd.read_parquet(BT / "_TWII.parquet").index if x >= start]
    todo = [d for d in days if not (out / f"{d}.json").exists()]
    print(f"{kind}: {len(days)} days, {len(todo)} to fetch, ~{len(todo) * FOREIGN_SLEEP / 60:.0f} min", flush=True)
    fails = streak = 0
    for i, day in enumerate(todo, 1):
        data = local(day)
        if data is None:
            try:
                data = fetcher(date.fromisoformat(day))
            except Exception as e:
                print(f"{day}: {e}", flush=True)
            time.sleep(FOREIGN_SLEEP)
        if data:
            (out / f"{day}.json").write_text(json.dumps(data), encoding="utf-8")
            streak = 0
        else:
            fails, streak = fails + 1, streak + 1
            if streak >= 5:
                print(f"{day}: 5 failures in a row, stopping (re-run later to resume)", flush=True)
                break
        if i % 50 == 0:
            print(f"{i}/{len(todo)} {day}", flush=True)
    print(f"{kind} done, {fails} failed", flush=True)


def load_inst(kind: str) -> pd.DataFrame:
    """dates x codes net shares; a row exists only for days that were fetched."""
    rows = {pd.Timestamp(p.stem): json.loads(p.read_text(encoding="utf-8")) for p in sorted(INST[kind][0].glob("*.json"))}
    return pd.DataFrame.from_dict(rows, orient="index").astype(float) if rows else pd.DataFrame()


def features(d: pd.DataFrame, ix: pd.Series, fx: pd.DataFrame | None = None, code: str = "",
             tx: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-day checklist items (same definitions as signals.score) plus forward outcomes."""
    o, c, h, l, v = d.Open, d.Close, d.High, d.Low, d.Volume
    box_hi, box_lo = c.shift().rolling(10).max(), c.shift().rolling(10).min()
    boxp = (box_hi / box_lo - 1) * 100
    v5 = v.shift().rolling(5).mean()
    dry, vr = v5 / v.shift().rolling(20).mean(), v / v5
    bb = ta.bbands(c, length=20)
    bw = (bb.iloc[:, 2] - bb.iloc[:, 0]) / bb.iloc[:, 1] * 100
    bw_rank = bw.rolling(60, min_periods=40).apply(lambda x: (x <= x[-1]).mean() * 100, raw=True).where(bw.notna())
    ma = pd.concat([c.rolling(n).mean() for n in (5, 10, 20)], axis=1)
    conv = (ma.max(axis=1) / ma.min(axis=1) - 1) * 100
    slope = (ma.iloc[:, 2] / c.shift(5).rolling(20).mean() - 1) * 100
    dtop = (c / box_hi - 1) * 100
    ixa = ix.reindex(d.index).ffill()
    rs20 = (c / c.shift(20) - ixa / ixa.shift(20)) * 100
    chg = (c / c.shift() - 1) * 100
    rng = h - l
    cpos = ((c - l) / rng * 100).where(rng > 0, 50.0)
    st = ta.stoch(h, l, c, k=9, d=3, smooth_k=3).reindex(d.index)
    k, dd = st.iloc[:, 0], st.iloc[:, 1]
    kd = (k > dd) & (k.shift() <= dd.shift() + 3) & (dd < 35)

    a = [boxp <= 7, dry < 1, vr >= 1.3, bw_rank <= 20, conv <= 5, slope.abs() <= 3, dtop.abs() <= 4, rs20 <= 0]
    b = [chg >= 2, boxp <= 6, dry < 1, vr >= 1.3, c >= box_hi, cpos >= 60, kd]
    f = pd.DataFrame({**dict(zip(A_NAMES, a)), **dict(zip(B_NAMES, b))}, index=d.index)
    f["A"], f["B"] = f[A_NAMES].sum(axis=1), f[B_NAMES].sum(axis=1)
    f["A_prev"] = f["A"].shift()
    if fx is not None and len(fx):
        has = pd.Series(d.index.isin(fx.index), index=d.index)
        net = (fx[code] if code in fx else pd.Series(np.nan, index=fx.index)).reindex(d.index)
        f["外資有資料"] = has & has.shift(fill_value=False)
        f["A8外資連買"] = (net > 0) & (net.shift() > 0)   # missing = not a buy, same as signals.score
        f["B8外資買超"] = net > 0
        f["A9分"], f["B8分"] = f["A"] + f["A8外資連買"], f["B"] + f["B8外資買超"]
        n0, av = net.fillna(0), v.rolling(20).mean()
        f["外資3日%"], f["外資5日%"] = n0.rolling(3).sum() / av * 100, n0.rolling(5).sum() / av * 100
    if tx is not None and len(tx):
        has = pd.Series(d.index.isin(tx.index), index=d.index)
        net = (tx[code] if code in tx else pd.Series(np.nan, index=tx.index)).reindex(d.index)
        buy = net > 0                                    # missing = trusts did not trade it
        f["投信有資料"] = has & has.rolling(21, min_periods=21).sum().eq(21)
        f["投信買超"] = buy
        f["投信連買≥2"] = buy & buy.shift(fill_value=False)
        f["投信連買≥3"] = f["投信連買≥2"] & buy.shift(2, fill_value=False)
        f["投信首買"] = buy & buy.shift().rolling(20).sum().eq(0)     # first buy in 20 bars
        f["投信大買"] = net >= 0.05 * v.rolling(20).mean()             # >= 5% of 20d avg volume
        f["投信賣超"] = net < 0
        n0, av = net.fillna(0), v.rolling(20).mean()
        f["投信3日%"], f["投信5日%"] = n0.rolling(3).sum() / av * 100, n0.rolling(5).sum() / av * 100

    entry = o.shift(-1).to_numpy()
    hi = np.column_stack([h.shift(-i) for i in range(1, HOLD + 1)]) / entry[:, None] - 1
    lo = np.column_stack([l.shift(-i) for i in range(1, HOLD + 1)]) / entry[:, None] - 1
    up, dn = hi >= HIT, lo <= STOP
    hit_day = np.where(up.any(axis=1), up.argmax(axis=1), HOLD)
    stop_day = np.where(dn.any(axis=1), dn.argmax(axis=1), HOLD)
    f["hit"] = hit_day < HOLD
    f["stop_first"] = (stop_day < HOLD) & (stop_day <= hit_day)   # same bar -> assume stop first
    f["max15"] = np.nanmax(hi, axis=1) * 100
    f["ret15"] = (c.shift(-HOLD).to_numpy() / entry - 1 - COST) * 100
    f["ret20"] = (c.shift(-20).to_numpy() / entry - 1 - COST) * 100

    # exit rules: stop STOP / target HIT checked each bar; a gap through the level fills at the open;
    # stop and target on the same bar -> stop first (conservative); otherwise exit at close of bar HOLD
    op = np.column_stack([o.shift(-i) for i in range(1, HOLD + 1)]) / entry[:, None] - 1
    cl = c.shift(-HOLD).to_numpy() / entry - 1
    sd, hd = np.minimum(stop_day, HOLD - 1)[:, None], np.minimum(hit_day, HOLD - 1)[:, None]
    stop_px = np.minimum(np.take_along_axis(op, sd, 1)[:, 0], STOP)
    tgt_px = np.maximum(np.take_along_axis(op, hd, 1)[:, 0], HIT)
    stopped = stop_day < HOLD
    f["ex停損"] = (np.where(stopped, stop_px, cl) - COST) * 100
    first_stop = stopped & (stop_day <= hit_day)
    f["ex停損停利"] = (np.where(first_stop, stop_px, np.where(hit_day < HOLD, tgt_px, cl)) - COST) * 100
    f["持有日"] = np.minimum(np.where(first_stop, stop_day, hit_day), HOLD - 1) + 1

    # batch 1 candidates (see report "第一批")
    f["near52"] = c / h.rolling(250, min_periods=200).max()
    f["vr"] = vr
    f["gap"] = (o.shift(-1) / c - 1) * 100      # next-day open vs signal-day close (entry gap)
    f["創52週新高"] = c > h.shift().rolling(250, min_periods=200).max()
    f["量50日前10%"] = v > v.shift().rolling(50).quantile(0.9)
    f["max20"] = chg.rolling(20).max()
    f["前20日漲停"] = (chg >= 9.5).shift().rolling(20).sum()
    f["r3"], f["r5"], f["r20"] = (c / c.shift(3) - 1) * 100, (c / c.shift(5) - 1) * 100, (c / c.shift(20) - 1) * 100
    ma20, ma60 = ma.iloc[:, 2], c.rolling(60).mean()
    f["均線多頭"] = (c > ma20) & (c > ma60) & (ma20 > ma20.shift(5)) & (ma60 > ma60.shift(5))
    f["前日均線多頭"] = f["均線多頭"].shift(fill_value=False)
    # D 破底翻: dipped through support intraday, closed back above it near the high of the day
    low10, ma20p = l.shift().rolling(10).min(), ma20.shift()
    strong = (chg >= 2) & (cpos >= 80)
    f["收紅強"] = strong
    f["破底翻10"] = (l < low10) & (c >= low10) & strong
    f["破MA20"] = (l < ma20p) & (ma20p <= c) & (c.shift() >= ma20p) & strong
    f["大盤多頭"] = (ix > ix.rolling(60).mean()).reindex(d.index).ffill().fillna(False).astype(bool)
    f["跳空突破"] = (o > h.shift()) & (o >= box_hi) & (c >= box_hi)
    f["缺口未補"] = f["跳空突破"] & (l > h.shift())

    # idea 2: the bar after a 放量突破+收紅 (this row = day t+1, entry = open of t+2)
    brk = f["B4放量"] & f["B5收過箱頂"] & f["B1收紅"]
    f["前日突破收紅"] = brk.shift(fill_value=False)
    f["前日near52"] = f["near52"].shift()
    f["隔日收漲"] = c > c.shift()
    f["隔日開高走低"] = (o > c.shift()) & (c < o)
    f["隔日守住箱頂"] = c >= box_hi.shift()
    # idea 3: relative strength on a market down day
    f["chg"] = chg
    f["大盤漲跌"] = (ix.pct_change() * 100).reindex(d.index)
    f["vol60"] = c.pct_change().rolling(60).std() * 100
    f["pos"] = np.arange(len(d))

    # Martin Luk 回調買入法 (daily proxy; the minute-bar trigger cannot be tested)
    e9, e21, e50 = (ta.ema(c, length=n) for n in (9, 21, 50))
    f["r21"], f["r63"], f["r126"] = ((c / c.shift(n) - 1) * 100 for n in (21, 63, 126))
    f["收在EMA21上"] = c > e21
    f["近3日觸EMA21"] = ((l <= e21 * 1.02) & (l >= e21 * 0.97)).rolling(3).max().astype(bool)
    f["EMA9_21上彎"] = (e9 >= e9.shift(3)) & (e21 >= e21.shift(5))
    f["EMA多頭排列"] = (e9 > e21) & (e21 > e50)
    f["低點墊高"] = l.rolling(10).min() > l.shift(10).rolling(10).min()
    f["波動收斂"] = rng.rolling(5).mean() < rng.rolling(20).mean()
    f["離前高"] = (c / h.shift().rolling(20).max() - 1) * 100
    f["突破前K高"] = c > h.shift()
    # R exit: stop = signal-day low, target = +3R, otherwise close of bar HOLD; gap through a level fills at the open
    stop_r = (l.to_numpy() / entry - 1)[:, None]                 # negative when entry > low
    f["停損距離%"] = -stop_r[:, 0] * 100
    tgt_r = -3 * stop_r
    dn_r, up_r = lo <= stop_r, hi >= tgt_r
    sd_r = np.where(dn_r.any(axis=1), dn_r.argmax(axis=1), HOLD)
    td_r = np.where(up_r.any(axis=1), up_r.argmax(axis=1), HOLD)
    s_px = np.minimum(np.take_along_axis(op, np.minimum(sd_r, HOLD - 1)[:, None], 1)[:, 0], stop_r[:, 0])
    t_px = np.maximum(np.take_along_axis(op, np.minimum(td_r, HOLD - 1)[:, None], 1)[:, 0], tgt_r[:, 0])
    first = (sd_r < HOLD) & (sd_r <= td_r)
    ret_r = np.where(first, s_px, np.where(td_r < HOLD, t_px, cl))
    valid = stop_r[:, 0] < 0
    f["exR停損3R"] = np.where(valid, (ret_r - COST) * 100, np.nan)
    f["exR_R倍"] = np.where(valid, ret_r / -stop_r[:, 0], np.nan)
    ok =(c.shift(-HOLD).notna() & (o.shift(-1) > 0) & (v.rolling(20).mean() >= MIN_VOL) & (c >= MIN_PX)
          & (d.index >= FIRST))
    return f[ok.to_numpy()]


def dedup(df: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    keep = []
    for _, g in df[mask].groupby("code"):
        last = -10**9
        for i, p in zip(g.index, g.pos):
            if p - last > DEDUP:
                keep.append(i)
                last = p
    return df.loc[keep]


def stats(g: pd.DataFrame, base_hit: float | None = None) -> dict:
    r = {"n": len(g), "達+15%": g.hit.mean() * 100, "先跌-7%": g.stop_first.mean() * 100,
         "15日報酬均": g.ret15.mean(), "15日報酬中位": g.ret15.median(), "15日最高均": g.max15.mean()}
    if "ret20" in g:
        r |= {"20日報酬均": g.ret20.mean(), "20日報酬中位": g.ret20.median(),
              "樣本外15日均": g.loc[g["期間"] == "樣本外", "ret15"].mean()}
    if base_hit:
        r["lift"] = r["達+15%"] / base_hit
    return r


def table(rows: dict) -> str:
    return pd.DataFrame(rows).T.round(2).to_string()


def foreign_report(df: pd.DataFrame) -> None:
    """Phase 2: original 9 / 8 item scores and whether foreign buying filters breakouts (covered days only)."""
    print(f"== 外資（第二階段）：有外資資料的股日 {len(df)}，{df.date.min():%Y-%m-%d}～{df.date.max():%Y-%m-%d} ==")
    brk = df["B4放量"] & df["B5收過箱頂"] & df["B1收紅"]
    buy, streak = df["B8外資買超"], df["A8外資連買"]
    sets = {f"A9分≥7/9": df["A9分"] >= 7, f"B8分≥7/8": df["B8分"] >= 7,
            "放量突破+收紅": brk, "  且外資買超": brk & buy, "  且外資非買超": brk & ~buy,
            "  且外資連買≥2": brk & streak, f"A≥{A_MIN}→突破+收紅 且外資買超": brk & (df.A_prev >= A_MIN) & buy,
            f"A≥{A_MIN}→突破+收紅 且外資非買超": brk & (df.A_prev >= A_MIN) & ~buy}
    evs = {k: dedup(df, m) for k, m in sets.items()}
    rows = {}
    for per in ("全部", "樣本內", "樣本外"):
        sel = (lambda x: x) if per == "全部" else (lambda x, per=per: x[x["期間"] == per])
        base = stats(sel(df))
        rows[f"{per} 基準"] = base
        rows.update({f"{per} {k}": stats(sel(ev), base["達+15%"]) for k, ev in evs.items()})
    print(table(rows), "\n")

    base_hit = df.hit.mean() * 100
    print("== 外資單項（未去重）==")
    print(table({n: stats(df[df[n]], base_hit) for n in ("A8外資連買", "B8外資買超")}
                | {"外資非買超": stats(df[~buy], base_hit)}), "\n")
    print("== A9 分數分級（9 項，未去重）==")
    print(table({f"A9={s}": stats(df[df["A9分"] == s], base_hit) for s in range(10) if (df["A9分"] == s).any()}), "\n")

    print("== 放量突破+收紅，依 60 日日波動與外資：達 +15% 比例 % (n) ==")
    bins, labels = [0, 2, 3, 4, 100], ["<2%", "2-3%", "3-4%", "≥4%"]
    out = {}
    for name in ("放量突破+收紅", "  且外資買超", "  且外資非買超"):
        g = evs[name]
        grp = g.groupby(pd.cut(g.vol60, bins, labels=labels), observed=False).hit
        out[name.strip()] = {lab: f"{m * 100:.0f} ({n})" if n else "-" for lab, m, n in zip(labels, grp.mean(), grp.size())}
    grp = df.groupby(pd.cut(df.vol60, bins, labels=labels), observed=False).hit
    out = {"基準": {lab: f"{m * 100:.0f} ({n})" for lab, m, n in zip(labels, grp.mean(), grp.size())}} | out
    print(pd.DataFrame(out).to_string(), "\n")


def trust_report(df: pd.DataFrame) -> None:
    """第二批：投信 (investment trust) flows, alone and on top of the momentum signals (covered days only)."""
    base = stats(df)
    bh = base["達+15%"]
    print(f"== 投信：有資料的股日 {len(df)}，{df.date.min():%Y-%m-%d}～{df.date.max():%Y-%m-%d}（已去重）==")
    single = {n: df[n] for n in ("投信買超", "投信連買≥2", "投信連買≥3", "投信首買", "投信大買", "投信賣超")}
    rows = {}
    for per in ("全部", "樣本內", "樣本外"):
        sel = (lambda x: x) if per == "全部" else (lambda x, per=per: x[x["期間"] == per])
        b = stats(sel(df))
        rows[f"{per} 基準"] = b
        rows.update({f"{per} {k}": stats(sel(dedup(df, m)), b["達+15%"]) for k, m in single.items()})
    print(table(rows), "\n")

    brk = df["B4放量"] & df["B5收過箱頂"] & df["B1收紅"]
    near = df.near52 >= 0.95
    t = {k: df[k] for k in ("投信買超", "投信首買", "投信大買")}
    cross = {}
    for name, m in (("放量突破+收紅", brk), ("距52週高≥95%", near), ("創52週新高", df["創52週新高"])):
        cross[name] = m
        cross[f"{name} 且投信買超"] = m & t["投信買超"]
        cross[f"{name} 且投信未買超"] = m & ~t["投信買超"]
        cross[f"{name} 且投信首買"] = m & t["投信首買"]
        cross[f"{name} 且投信大買"] = m & t["投信大買"]
    evs = {k: dedup(df, m) for k, m in cross.items()}
    print("== 投信 × 動能條件（已去重）==")
    print(table({k: stats(ev, bh) for k, ev in evs.items()}), "\n")
    print("== 投信 × 動能：出場方式比較（已去重）==")
    print(table({k: exit_stats(ev) for k, ev in evs.items() if "首買" not in k and "大買" not in k}), "\n")


def batch1_report(df: pd.DataFrame) -> None:
    """第一批: 52w high, abnormal volume, MAX / limit-up, short-term reversal, MA trend + market state, gap breakout."""
    base = stats(df)
    bh = base["達+15%"]
    brk = df["B4放量"] & df["B5收過箱頂"] & df["B1收紅"]
    rk5, rk20 = df.groupby("date").r5.rank(pct=True), df.groupby("date").r20.rank(pct=True)

    print("== 第一批：單一條件（已去重；主看 15/20 日報酬，樣本外欄 = 2025-10-08 後的 15 日報酬均）==")
    single = {"放量突破+收紅": brk, "創52週新高": df["創52週新高"], "量50日前10%": df["量50日前10%"],
              "量50日前10% 且收紅≥2%": df["量50日前10%"] & df["B1收紅"], "跳空突破": df["跳空突破"],
              "跳空突破 且缺口未補": df["缺口未補"], "均線多頭": df["均線多頭"], "前20日有漲停": df["前20日漲停"] >= 1,
              "5日跌幅最大10%": rk5 <= 0.1, "5日漲幅最大10%": rk5 > 0.9,
              "20日跌幅最大10%": rk20 <= 0.1, "20日漲幅最大10%": rk20 > 0.9}
    print(table({"基準": base} | {k: stats(dedup(df, m), bh) for k, m in single.items()}), "\n")

    print("== 分組（未去重）==")
    groups = {
        "距52週高": pd.cut(df.near52, [0, 0.7, 0.85, 0.95, 1.01], labels=["<70%", "70-85%", "85-95%", "≥95%"]),
        "近20日最大單日漲幅": pd.cut(df.max20, [-100, 3, 6, 9.5, 100], labels=["<3%", "3-6%", "6-9.5%", "≥9.5%(漲停)"]),
        "5日報酬分位": pd.cut(rk5, [0, .1, .3, .7, .9, 1], labels=["跌最多10%", "10-30%", "中間40%", "70-90%", "漲最多10%"]),
        "20日報酬分位": pd.cut(rk20, [0, .1, .3, .7, .9, 1], labels=["跌最多10%", "10-30%", "中間40%", "70-90%", "漲最多10%"]),
    }
    for name, cat in groups.items():
        print(f"-- {name}")
        print(table({str(k): stats(g, bh) for k, g in df.groupby(cat, observed=True)}), "\n")

    print("== 放量突破+收紅 × 各條件（已去重）==")
    cross = {
        "距52週高≥95%": df.near52 >= 0.95, "距52週高<85%": df.near52 < 0.85,
        "前20日無漲停": df["前20日漲停"] == 0, "前20日有漲停": df["前20日漲停"] >= 1,
        "大盤多頭": df["大盤多頭"], "大盤空頭": ~df["大盤多頭"],
        "前日均線多頭": df["前日均線多頭"], "前日非均線多頭": ~df["前日均線多頭"],
        "量50日前10%": df["量50日前10%"], "量未達50日前10%": ~df["量50日前10%"],
        "跳空": df["跳空突破"], "非跳空": ~df["跳空突破"],
    }
    print(table({"放量突破+收紅": stats(dedup(df, brk), bh)}
                | {f"  {k}": stats(dedup(df, brk & m), bh) for k, m in cross.items()}), "\n")

    print("== 均線多頭 × 60 日波動（未去重；Han-Yang-Zhou：高波動股均線擇時較有效）：20 日報酬均 % / 中位 (n) ==")
    vb = pd.cut(df.vol60, [0, 2, 3, 4, 100], labels=["<2%", "2-3%", "3-4%", "≥4%"])
    out = {}
    for name, m in (("均線多頭", df["均線多頭"]), ("非均線多頭", ~df["均線多頭"]), ("全部", df.vol60.notna())):
        g = df[m].groupby(vb[m], observed=False).ret20
        out[name] = {k: f"{a:.2f} / {b:.2f} ({n})" for k, a, b, n in zip(g.mean().index, g.mean(), g.median(), g.size())}
    print(pd.DataFrame(out).to_string(), "\n")


def exit_stats(g: pd.DataFrame) -> dict:
    r = {"n": len(g)}
    for col, name in (("ret15", "持有15日"), ("ex停損", "停損-7%"), ("ex停損停利", "停損-7%停利+15%")):
        x = g[col].dropna()
        r |= {f"{name} 均": x.mean(), f"{name} 中位": x.median(), f"{name} 勝率": (x > 0).mean() * 100}
    r["停損停利 平均持有日"] = g["持有日"].mean()
    return r


def _periods(df: pd.DataFrame, sets: dict, ref: str, dedup_ref: bool = True) -> dict:
    """stats per period for each (deduped) set; lift vs the `ref` set of the same period."""
    rows = {}
    for per in ("全部", "樣本內", "樣本外"):
        sel = (lambda x: x) if per == "全部" else (lambda x, per=per: x[x["期間"] == per])
        evs = {k: sel(dedup(df, m)) if (k != ref or dedup_ref) else sel(df[m]) for k, m in sets.items()}
        rh = evs[ref].hit.mean() * 100
        rows.update({f"{per} {k}": stats(ev, rh) for k, ev in evs.items()})
    return rows


def ideas_report(df: pd.DataFrame) -> None:
    """Idea 2: does the bar after a breakout tell anything?  Idea 3: relative strength on market down days."""
    nxt = df["前日突破收紅"]
    print("== 想法 2：放量突破+收紅的「隔天」走勢（本列=隔天，進場=再隔一天開盤；已去重）==")
    sets = {"隔天(全部)": nxt, "  隔天收漲": nxt & df["隔日收漲"], "  隔天收跌": nxt & ~df["隔日收漲"],
            "  隔天開高走低": nxt & df["隔日開高走低"], "  隔天守住箱頂": nxt & df["隔日守住箱頂"],
            "  隔天跌回箱內": nxt & ~df["隔日守住箱頂"],
            "  距52週高≥95% 且隔天收漲": nxt & (df["前日near52"] >= 0.95) & df["隔日收漲"],
            "  距52週高≥95% 且隔天收跌": nxt & (df["前日near52"] >= 0.95) & ~df["隔日收漲"],
            "  距52週高<85% 且隔天收漲": nxt & (df["前日near52"] < 0.85) & df["隔日收漲"],
            "  距52週高<85% 且隔天收跌": nxt & (df["前日near52"] < 0.85) & ~df["隔日收漲"]}
    print(table(_periods(df, sets, "隔天(全部)")), "\n")

    down = df["大盤漲跌"] <= -1
    rk = df.groupby("date").chg.rank(pct=True)
    print(f"== 想法 3：加權指數跌 ≥1% 的日子（{df.loc[down, 'date'].nunique()} 天），個股當日表現 → 之後報酬（已去重）==")
    sets = {"大盤跌日(全部股)": down, "  逆勢收漲": down & (df.chg > 0), "  逆勢收紅≥2%": down & (df.chg >= 2),
            "  當日漲幅前10%": down & (rk > 0.9), "  當日跌幅前10%": down & (rk <= 0.1),
            "  逆勢收紅≥2% 且均線多頭": down & (df.chg >= 2) & df["均線多頭"],
            "  逆勢收紅≥2% 且距52週高≥95%": down & (df.chg >= 2) & (df.near52 >= 0.95)}
    print(table(_periods(df, sets, "大盤跌日(全部股)")), "\n")
    print("-- 對照：非大盤跌日的收紅≥2%")
    print(table({"全部股日": stats(df[~down]), "收紅≥2%": stats(dedup(df, ~down & (df.chg >= 2)))}), "\n")


def combo_report(df: pd.DataFrame) -> None:
    """Pre-registered combo (decided before looking at it): 放量突破+收紅 + 距52週高≥95% + 前日均線多頭 + 大盤多頭."""
    brk = df["B4放量"] & df["B5收過箱頂"] & df["B1收紅"]
    combo = brk & (df.near52 >= 0.95) & df["前日均線多頭"] & df["大盤多頭"]
    sets = {"放量突破+收紅": brk, "創52週新高": df["創52週新高"], "組合": combo}
    evs = {k: dedup(df, m) for k, m in sets.items()}
    print("== 預先定義組合：放量突破+收紅 + 距52週高≥95% + 前日均線多頭 + 大盤多頭（已去重；報酬已扣成本，單位 %）==")
    rows = {}
    for per in ("全部", "樣本內", "樣本外"):
        sel = (lambda x: x) if per == "全部" else (lambda x, per=per: x[x["期間"] == per])
        rows[f"{per} 基準(全部股日)"] = exit_stats(sel(df))
        rows.update({f"{per} {k}": exit_stats(sel(ev)) for k, ev in evs.items()})
    print(table(rows), "\n")

    print("-- 組合 依年度（停損-7%停利+15%）")
    ev = evs["組合"]
    yr = ev.date.dt.year
    base_yr = df.groupby(df.date.dt.year)["ex停損停利"].mean()
    print(pd.DataFrame({"n": ev.groupby(yr).size(), "均": ev.groupby(yr)["ex停損停利"].mean(),
                        "中位": ev.groupby(yr)["ex停損停利"].median(),
                        "勝率": ev.groupby(yr)["ex停損停利"].apply(lambda x: (x > 0).mean() * 100),
                        "基準均": base_yr}).round(2).to_string(), "\n")
    ev[["date", "code", "期間", "ret15", "ex停損", "ex停損停利", "持有日", "vol60", "near52"]].to_csv(
        BT / "combo_events.csv", index=False, encoding="utf-8-sig")
    print(f"組合事件明細 -> {BT / 'combo_events.csv'}（{len(ev)} 筆）\n")


def robust(df: pd.DataFrame, ev: pd.DataFrame, crowd: int = 20) -> dict:
    """Clustering-robust view of a (deduped) event set. 同日超額 = per signal date, mean ret15 of the events minus
    mean ret15 of every stock-day in `df` that date; then mean / median across dates. 排除擁擠日 = drop signal
    dates on which the set has >= `crowd` events, recompute n / ret15 / 停損停利."""
    nan = float("nan")
    if ev.empty:
        return {"日數": 0, "同日超額均": nan, "同日超額中位": nan, "擁擠日數": 0, "排除擁擠 n": 0,
                "排除擁擠 15日均": nan, "排除擁擠 15日中位": nan, "排除擁擠 停損停利均": nan}
    day_base = df.groupby("date").ret15.mean()
    cnt = ev.groupby("date").size()
    exc = ev.groupby("date").ret15.mean() - day_base.reindex(cnt.index)
    kept = ev[ev.date.map(cnt) < crowd]
    return {"日數": len(cnt), "同日超額均": exc.mean(), "同日超額中位": exc.median(), "擁擠日數": int((cnt >= crowd).sum()),
            "排除擁擠 n": len(kept), "排除擁擠 15日均": kept.ret15.mean(), "排除擁擠 15日中位": kept.ret15.median(),
            "排除擁擠 停損停利均": kept["ex停損停利"].mean()}


def _ex_gap(g: pd.DataFrame, df: pd.DataFrame, is_base: bool = False) -> dict:
    """is_base: baseline rows are not event sets, so no crowded-date exclusion."""
    return exit_stats(g) | {"隔日開盤跳空均%": g.gap.mean()} | robust(df, g, 10**9 if is_base else 20)


def _ex_table(evs: dict, bases: dict, df: pd.DataFrame) -> str:
    """exit_stats (+ mean entry gap + robustness columns) per period; `bases` rows are used as given, `evs` are already
    deduped; `df` supplies the all-stock-day reference for 同日超額."""
    rows = {}
    for per in ("全部", "樣本內", "樣本外"):
        sel = (lambda x: x) if per == "全部" else (lambda x, per=per: x[x["期間"] == per])
        rows.update({f"{per} {k}": _ex_gap(sel(g), df, k in bases) for k, g in (bases | evs).items()})
    return table(rows)


def refine_report(df: pd.DataFrame) -> None:
    """Thresholds fixed in advance: A looser near-miss thresholds, C multi-day institutional flows, E limit-up days."""
    b5, trend = df["B5收過箱頂"], df["前日均線多頭"] & df["大盤多頭"]
    brk = df["B4放量"] & b5 & df["B1收紅"]
    combo = brk & (df.near52 >= 0.95) & trend
    print("== refine A 放寬門檻：B1收紅 & B5收過箱頂 & 前日均線多頭 & 大盤多頭，near52 × 量比 vr（已去重；報酬已扣成本 %）==")
    base = df["B1收紅"] & b5 & trend
    sets = {"現行組合": combo}
    for nr in (0.90, 0.92, 0.95):
        for vr in (1.0, 1.2, 1.3):
            sets[f"near52≥{nr:.2f} vr≥{vr:.1f}"] = base & (df.near52 >= nr) & (df.vr >= vr)
    sets["近失格(0.90≤near<0.95 & vr≥1.3 | near≥0.95 & 1.2≤vr<1.3)"] = base & (
        ((df.near52 >= 0.90) & (df.near52 < 0.95) & (df.vr >= 1.3)) | ((df.near52 >= 0.95) & (df.vr >= 1.2) & (df.vr < 1.3)))
    evs = {k: dedup(df, m) for k, m in sets.items()}
    print(_ex_table(evs, {"基準(全部股日)": df}, df), "\n")
    print("-- A 依年度（停損-7%停利+15% 均 (n)）")
    yrs = sorted(df.date.dt.year.unique())
    out = {"基準": {y: f"{g['ex停損停利'].mean():.2f} ({len(g)})" for y, g in df.groupby(df.date.dt.year)}}
    for k, ev in evs.items():
        out[k] = {y: f"{g['ex停損停利'].mean():.2f} ({len(g)})" for y, g in ev.groupby(ev.date.dt.year)}
    print(pd.DataFrame(out).T.reindex(columns=yrs).fillna("-").to_string(), "\n")

    print("== refine C 法人累計：近 3/5 日淨買超 / 20日均量 %（缺資料日=0；限有資料列；已去重）==")
    if "投信有資料" not in df or "外資有資料" not in df:
        print("缺投信或外資資料，略過\n")
    else:
        T, F = df[df["投信有資料"]], df[df["外資有資料"]]
        TF = df[df["投信有資料"] & df["外資有資料"]]
        overlays = {"(a)全部股日": lambda g: pd.Series(True, index=g.index), "(b)near52≥0.95": lambda g: g.near52 >= 0.95,
                    "(c)創52週新高": lambda g: g["創52週新高"],
                    "(d)放量突破+收紅": lambda g: g["B4放量"] & g["B5收過箱頂"] & g["B1收紅"]}
        flows = [("投信", T, {"投信3日%≥2": lambda g: g["投信3日%"] >= 2, "投信3日%≥5": lambda g: g["投信3日%"] >= 5,
                              "投信5日%≥2": lambda g: g["投信5日%"] >= 2, "投信5日%≥5": lambda g: g["投信5日%"] >= 5,
                              "[單日]投信買超": lambda g: g["投信買超"], "[單日]投信大買": lambda g: g["投信大買"]}),
                 ("外資", F, {"外資3日%≥5": lambda g: g["外資3日%"] >= 5, "外資3日%≥10": lambda g: g["外資3日%"] >= 10,
                              "外資5日%≥5": lambda g: g["外資5日%"] >= 5, "外資5日%≥10": lambda g: g["外資5日%"] >= 10,
                              "[單日]外資買超": lambda g: g["B8外資買超"]}),
                 ("兩者", TF, {"投信5日>0 且 外資5日>0": lambda g: (g["投信5日%"] > 0) & (g["外資5日%"] > 0)})]
        for oname, ofn in overlays.items():
            evs, bases = {}, {}
            for tag, g, fl in flows:
                om = ofn(g)
                bases[f"{oname}基準({tag}有資料)"] = g if oname.startswith("(a)") else dedup(g, om)
                evs.update({f"{oname} {k}": dedup(g, om & fn(g)) for k, fn in fl.items()})
            print(f"-- {oname}")
            print(_ex_table(evs, bases, df), "\n")

    print("== refine E 漲停日（chg≥9.5 為漲停收盤代理；進場=隔日開盤，隔日開盤跳空均 = open(t+1)/close(t)-1；已去重）==")
    lim, vr = df.chg >= 9.5, df.vr
    sets = {"漲停(全部)": lim, "(1)漲停 & 收過箱頂": lim & b5,
            "(2)漲停 & 收過箱頂 & near52≥0.95 & 前日均線多頭 & 大盤多頭": lim & b5 & (df.near52 >= 0.95) & trend,
            "(3)現行組合": combo, "(3)組合 & 漲停": combo & lim, "(3)組合 & 非漲停": combo & ~lim,
            "(4)漲停 & vr<1.3": lim & (vr < 1.3), "(4)漲停 & vr≥1.3": lim & (vr >= 1.3)}
    print(_ex_table({k: dedup(df, m) for k, m in sets.items()}, {"基準(全部股日)": df}, df), "\n")


def load_industry() -> dict:
    """{code: 產業別 code} for TWSE-listed + TPEx stocks, cached to cache/bt/industry.json. The classification is
    the *current* one, applied to all history (reclassified / delisted stocks are mis-grouped in the past)."""
    p = BT / "industry.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for url, kc, ki in (("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", "公司代號", "產業別"),
                        ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", "SecuritiesCompanyCode", "SecuritiesIndustryCode")):
        for attempt in range(6):          # TPEx sometimes drops the connection
            try:
                rows = pm._get(url).json()
                break
            except Exception as e:
                print(f"{url}: {e}, retry {attempt + 1}", flush=True)
                time.sleep(3)
        else:
            raise RuntimeError(f"cannot fetch {url}")
        out |= {r[kc].strip(): r[ki].strip() for r in rows if re.fullmatch(r"[1-9]\d{3}", r[kc].strip())}
    BT.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"industry: {len(out)} stocks, {len(set(out.values()))} industries -> {p}")
    return out


def add_group(df: pd.DataFrame, min_size: int = 5) -> pd.DataFrame:
    """Per date x industry, over the stocks present in `df` that day: peers (excluding the stock itself) at a 52w
    high / near52>=0.95 / with 5-day trust net buying. Industries with < min_size stocks that day -> NaN."""
    df["產業"] = df.code.map(load_industry())
    key = [df.date, df.產業]
    size = df.code.groupby(key).transform("size")
    ok = size >= min_size
    new, near = df["創52週新高"].astype(float), (df.near52 >= 0.95).astype(float)
    n_new, n_near = new.groupby(key).transform("sum") - new, near.groupby(key).transform("sum") - near
    df["同業新高數"] = n_new.where(ok)
    df["同業新高比"] = (n_new / (size - 1)).where(ok)
    df["同業近高比"] = (n_near / (size - 1)).where(ok)
    df["同業投信買比"] = np.nan
    if "投信5日%" in df:
        has = df["投信有資料"].astype(float)
        buy = ((df["投信5日%"] > 0) & df["投信有資料"]).astype(float)
        cnt, nb = has.groupby(key).transform("sum") - has, buy.groupby(key).transform("sum") - buy
        df["同業投信買比"] = (nb / cnt).where(ok & (cnt > 0))
    return df


def _year_table(df: pd.DataFrame, ev: pd.DataFrame) -> str:
    yr = ev.date.dt.year
    day = ev.groupby("date").ret15.mean() - df.groupby("date").ret15.mean()
    exc = day.dropna().groupby(day.dropna().index.year).mean()
    ex = ev.groupby(yr)["ex停損停利"]
    return pd.DataFrame({"n": ev.groupby(yr).size(), "日數": ev.groupby(yr).date.nunique(),
                         "15日均": ev.groupby(yr).ret15.mean(), "停損停利均": ex.mean(), "停損停利中位": ex.median(),
                         "停損停利勝率": ex.apply(lambda x: (x > 0).mean() * 100), "同日超額均": exc,
                         "基準停損停利均": df.groupby(df.date.dt.year)["ex停損停利"].mean()}).round(2).to_string()


def _best(df: pd.DataFrame, evs: dict, exclude: tuple = ()) -> str | None:
    """Best set = highest min(樣本內, 樣本外 同日超額均) among sets with n >= 50 in both periods (fixed rule)."""
    score = {}
    for k, ev in evs.items():
        a, b = ev[ev["期間"] == "樣本內"], ev[ev["期間"] == "樣本外"]
        if k not in exclude and len(a) >= 50 and len(b) >= 50:
            score[k] = min(robust(df, a)["同日超額均"], robust(df, b)["同日超額均"])
    return max(score, key=score.get) if score else None


def _named(sets: list) -> dict:
    """(key, mask) pairs; keys starting with two spaces are children of the previous top-level key (made unique by
    prefixing it)."""
    out, last = {}, ""
    for k, m in sets:
        if not k.startswith("  "):
            last = k
        out[k if not k.startswith("  ") else f"{last.split(' [')[0]}{k.rstrip()}"] = m
    return out


def group_reversal_report(df: pd.DataFrame) -> None:
    """B industry / group momentum and D 破底翻; sets pre-registered (not tuned after looking). Robustness columns:
    日數 / 同日超額 / 排除擁擠日 (dates with >= 20 events of the set dropped)."""
    brk = df["B4放量"] & df["B5收過箱頂"] & df["B1收紅"]
    combo = brk & (df.near52 >= 0.95) & df["前日均線多頭"] & df["大盤多頭"]
    avail = df["同業新高數"].notna()
    print("== B 族群動能：產業別為現行分類套用全期；同日同產業股數<5 或無產業對照者視為不可用 ==")
    print(f"股日 {len(df)}，無產業對照 {df.產業.isna().sum()}，產業當日<5檔 {(df.產業.notna() & ~avail).sum()}，可用 {avail.sum()}"
          f"（{avail.mean() * 100:.0f}%）；平均每產業每日 {df[avail].groupby(['date', '產業']).size().mean():.1f} 檔\n")
    nh, nr = df["創52週新高"] & avail, (df.near52 >= 0.95) & avail
    tb = nh & df["投信有資料"] & (df["投信5日%"] >= 5) if "投信5日%" in df else nh & False
    sets = [("現行組合(不限同業可用)", combo), ("創52週新高 [同業可用]", nh),
            ("  & 同業新高數≥2", nh & (df.同業新高數 >= 2)), ("  & 同業新高數≥3", nh & (df.同業新高數 >= 3)),
            ("near52≥0.95 [同業可用]", nr),
            ("  & 同業近高比≥20%", nr & (df.同業近高比 >= 0.2)), ("  & 同業近高比≥30%", nr & (df.同業近高比 >= 0.3)),
            ("現行組合 [同業可用]", combo & avail),
            ("  & 同業新高數≥2", combo & avail & (df.同業新高數 >= 2)), ("  & 同業新高數=0", combo & avail & (df.同業新高數 == 0)),
            ("創52週新高&投信5日%≥5 [同業可用]", tb),
            ("  & 同業新高數≥2", tb & (df.同業新高數 >= 2))]
    evs = {k: dedup(df, m) for k, m in _named(sets).items()}
    print(_ex_table(evs, {"基準(全部股日)": df}, df), "\n")
    bk = _best(df, evs, exclude=tuple(k for k in evs if "不限" in k or "[同業可用]" in k))
    if bk:
        print(f"-- B 最佳組（規則：樣本內/外 n≥50 且 min(兩期同日超額均) 最大，不含基準列）：{bk}")
        print(_year_table(df, evs[bk]), "\n")

    print("== D 破底翻：low<前10日最低 & close≥該低點 & 收在日內高 80% 以上 & 漲≥2%；破MA20：low<MA20(t-1)≤close 且前日收在 MA20 之上 ==")
    d10 = df["破底翻10"]
    sets = [("現行組合", combo), ("收紅≥2%&收在高檔≥80%(對照)", df["收紅強"]),
            ("破底翻10", d10), ("  & 前日均線多頭", d10 & df["前日均線多頭"]), ("  & near52≥0.90", d10 & (df.near52 >= 0.90)),
            ("  & vr≥1.3", d10 & (df.vr >= 1.3)), ("破MA20", df["破MA20"])]
    evs = {k: dedup(df, m) for k, m in _named(sets).items()}
    print(_ex_table(evs, {"基準(全部股日)": df}, df), "\n")
    bk = _best(df, evs, exclude=("現行組合", "收紅≥2%&收在高檔≥80%(對照)"))
    if bk:
        print(f"-- D 最佳組（同上規則）：{bk}")
        print(_year_table(df, evs[bk]), "\n")


def add_breadth(df: pd.DataFrame, min_size: int = 5) -> pd.DataFrame:
    """Per date x industry (same peer pool / exclusions as add_group): count and share of peers (excluding the stock
    itself) whose Y-day return (r3 / r5, %) is > Z%, Y in {3, 5}, Z in {10, 15}. Industries < min_size -> NaN."""
    key = [df.date, df.產業]
    size = df.code.groupby(key).transform("size")
    ok = size >= min_size
    for y in (3, 5):
        for z in (10, 15):
            hit = (df[f"r{y}"] > z).astype(float)
            n = hit.groupby(key).transform("sum") - hit
            df[f"同業{y}日漲{z}數"], df[f"同業{y}日漲{z}比"] = n.where(ok), (n / (size - 1)).where(ok)
    return df


def breadth_report(df: pd.DataFrame) -> None:
    """B2 族群漲幅廣度: >= X peers in the same industry rose > Z% over the last Y trading days. 12 cells (Y 3/5 x Z 10/15
    x X 數>=2 / 數>=3 / 比>=20%) fixed in advance, overlaid on (a) all stock-days and (b) 創52週新高 or 現行組合."""
    add_breadth(df)
    brk = df["B4放量"] & df["B5收過箱頂"] & df["B1收紅"]
    combo = brk & (df.near52 >= 0.95) & df["前日均線多頭"] & df["大盤多頭"]
    avail = df["同業新高數"].notna()
    bases = {"(a)": pd.Series(True, index=df.index), "(b)": df["創52週新高"] | combo}
    print("== B2 族群漲幅廣度：同產業(排除自己)近 Y 個交易日漲幅 > Z% 的檔數 / 占比；同業池與 <5檔排除同 B 族群動能 ==")
    print("(a)=全部股日；(b)=創52週新高 或 現行組合(放量突破+收紅 & near52≥0.95 & 前日均線多頭 & 大盤多頭)；已去重；報酬已扣成本 %")
    print(f"股日 {len(df)}，同業可用 {avail.sum()}（{avail.mean() * 100:.0f}%）；(b) 股日 {bases['(b)'].sum()}"
          f"（同業可用 {(bases['(b)'] & avail).sum()}）\n")
    cells = {}
    for y in (3, 5):
        for z in (10, 15):
            n, r = df[f"同業{y}日漲{z}數"], df[f"同業{y}日漲{z}比"]
            for xn, m in (("數≥2", n >= 2), ("數≥3", n >= 3), ("比≥20%", r >= 0.2)):
                cells[f"{y}日漲{z}% {xn}"] = m
    n5 = df["同業5日漲10數"]
    evs = {}
    for bn, bm in bases.items():
        evs[f"{bn}基準 [同業可用]"] = dedup(df, bm & avail)
        evs.update({f"{bn} {k}": dedup(df, bm & m) for k, m in ({"同業新高數≥2": df["同業新高數"] >= 2} | cells).items()})
    evs["(b) & 同業5日漲10數=0"] = dedup(df, bases["(b)"] & (n5 == 0))
    lag = "落後補漲：自己5日漲<10% & 同業5日漲10數≥2"
    explore = {lag: dedup(df, (df.r5 < 10) & (n5 >= 2))}
    ref = {"基準(全部股日)": df}
    for bn in bases:
        tag = f"{bn}基準 [同業可用]"
        print(f"-- 基底 {bn}")
        print(_ex_table({k: v for k, v in evs.items() if k.startswith(bn)}, ref, df), "\n")
    print("-- 【探索】落後補漲（僅 (a)，Y=5 Z=10）")
    print(_ex_table(explore, ref, df), "\n")

    # lead check on base (a): is the stock already at / about to make its own 52w high when breadth fires?
    d2 = df.sort_values(["code", "date"])
    nh = d2["創52週新高"].astype(float)
    nxt = pd.concat([nh.groupby(d2.code).shift(-i) for i in range(1, 6)], axis=1).max(axis=1).reindex(df.index)
    sets = {k: v for k, v in evs.items() if k.startswith("(a)")} | explore
    rows = {}
    for k, ev in sets.items():
        today = ev["創52週新高"]
        rows[k] = {"n": len(ev), "當日已創新高%": today.mean() * 100, "當日near52≥0.95%": (ev.near52 >= 0.95).mean() * 100,
                   "未創新高者5日內創新高%": nxt.loc[ev.index][~today].mean() * 100, "自己5日漲幅均%": ev.r5.mean()}
    print("-- 領先性（base (a)，已去重；「5日內」以同檔後 5 筆資料列近似）")
    print(table(rows), "\n")

    score = {}
    for k, ev in evs.items():
        if k[4:] in cells:
            a, b = ev[ev["期間"] == "樣本內"], ev[ev["期間"] == "樣本外"]
            if len(a) >= 100 and len(b) >= 100:
                score[k] = min(robust(df, a)["同日超額中位"], robust(df, b)["同日超額中位"])
    if score:
        bk = max(score, key=score.get)
        print(f"-- B2 最佳格（規則：樣本內/外 n≥100 且 min(兩期同日超額中位) 最大；僅 12 格×2 基底，不含對照列）：{bk}")
        print(_year_table(df, evs[bk]), "\n")
    else:
        print("-- B2 最佳格：無任何格在兩期 n≥100\n")


def pullback_report(df: pd.DataFrame) -> None:
    """Martin Luk 回調買入法, daily proxy; sets fixed in advance (2026-10-17, before looking). 強勢 = r21 / r63 / r126 any
    ≥ 30% and in that day's top 30% (rank over the cached liquid stock-days). Trigger = close > previous high after
    touching EMA21 (the minute-bar trigger is replaced by the daily bar). Extra exit: stop = signal-day low, +3R target."""
    rk = {n: df.groupby("date")[n].rank(pct=True) for n in ("r21", "r63", "r126")}
    strong = pd.Series(False, index=df.index)
    for n in rk:
        strong |= (df[n] >= 30) & (rk[n] >= 0.7)
    sup = df["近3日觸EMA21"] & df["收在EMA21上"] & df["EMA9_21上彎"]
    base = df["低點墊高"] & df["波動收斂"]
    trig = df["突破前K高"]
    s3 = strong & sup
    s4 = s3 & base
    s5 = s4 & trig
    sets = _named([("強勢", strong), ("強勢&回到EMA21", s3), ("  &低點墊高&波動收斂", s4),
                   ("  &低點墊高&波動收斂&突破前K高", s5),
                   ("  &...&突破前K高&停損距離≤3%", s5 & (df["停損距離%"] <= 3)),
                   ("  &...&突破前K高&同業新高數≥2", s5 & (df.同業新高數 >= 2)),
                   ("  &...&突破前K高&大盤多頭", s5 & df["大盤多頭"]),
                   ("  &...&突破前K高&EMA多頭排列", s5 & df["EMA多頭排列"]),
                   ("非強勢&同樣回檔型態(對照)", ~strong & sup & base & trig)])
    evs = {k: dedup(df, m) for k, m in sets.items()}
    print("== Martin Luk 回調買入法（日線代理；分鐘線觸發無法回測；已去重；報酬已扣成本 %）==")
    print("強勢=近1/3/6月漲幅任一≥30%且當日排名前30%；回到EMA21=近3日低點在EMA21的-3%~+2%且收在EMA21上、EMA9/21上彎；")
    print("低點墊高=近10日最低>前10日最低；波動收斂=近5日平均振幅<近20日；觸發=收盤>前一日高\n")
    print(_ex_table(evs, {"基準(全部股日)": df}, df), "\n")

    rows = {}
    for per in ("全部", "樣本內", "樣本外"):
        for k, ev in evs.items():
            g = ev if per == "全部" else ev[ev["期間"] == per]
            x = g["exR停損3R"].dropna()
            rows[f"{per} {k}"] = {"n": len(x), "停損距離%中位": g["停損距離%"].median(), "均%": x.mean(), "中位%": x.median(),
                                 "勝率": (x > 0).mean() * 100, "平均R": g["exR_R倍"].mean(),
                                 "達3R%": (g["exR_R倍"] >= 2.99).mean() * 100}
    print("-- 出場：停損=訊號日低點、停利=+3R、否則第15日收盤（R=進場價-訊號日低）")
    print(table(rows), "\n")
    bk = _best(df, evs, exclude=("強勢", "非強勢&同樣回檔型態(對照)"))
    if bk:
        print(f"-- 最佳組（規則同 B：樣本內/外 n≥50 且 min(兩期同日超額均) 最大，不含強勢/對照列）：{bk}")
        print(_year_table(df, evs[bk]), "\n")


def run(since: str = "", only: str = "") -> None:
    ix = pd.read_parquet(BT / "_TWII.parquet").Close
    fx, tx = load_inst("foreign"), load_inst("trust")
    parts = []
    for p in sorted(BT.glob("[0-9]*.parquet")):
        d = cut_unadjusted(pd.read_parquet(p).dropna(subset=["Open", "High", "Low", "Close"]))
        if len(d) < 80:
            print(f"{p.stem}: {len(d)} bars, skipped")
            continue
        parts.append(features(d, ix, fx, p.stem, tx).assign(code=p.stem))
    df = pd.concat(parts).reset_index(names="date").reset_index(drop=True)
    if since:  # indicators still use full history; only signal days >= since are evaluated
        df = df[df.date >= since].reset_index(drop=True)
    df["期間"] = np.where(df.date >= OOS, "樣本外", "樣本內")
    add_group(df)

    print(f"股票 {df.code.nunique()} 檔：{','.join(sorted(df.code.unique()))}")
    print(f"股日 {len(df)}，{df.date.min():%Y-%m-%d}～{df.date.max():%Y-%m-%d}；樣本外自 {OOS}")
    print(f"進場=訊號隔日開盤；{HOLD} 日內最高 ≥ +{HIT:.0%} = 達標；先跌 {STOP:.0%}；報酬已扣 {COST:.1%}\n")
    if only == "refine":
        refine_report(df)
        return
    if only == "bd":
        group_reversal_report(df)
        return
    if only == "breadth":
        breadth_report(df)
        return
    if only == "pullback":
        pullback_report(df)
        return
    ev_a, ev_b = dedup(df, df.A >= A_MIN), dedup(df, df.B >= B_MIN)

    rows = {}
    for per in ("全部", "樣本內", "樣本外"):
        sel = (lambda x: x) if per == "全部" else (lambda x, per=per: x[x["期間"] == per])
        base = stats(sel(df))
        rows[f"{per} 基準(全部股日)"] = base
        rows[f"{per} A≥{A_MIN}/8"] = stats(sel(ev_a), base["達+15%"])
        rows[f"{per} B≥{B_MIN}/7"] = stats(sel(ev_b), base["達+15%"])
    print("== 訊號 vs 基準（訊號已去重：同檔 10 日內只算第一次）==")
    print(table(rows), "\n")

    # 起漲訊號.md usage: A high score, then next day confirms (放量 + 收過箱頂); entry = open after the confirm day
    brk = df["B4放量"] & df["B5收過箱頂"]
    pre = df.A_prev >= A_MIN
    conf = {f"A≥{A_MIN} → 隔日放量突破": brk & pre, f"A≥{A_MIN} → 隔日放量突破且收紅≥2%": brk & pre & df["B1收紅"],
            f"前日 A<{A_MIN} → 放量突破（對照）": brk & ~pre, f"前日 A<{A_MIN} → 放量突破且收紅≥2%（對照）": brk & ~pre & df["B1收紅"]}
    conf_ev = {k: dedup(df, m) for k, m in conf.items()}
    rows = {}
    for per in ("全部", "樣本內", "樣本外"):
        sel = (lambda x: x) if per == "全部" else (lambda x, per=per: x[x["期間"] == per])
        base = stats(sel(df))
        rows[f"{per} 基準"] = base
        rows.update({f"{per} {k}": stats(sel(ev), base["達+15%"]) for k, ev in conf_ev.items()})
    print("== A 高分 + 隔日確認（進場=確認日隔日開盤；已去重）==")
    print(table(rows), "\n")

    base_hit = df.hit.mean() * 100
    for col, top in (("A", 8), ("B", 7)):
        print(f"== {col} 分數分級（未去重）==")
        print(table({f"{col}={s}": stats(df[df[col] == s], base_hit) for s in range(top + 1) if (df[col] == s).any()}), "\n")

    print("== 單項條件成立時（未去重）==")
    print(table({n: stats(df[df[n]], base_hit) for n in A_NAMES + B_NAMES}), "\n")

    print("== 依 60 日日波動分組：達 +15% 比例 % (n) ==")
    bins, labels = [0, 2, 3, 4, 100], ["<2%", "2-3%", "3-4%", "≥4%"]
    out = {}
    groups = [("基準", df), (f"A≥{A_MIN}", ev_a), (f"B≥{B_MIN}", ev_b)]
    groups += [(k.split("（")[0].replace("→ 隔日", "→"), ev) for k, ev in conf_ev.items()]
    for name, g in groups:
        grp = g.groupby(pd.cut(g.vol60, bins, labels=labels), observed=False).hit
        out[name] = {lab: f"{m * 100:.0f} ({n})" if n else "-" for lab, m, n in zip(labels, grp.mean(), grp.size())}
    print(pd.DataFrame(out).to_string(), "\n")

    if "外資有資料" in df:
        foreign_report(df[df["外資有資料"]].reset_index(drop=True))
    batch1_report(df)
    if "投信有資料" in df:
        trust_report(df[df["投信有資料"]].reset_index(drop=True))
    combo_report(df)
    ideas_report(df)
    refine_report(df)
    group_reversal_report(df)
    breadth_report(df)
    pullback_report(df)

    cols = ["date", "code", "期間", "A", "B", "hit", "stop_first", "max15", "ret15", "vol60"]
    ev = pd.concat([ev_a.assign(訊號="A"), ev_b.assign(訊號="B")])[["訊號"] + cols].sort_values(["訊號", "date"])
    ev.to_csv(BT / "events.csv", index=False, encoding="utf-8-sig")
    print(f"事件明細 -> {BT / 'events.csv'}（{len(ev)} 筆）")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    fp = sub.add_parser("fetch")
    fp.add_argument("symbols", nargs="?", default="", help="comma separated codes")
    fp.add_argument("--random", type=int, default=0, help="add N random uncached stocks from universe(--date)")
    fp.add_argument("--date", default="2026-10-07", help="universe day for --random")
    fp.add_argument("--seed", type=int, default=None)
    fp.add_argument("--all-stocks", action="store_true", help="--random draws from all common stocks, not only liquid")
    rp = sub.add_parser("run")
    rp.add_argument("--since", default="", help="only evaluate signal days >= YYYY-MM-DD")
    rp.add_argument("--only", default="", choices=["", "refine", "bd", "breadth", "pullback"],
                    help="refine = only refine_report; bd = only group_reversal_report; breadth = only breadth_report; "
                         "pullback = only pullback_report")
    sub.add_parser("foreign")
    sub.add_parser("trust")
    args = ap.parse_args()
    if args.cmd in INST:
        inst_fetch(args.cmd)
    elif args.cmd == "fetch":
        codes = [x.strip() for x in args.symbols.split(",") if x.strip()]
        if args.random:
            pool = [c for c in universe(args.date, not args.all_stocks) if not (BT / f"{c}.parquet").exists() and c not in codes]
            codes += sorted(random.Random(args.seed).sample(pool, min(args.random, len(pool))))
            print(f"universe {args.date}: {len(pool)} uncached, sampled {args.random}")
        fetch(codes)
    else:
        pd.set_option("display.width", 250)
        pd.set_option("display.max_columns", 30)
        run(args.since, args.only)


if __name__ == "__main__":
    main()
