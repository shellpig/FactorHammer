"""Tests for config API endpoints (Phase 10-A).

Uses FastAPI TestClient (synchronous wrapper around httpx).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------


def test_health_returns_ok() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------


@patch("api.routers.config.read_config")
def test_get_config_returns_masked_config(mock_read: MagicMock) -> None:
    mock_read.return_value = {"ui": {"theme": "dark"}, "ai": {"enabled": False}}
    response = client.get("/api/config")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "ui" in body["data"]
    mock_read.assert_called_once_with(mask_secrets=True)


@patch("api.routers.config.read_config")
def test_get_config_never_contains_raw_secrets(mock_read: MagicMock) -> None:
    mock_read.return_value = {"ui": {}}
    response = client.get("/api/config")
    body = response.json()
    assert "secrets" not in body.get("data", {})


# ---------------------------------------------------------------------------
# PUT /api/config
# ---------------------------------------------------------------------------


@patch("api.routers.config.update_config")
def test_put_config_whitelist_key_succeeds(mock_update: MagicMock) -> None:
    response = client.put("/api/config", json={"patch": {"ui": {"theme": "light"}}})
    assert response.status_code == 200
    mock_update.assert_called_once_with({"ui": {"theme": "light"}})


@patch("api.routers.config.update_config")
def test_put_config_non_whitelist_key_returns_422(mock_update: MagicMock) -> None:
    mock_update.side_effect = ValueError("Config key 'system' is not in the update whitelist.")
    response = client.put("/api/config", json={"patch": {"system": {"data_dir": "/evil"}}})
    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["error"]["code"] == "WHITELIST_REJECTED"


# ---------------------------------------------------------------------------
# PUT /api/config/secrets
# ---------------------------------------------------------------------------


@patch("api.routers.config.update_secrets")
def test_put_secrets_returns_200_and_does_not_echo_values(mock_update: MagicMock) -> None:
    response = client.put("/api/config/secrets", json={"keys": {"openai": "sk-test"}})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["updated"] is True
    # Ensure the response body never echoes the key value
    assert "sk-test" not in str(body)


@patch("api.routers.config.update_secrets")
def test_put_secrets_unknown_provider_returns_422(mock_update: MagicMock) -> None:
    mock_update.side_effect = ValueError("Unknown secret provider: 'binance'")
    response = client.put("/api/config/secrets", json={"keys": {"binance": "xxx"}})
    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "UNKNOWN_PROVIDER"


# ---------------------------------------------------------------------------
# GET /api/config/secrets/status
# ---------------------------------------------------------------------------


@patch("api.routers.config.get_secrets_status")
def test_get_secrets_status_returns_boolean_values(mock_status: MagicMock) -> None:
    mock_status.return_value = {"openai": True, "anthropic": False, "gemini": False}
    response = client.get("/api/config/secrets/status")
    assert response.status_code == 200
    data = response.json()["data"]
    for v in data.values():
        assert isinstance(v, bool)


@patch("api.routers.config.get_secrets_status")
def test_get_secrets_status_never_returns_key_values(mock_status: MagicMock) -> None:
    mock_status.return_value = {"openai": True}
    response = client.get("/api/config/secrets/status")
    body_str = str(response.json())
    # Ensure nothing that looks like an API key appears
    assert "sk-" not in body_str
    assert "ant-" not in body_str
