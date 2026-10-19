"""TDCC 集保股權分散表 (shareholding distribution by holding size) collector.

Usage (any cwd):
  ...\\.venv\\Scripts\\python.exe tdcc.py weekly              # latest week, all securities (open data) -> cache/tdcc/weekly/<date>.csv.gz
  ...\\.venv\\Scripts\\python.exe tdcc.py backfill [codes]     # ~51 past weeks per stock (TDCC query page) -> cache/tdcc/hist/<code>.json
                                                              # default codes = liquid TWSE/TPEx common stocks of the last weekly file
  ...\\.venv\\Scripts\\python.exe tdcc.py backtest            # weekly cross-sectional test of the 大戶 share change (needs hist + cache/bt)
Both are resumable / idempotent. Levels 1..15 (1 = 1-999 shares ... 12 = 400,001-600,000, 15 = > 1,000,000 shares);
大戶(400張以上) = levels 12-15, 千張大戶 = level 15.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import time

import numpy as np
import pandas as pd
import requests

from signals import HERE

OUT = HERE / "cache" / "tdcc"
WEEKLY, HIST = OUT / "weekly", OUT / "hist"
QRY = "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
SLEEP = 0.6  # seconds between query-page requests


def weekly() -> None:
    r = requests.get("https://opendata.tdcc.com.tw/getOD.ashx?id=1-5", timeout=120, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    df = pd.read_csv(io.BytesIO(r.content), encoding="utf-8-sig", dtype={"證券代號": str})
    day = str(df["資料日期"].iloc[0])
    WEEKLY.mkdir(parents=True, exist_ok=True)
    p = WEEKLY / f"{day}.csv.gz"
    if p.exists():
        print(f"{day}: already saved")
        return
    df.to_csv(p, index=False, encoding="utf-8")
    print(f"{day}: {df['證券代號'].nunique()} securities -> {p}")


def _default_codes() -> list[str]:
    from backtest_signals import universe
    files = sorted(WEEKLY.glob("*.csv.gz"))
    if not files:
        raise SystemExit("run `tdcc.py weekly` first")
    d = files[-1].name[:8]
    for back in range(0, 7):   # last trading day on/before the TDCC date
        day = (pd.Timestamp(d) - pd.Timedelta(days=back)).strftime("%Y-%m-%d")
        try:
            codes = universe(day)
            if codes:
                return codes
        except Exception:
            pass
    raise SystemExit("no universe")


class Query:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Mozilla/5.0"
        self._refresh(self.s.get(QRY, timeout=30).text)

    def _refresh(self, html: str) -> None:
        self.token = re.search(r'name="SYNCHRONIZER_TOKEN"[^>]*value="([^"]*)"', html).group(1)
        self.dates = re.findall(r'<option value="(\d{8})"', html)

    def get(self, code: str, day: str) -> list | None:
        r = self.s.post(QRY, timeout=30, data={"SYNCHRONIZER_TOKEN": self.token, "SYNCHRONIZER_URI": "/portal/zh/smWeb/qryStock",
                                               "method": "submit", "firDate": day, "scaDate": day, "sqlMethod": "StockNo",
                                               "stockNo": code, "stockName": ""})
        r.raise_for_status()
        self._refresh(r.text)
        t = next((t for t in pd.read_html(io.StringIO(r.text)) if t.shape[1] == 5), None)
        if t is None or len(t) < 15:
            return None
        t = t.iloc[:15]
        return [[int(a or 0), int(b or 0), float(c or 0)] for a, b, c in
                zip(t.iloc[:, 2].fillna(0), t.iloc[:, 3].fillna(0), t.iloc[:, 4].fillna(0))]


def backfill(codes: list[str]) -> None:
    HIST.mkdir(parents=True, exist_ok=True)
    q = Query()
    print(f"{len(codes)} stocks x {len(q.dates)} weeks ({q.dates[-1]}~{q.dates[0]})", flush=True)
    fails = 0
    for i, code in enumerate(codes, 1):
        p = HIST / f"{code}.json"
        have = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        todo = [d for d in q.dates if d not in have]
        for d in todo:
            for attempt in range(3):
                try:
                    have[d] = q.get(code, d)
                    fails = 0
                    break
                except Exception as e:
                    print(f"{code} {d}: {e}, retry {attempt + 1}", flush=True)
                    time.sleep(10 * (attempt + 1))
                    try:
                        q = Query()
                    except Exception as e2:
                        print(f"re-open query page: {e2}", flush=True)
            else:
                fails += 1
                if fails >= 10:
                    p.write_text(json.dumps(have), encoding="utf-8")
                    raise SystemExit("10 failures in a row, stopping (re-run later to resume)")
            time.sleep(SLEEP)
        if todo:
            p.write_text(json.dumps(have), encoding="utf-8")
        print(f"{i}/{len(codes)} {code}: +{len(todo)}", flush=True)


def _panel(lag: int) -> pd.DataFrame:
    """One row per (TDCC data date D, stock): weekly changes of the holder distribution, past returns up to close of D,
    forward returns from the open of the first trading day after D+1 (Fri data -> Mon open; `lag` extra trading days)."""
    from backtest_signals import BT
    from signals import cut_unadjusted
    rows = []
    for p in sorted(HIST.glob("*.json")):
        px = BT / f"{p.stem}.parquet"
        if not px.exists():
            continue
        d = cut_unadjusted(pd.read_parquet(px).dropna(subset=["Open", "Close"]))
        days, o, c = d.index, d.Open.to_numpy(), d.Close.to_numpy()
        h = json.loads(p.read_text(encoding="utf-8"))
        ws = sorted(k for k in h if h[k])
        for prev, cur in zip(ws, ws[1:]):
            a, b = h[prev], h[cur]
            D = pd.Timestamp(cur)
            i0 = days.searchsorted(D, side="right") - 1          # last bar on/before D
            e = days.searchsorted(D + pd.Timedelta(days=1), side="right") + lag
            if i0 < 20 or days[i0] < D - pd.Timedelta(days=4):
                continue
            r = {"week": D, "code": p.stem,
                 "d大戶": sum(x[2] for x in b[11:]) - sum(x[2] for x in a[11:]),
                 "d千張": b[14][2] - a[14][2],
                 "d人數%": (sum(x[0] for x in b) / max(sum(x[0] for x in a), 1) - 1) * 100,
                 "ret1w": (c[i0] / c[i0 - 5] - 1) * 100, "ret4w": (c[i0] / c[i0 - 20] - 1) * 100}
            for n in (5, 10, 20):
                r[f"f{n}"] = (c[e + n - 1] / o[e] - 1) * 100 if e + n - 1 < len(c) else float("nan")
            rows.append(r)
    return pd.DataFrame(rows)


def _boot(x: pd.Series, block: int = 4, reps: int = 5000, seed: int = 0) -> tuple[float, float]:
    """Moving-block bootstrap 95% CI of the mean of a weekly series (blocks of `block` consecutive weeks)."""
    v = x.dropna().to_numpy()
    if len(v) < block * 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    k = -(-len(v) // block)
    starts = rng.integers(0, len(v) - block + 1, size=(reps, k))
    means = v[(starts[:, :, None] + np.arange(block)).reshape(reps, -1)[:, :len(v)]].mean(axis=1)
    return tuple(np.percentile(means, [2.5, 97.5]))


def _week_stats(s: pd.Series) -> dict:
    lo, hi = _boot(s)
    return {"週數": s.notna().sum(), "均": s.mean(), "中位": s.median(), "CI低": lo, "CI高": hi, "正的週%": (s > 0).mean() * 100}


def backtest() -> None:
    """Pre-registered (2026-10-20, Codex design): main signal = weekly change of the >=400張 share (levels 12-15, pp).
    Cross-sectional per week: forward return minus that week's mean (excess), quintiles of the signal, and a
    Fama-MacBeth regression on industry-demeaned excess with past 1w / 4w return controls. Weekly blocks bootstrap."""
    from backtest_signals import load_industry
    ind = load_industry()
    pd.set_option("display.width", 250)
    for lag in (0, 1):
        df = _panel(lag)
        df["產業"] = df.code.map(ind)
        print(f"\n######## 進場 = 資料日 D 後第一個可得交易日開盤 + {lag} 日（{'週一' if lag == 0 else '週二'}）########")
        print(f"{df.code.nunique()} 檔，{df.week.nunique()} 週（{df.week.min():%Y-%m-%d}～{df.week.max():%Y-%m-%d}），{len(df)} 股週")
        for n in (5, 10, 20):
            f = f"f{n}"
            g = df.dropna(subset=[f]).copy()
            g["ex"] = g[f] - g.groupby("week")[f].transform("mean")
            g["q"] = g.groupby("week")["d大戶"].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1)
            qt = g.groupby(["week", "q"]).ex.mean().unstack()
            print(f"\n== {n} 日（{g.week.nunique()} 週）：大戶占比週變化五分位 → 同週超額報酬 % ==")
            rows = {f"Q{q}": _week_stats(qt[q]) for q in range(1, 6)}
            rows["Q5-Q1"] = _week_stats(qt[5] - qt[1])
            rows["Q5-Q1 前半週"] = _week_stats((qt[5] - qt[1]).iloc[:len(qt) // 2])
            rows["Q5-Q1 後半週"] = _week_stats((qt[5] - qt[1]).iloc[len(qt) // 2:])
            print(pd.DataFrame(rows).T.round(2).to_string())
            # Fama-MacBeth: industry-demeaned excess on z-ranked signal + momentum controls
            g["y"] = g.ex - g.groupby(["week", "產業"]).ex.transform("mean").where(
                g.groupby(["week", "產業"]).ex.transform("size") >= 3, 0)
            coef = {}
            for sig in ("d大戶", "d千張", "d人數%"):
                cs = []
                for w, x in g.groupby("week"):
                    z = x[[sig, "ret1w", "ret4w"]].rank(pct=True) - 0.5
                    X = np.column_stack([np.ones(len(z)), z.to_numpy()])
                    cs.append(np.linalg.lstsq(X, x.y.to_numpy(), rcond=None)[0][1])
                coef[sig + ("（主）" if sig == "d大戶" else "（探索）")] = _week_stats(pd.Series(cs))
            print(f"-- 控制產業 + 前1週/前4週漲幅後，訊號由最低排到最高的超額報酬差 %（Fama-MacBeth）--")
            print(pd.DataFrame(coef).T.round(2).to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("weekly")
    bp = sub.add_parser("backfill")
    bp.add_argument("codes", nargs="?", default="")
    sub.add_parser("backtest")
    a = ap.parse_args()
    if a.cmd == "weekly":
        weekly()
    elif a.cmd == "backtest":
        backtest()
    else:
        backfill([c.strip() for c in a.codes.split(",") if c.strip()] or _default_codes())


if __name__ == "__main__":
    main()
