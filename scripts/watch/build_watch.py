"""Build intraday watch page data for a list of TW symbols.

Usage (any cwd):
  C:\\_work\\AI_Work\\Projects\\QuantTraderV2\\.venv\\Scripts\\python.exe build_watch.py --symbols 6182,2489 --out watch.html
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore")
PROJECT = Path(r"C:\_work\AI_Work\Projects\QuantTraderV2")
os.chdir(PROJECT)
sys.path.insert(0, str(PROJECT))

import pandas as pd  # noqa: E402
import pandas_ta as ta  # noqa: E402
import yfinance as yf  # noqa: E402

from src.analysis.technical_summary import generate_technical_summary  # noqa: E402
from src.data.realtime import RealtimeFetcher  # noqa: E402
from src.data.storage import ParquetStorage  # noqa: E402
from src.services import dashboard_service as ds  # noqa: E402

TZ = ZoneInfo("Asia/Taipei")
KEY_LEVELS = ("近20日高點", "近60日高點", "近期低點")
FRESH_MIN = 15  # a major event flashes for this many minutes
HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"


# ── helpers ──────────────────────────────────────────────────────────────
def r(x, n=2):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, n)


def tick_size(price: float, is_etf: bool) -> float:
    if is_etf:
        return 0.01 if price < 50 else 0.05
    for bound, tick in ((10, 0.01), (50, 0.05), (100, 0.1), (500, 0.5), (1000, 1.0)):
        if price < bound:
            return tick
    return 5.0


def limit_prices(prev_close: float, is_etf: bool) -> tuple[float, float]:
    up_raw, dn_raw = prev_close * 1.1, prev_close * 0.9
    t_up = tick_size(up_raw, is_etf)
    t_dn = tick_size(dn_raw, is_etf)
    up = math.floor(up_raw / t_up + 1e-9) * t_up
    dn = math.ceil(dn_raw / t_dn - 1e-9) * t_dn
    return round(up, 2), round(dn, 2)


# ── daily context (once per day, cached) ─────────────────────────────────
def daily_context(symbol: str, today: str) -> pd.DataFrame:
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"daily_{symbol}_{today}.csv"
    if path.exists():
        df = pd.read_csv(path, parse_dates=["date"])
        df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(TZ)
        return df
    storage = ParquetStorage()
    df, err = ds._prepare_daily_data(symbol, storage, market="tw")
    if err or df.empty:
        df = storage.load_daily(symbol, market="tw")
    df = ds._normalize_daily_df(df, market="tw")
    df = df[df["date"].dt.strftime("%Y-%m-%d") < today].tail(320).reset_index(drop=True)
    df[["date", "open", "high", "low", "close", "volume"]].to_csv(path, index=False)
    return df[["date", "open", "high", "low", "close", "volume"]]


# ── indicator snapshot on a daily frame ──────────────────────────────────
def daily_indicators(df: pd.DataFrame) -> dict:
    c, h, l = df["close"], df["high"], df["low"]
    ma = {n: r(c.rolling(n).mean().iloc[-1]) for n in (5, 10, 20, 60)}
    st = ta.stoch(h, l, c, k=9, d=3, smooth_k=3)
    mc = ta.macd(c, 12, 26, 9)
    rsi = ta.rsi(c, 14)
    summ = generate_technical_summary(df)
    return {
        "close": r(c.iloc[-1]),
        "ma": ma,
        "k": r(st.iloc[-1, 0]), "d": r(st.iloc[-1, 1]),
        "dif": r(mc.iloc[-1, 0], 3), "dea": r(mc.iloc[-1, 2], 3), "hist": r(mc.iloc[-1, 1], 3),
        "rsi": r(rsi.iloc[-1]),
        "trend": summ.trend_direction,
        "ma_status": summ.ma_status,
        "kd_status": summ.kd_status,
        "macd_status": summ.macd_status,
        "score": r(summ.short_term_score, 3),
        "score_label": summ.short_term_label,
        "bias20": r((c.iloc[-1] / c.rolling(20).mean().iloc[-1] - 1) * 100),
        "resistance": [{"v": r(x.value), "label": x.label} for x in summ.resistance_levels],
        "support": [{"v": r(x.value), "label": x.label} for x in summ.support_levels],
    }


# ── per symbol ───────────────────────────────────────────────────────────
def build_symbol(symbol: str, rt: RealtimeFetcher) -> dict:
    out: dict = {"symbol": symbol, "warnings": []}
    is_etf = symbol.startswith("00")

    # realtime snapshot (TWSE MIS)
    try:
        q = rt.fetch_quote(symbol)
        ba = rt.fetch_bid_ask_structure(q)
        out["name"] = q.name
        out["quote"] = {
            "price": r(q.price), "change": r(q.change), "pct": r(q.change_pct),
            "open": r(q.open), "high": r(q.high), "low": r(q.low), "prev": r(q.yesterday_close),
            "vol": q.volume, "time": q.timestamp, "date": q.trade_date,
            "estimated": q.is_estimated_price, "market_open": q.is_market_open,
        }
        out["book"] = {
            "bid": [[r(p), v] for p, v in zip(q.best_bid, q.best_bid_vol)],
            "ask": [[r(p), v] for p, v in zip(q.best_ask, q.best_ask_vol)],
            "bid_ratio": r(ba.bid_ratio, 3), "ask_ratio": r(ba.ask_ratio, 3), "label": ba.label,
        }
    except Exception as exc:  # noqa: BLE001
        out["warnings"].append(f"即時報價失敗：{exc}")
        out["quote"] = None
        out["book"] = None

    # 1m bars (yfinance)
    mkt = rt._market_map.get(symbol, "tse")
    yf_sym = f"{symbol}.TWO" if mkt == "otc" else f"{symbol}.TW"
    m1 = yf.Ticker(yf_sym).history(period="7d", interval="1m", prepost=False)
    if m1.empty:
        out["warnings"].append("yfinance 分K 無資料")
        return out
    m1.index = pd.to_datetime(m1.index, utc=True).tz_convert(TZ)
    m1 = m1[["Open", "High", "Low", "Close", "Volume"]].rename(columns=str.lower)
    m1["day"] = m1.index.strftime("%Y-%m-%d")
    today = out.get("quote", {}) and out["quote"].get("date")
    today = today if today in set(m1["day"]) else m1["day"].iloc[-1]
    out["trade_date"] = today
    t = m1[m1["day"] == today].copy()
    past = m1[m1["day"] < today].copy()
    if not out.get("name"):
        out["name"] = symbol

    # daily context up to yesterday
    daily = daily_context(symbol, today)
    prev = daily.iloc[-1]
    prev_close = float(out["quote"]["prev"]) if out.get("quote") and out["quote"]["prev"] else float(prev["close"])
    base = daily_indicators(daily)
    up, dn = limit_prices(prev_close, is_etf)

    # current values
    price = out["quote"]["price"] if out.get("quote") and not out["quote"]["estimated"] else r(t["close"].iloc[-1])
    day_hi = max(t["high"].max(), out["quote"]["high"] if out.get("quote") else 0)
    day_lo = min(t["low"].min(), out["quote"]["low"] if out.get("quote") else 1e9)
    cum_vol_shares = (out["quote"]["vol"] * 1000) if out.get("quote") else t["volume"].sum()

    # VWAP
    typ = (t["high"] + t["low"] + t["close"]) / 3
    t["vwap"] = (typ * t["volume"]).cumsum() / t["volume"].cumsum().replace(0, pd.NA)
    t["vwap"] = t["vwap"].ffill().fillna(t["close"])
    vwap = float(t["vwap"].iloc[-1])

    # opening range 09:00-09:29
    orng = t[t.index.strftime("%H:%M") < "09:30"]
    or_hi, or_lo = (float(orng["high"].max()), float(orng["low"].min())) if len(orng) else (None, None)
    now_hm = t.index[-1].strftime("%H:%M")
    if or_hi is None or now_hm < "09:30":
        or_state = "形成中"
    elif price > or_hi:
        or_state = "突破高點"
    elif price < or_lo:
        or_state = "跌破低點"
    else:
        or_state = "區間內"

    # volume ratio vs past days same time
    t_cum = t["volume"].sum()
    ratios = []
    for _, g in past.groupby("day"):
        sub = g[g.index.strftime("%H:%M") <= now_hm]["volume"].sum()
        if sub > 0:
            ratios.append(sub)
    vol_ratio = r(t_cum / (sum(ratios) / len(ratios)), 2) if ratios else None

    # 5m KD / RSI (continuous over recent days)
    m5 = m1[["open", "high", "low", "close", "volume"]].resample("5min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    st5 = ta.stoch(m5["high"], m5["low"], m5["close"], k=9, d=3, smooth_k=3)
    rsi5 = ta.rsi(m5["close"], 14)
    k5, d5 = r(st5.iloc[-1, 0]), r(st5.iloc[-1, 1])
    k5p, d5p = r(st5.iloc[-2, 0]), r(st5.iloc[-2, 1])
    flat = m5["high"].tail(9).max() == m5["low"].tail(9).min()
    if flat:
        k5 = d5 = None
        kd5_state = "價格無波動"
    elif k5 is None:
        kd5_state = "資料不足"
    elif k5 > 80 and d5 > 80:
        kd5_state = "高檔"
    elif k5 < 20 and d5 < 20:
        kd5_state = "低檔"
    elif k5p is not None and k5p <= d5p and k5 > d5:
        kd5_state = "黃金交叉"
    elif k5p is not None and k5p >= d5p and k5 < d5:
        kd5_state = "死亡交叉"
    else:
        kd5_state = "偏多" if k5 > d5 else "偏空"

    day_pos = r((price - day_lo) / (day_hi - day_lo) * 100, 0) if day_hi > day_lo else 50

    # key levels (daily, as of yesterday)
    levels = [
        {"v": r(prev["high"]), "label": "昨高"},
        {"v": r(prev["low"]), "label": "昨低"},
    ]
    for n, v in base["ma"].items():
        if v:
            levels.append({"v": v, "label": f"MA{n}"})
    for x in base["resistance"]:
        levels.append({"v": x["v"], "label": x["label"]})
    for x in base["support"]:
        levels.append({"v": x["v"], "label": x["label"]})
    merged: dict[float, list[str]] = {}
    for lv in levels:
        key = round(lv["v"], 2)
        merged.setdefault(key, [])
        if lv["label"] not in merged[key]:
            merged[key].append(lv["label"])
    levels = sorted(({"v": k, "label": "・".join(v)} for k, v in merged.items()), key=lambda x: -x["v"])
    # how many times a static level was tested (touched within 1% but not closed through) in the last 10 days
    recent = daily.tail(10)
    for lv in levels:
        lv["dist"] = r((lv["v"] / price - 1) * 100)
        lv["side"] = "above" if lv["v"] > price else "below"
        labels = lv["label"].split("・")
        lv["key"] = any(x in KEY_LEVELS for x in labels)
        if any(x in ("近20日高點", "近60日高點") for x in labels):
            lv["type"] = "res"
        elif "近期低點" in labels:
            lv["type"] = "sup"
        else:
            lv["type"] = "res" if lv["v"] >= prev_close else "sup"
        lv["tests"] = 0
        if any(x in KEY_LEVELS or x in ("昨高", "昨低") for x in labels):
            v = lv["v"]
            if lv["type"] == "res":
                hit = ((recent["high"] - v).abs() / v <= 0.01) & (recent["close"] < v)
            else:
                hit = ((recent["low"] - v).abs() / v <= 0.01) & (recent["close"] > v)
            # yesterday trivially touches its own high/low
            if "昨高" in labels or "昨低" in labels:
                hit = hit.iloc[:-1]
            lv["tests"] = int(hit.sum())

    # projection: if today closes at current price
    today_bar = pd.DataFrame([{
        "date": pd.Timestamp(today, tz=TZ), "open": float(t["open"].iloc[0]),
        "high": float(day_hi), "low": float(day_lo), "close": float(price), "volume": float(cum_vol_shares),
    }])
    proj = daily_indicators(pd.concat([daily, today_bar], ignore_index=True))

    # events from 1m bars
    avg20_shares = float(daily["volume"].tail(20).mean())
    events = detect_events(t, past, or_hi, or_lo, levels, up, dn, prev_close, avg20_shares)
    # yfinance misses the 13:25-13:30 closing auction; append the official close
    if out.get("quote") and not out["quote"]["market_open"] and out["quote"]["time"] >= "13:30":
        t.loc[t.index[-1] + pd.Timedelta(minutes=6)] = {
            "open": price, "high": price, "low": price, "close": price,
            "volume": max(0.0, cum_vol_shares - t["volume"].sum()), "day": today, "vwap": t["vwap"].iloc[-1],
        }

    # alert: latest major event, fresh if within FRESH_MIN of data time
    data_now = datetime.now(TZ) if out.get("quote") and out["quote"]["market_open"] else t.index[-1]
    now_min = data_now.hour * 60 + data_now.minute
    # price events outrank volume surges for the summary highlight
    majors = [e for e in events if e["level"] == 2 and e["kind"] != "vol"] or [e for e in events if e["level"] == 2]
    alert = None
    if majors:
        e = majors[-1]
        h, m = map(int, e["t"].split(":"))
        alert = {**e, "fresh": now_min - (h * 60 + m) <= FRESH_MIN}

    # daily status changes if today closes at the current price
    changes = []
    if proj["kd_status"] in ("KD 黃金交叉", "KD 死亡交叉") and proj["kd_status"] != base["kd_status"]:
        changes.append(f"KD 將{proj['kd_status'][3:]}")
    if proj["ma_status"] != base["ma_status"] and any("排列" in x for x in (proj["ma_status"], base["ma_status"])):
        changes.append(f"均線 {base['ma_status']} → {proj['ma_status']}")
    if base["hist"] is not None and proj["hist"] is not None and (base["hist"] > 0) != (proj["hist"] > 0):
        changes.append("MACD 柱狀體將翻正" if proj["hist"] > 0 else "MACD 柱狀體將翻負")

    # chart series (1m)
    out.update({
        "price": r(price),
        "limit_up": up, "limit_down": dn,
        "vwap": r(vwap), "vwap_diff": r((price / vwap - 1) * 100),
        "or": {"hi": r(or_hi), "lo": r(or_lo), "state": or_state},
        "vol_ratio": vol_ratio, "vol_lots": round(cum_vol_shares / 1000),
        "day_pos": day_pos, "day_hi": r(day_hi), "day_lo": r(day_lo),
        "kd5": {"k": k5, "d": d5, "state": kd5_state}, "rsi5": r(rsi5.iloc[-1]),
        "levels": levels,
        "base": base, "proj": proj,
        "events": events,
        "alert": alert,
        "proj_changes": changes,
        "series": {
            "t": [ts.strftime("%H:%M") for ts in t.index],
            "c": [r(x) for x in t["close"]],
            "v": [int(x // 1000) for x in t["volume"]],
            "w": [r(x) for x in t["vwap"]],
        },
        "last_bar": now_hm,
    })
    return out


def detect_events(t, past, or_hi, or_lo, levels, up, dn, prev_close, avg20_shares) -> list[dict]:
    ev: list[dict] = []
    closes = t["close"].tolist()
    times = [ts.strftime("%H:%M") for ts in t.index]
    vw = t["vwap"].tolist()

    # level 2 = major (summary row highlights), level 1 = normal
    def add(i, kind, text, level=1):
        ev.append({"t": times[i], "kind": kind, "text": text, "level": level})

    # opening range break (after 09:30)
    hit_hi = hit_lo = False
    # vwap cross with 3-bar debounce
    side = None
    pending = None
    vwap_last = None
    # level crossings
    lv_side = {}
    lv_last: dict[str, int] = {}
    for lv in levels:
        lv_side[lv["label"] + str(lv["v"])] = closes[0] > lv["v"]
    touched_up = locked = False

    # 5m volume surge vs past same bucket
    t5 = t["volume"].resample("5min").sum()
    past_bucket: dict[str, list[float]] = {}
    for day, g in past.groupby("day"):
        s = g["volume"].resample("5min").sum()
        for ts, v in s.items():
            past_bucket.setdefault(ts.strftime("%H:%M"), []).append(v)
    last_surge = None
    for ts, v in t5.items():
        hm = ts.strftime("%H:%M")
        hist = past_bucket.get(hm)
        if not hist or hm < "09:05":
            continue
        avg = sum(hist) / len(hist)
        if avg > 0 and v >= 3 * avg and v >= max(200_000, avg20_shares * 0.02):
            if last_surge is None or (ts - last_surge).seconds >= 900:
                i = min(range(len(times)), key=lambda j: abs(pd.Timestamp(t.index[j]) - ts))
                add(i, "vol", f"放量 {int(v // 1000):,} 張／5分（同時段均量 {v / avg:.1f} 倍）", 2 if v >= 8 * avg else 1)
                last_surge = ts

    for i, c in enumerate(closes):
        hm = times[i]
        if or_hi is not None and hm >= "09:30":
            if not hit_hi and c > or_hi:
                add(i, "up", f"突破開盤區間高點 {or_hi:g}")
                hit_hi = True
            if not hit_lo and c < or_lo:
                add(i, "down", f"跌破開盤區間低點 {or_lo:g}")
                hit_lo = True
        # VWAP cross: beyond 0.2% band for 3 bars, 15-min cool-down
        if hm >= "09:10":
            band = vw[i] * 0.002
            s = True if c > vw[i] + band else False if c < vw[i] - band else None
            if side is None:
                side = s
            elif s is not None and s != side:
                pending = (s, pending[1] if pending and pending[0] == s else i, (pending[2] + 1) if pending and pending[0] == s else 1)
                if pending[2] >= 3:
                    j = pending[1]
                    if vwap_last is None or j - vwap_last >= 15:
                        add(j, "up" if s else "down", f"{'站上' if s else '跌破'} VWAP {vw[j]:.2f}")
                        vwap_last = j
                        side = s
                    pending = None
            else:
                pending = None
        # level cross: 2 closes beyond a 0.1% margin + 20-min cool-down per level
        if i >= 1 and hm >= "09:05":
            for lv in levels:
                key = lv["label"] + str(lv["v"])
                m = lv["v"] * 0.001
                above = c > lv["v"] + m and closes[i - 1] > lv["v"] + m
                below = c < lv["v"] - m and closes[i - 1] < lv["v"] - m
                if (above and not lv_side[key]) or (below and lv_side[key]):
                    if i - lv_last.get(key, -99) >= 20:
                        if above:
                            verb = "突破" if lv["type"] == "res" else "站回"
                        else:
                            verb = "跌破" if lv["type"] == "sup" else "跌回"
                        tested = lv.get("tests", 0) >= 2
                        major = verb in ("突破", "跌破") and (lv.get("key") or tested)
                        note = f"，10 日內測試 {lv['tests']} 次" if tested else ""
                        add(i - 1, "up" if above else "down", f"{verb} {lv['v']:g}（{lv['label']}{note}）", 2 if major else 1)
                        lv_last[key] = i
                        lv_side[key] = above
        if not touched_up and t["high"].iloc[i] >= up:
            add(i, "up", f"觸及漲停 {up:g}", 2)
            touched_up = True
        if touched_up and not locked and all(x >= up for x in t["low"].iloc[i:]):
            add(i, "up", f"鎖漲停 {up:g}", 2)
            locked = True
        if t["low"].iloc[i] <= dn and not any(e["text"].startswith("觸及跌停") for e in ev):
            add(i, "down", f"觸及跌停 {dn:g}", 2)

    ev.sort(key=lambda e: e["t"])
    return ev


def main() -> None:
    global FRESH_MIN
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--note", default="")
    ap.add_argument("--fresh-min", type=int, default=FRESH_MIN)
    args = ap.parse_args()
    FRESH_MIN = args.fresh_min
    rt = RealtimeFetcher(cache_ttl=0, request_timeout=8)
    rt.load_market_map()
    stocks = []
    for s in [x.strip() for x in args.symbols.split(",") if x.strip()]:
        try:
            stocks.append(build_symbol(s, rt))
        except Exception as exc:  # noqa: BLE001
            stocks.append({"symbol": s, "name": s, "warnings": [f"建置失敗：{exc!r}"]})
    data = {
        "generated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "note": args.note,
        "stocks": stocks,
    }
    tpl = (HERE / "watch_template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    Path(args.out).write_text(html, encoding="utf-8")
    (HERE / "last_data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    dates = sorted({x.get("trade_date") for x in stocks if x.get("trade_date")})
    print("ok", data["generated"], "trade_date=" + ",".join(dates),
          [(x["symbol"], x.get("price"), len(x.get("events", []))) for x in stocks])


if __name__ == "__main__":
    main()
