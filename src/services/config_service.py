"""Config service — non-UI config & secrets management (Phase 10-A).

All functions return plain Python dicts or raise exceptions.
No Streamlit calls are made here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import requests
import yaml

from src.core.config import clear_config_cache, get_config, get_project_root
from src.core.strategy_config import (
    DEFAULT_STRATEGY_PRESETS,
    normalize_strategy_preset,
)

# Keys allowed to be updated via general config PUT
CONFIG_UPDATE_WHITELIST: frozenset[str] = frozenset(
    {"ui", "ai", "risk", "backtest.initial_capital"}
)

# Secret key names in .env (env var name -> config path label)
# 15-A-2：移除 GOOGLE_API_KEY（Google API Key 欄位為 legacy，後續不讀不寫不顯示）
_SECRET_ENV_KEYS: dict[str, str] = {
    "OPENAI_API_KEY": "openai",
    "ANTHROPIC_API_KEY": "anthropic",
    "GEMINI_API_KEY": "gemini",
    "FINMIND_TOKEN": "finmind",
    "DEEPSEEK_API_KEY": "deepseek",
}

_SECRET_MASK = "***configured***"


class FinMindTokenInvalid(ValueError):
    """Raised when FinMind rejects the provided token."""


class FinMindUnreachable(ConnectionError):
    """Raised when FinMind validation endpoint is unreachable."""


# ---------------------------------------------------------------------------
# 15-A-2：Per-provider validation types and validators
# ---------------------------------------------------------------------------

ValidationStatus = Literal["ok", "invalid_key", "no_quota", "unreachable", "skipped"]


@dataclass(slots=True)
class ValidationResult:
    """Result of a per-provider API key validation."""

    status: ValidationStatus
    message: str

    def is_savable(self) -> bool:
        """Return True if the key should be written to .env (ok or no_quota)."""
        return self.status in {"ok", "no_quota"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_config(*, mask_secrets: bool = True) -> dict[str, Any]:
    """Read config.yaml and return a dict.

    When ``mask_secrets=True`` (default), API key values are replaced with
    ``"***configured***"`` or omitted.  The ``secrets`` section is never
    returned as-is.
    """
    config = get_config().copy()
    # Always strip raw secrets section from returned value
    config.pop("secrets", None)

    if mask_secrets:
        # Mask any accidentally stored key-like fields in ai section
        ai_section = config.get("ai", {})
        if isinstance(ai_section, dict):
            for key in ("api_key", "openai_api_key", "anthropic_api_key", "gemini_api_key"):
                if key in ai_section and ai_section[key]:
                    ai_section[key] = _SECRET_MASK

    return config


def update_config(patch: dict[str, Any]) -> None:
    """Apply a partial config update.

    Only top-level keys in ``CONFIG_UPDATE_WHITELIST`` are accepted.
    Attempts to update other keys raise ``ValueError``.
    """
    # Validate patch keys
    for key in patch:
        if key not in CONFIG_UPDATE_WHITELIST:
            raise ValueError(
                f"Config key '{key}' is not in the update whitelist. "
                f"Allowed: {sorted(CONFIG_UPDATE_WHITELIST)}"
            )

    root = get_project_root()
    config_path = root / "config.yaml"
    config = get_config().copy()
    config.pop("secrets", None)

    for key, value in patch.items():
        if "." in key:
            # Support dot-notation like "backtest.initial_capital"
            parts = key.split(".", 1)
            section, subkey = parts[0], parts[1]
            if section not in config or not isinstance(config[section], dict):
                config[section] = {}
            config[section][subkey] = value
        else:
            if key in config and isinstance(config[key], dict) and isinstance(value, dict):
                config[key].update(value)
            else:
                config[key] = value

    config_path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    clear_config_cache()


def update_secrets(keys: dict[str, str]) -> None:
    """Write-only: persist API keys to .env file and sync current process env.

    Values are written directly; existing unrelated keys are preserved.
    The function never returns key values.

    Also syncs ``os.environ`` so the running process immediately reflects the
    new values without requiring a restart (15-A-2: single write point).

    Args:
        keys: Mapping of provider name to API key value.
              Recognised provider names: ``openai``, ``anthropic``,
              ``gemini``, ``finmind``, ``deepseek``.
    """
    # Build reverse mapping: provider label -> env var name
    label_to_env = {v: k for k, v in _SECRET_ENV_KEYS.items()}

    env_updates: dict[str, str] = {}
    for provider, value in keys.items():
        env_var = label_to_env.get(provider)
        if env_var is None:
            raise ValueError(
                f"Unknown secret provider: '{provider}'. "
                f"Recognised: {sorted(label_to_env.keys())}"
            )
        env_updates[env_var] = str(value).strip()

    _write_env(get_project_root() / ".env", env_updates)

    # Sync os.environ so the current process sees the new values immediately.
    # This is the single authoritative write point; callers must not set
    # os.environ manually after calling update_secrets().
    for env_var, value in env_updates.items():
        os.environ[env_var] = value

    clear_config_cache()


def get_secrets_status() -> dict[str, bool]:
    """Return a dict indicating whether each secret is configured.

    Never returns actual key values.

    Example::

        {"openai": True, "anthropic": False, "gemini": False, "finmind": True}
    """
    root = get_project_root()
    # Re-read .env to get current values independent of cache
    env_path = root / ".env"
    env_values: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env_values[k.strip()] = v.strip()

    def _is_set(value: str | None) -> bool:
        return value is not None and value.strip() != ""

    # Also check os.environ (may have been set outside .env)
    status: dict[str, bool] = {}
    for env_var, label in _SECRET_ENV_KEYS.items():
        if env_var in env_values:
            # .env explicitly defines this key; value in .env is authoritative.
            status[label] = _is_set(env_values[env_var])
        else:
            status[label] = _is_set(os.getenv(env_var))

    return status


def validate_finmind_token(token: str) -> None:
    """Validate FinMind token via a lightweight data query.

    Uses the same host/path as the data fetcher so a token that validates here
    is guaranteed to work for fetcher calls (and vice-versa).

    Raises:
        FinMindTokenInvalid: token rejected by FinMind.
        FinMindUnreachable: network/timeout/server-side errors / rate-limited.
    """
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockInfo",
        "data_id": "2330",
        "start_date": "2024-01-02",
        "end_date": "2024-01-02",
        "token": token,
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
    except (requests.ConnectionError, requests.Timeout, requests.RequestException) as exc:
        raise FinMindUnreachable(str(exc)) from exc

    if resp.status_code == 429 or resp.status_code >= 500:
        raise FinMindUnreachable(f"FinMind returned HTTP {resp.status_code}.")
    if resp.status_code != 200:
        raise FinMindTokenInvalid(f"FinMind rejected token (HTTP {resp.status_code}).")

    try:
        body = resp.json()
    except ValueError as exc:
        raise FinMindTokenInvalid("Invalid response from FinMind.") from exc

    if body.get("status") in (200, "200", "success"):
        return
    raise FinMindTokenInvalid(str(body.get("msg") or "Token rejected by FinMind."))


def validate_finmind_token_wrapped(token: str) -> ValidationResult:
    """Wrap validate_finmind_token() as a ValidationResult for 15-A-2 contract.

    Empty/blank token → skipped (router handles the mandatory-FinMind early return
    and maps blank to invalid_key in the response; wrapper itself stays neutral).
    """
    if not token.strip():
        return ValidationResult("skipped", "未提供 FinMind token")
    try:
        validate_finmind_token(token.strip())
    except FinMindTokenInvalid:
        return ValidationResult("invalid_key", "FinMind token 無效")
    except FinMindUnreachable:
        return ValidationResult("unreachable", "無法連線至 FinMind 伺服器")
    return ValidationResult("ok", "FinMind token 驗證成功")


def validate_deepseek_token(token: str) -> ValidationResult:
    """Validate DeepSeek API key via GET /user/balance (no /v1 prefix).

    Status mapping:
        200 + is_available=True   -> ok
        200 + is_available=False  -> no_quota
        200 + JSON parse error    -> unreachable (conservative; don't write)
        200 + is_available absent -> unreachable (conservative; don't write)
        401                       -> invalid_key
        402                       -> no_quota (Insufficient Balance per official docs)
        other 4xx                 -> invalid_key
        5xx / network             -> unreachable
    """
    if not token.strip():
        return ValidationResult("skipped", "未提供 DeepSeek key")
    try:
        resp = requests.get(
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": f"Bearer {token.strip()}"},
            timeout=10.0,
        )
    except requests.RequestException as exc:
        return ValidationResult("unreachable", f"無法連線至 DeepSeek：{exc}")

    if resp.status_code == 401:
        return ValidationResult("invalid_key", "DeepSeek 拒絕此 key（401）")
    if resp.status_code == 402:
        # DeepSeek 官方 Error Codes 明示 402 = Insufficient Balance；key 有效可寫入
        return ValidationResult("no_quota", "API key 有效但 DeepSeek 帳號餘額不足")
    if resp.status_code == 200:
        try:
            data = resp.json()
        except ValueError:
            return ValidationResult("unreachable", "DeepSeek balance response 無法解析")
        # balance API 缺 is_available 時保守視為不可判斷，避免誤把壞 key 寫入。
        is_available = data.get("is_available")
        if is_available is True:
            return ValidationResult("ok", "DeepSeek key 驗證成功")
        if is_available is False:
            return ValidationResult("no_quota", "API key 有效但 DeepSeek 帳號餘額不足")
        return ValidationResult("unreachable", "DeepSeek balance response 缺少 is_available")
    # 400 / 422 / other 4xx → invalid_key（不代表 key ok）
    return ValidationResult("invalid_key", f"DeepSeek 回 {resp.status_code}（視為無效）")


def validate_openai_token(token: str) -> ValidationResult:
    """Validate OpenAI API key via GET /v1/models."""
    if not token.strip():
        return ValidationResult("skipped", "未提供 OpenAI key")
    try:
        resp = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {token.strip()}"},
            timeout=10.0,
        )
    except requests.RequestException as exc:
        return ValidationResult("unreachable", f"無法連線至 OpenAI：{exc}")

    if resp.status_code == 200:
        return ValidationResult("ok", "OpenAI key 驗證成功")
    if resp.status_code == 401:
        return ValidationResult("invalid_key", "OpenAI 拒絕此 key（401）")
    return ValidationResult("invalid_key", f"OpenAI 回 {resp.status_code}（視為無效）")


def validate_anthropic_token(token: str) -> ValidationResult:
    """Validate Anthropic API key via 1-token POST /v1/messages ping."""
    if not token.strip():
        return ValidationResult("skipped", "未提供 Anthropic key")
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": token.strip(),
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "."}],
            },
            timeout=10.0,
        )
    except requests.RequestException as exc:
        return ValidationResult("unreachable", f"無法連線至 Anthropic：{exc}")

    if resp.status_code == 200:
        return ValidationResult("ok", "Anthropic key 驗證成功（已扣 1 token）")
    if resp.status_code == 401:
        return ValidationResult("invalid_key", "Anthropic 拒絕此 key（401）")
    return ValidationResult("invalid_key", f"Anthropic 回 {resp.status_code}（視為無效）")


def validate_gemini_token(token: str) -> ValidationResult:
    """Validate Gemini API key via GET /v1beta/models."""
    if not token.strip():
        return ValidationResult("skipped", "未提供 Gemini key")
    try:
        resp = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": token.strip()},
            timeout=10.0,
        )
    except requests.RequestException as exc:
        return ValidationResult("unreachable", f"無法連線至 Gemini：{exc}")

    if resp.status_code == 200:
        return ValidationResult("ok", "Gemini key 驗證成功")
    if resp.status_code in {400, 401, 403}:
        return ValidationResult("invalid_key", "Gemini 拒絕此 key")
    return ValidationResult("invalid_key", f"Gemini 回 {resp.status_code}（視為無效）")


def get_strategy_presets_config() -> list[dict[str, Any]]:
    """Return the current list of strategy presets from config."""
    from src.core.strategy_config import get_strategy_presets
    return get_strategy_presets(get_config())



def upsert_strategy_preset(preset: dict[str, Any]) -> None:
    """Add or update a strategy preset (matched by name)."""
    normalised = normalize_strategy_preset(preset)
    existing = get_strategy_presets_config()

    name = str(normalised.get("name", "")).strip()
    updated = [
        normalised if str(p.get("name", "")).strip() == name else p
        for p in existing
    ]
    if not any(str(p.get("name", "")).strip() == name for p in existing):
        updated.append(normalised)

    _save_strategy_presets(updated)


def delete_strategy_preset_by_name(name: str) -> None:
    """Delete preset matching name (case-sensitive trimmed). Idempotent."""
    existing = get_strategy_presets_config()
    target = str(name).strip()
    updated = [p for p in existing if str(p.get("name", "")).strip() != target]
    if len(updated) != len(existing):
        _save_strategy_presets(updated)


def delete_strategy_preset_by_index(index: int) -> None:
    """Delete strategy preset at the given 0-based index."""
    existing = get_strategy_presets_config()
    if index < 0 or index >= len(existing):
        raise IndexError(f"Strategy index {index} out of range (have {len(existing)} presets).")
    updated = existing[:index] + existing[index + 1 :]
    _save_strategy_presets(updated)


def restore_strategy_defaults() -> None:
    """Reset strategies to DEFAULT_STRATEGY_PRESETS."""
    _save_strategy_presets(list(DEFAULT_STRATEGY_PRESETS))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _save_strategy_presets(strategies: list[dict[str, Any]]) -> None:
    root = get_project_root()
    config_path = root / "config.yaml"
    config = get_config().copy()
    config.pop("secrets", None)
    config["strategies"] = strategies
    config.pop("strategy", None)
    config_path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    clear_config_cache()


def _write_env(path: Path, updates: dict[str, str]) -> None:
    current_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    new_lines: list[str] = []

    for line in current_lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue

        key, _ = line.split("=", 1)
        key = key.strip()
        if key in remaining:
            new_lines.append(f"{key}={remaining.pop(key)}")
        else:
            new_lines.append(line)

    for key, value in remaining.items():
        new_lines.append(f"{key}={value}")

    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)
