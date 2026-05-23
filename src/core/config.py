"""Configuration loading helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_config: dict[str, Any] | None = None


def get_project_root() -> Path:
    """Return project root directory (the one containing config.yaml)."""
    current_file = Path(__file__).resolve()
    for candidate in current_file.parents:
        if (candidate / "config.yaml").exists():
            return candidate
    return current_file.parents[2]


def _load_yaml_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Missing config.yaml: {config_path}")

    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(parsed, dict):
        raise ValueError("config.yaml must contain a top-level mapping.")
    return parsed


def get_config() -> dict[str, Any]:
    """Read config.yaml, merge .env secrets, and return cached config."""
    global _config
    if _config is not None:
        return _config

    root = get_project_root()
    load_dotenv(root / ".env", override=False)

    config = _load_yaml_config(root / "config.yaml")
    config["secrets"] = {
        "finmind_token": os.getenv("FINMIND_TOKEN", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        # 15-A-2：移除 google_api_key（GOOGLE_API_KEY 保留在 .env 但不再讀取）
        "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY", ""),
    }
    
    if "ui" not in config or not isinstance(config["ui"], dict):
        config["ui"] = {}
        
    _config = config
    return _config


def get_data_dir() -> Path:
    """Return absolute data directory path and create it if missing."""
    config = get_config()
    system_section = config.get("system", {})
    if not isinstance(system_section, dict):
        system_section = {}

    configured = system_section.get("data_dir", "./data")
    raw_path = Path(str(configured))
    data_dir = raw_path if raw_path.is_absolute() else (get_project_root() / raw_path)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir.resolve()


def clear_config_cache() -> None:
    """Clear in-memory config cache (useful for tests)."""
    global _config
    _config = None
