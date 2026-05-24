"""Config router — /api/config/* endpoints (Phase 10-A)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services.config_service import (
    CONFIG_UPDATE_WHITELIST,
    FinMindTokenInvalid,
    FinMindUnreachable,
    ValidationResult,
    delete_strategy_preset_by_name,
    get_secrets_status,
    get_strategy_presets_config,
    read_config,
    restore_strategy_defaults,
    update_config,
    update_secrets,
    upsert_strategy_preset,
    validate_anthropic_token,
    validate_deepseek_token,
    validate_finmind_token,
    validate_finmind_token_wrapped,
    validate_gemini_token,
    validate_openai_token,
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
    deepseek: str | None = None   # 15-A-2 新增


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
    """Validate API keys and write savable ones to .env.

    15-A-2 contract:
    - FinMind is required: blank/None body and .env also lacks FINMIND_TOKEN
      → 200 with results.finmind error and saved=[]; no other keys written.
      If body is blank but .env already has FINMIND_TOKEN (already onboarded),
      finmind is treated as already-configured (not in results, not re-validated,
      not re-written) and other providers are still validated.
    - Other providers are optional (validate-if-present): absent/blank → skipped
      (not in results); present → validated individually.
    - ok and no_quota → written to .env; invalid_key and unreachable → not written.
    - HTTP status is always 200; per-provider status in results[provider].status.
    """
    # ── (a) FinMind 必填驗證 ──
    finmind_token = (request.finmind or "").strip()
    results: dict[str, dict[str, str]] = {}
    to_save: dict[str, str] = {}

    if not finmind_token:
        # body 空白：fallback 看 .env 是否已有 FINMIND_TOKEN
        # 已 onboarded → 視為已設定，不放進 results 也不重寫；未 onboarded → 必填失敗
        if get_secrets_status().get("finmind", False):
            pass  # 已設定，跳過 finmind 驗證、繼續驗其他 provider
        else:
            return {
                "data": {
                    "results": {
                        "finmind": {
                            "status": "invalid_key",
                            "message": "FinMind token 為必填",
                        }
                    },
                    "saved": [],
                },
                "meta": {},
            }
    else:
        finmind_result: ValidationResult = validate_finmind_token_wrapped(finmind_token)
        results["finmind"] = {
            "status": finmind_result.status,
            "message": finmind_result.message,
        }
        if not finmind_result.is_savable():
            return {"data": {"results": results, "saved": []}, "meta": {}}
        to_save["finmind"] = finmind_token


    # ── (b) 其他 provider 選填 validate-if-present ──
    optional_validators: dict[str, Any] = {
        "deepseek": (request.deepseek, validate_deepseek_token),
        "openai": (request.openai, validate_openai_token),
        "anthropic": (request.anthropic, validate_anthropic_token),
        "gemini": (request.gemini, validate_gemini_token),
    }

    for provider, (token, validator) in optional_validators.items():
        if token is None or not token.strip():
            continue  # 沒送 / 空白 → 不驗證、不出現在 results
        result: ValidationResult = validator(token)
        results[provider] = {"status": result.status, "message": result.message}
        if result.is_savable():
            to_save[provider] = token.strip()

    # ── (c) 寫入 .env + runtime env（update_secrets 是單一寫入點） ──
    if to_save:
        try:
            update_secrets(to_save)
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail={"error": {"code": "ENV_WRITE_FAILED", "message": f"寫入設定檔失敗：{exc}"}},
            ) from exc

    saved: list[str] = list(to_save.keys())

    return {"data": {"results": results, "saved": saved}, "meta": {}}





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
