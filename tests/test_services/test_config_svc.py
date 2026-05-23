"""Tests for config_service (Phase 10-A / 15-A-2)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.config import clear_config_cache
from src.core.config import get_config as core_get_config
from src.services.config_service import (
    CONFIG_UPDATE_WHITELIST,
    FinMindTokenInvalid,
    FinMindUnreachable,
    ValidationResult,
    _write_env,
    delete_strategy_preset_by_name,
    get_secrets_status,
    read_config,
    update_config,
    update_secrets,
    validate_anthropic_token,
    validate_deepseek_token,
    validate_finmind_token,
    validate_finmind_token_wrapped,
    validate_gemini_token,
    validate_openai_token,
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


@patch("src.services.config_service.get_project_root")
def test_get_secrets_status_whitespace_is_false(
    mock_root: MagicMock,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=   \n", encoding="utf-8")
    mock_root.return_value = tmp_path
    assert get_secrets_status()["openai"] is False


@patch("src.services.config_service.get_project_root")
def test_get_secrets_status_env_value_is_authoritative_over_os_environ(
    mock_root: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=\n", encoding="utf-8")
    mock_root.return_value = tmp_path
    monkeypatch.setenv("OPENAI_API_KEY", "from-os-env")
    assert get_secrets_status()["openai"] is False


@patch("src.services.config_service.get_project_root")
def test_get_secrets_status_falls_back_to_os_environ_when_key_missing_in_env(
    mock_root: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("FINMIND_TOKEN=abc\n", encoding="utf-8")
    mock_root.return_value = tmp_path
    monkeypatch.setenv("OPENAI_API_KEY", "from-os-env")
    assert get_secrets_status()["openai"] is True


@patch("src.services.config_service.get_project_root")
def test_secrets_status_includes_deepseek(
    mock_root: MagicMock,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DEEPSEEK_API_KEY=sk-ds-test\n", encoding="utf-8")
    mock_root.return_value = tmp_path

    status = get_secrets_status()
    assert "deepseek" in status
    assert isinstance(status["deepseek"], bool)
    assert status["deepseek"] is True


@patch("src.core.config.get_project_root")
def test_get_config_secrets_includes_deepseek_api_key(
    mock_root: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "config.yaml").write_text("ui:\n  theme: dark\n", encoding="utf-8")
    (tmp_path / ".env").write_text("", encoding="utf-8")
    mock_root.return_value = tmp_path

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    clear_config_cache()
    config = core_get_config()
    assert config["secrets"]["deepseek_api_key"] == "sk-x"

    monkeypatch.delenv("DEEPSEEK_API_KEY")
    clear_config_cache()
    config = core_get_config()
    assert config["secrets"]["deepseek_api_key"] == ""

    clear_config_cache()


# ---------------------------------------------------------------------------
# delete_strategy_preset_by_name
# ---------------------------------------------------------------------------


@patch("src.services.config_service.get_config")
@patch("src.services.config_service.get_project_root")
@patch("src.services.config_service.clear_config_cache")
def test_delete_strategy_preset_by_name_removes_entry(
    mock_clear: MagicMock,
    mock_root: MagicMock,
    mock_get_config: MagicMock,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("strategies: []\n", encoding="utf-8")
    mock_root.return_value = tmp_path
    mock_get_config.return_value = {
        "strategies": [
            {"name": "MA Cross", "type": "moving_average_cross", "params": {}},
            {"name": "RSI", "type": "rsi", "params": {}},
        ]
    }

    delete_strategy_preset_by_name("MA Cross")

    written = config_path.read_text(encoding="utf-8")
    assert "MA Cross" not in written
    assert "RSI" in written


@patch("src.services.config_service.get_config")
@patch("src.services.config_service.get_project_root")
@patch("src.services.config_service.clear_config_cache")
def test_delete_strategy_preset_by_name_nonexistent_no_write(
    mock_clear: MagicMock,
    mock_root: MagicMock,
    mock_get_config: MagicMock,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("sentinel: true\n", encoding="utf-8")
    mock_root.return_value = tmp_path
    mock_get_config.return_value = {
        "strategies": [{"name": "RSI", "strategy": "rsi"}]
    }

    delete_strategy_preset_by_name("DoesNotExist")

    # No rewrite happened — sentinel file unchanged
    assert config_path.read_text(encoding="utf-8") == "sentinel: true\n"
    mock_clear.assert_not_called()


@patch("src.services.config_service.get_config")
@patch("src.services.config_service.get_project_root")
@patch("src.services.config_service.clear_config_cache")
def test_delete_strategy_preset_by_name_strips_spaces(
    mock_clear: MagicMock,
    mock_root: MagicMock,
    mock_get_config: MagicMock,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("strategies: []\n", encoding="utf-8")
    mock_root.return_value = tmp_path
    mock_get_config.return_value = {
        "strategies": [{"name": "  MA Cross  ", "type": "moving_average_cross", "params": {}}]
    }

    delete_strategy_preset_by_name("  MA Cross  ")

    written = config_path.read_text(encoding="utf-8")
    assert "MA Cross" not in written


# ---------------------------------------------------------------------------
# _write_env (Phase 12-B)
# ---------------------------------------------------------------------------


def test_write_env_preserves_comments_blank_lines_unknown_keys_and_order(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# header comment\n"
        "CUSTOM_VAR=xyz\n"
        "\n"
        "B=1\n"
        "A=2\n"
        "# middle comment\n",
        encoding="utf-8",
    )

    _write_env(env_path, {"A": "updated", "FINMIND_TOKEN": "fm-token"})
    lines = env_path.read_text(encoding="utf-8").splitlines()

    assert lines[0] == "# header comment"
    assert lines[1] == "CUSTOM_VAR=xyz"
    assert lines[2] == ""
    assert lines[3] == "B=1"
    assert lines[4] == "A=updated"
    assert lines[5] == "# middle comment"
    assert lines[6] == "FINMIND_TOKEN=fm-token"


def test_write_env_atomic_replace_failure_keeps_original_file(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=old\n", encoding="utf-8")

    with patch("src.services.config_service.os.replace", side_effect=OSError("replace failed")):
        with pytest.raises(OSError, match="replace failed"):
            _write_env(env_path, {"OPENAI_API_KEY": "new"})

    assert env_path.read_text(encoding="utf-8") == "OPENAI_API_KEY=old\n"
    tmp_content = (tmp_path / ".env.tmp").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=new" in tmp_content


def test_write_env_preserves_utf8_comments(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("# 中文註解\nOPENAI_API_KEY=old\n", encoding="utf-8")
    _write_env(env_path, {"OPENAI_API_KEY": "new"})
    content = env_path.read_text(encoding="utf-8")
    assert "# 中文註解" in content
    assert "OPENAI_API_KEY=new" in content


@patch("src.services.config_service.get_project_root")
@patch("src.services.config_service.clear_config_cache")
def test_update_secrets_preserves_comments_and_blank_lines(
    mock_clear: MagicMock,
    mock_root: MagicMock,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("# keep me\n\nOPENAI_API_KEY=old\n", encoding="utf-8")
    mock_root.return_value = tmp_path

    update_secrets({"openai": "new"})
    content = env_path.read_text(encoding="utf-8")
    assert "# keep me" in content
    assert "\n\n" in content
    assert "OPENAI_API_KEY=new" in content
    mock_clear.assert_called_once()


# ---------------------------------------------------------------------------
# validate_finmind_token (Phase 12-B)
# ---------------------------------------------------------------------------


def _mock_response(
    *,
    status_code: int,
    json_body: dict[str, object] | None = None,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {} if json_body is None else json_body
    return response


@patch("src.services.config_service.requests.get")
@pytest.mark.parametrize("status_code", [401, 403, 422])
def test_validate_finmind_token_rejected_status_codes(
    mock_get: MagicMock,
    status_code: int,
) -> None:
    mock_get.return_value = _mock_response(status_code=status_code)
    with pytest.raises(FinMindTokenInvalid):
        validate_finmind_token("bad-token")


@patch("src.services.config_service.requests.get")
def test_validate_finmind_token_connection_error(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.ConnectionError("conn error")
    with pytest.raises(FinMindUnreachable):
        validate_finmind_token("token")


@patch("src.services.config_service.requests.get")
def test_validate_finmind_token_timeout(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.Timeout("timeout")
    with pytest.raises(FinMindUnreachable):
        validate_finmind_token("token")


@patch("src.services.config_service.requests.get")
def test_validate_finmind_token_http_500(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(status_code=500)
    with pytest.raises(FinMindUnreachable):
        validate_finmind_token("token")


@patch("src.services.config_service.requests.get")
def test_validate_finmind_token_success_200(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(status_code=200, json_body={"status": 200, "msg": "success"})
    validate_finmind_token("token")
    mock_get.assert_called_once_with(
        "https://api.finmindtrade.com/api/v4/data",
        params={
            "dataset": "TaiwanStockInfo",
            "data_id": "2330",
            "start_date": "2024-01-02",
            "end_date": "2024-01-02",
            "token": "token",
        },
        timeout=5,
    )


@patch("src.services.config_service.requests.get")
def test_validate_finmind_token_http_400_is_invalid(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(
        status_code=400,
        json_body={"msg": "Token is illegal.", "status": 400},
    )
    with pytest.raises(FinMindTokenInvalid):
        validate_finmind_token("bad-token")


@patch("src.services.config_service.requests.get")
def test_validate_finmind_token_200_with_invalid_status_in_body(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(
        status_code=200,
        json_body={"status": "error", "msg": "token invalid"},
    )
    with pytest.raises(FinMindTokenInvalid):
        validate_finmind_token("token")


@patch("src.services.config_service.requests.get")
def test_validate_finmind_token_200_missing_status_is_invalid(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(status_code=200, json_body={"msg": "ok but no status"})
    with pytest.raises(FinMindTokenInvalid):
        validate_finmind_token("token")


# ---------------------------------------------------------------------------
# 15-A-2：ValidationResult dataclass
# ---------------------------------------------------------------------------


def test_validation_result_is_savable_ok() -> None:
    assert ValidationResult("ok", "msg").is_savable() is True


def test_validation_result_is_savable_no_quota() -> None:
    assert ValidationResult("no_quota", "msg").is_savable() is True


def test_validation_result_not_savable_invalid_key() -> None:
    assert ValidationResult("invalid_key", "msg").is_savable() is False


def test_validation_result_not_savable_unreachable() -> None:
    assert ValidationResult("unreachable", "msg").is_savable() is False


def test_validation_result_not_savable_skipped() -> None:
    assert ValidationResult("skipped", "msg").is_savable() is False


# ---------------------------------------------------------------------------
# 15-A-2：validate_finmind_token_wrapped
# ---------------------------------------------------------------------------


@patch("src.services.config_service.requests.get")
def test_validate_finmind_token_wrapped_ok(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(status_code=200, json_body={"status": 200, "msg": "success"})
    result = validate_finmind_token_wrapped("valid-token")
    assert result.status == "ok"


@patch("src.services.config_service.requests.get")
def test_validate_finmind_token_wrapped_invalid(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(status_code=401)
    result = validate_finmind_token_wrapped("bad-token")
    assert result.status == "invalid_key"


@patch("src.services.config_service.requests.get")
def test_validate_finmind_token_wrapped_unreachable(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.ConnectionError("timeout")
    result = validate_finmind_token_wrapped("token")
    assert result.status == "unreachable"


def test_validate_finmind_token_wrapped_empty_is_skipped() -> None:
    """Wrapper 本身回 skipped；router 負責 blank finmind 的 early-return invalid_key。"""
    result = validate_finmind_token_wrapped("")
    assert result.status == "skipped"


# ---------------------------------------------------------------------------
# 15-A-2：validate_deepseek_token
# ---------------------------------------------------------------------------


@patch("src.services.config_service.requests.get")
def test_validate_deepseek_token_ok(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(status_code=200, json_body={"is_available": True})
    result = validate_deepseek_token("sk-ds-good")
    assert result.status == "ok"


@patch("src.services.config_service.requests.get")
def test_validate_deepseek_token_no_quota_402(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(status_code=402)
    result = validate_deepseek_token("sk-ds-broke")
    assert result.status == "no_quota"
    assert result.is_savable() is True


@patch("src.services.config_service.requests.get")
def test_validate_deepseek_token_no_quota_is_available_false(mock_get: MagicMock) -> None:
    """200 with is_available=False → no_quota (key is valid, just out of balance)."""
    mock_get.return_value = _mock_response(status_code=200, json_body={"is_available": False})
    result = validate_deepseek_token("sk-ds-broke")
    assert result.status == "no_quota"
    assert result.is_savable() is True


@patch("src.services.config_service.requests.get")
def test_validate_deepseek_token_200_missing_is_available_is_unreachable(mock_get: MagicMock) -> None:
    """200 但 response body 缺少 is_available → unreachable（保守不寫入）."""
    mock_get.return_value = _mock_response(status_code=200, json_body={"balance": 100})
    result = validate_deepseek_token("sk-ds")
    assert result.status == "unreachable"
    assert result.is_savable() is False


@patch("src.services.config_service.requests.get")
def test_validate_deepseek_token_200_json_parse_error_is_unreachable(mock_get: MagicMock) -> None:
    """200 但 JSON 解析失敗 → unreachable（保守不寫入）."""
    mock = _mock_response(status_code=200, json_body={})
    mock.json.side_effect = ValueError("bad json")
    mock_get.return_value = mock
    result = validate_deepseek_token("sk-ds")
    assert result.status == "unreachable"
    assert result.is_savable() is False


@patch("src.services.config_service.requests.get")
def test_validate_deepseek_token_invalid_401(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(status_code=401)
    result = validate_deepseek_token("sk-bad")
    assert result.status == "invalid_key"


@patch("src.services.config_service.requests.get")
def test_validate_deepseek_token_unreachable(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.ConnectionError("down")
    result = validate_deepseek_token("sk-ds")
    assert result.status == "unreachable"


def test_validate_deepseek_token_empty_is_skipped() -> None:
    result = validate_deepseek_token("")
    assert result.status == "skipped"


# ---------------------------------------------------------------------------
# 15-A-2：validate_openai_token
# ---------------------------------------------------------------------------


@patch("src.services.config_service.requests.get")
def test_validate_openai_token_ok(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(status_code=200)
    result = validate_openai_token("sk-openai-good")
    assert result.status == "ok"


@patch("src.services.config_service.requests.get")
def test_validate_openai_token_invalid_401(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(status_code=401)
    result = validate_openai_token("sk-bad")
    assert result.status == "invalid_key"


@patch("src.services.config_service.requests.get")
def test_validate_openai_token_unreachable(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.Timeout("timeout")
    result = validate_openai_token("sk-openai")
    assert result.status == "unreachable"


def test_validate_openai_token_empty_is_skipped() -> None:
    assert validate_openai_token("").status == "skipped"


# ---------------------------------------------------------------------------
# 15-A-2：validate_anthropic_token
# ---------------------------------------------------------------------------


@patch("src.services.config_service.requests.post")
def test_validate_anthropic_token_ok(mock_post: MagicMock) -> None:
    mock_post.return_value = _mock_response(status_code=200)
    result = validate_anthropic_token("sk-ant-good")
    assert result.status == "ok"


@patch("src.services.config_service.requests.post")
def test_validate_anthropic_token_invalid_401(mock_post: MagicMock) -> None:
    mock_post.return_value = _mock_response(status_code=401)
    result = validate_anthropic_token("sk-ant-bad")
    assert result.status == "invalid_key"


@patch("src.services.config_service.requests.post")
def test_validate_anthropic_token_unreachable(mock_post: MagicMock) -> None:
    mock_post.side_effect = requests.ConnectionError("down")
    result = validate_anthropic_token("sk-ant")
    assert result.status == "unreachable"


def test_validate_anthropic_token_empty_is_skipped() -> None:
    assert validate_anthropic_token("").status == "skipped"


# ---------------------------------------------------------------------------
# 15-A-2：validate_gemini_token
# ---------------------------------------------------------------------------


@patch("src.services.config_service.requests.get")
def test_validate_gemini_token_ok(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(status_code=200)
    result = validate_gemini_token("AIza-good")
    assert result.status == "ok"


@patch("src.services.config_service.requests.get")
def test_validate_gemini_token_invalid_401(mock_get: MagicMock) -> None:
    mock_get.return_value = _mock_response(status_code=401)
    result = validate_gemini_token("AIza-bad")
    assert result.status == "invalid_key"


@patch("src.services.config_service.requests.get")
def test_validate_gemini_token_unreachable(mock_get: MagicMock) -> None:
    mock_get.side_effect = requests.Timeout("timeout")
    result = validate_gemini_token("AIza")
    assert result.status == "unreachable"


def test_validate_gemini_token_empty_is_skipped() -> None:
    assert validate_gemini_token("").status == "skipped"


# ---------------------------------------------------------------------------
# 15-A-2：google_api_key fallback 移除 regression
# ---------------------------------------------------------------------------


@patch("src.core.config.get_project_root")
def test_get_config_secrets_no_longer_contains_google_api_key(
    mock_root: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """15-A-2 regression: google_api_key 不再出現在 config[secrets]。"""
    (tmp_path / "config.yaml").write_text("ui:\n  theme: dark\n", encoding="utf-8")
    (tmp_path / ".env").write_text("", encoding="utf-8")
    mock_root.return_value = tmp_path

    monkeypatch.setenv("GOOGLE_API_KEY", "goog-should-not-appear")
    clear_config_cache()
    config = core_get_config()
    assert "google_api_key" not in config.get("secrets", {}), (
        "google_api_key should not be in config[secrets] after 15-A-2"
    )

    clear_config_cache()


@patch("src.services.config_service.get_project_root")
def test_secrets_status_no_longer_contains_google(
    mock_root: MagicMock,
    tmp_path: Path,
) -> None:
    """15-A-2 regression: get_secrets_status() 不再回傳 'google' 鍵。"""
    (tmp_path / ".env").write_text("GOOGLE_API_KEY=goog-key\n", encoding="utf-8")
    mock_root.return_value = tmp_path
    status = get_secrets_status()
    assert "google" not in status, "google should not appear in secrets_status after 15-A-2"

