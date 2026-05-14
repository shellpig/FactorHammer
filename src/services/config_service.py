"""Config service — non-UI config & secrets management (Phase 10-A).

All functions return plain Python dicts or raise exceptions.
No Streamlit calls are made here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

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
_SECRET_ENV_KEYS: dict[str, str] = {
    "OPENAI_API_KEY": "openai",
    "ANTHROPIC_API_KEY": "anthropic",
    "GEMINI_API_KEY": "gemini",
    "FINMIND_TOKEN": "finmind",
    "GOOGLE_API_KEY": "google",
}

_SECRET_MASK = "***configured***"


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
    """Write-only: persist API keys to .env file.

    Values are written directly; existing unrelated keys are preserved.
    The function never returns key values.

    Args:
        keys: Mapping of provider name to API key value.
              Recognised provider names: ``openai``, ``anthropic``,
              ``gemini``, ``finmind``, ``google``.
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

    # Also check os.environ (may have been set outside .env)
    status: dict[str, bool] = {}
    for env_var, label in _SECRET_ENV_KEYS.items():
        value = env_values.get(env_var) or os.getenv(env_var, "")
        status[label] = bool(value)

    return status


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
    current_lines: list[str]
    if path.exists():
        current_lines = path.read_text(encoding="utf-8").splitlines()
    else:
        current_lines = []

    by_key: dict[str, str] = {}
    for line in current_lines:
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        by_key[k.strip()] = v

    for key, value in updates.items():
        by_key[key] = value

    rendered = [f"{k}={v}" for k, v in sorted(by_key.items())]
    path.write_text("\n".join(rendered) + "\n", encoding="utf-8")
