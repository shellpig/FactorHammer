"""Tests for config_service (Phase 10-A)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.config_service import (
    CONFIG_UPDATE_WHITELIST,
    _write_env,
    get_secrets_status,
    read_config,
    update_config,
    update_secrets,
)


# ---------------------------------------------------------------------------
# read_config — secrets masking
# ---------------------------------------------------------------------------


@patch("src.services.config_service.get_config")
def test_read_config_masks_secrets(mock_get_config: MagicMock) -> None:
    mock_get_config.return_value = {
        "ui": {"theme": "dark"},
        "ai": {"enabled": True, "api_key": "sk-supersecret"},
        "secrets": {
            "openai_api_key": "sk-supersecret",
            "anthropic_api_key": "ant-supersecret",
        },
    }
    result = read_config(mask_secrets=True)
    assert "secrets" not in result
    ai = result.get("ai", {})
    if "api_key" in ai:
        assert ai["api_key"] == "***configured***"


@patch("src.services.config_service.get_config")
def test_read_config_does_not_return_raw_secrets_section(mock_get_config: MagicMock) -> None:
    mock_get_config.return_value = {
        "ui": {},
        "secrets": {"openai_api_key": "sk-real"},
    }
    result = read_config()
    assert "secrets" not in result


@patch("src.services.config_service.get_config")
def test_read_config_returns_ui_section(mock_get_config: MagicMock) -> None:
    mock_get_config.return_value = {"ui": {"theme": "midnight_blue"}, "secrets": {}}
    result = read_config()
    assert result.get("ui", {}).get("theme") == "midnight_blue"


# ---------------------------------------------------------------------------
# update_config — whitelist
# ---------------------------------------------------------------------------


@patch("src.services.config_service.get_config")
@patch("src.services.config_service.get_project_root")
@patch("src.services.config_service.clear_config_cache")
def test_update_config_allows_whitelisted_keys(
    mock_clear: MagicMock,
    mock_root: MagicMock,
    mock_get_config: MagicMock,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("ui:\n  theme: dark\n", encoding="utf-8")
    mock_root.return_value = tmp_path
    mock_get_config.return_value = {"ui": {"theme": "dark"}, "secrets": {}}

    update_config({"ui": {"theme": "light"}})
    mock_clear.assert_called_once()


@patch("src.services.config_service.get_config")
@patch("src.services.config_service.get_project_root")
@patch("src.services.config_service.clear_config_cache")
def test_update_config_rejects_non_whitelisted_key(
    mock_clear: MagicMock,
    mock_root: MagicMock,
    mock_get_config: MagicMock,
    tmp_path: Path,
) -> None:
    mock_get_config.return_value = {"secrets": {}}
    mock_root.return_value = tmp_path

    with pytest.raises(ValueError, match="whitelist"):
        update_config({"system": {"data_dir": "/evil"}})


def test_config_update_whitelist_contains_expected_keys() -> None:
    assert "ui" in CONFIG_UPDATE_WHITELIST
    assert "ai" in CONFIG_UPDATE_WHITELIST
    assert "risk" in CONFIG_UPDATE_WHITELIST
    assert "backtest.initial_capital" in CONFIG_UPDATE_WHITELIST


# ---------------------------------------------------------------------------
# update_secrets — write-only
# ---------------------------------------------------------------------------


@patch("src.services.config_service.get_project_root")
@patch("src.services.config_service.clear_config_cache")
def test_update_secrets_writes_env_file(
    mock_clear: MagicMock,
    mock_root: MagicMock,
    tmp_path: Path,
) -> None:
    mock_root.return_value = tmp_path
    update_secrets({"openai": "sk-test-key"})
    env_content = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-test-key" in env_content


@patch("src.services.config_service.get_project_root")
@patch("src.services.config_service.clear_config_cache")
def test_update_secrets_rejects_unknown_provider(
    mock_clear: MagicMock,
    mock_root: MagicMock,
    tmp_path: Path,
) -> None:
    mock_root.return_value = tmp_path
    with pytest.raises(ValueError, match="Unknown secret provider"):
        update_secrets({"binance": "api-key-xyz"})


# ---------------------------------------------------------------------------
# get_secrets_status — boolean only
# ---------------------------------------------------------------------------


@patch("src.services.config_service.get_project_root")
def test_get_secrets_status_returns_boolean_values(
    mock_root: MagicMock,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-test\nANTHROPIC_API_KEY=\n", encoding="utf-8")
    mock_root.return_value = tmp_path

    status = get_secrets_status()
    assert isinstance(status["openai"], bool)
    assert isinstance(status["anthropic"], bool)
    assert status["openai"] is True
    assert status["anthropic"] is False


@patch("src.services.config_service.get_project_root")
def test_get_secrets_status_never_returns_key_values(
    mock_root: MagicMock,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-supersecret\n", encoding="utf-8")
    mock_root.return_value = tmp_path

    status = get_secrets_status()
    for v in status.values():
        assert isinstance(v, bool), f"Expected bool, got {type(v).__name__}: {v!r}"
