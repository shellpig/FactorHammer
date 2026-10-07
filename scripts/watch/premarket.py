"""Auto-generate the premarket note (previous trading day's market summary).

Usage (any cwd):
  C:\\_work\\AI_Work\\Projects\\QuantTraderV2\\.venv\\Scripts\\python.exe premarket.py [--symbols 2492,6182] [--write]

Sources (all public, no quota):
  TWSE FMTQIK    加權指數收盤、漲跌點數（也用來找最近交易日）
  TWSE MI_INDEX  漲跌家數（股票）
  TWSE BFI82U    外資、投信買賣超金額（上市）
  TWSE TWT38U    外資個股買賣超（上市）
  TPEx dailyTrade 三大法人個股買賣超（上櫃，取外資合計）
  TAIFEX futDataDown  台指期近月一般時段收盤 → 正/逆價差
  TAIFEX pcRatioDown  買賣權未平倉量比率
  TAIFEX VIX log2data 臺指選擇權波動率指數（13:45 收盤值）
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Asia/Taipei")
HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
NOTE = HERE / "premarket_note.txt"
META = CACHE / "premarket_meta.json"
H = {"User-Agent": "Mozilla/5.0"}
READY_HM = "17:00"   # before this, today's after-close data may be incomplete -> use yesterday
RETRY_SEC = 600      # retry interval while some items are still missing
SELL_TOP = 30        # watchlist stock shown if within this foreign net-sell rank of its market
ITEMS = ("index", "breadth", "inst", "foreign", "futures", "pcr", "vix")

_mem: dict = {"cutoff": None, "raw": None, "ts": 0.0}


def _num(s) -> float | None:
    s = str(s).strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _get(url: str, **kw) -> requests.Response:
    r = requests.get(url, headers=H, timeout=15, **kw)
    r.raise_for_status()
    return r


def _post(url: str, data: dict) -> str:
    r = requests.post(url, data=data, headers=H, timeout=20)
    r.raise_for_status()
    return r.content.decode("cp950", "replace")


# ── fetchers (each returns None when not published / failed) ─────────────
def fetch_index(cutoff: date) -> dict | None:
    """Latest trading day <= cutoff from FMTQIK (monthly table)."""
    for month in (cutoff, cutoff.replace(day=1) - timedelta(days=1)):
        d = _get(f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={month:%Y%m01}&response=json").json()
        rows = []
        for row in d.get("data") or []:
            y, m, dd = (int(x) for x in row[0].split("/"))
            day = date(y + 1911, m, dd)
            if day <= cutoff:
                rows.append((day, _num(row[4]), _num(row[5])))
        if rows:
            day, close, chg = max(rows)
            return {"date": day.isoformat(), "close": close, "chg": chg}
    return None


def fetch_breadth(d: date) -> dict | None:
    j = _get(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={d:%Y%m%d}&type=MS&response=json").json()
    for t in j.get("tables") or []:
        if t.get("title") == "漲跌證券數合計":
            rows = {r[0]: r[2] for r in t["data"]}  # column 2 = 股票
            up = _num(rows["上漲(漲停)"].split("(")[0])
            down = _num(rows["下跌(跌停)"].split("(")[0])
            return {"up": int(up), "down": int(down)}
    return None


def fetch_inst(d: date) -> dict | None:
    j = _get(f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?type=day&dayDate={d:%Y%m%d}&response=json").json()
    rows = {r[0]: _num(r[3]) for r in j.get("data") or []}
    if not rows:
        return None
    foreign = (rows.get("外資及陸資(不含外資自營商)") or 0) + (rows.get("外資自營商") or 0)
    return {"foreign": foreign, "trust": rows.get("投信")}


def fetch_foreign(d: date) -> dict | None:
    """Per-stock foreign net (shares) with net-sell rank within its market."""
    out: dict = {}
    j = _get(f"https://www.twse.com.tw/rwd/zh/fund/TWT38U?date={d:%Y%m%d}&response=json").json()
    twse = [(r[1].strip(), r[2].strip(), _num(r[11])) for r in j.get("data") or []]
    j = _get(f"https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={d:%Y/%m/%d}&response=json").json()
    tables = j.get("tables") or [{}]
    tpex = [(r[0].strip(), r[1].strip(), _num(r[10])) for r in tables[0].get("data") or []]  # 10 = 外資及陸資合計 買賣超
    if not twse or not tpex:
        return None
    for market, rows in (("上市", twse), ("上櫃", tpex)):
        sells = sorted((x for x in rows if x[2] is not None and x[2] < 0), key=lambda x: x[2])
        rank = {code: i + 1 for i, (code, _, _) in enumerate(sells)}
        for code, name, net in rows:
            out[code] = {"name": name, "net": net, "sell_rank": rank.get(code), "market": market}
    return out


def fetch_futures(d: date) -> dict | None:
    txt = _post("https://www.taifex.com.tw/cht/3/futDataDown", {
        "down_type": "1", "commodity_id": "TX",
        "queryStartDate": f"{d:%Y/%m/%d}", "queryEndDate": f"{d:%Y/%m/%d}"})
    for line in txt.splitlines()[1:]:
        c = [x.strip() for x in line.split(",")]
        # rows are ordered by expiry; the first plain monthly contract in the regular session is the near month
        if len(c) > 17 and c[1] == "TX" and re.fullmatch(r"\d{6}", c[2]) and c[17] == "一般":
            close = _num(c[6])
            if close is not None:
                return {"close": close, "month": c[2]}
    return None


def fetch_pcr(d: date) -> float | None:
    txt = _post("https://www.taifex.com.tw/cht/3/pcRatioDown",
                {"queryStartDate": f"{d:%Y/%m/%d}", "queryEndDate": f"{d:%Y/%m/%d}"})
    for line in txt.splitlines()[1:]:
        c = line.split(",")
        if c[0].strip() == f"{d:%Y/%m/%d}":
            return _num(c[6])  # 買賣權未平倉量比率%
    return None


def fetch_vix(d: date) -> float | None:
    r = _get(f"https://www.taifex.com.tw/file/taifex/Dailydownload/vix/log2data/{d:%Y%m}new.txt")
    for line in r.content.decode("cp950", "replace").splitlines():
        c = line.split()
        if len(c) >= 3 and c[0] == f"{d:%Y%m%d}":
            return _num(c[2])
    return None


# ── raw data with cache ──────────────────────────────────────────────────
def _cutoff(now: datetime) -> date:
    today = now.date()
    return today if now.strftime("%H:%M") >= READY_HM else today - timedelta(days=1)


def fetch_raw(cutoff: date, log=print) -> dict | None:
    idx = fetch_index(cutoff)
    if not idx:
        return None
    d = date.fromisoformat(idx["date"])
    path = CACHE / f"premarket_{d:%Y-%m-%d}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if all(raw.get(k) is not None for k in ITEMS):
            return raw
    except (OSError, ValueError):
        raw = {}
    raw["index"] = idx
    for key, fn in (("breadth", fetch_breadth), ("inst", fetch_inst), ("foreign", fetch_foreign),
                    ("futures", fetch_futures), ("pcr", fetch_pcr), ("vix", fetch_vix)):
        if raw.get(key) is not None:
            continue
        try:
            raw[key] = fn(d)
        except Exception as exc:  # noqa: BLE001  one source failing must not drop the rest
            raw[key] = None
            log(f"premarket {key} failed: {exc!r}")
    if all(raw.get(k) is not None for k in ITEMS):
        CACHE.mkdir(exist_ok=True)
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return raw


def get_raw(now: datetime | None = None, log=print) -> dict | None:
    """Raw data for the latest trading day; complete results are cached, partial ones retried every RETRY_SEC."""
    now = now or datetime.now(TZ)
    cutoff = _cutoff(now)
    raw = _mem["raw"]
    if _mem["cutoff"] == cutoff and raw:
        complete = all(raw.get(k) is not None for k in ITEMS)
        if complete or time.time() - _mem["ts"] < RETRY_SEC:
            return raw
    new = fetch_raw(cutoff, log)
    if new is None and _mem["cutoff"] == cutoff:
        new = raw
    _mem.update(cutoff=cutoff, raw=new, ts=time.time())
    return new


# ── text ─────────────────────────────────────────────────────────────────
def compose(raw: dict, symbols: list[str]) -> str:
    d = date.fromisoformat(raw["index"]["date"])
    parts = []
    idx = raw["index"]
    close, chg = idx["close"], idx["chg"]
    parts.append(f"加權 {close:,.0f} {chg / (close - chg) * 100:+.2f}%")
    inst = raw.get("inst")
    parts.append(f"外資 {inst['foreign'] / 1e8:+,.0f} 億、投信 {inst['trust'] / 1e8:+,.0f} 億" if inst else "法人 缺")
    fut = raw.get("futures")
    if fut:
        basis = fut["close"] - close
        parts.append(f"台指期{'正' if basis >= 0 else '逆'}價差 {abs(basis):,.0f}")
    else:
        parts.append("台指期 缺")
    br = raw.get("breadth")
    parts.append(f"漲 {br['up']}／跌 {br['down']}" if br else "漲跌家數 缺")
    pcr, vix = raw.get("pcr"), raw.get("vix")
    parts.append(f"PCR {pcr:.1f}%" if pcr is not None else "PCR 缺")
    parts[-1] += f"、VIX {vix:.2f}" if vix is not None else "、VIX 缺"
    fr = raw.get("foreign")
    if fr is None:
        parts.append("外資賣超榜 缺")
    else:
        hits = sorted(((fr[s]["sell_rank"], s) for s in symbols
                       if s in fr and fr[s]["sell_rank"] and fr[s]["sell_rank"] <= SELL_TOP))
        if hits:
            parts.append("外資賣超榜：" + "、".join(
                f"{s} {fr[s]['name']} {abs(fr[s]['net']) / 1000:,.0f} 張（{fr[s].get('market', '')}第 {rk}）" for rk, s in hits))
        else:
            parts.append(f"外資賣超榜：追蹤股未進前 {SELL_TOP}")
    return f"盤前（{d.month}/{d.day}）：" + "｜".join(parts)


def update_note_file(symbols: list[str], log=print) -> bool:
    """Rewrite premarket_note.txt when the generated text changes (new day, watchlist change, data filled in).
    A manual edit survives until the next change. Returns True if the file was written."""
    raw = get_raw(log=log)
    if not raw:
        return False
    text = compose(raw, symbols)
    try:
        last = json.loads(META.read_text(encoding="utf-8")).get("text")
    except (OSError, ValueError):
        last = None
    if text == last:
        return False
    NOTE.write_text(text + "\n", encoding="utf-8")
    CACHE.mkdir(exist_ok=True)
    META.write_text(json.dumps({"text": text, "at": datetime.now(TZ).isoformat(timespec="seconds")},
                               ensure_ascii=False), encoding="utf-8")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="")
    ap.add_argument("--write", action="store_true", help="also update premarket_note.txt")
    args = ap.parse_args()
    symbols = [x.strip() for x in args.symbols.split(",") if x.strip()]
    if not symbols:
        try:
            symbols = json.loads((HERE / "watchlist.json").read_text(encoding="utf-8"))["symbols"]
        except (OSError, ValueError, KeyError):
            symbols = []
    if args.write:
        print("written" if update_note_file(symbols) else "unchanged")
    raw = get_raw()
    print(compose(raw, symbols) if raw else "no data")


if __name__ == "__main__":
    main()
