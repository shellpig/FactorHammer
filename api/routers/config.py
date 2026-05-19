"""Config router — /api/config/* endpoints (Phase 10-A)."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services.config_service import (
    CONFIG_UPDATE_WHITELIST,
    FinMindTokenInvalid,
    FinMindUnreachable,
    delete_strategy_preset_by_name,
    get_secrets_status,
    get_strategy_presets_config,
    read_config,
    restore_strategy_defaults,
    update_config,
    update_secrets,
    upsert_strategy_preset,
    validate_finmind_token,
)

router = APIRouter(prefix="/api/config", tags=["config"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class ConfigPatchRequest(BaseModel):
    patch: dict[str, Any]


class SecretsUpdateRequest(BaseModel):
    keys: dict[str, str]


class SecretsValidateRequest(BaseModel):
    finmind: str | None = None
    anthropic: str | None = None
    openai: str | None = None
    gemini: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
def get_config_endpoint() -> dict[str, Any]:
    """Return current config with secrets masked."""
    config = read_config(mask_secrets=True)
    return {"data": config, "meta": {}}


@router.put("")
def put_config_endpoint(request: ConfigPatchRequest) -> dict[str, Any]:
    """Apply a partial config update (whitelist-only)."""
    try:
        update_config(request.patch)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "WHITELIST_REJECTED", "message": str(exc)}},
        ) from exc
    return {"data": {"updated": True}, "meta": {}}


@router.put("/secrets")
def put_secrets(request: SecretsUpdateRequest) -> dict[str, Any]:
    """Write-only: store API keys in .env.  Never returns key values."""
    try:
        update_secrets(request.keys)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "UNKNOWN_PROVIDER", "message": str(exc)}},
        ) from exc
    return {"data": {"updated": True}, "meta": {}}


@router.get("/secrets/status")
def get_secrets_status_endpoint() -> dict[str, Any]:
    """Return boolean configured status for each API key."""
    status = get_secrets_status()
    return {"data": status, "meta": {}}


@router.post("/secrets/validate")
def post_secrets_validate(request: SecretsValidateRequest) -> dict[str, Any]:
    finmind = (request.finmind or "").strip()
    if not finmind:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "FINMIND_REQUIRED", "message": "FinMind token 為必填欄位。"}},
        )

    try:
        validate_finmind_token(finmind)
    except FinMindTokenInvalid as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "FINMIND_TOKEN_INVALID",
                    "message": "Token 無效，請確認從 FinMind 使用者資訊頁複製正確。",
                }
            },
        ) from exc
    except FinMindUnreachable as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "code": "FINMIND_UNREACHABLE",
                    "message": "無法連線至 FinMind 伺服器，請檢查網路後重試。",
                }
            },
        ) from exc

    updates: dict[str, str] = {"finmind": finmind}
    if request.anthropic is not None and request.anthropic.strip():
        updates["anthropic"] = request.anthropic.strip()
    if request.openai is not None and request.openai.strip():
        updates["openai"] = request.openai.strip()
    if request.gemini is not None and request.gemini.strip():
        updates["gemini"] = request.gemini.strip()

    try:
        update_secrets(updates)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "ENV_WRITE_FAILED", "message": f"寫入設定檔失敗：{exc}"}},
        ) from exc

    label_to_env = {
        "finmind": "FINMIND_TOKEN",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }
    for label, value in updates.items():
        os.environ[label_to_env[label]] = value

    return {"data": {"updated": True}, "meta": {}}


@router.get("/strategies")
def get_strategies() -> dict[str, Any]:
    """Return strategy preset list."""
    presets = get_strategy_presets_config()
    return {"data": presets, "meta": {"count": len(presets)}}


class StrategyPresetUpsertRequest(BaseModel):
    preset: dict[str, Any]


@router.post("/strategies", status_code=201)
def upsert_strategy(request: StrategyPresetUpsertRequest) -> dict[str, Any]:
    """Add or update a strategy preset (matched by name)."""
    try:
        upsert_strategy_preset(request.preset)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "INVALID_PRESET", "message": str(exc)}},
        ) from exc
    name = str(request.preset.get("name", "")).strip()
    return {"data": {"upserted": True, "name": name}, "meta": {}}


@router.post("/strategies/restore")
def restore_strategies() -> dict[str, Any]:
    """Reset strategy presets to defaults."""
    restore_strategy_defaults()
    count = len(get_strategy_presets_config())
    return {"data": {"count": count}, "meta": {}}


@router.delete("/strategies/{name}", status_code=204)
def delete_strategy(name: str) -> None:
    """Delete strategy preset by name. Idempotent — name not found is not an error."""
    delete_strategy_preset_by_name(name)
    return None
