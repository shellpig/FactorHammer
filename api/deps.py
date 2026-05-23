"""Shared dependencies for FastAPI dependency injection (Phase 10-A)."""

from __future__ import annotations

from api.job_manager import JobManager, get_job_manager
from src.ai.advisor import AIAdvisor


def get_manager() -> JobManager:
    """Dependency: return the singleton JobManager."""
    return get_job_manager()


def get_advisor() -> AIAdvisor:
    """Dependency: return an instance of AIAdvisor."""
    return AIAdvisor()
