"""Local intraday watch board server.

Usage:
  C:\\_work\\AI_Work\\Projects\\QuantTraderV2\\.venv\\Scripts\\python.exe watch_server.py [--port 8765]

GET /               page (template + latest data)
GET /data.json      latest data
GET /api/watchlist  {"symbols": [...]}
POST /api/watchlist {"symbols": [...]}  max 8, each ^\\d{4,6}[A-Z]?$
"""
from __future__ import annotations

import argparse
import json
import re
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import build_watch as bw

HERE = Path(__file__).resolve().parent
WATCHLIST = HERE / "watchlist.json"
NOTE = HERE / "premarket_note.txt"
DEFAULT_SYMBOLS = ["6182", "2489", "1476", "2492", "3264", "3324", "6669"]
MAX_WATCH = 8
CODE_RE = re.compile(r"^\d{4,6}[A-Z]?$")
INTERVAL = 120          # seconds between builds during market hours
OPEN_HM, FINAL_HM = "09:00", "13:35"
TZ = bw.TZ

_lock = threading.Lock()           # guards _data / watchlist file
_build_lock = threading.Lock()     # one build at a time
_wake = threading.Event()          # set when the watchlist changed
_data: dict = {"generated": "", "note": "", "stocks": []}


def log(msg: str) -> None:
    print(f"[{datetime.now(TZ):%H:%M:%S}] {msg}", flush=True)


# ── watchlist ────────────────────────────────────────────────────────────
def load_watchlist() -> list[str]:
    try:
        syms = json.loads(WATCHLIST.read_text(encoding="utf-8"))["symbols"]
        return [s for s in syms if isinstance(s, str) and CODE_RE.match(s)][:MAX_WATCH]
    except (OSError, ValueError, KeyError, TypeError):
        return list(DEFAULT_SYMBOLS)


def save_watchlist(symbols: list[str]) -> None:
    payload = {"symbols": symbols, "updated_at": datetime.now(TZ).isoformat(timespec="seconds")}
    tmp = WATCHLIST.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(WATCHLIST)


def validate_symbols(raw) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise ValueError("symbols 必須是字串陣列")
    out: list[str] = []
    for x in raw:
        code = x.strip().upper()
        if not CODE_RE.match(code):
            raise ValueError(f"代碼格式不對：{x}")
        if code not in out:
            out.append(code)
    if len(out) > MAX_WATCH:
        raise ValueError(f"最多 {MAX_WATCH} 檔")
    return out


# ── build loop ───────────────────────────────────────────────────────────
def read_note() -> str:
    try:
        return NOTE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def do_build() -> dict | None:
    """Build once; on failure keep the previous data. Returns the new data or None."""
    global _data
    with _build_lock:
        try:
            data = bw.build(load_watchlist(), read_note())
            bw.write_outputs(data)
        except Exception:  # noqa: BLE001
            log("build failed, keeping previous data:\n" + traceback.format_exc())
            return None
        with _lock:
            _data = data
        dates = sorted({s.get("trade_date") for s in data["stocks"] if s.get("trade_date")})
        log(f"built {len(data['stocks'])} symbols trade_date={','.join(dates)}")
        return data


def build_loop() -> None:
    last_start = 0.0             # time.time() of the last build start
    last_start_dt: datetime | None = None
    holiday_day = ""             # date known to be a non-trading day
    while True:
        now = datetime.now(TZ)
        today, hm = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
        weekday = now.weekday() < 5
        dirty = _wake.is_set()
        in_hours = weekday and OPEN_HM <= hm <= FINAL_HM and holiday_day != today
        final_due = (
            weekday and hm >= FINAL_HM and holiday_day != today
            and (last_start_dt is None or last_start_dt.strftime("%Y-%m-%d") != today
                 or last_start_dt.strftime("%H:%M") < FINAL_HM)
        )
        first = last_start == 0.0
        if first or dirty or final_due or (in_hours and time.time() - last_start >= INTERVAL):
            _wake.clear()
            last_start, last_start_dt = time.time(), now
            data = do_build()
            # MIS date != today once the market should have opened -> holiday
            if data and weekday and hm >= "09:05":
                dates = {s.get("trade_date") for s in data["stocks"] if s.get("trade_date")}
                if dates and today not in dates:
                    holiday_day = today
                    log(f"trade_date {sorted(dates)} != {today}: treating as non-trading day")
        _wake.wait(15)


# ── HTTP ─────────────────────────────────────────────────────────────────
class Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second instance bind the same port silently; fail instead
    allow_reuse_address = False


class Handler(BaseHTTPRequestHandler):
    server_version = "watch/1"

    def log_message(self, fmt, *args):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        with _lock:
            data = _data
        if path in ("/", "/index.html"):
            self._send(200, bw.render_html(data).encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/data.json":
            self._json(200, data)
        elif path == "/api/watchlist":
            with _lock:
                self._json(200, {"symbols": load_watchlist()})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path.split("?", 1)[0] != "/api/watchlist":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > 4096:
                raise ValueError("body 大小不合法")
            symbols = validate_symbols(json.loads(self.rfile.read(length))["symbols"])
        except (ValueError, KeyError, TypeError) as exc:
            return self._json(400, {"error": str(exc)})
        with _lock:
            save_watchlist(symbols)
        _wake.set()
        log(f"watchlist -> {','.join(symbols)}")
        self._json(200, {"symbols": symbols})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    # serve the previous snapshot until the first build finishes
    try:
        last = json.loads((HERE / "last_data.json").read_text(encoding="utf-8"))
        with _lock:
            _data.update(last)
    except (OSError, ValueError):
        pass
    threading.Thread(target=build_loop, daemon=True).start()
    srv = Server((args.host, args.port), Handler)
    log(f"serving on http://{args.host}:{args.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
