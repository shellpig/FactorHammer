"""FastAPI application entry point (Phase 10-A).

Run with:
    uvicorn api.main:app --reload --port 8000
Or via:
    run_api.bat
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import ai, analysis, config, data, jobs, realtime

app = FastAPI(
    title="QuantTrader API",
    description="Backend API for QuantTrader — Taiwan/US stock research toolkit.",
    version="0.10.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────
app.include_router(config.router)
app.include_router(data.router)
app.include_router(jobs.router)
app.include_router(analysis.router)
app.include_router(realtime.router)
app.include_router(ai.router)


# ── Health ────────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    """Health check — no envelope per spec."""
    return {"status": "ok"}
