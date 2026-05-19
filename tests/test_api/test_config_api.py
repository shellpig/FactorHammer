"""Tests for config API endpoints (Phase 10-A).

Uses FastAPI TestClient (synchronous wrapper around httpx).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.services.config_service import FinMindTokenInvalid, FinMindUnreachable

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
# POST /api/config/secrets/validate (Phase 12-B)
# ---------------------------------------------------------------------------


def test_post_secrets_validate_missing_finmind_returns_400() -> None:
    response = client.post("/api/config/secrets/validate", json={})
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"]["code"] == "FINMIND_REQUIRED"


def test_post_secrets_validate_blank_finmind_returns_400() -> None:
    response = client.post("/api/config/secrets/validate", json={"finmind": "   "})
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "FINMIND_REQUIRED"


@patch("api.routers.config.update_secrets")
@patch("api.routers.config.validate_finmind_token")
def test_post_secrets_validate_invalid_token_returns_400(
    mock_validate: MagicMock,
    mock_update: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FINMIND_TOKEN", "old-token")
    mock_validate.side_effect = FinMindTokenInvalid("bad token")

    response = client.post("/api/config/secrets/validate", json={"finmind": "bad-token"})
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"]["code"] == "FINMIND_TOKEN_INVALID"
    assert os.getenv("FINMIND_TOKEN") == "old-token"
    mock_update.assert_not_called()


@patch("api.routers.config.update_secrets")
@patch("api.routers.config.validate_finmind_token")
def test_post_secrets_validate_unreachable_returns_502(
    mock_validate: MagicMock,
    mock_update: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FINMIND_TOKEN", "old-token")
    mock_validate.side_effect = FinMindUnreachable("network down")

    response = client.post("/api/config/secrets/validate", json={"finmind": "candidate-token"})
    assert response.status_code == 502
    body = response.json()
    assert body["detail"]["error"]["code"] == "FINMIND_UNREACHABLE"
    assert os.getenv("FINMIND_TOKEN") == "old-token"
    mock_update.assert_not_called()


@patch("api.routers.config.update_secrets")
@patch("api.routers.config.validate_finmind_token")
def test_post_secrets_validate_env_write_failure_returns_500(
    mock_validate: MagicMock,
    mock_update: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FINMIND_TOKEN", "old-token")
    mock_validate.return_value = None
    mock_update.side_effect = OSError("disk full")

    response = client.post("/api/config/secrets/validate", json={"finmind": "new-token"})
    assert response.status_code == 500
    body = response.json()
    assert body["detail"]["error"]["code"] == "ENV_WRITE_FAILED"
    assert "寫入設定檔失敗" in body["detail"]["error"]["message"]
    assert os.getenv("FINMIND_TOKEN") == "old-token"


@patch("api.routers.config.update_secrets")
@patch("api.routers.config.validate_finmind_token")
def test_post_secrets_validate_success_updates_finmind_only(
    mock_validate: MagicMock,
    mock_update: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_validate.return_value = None
    monkeypatch.setenv("FINMIND_TOKEN", "old-token")
    monkeypatch.setenv("OPENAI_API_KEY", "old-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "old-anthropic")

    response = client.post("/api/config/secrets/validate", json={"finmind": "new-token"})
    assert response.status_code == 200
    assert response.json() == {"data": {"updated": True}, "meta": {}}

    mock_update.assert_called_once_with({"finmind": "new-token"})
    assert os.getenv("FINMIND_TOKEN") == "new-token"
    assert os.getenv("OPENAI_API_KEY") == "old-openai"
    assert os.getenv("ANTHROPIC_API_KEY") == "old-anthropic"


@patch("api.routers.config.update_secrets")
@patch("api.routers.config.validate_finmind_token")
def test_post_secrets_validate_success_with_anthropic(
    mock_validate: MagicMock,
    mock_update: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_validate.return_value = None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "old-anthropic")

    payload = {"finmind": "fm-token", "anthropic": "ant-token"}
    response = client.post("/api/config/secrets/validate", json=payload)
    assert response.status_code == 200

    mock_update.assert_called_once_with({"finmind": "fm-token", "anthropic": "ant-token"})
    assert os.getenv("FINMIND_TOKEN") == "fm-token"
    assert os.getenv("ANTHROPIC_API_KEY") == "ant-token"


@patch("api.routers.config.update_secrets")
@patch("api.routers.config.validate_finmind_token")
def test_post_secrets_validate_null_optional_keys_do_not_overwrite(
    mock_validate: MagicMock,
    mock_update: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_validate.return_value = None
    monkeypatch.setenv("OPENAI_API_KEY", "existing-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "existing-anthropic")

    payload = {"finmind": "fm-token", "openai": None}
    response = client.post("/api/config/secrets/validate", json=payload)
    assert response.status_code == 200

    mock_update.assert_called_once_with({"finmind": "fm-token"})
    assert os.getenv("OPENAI_API_KEY") == "existing-openai"
    assert os.getenv("ANTHROPIC_API_KEY") == "existing-anthropic"


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


# ---------------------------------------------------------------------------
# GET /api/config/strategies — includes market field
# ---------------------------------------------------------------------------


@patch("api.routers.config.get_strategy_presets_config")
def test_get_strategies_returns_market_when_present(mock_get: MagicMock) -> None:
    mock_get.return_value = [
        {
            "name": "MA20_MA60",
            "type": "moving_average_cross",
            "params": {"short_window": 20, "long_window": 60},
            "market": "tw",
        }
    ]
    response = client.get("/api/config/strategies")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["count"] == 1
    assert body["data"][0]["market"] == "tw"


# ---------------------------------------------------------------------------
# POST /api/config/strategies — upsert (Phase 10-G-2)
# ---------------------------------------------------------------------------


@patch("api.routers.config.upsert_strategy_preset")
def test_post_strategies_upsert_returns_201(mock_upsert: MagicMock) -> None:
    preset = {"name": "TestMA", "strategy": "moving_average_cross", "params": {"short_window": 10, "long_window": 30}, "market": "tw"}
    response = client.post("/api/config/strategies", json={"preset": preset})
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["upserted"] is True
    assert data["name"] == "TestMA"
    mock_upsert.assert_called_once_with(preset)


@patch("api.routers.config.upsert_strategy_preset")
def test_post_strategies_invalid_preset_returns_422(mock_upsert: MagicMock) -> None:
    mock_upsert.side_effect = ValueError("Unknown strategy: bad_strategy")
    response = client.post("/api/config/strategies", json={"preset": {"name": "X", "strategy": "bad_strategy"}})
    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "INVALID_PRESET"


@patch("api.routers.config.upsert_strategy_preset")
@patch("api.routers.config.get_strategy_presets_config")
def test_post_strategies_idempotent_upsert(mock_get: MagicMock, mock_upsert: MagicMock) -> None:
    mock_get.return_value = [{"name": "TestMA"}]
    preset = {"name": "TestMA", "strategy": "moving_average_cross", "params": {}, "market": "tw"}
    resp1 = client.post("/api/config/strategies", json={"preset": preset})
    resp2 = client.post("/api/config/strategies", json={"preset": preset})
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert mock_upsert.call_count == 2


# ---------------------------------------------------------------------------
# DELETE /api/config/strategies/{name} (Phase 10-G-2)
# ---------------------------------------------------------------------------


@patch("api.routers.config.delete_strategy_preset_by_name")
def test_delete_strategy_existing_returns_204(mock_delete: MagicMock) -> None:
    response = client.delete("/api/config/strategies/TestMA")
    assert response.status_code == 204
    mock_delete.assert_called_once_with("TestMA")


@patch("api.routers.config.delete_strategy_preset_by_name")
def test_delete_strategy_nonexistent_still_returns_204(mock_delete: MagicMock) -> None:
    response = client.delete("/api/config/strategies/NonExistentPreset")
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# POST /api/config/strategies/restore (Phase 10-G-2)
# ---------------------------------------------------------------------------


@patch("api.routers.config.restore_strategy_defaults")
@patch("api.routers.config.get_strategy_presets_config")
def test_post_strategies_restore_returns_count(mock_get: MagicMock, mock_restore: MagicMock) -> None:
    mock_get.return_value = [{"name": f"P{i}"} for i in range(8)]
    response = client.post("/api/config/strategies/restore")
    assert response.status_code == 200
    assert response.json()["data"]["count"] == 8
    mock_restore.assert_called_once()
