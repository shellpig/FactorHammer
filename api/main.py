"""FastAPI application entry point (Phase 10-A).

Run with:
    uvicorn api.main:app --reload --port 8000
Or via:
    run_api.bat
"""

from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.routers import ai, analysis, config, data, jobs, realtime
from src.core.config import get_project_root

load_dotenv(get_project_root() / ".env", override=False)

app = FastAPI(
    title="FactorHammer API",
    description="Backend API for FactorHammer — Taiwan/US stock research toolkit.",
    version="0.5.3",
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


# ── No-cache middleware ───────────────────────────────────────────────────
@app.middleware("http")
async def add_no_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ── Health ────────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    """Health check — no envelope per spec."""
    return {"status": "ok"}
