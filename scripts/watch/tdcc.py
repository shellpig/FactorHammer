"""TDCC 集保股權分散表 (shareholding distribution by holding size) collector.

Usage (any cwd):
  ...\\.venv\\Scripts\\python.exe tdcc.py weekly              # latest week, all securities (open data) -> cache/tdcc/weekly/<date>.csv.gz
  ...\\.venv\\Scripts\\python.exe tdcc.py backfill [codes]     # ~51 past weeks per stock (TDCC query page) -> cache/tdcc/hist/<code>.json
                                                              # default codes = liquid TWSE/TPEx common stocks of the last weekly file
Both are resumable / idempotent. Levels 1..15 (1 = 1-999 shares ... 12 = 400,001-600,000, 15 = > 1,000,000 shares);
大戶(400張以上) = levels 12-15, 千張大戶 = level 15.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import time

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
                    q = Query()
            else:
                fails += 1
                if fails >= 10:
                    p.write_text(json.dumps(have), encoding="utf-8")
                    raise SystemExit("10 failures in a row, stopping (re-run later to resume)")
            time.sleep(SLEEP)
        if todo:
            p.write_text(json.dumps(have), encoding="utf-8")
        print(f"{i}/{len(codes)} {code}: +{len(todo)}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("weekly")
    bp = sub.add_parser("backfill")
    bp.add_argument("codes", nargs="?", default="")
    a = ap.parse_args()
    if a.cmd == "weekly":
        weekly()
    else:
        backfill([c.strip() for c in a.codes.split(",") if c.strip()] or _default_codes())


if __name__ == "__main__":
    main()
