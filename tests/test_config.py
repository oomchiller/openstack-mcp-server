"""SPEC CFG: server settings from the environment."""

import pytest

from openstack_mcp_server.config import ConfigError, Settings

from .conftest import PROJECT_A, PROJECT_B


def env(**values: str) -> dict[str, str]:
    return {f"OPENSTACK_MCP_{key}": value for key, value in values.items()}


def test_cfg_defaults() -> None:
    settings = Settings.from_env({})
    assert settings == Settings()
    assert settings.mode == "readonly"
    assert not settings.write_tools_registered
    assert settings.transport == "stdio"
    assert (settings.default_limit, settings.max_limit) == (50, 100)
    assert settings.max_response_bytes == 524288
    assert settings.api_timeout == 10
    assert settings.enable_prompts and settings.enable_resources


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("0", False),
        ("No", False),
    ],
)
def test_cfg_8_booleans(raw: str, expected: bool) -> None:
    assert Settings.from_env(env(ENABLE_PROMPTS=raw)).enable_prompts is expected


def test_cfg_9_project_ids_are_parsed_and_trimmed() -> None:
    uuid = "12345678-1234-1234-1234-123456789abc"
    settings = Settings.from_env(env(PROJECT_IDS=f" {PROJECT_A} , {uuid},{PROJECT_B}"))
    assert settings.project_ids == (PROJECT_A, uuid, PROJECT_B)


@pytest.mark.parametrize(
    "value",
    [
        f"{PROJECT_A},,{PROJECT_B}",
        "not-a-project",
        f"{PROJECT_A},{PROJECT_A}",
        ",".join(f"{i:032x}" for i in range(101)),
    ],
)
def test_cfg_9_project_ids_rejected(value: str) -> None:
    with pytest.raises(ConfigError) as caught:
        Settings.from_env(env(PROJECT_IDS=value))
    assert caught.value.variable == "OPENSTACK_MCP_PROJECT_IDS"


def test_cfg_10_upstream_variables_are_ignored() -> None:
    settings = Settings.from_env(
        {"TRANSPORT": "streamable-http", "DEBUG_MODE": "true", "CLOUD_NAME": "other"}
    )
    assert settings == Settings()


def test_cfg_11_default_limit_must_not_exceed_max() -> None:
    with pytest.raises(ConfigError, match="OPENSTACK_MCP_DEFAULT_LIMIT"):
        Settings.from_env(env(MAX_LIMIT="20", DEFAULT_LIMIT="30"))
    assert Settings.from_env(env(MAX_LIMIT="20")).default_limit == 20


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MODE", "superuser"),
        ("ENABLE_WRITE_TOOLS", "maybe"),
        ("MAX_LIMIT", "zero"),
        ("MAX_LIMIT", "1001"),
        ("DEFAULT_LIMIT", "-1"),
        ("MAX_RESPONSE_BYTES", "100"),
        ("API_TIMEOUT", "600"),
        ("TRANSPORT", "sse"),
        ("HTTP_PORT", "70000"),
        ("LOG_LEVEL", "TRACE"),
        ("CACERT_PEM", "not a certificate"),
    ],
)
def test_cfg_12_invalid_values_name_variable_not_value(name: str, value: str) -> None:
    with pytest.raises(ConfigError) as caught:
        Settings.from_env(env(**{name: value}))
    assert f"OPENSTACK_MCP_{name}" in str(caught.value)
    assert value not in str(caught.value)


def test_cfg_6_pem_is_accepted_and_hidden_from_repr() -> None:
    pem = "-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n"
    settings = Settings.from_env(env(CACERT_PEM=pem))
    assert settings.cacert_pem == pem
    assert "BEGIN CERTIFICATE" not in repr(settings)


def test_ro_2_write_gates() -> None:
    assert not Settings.from_env(env(MODE="admin")).write_tools_registered
    both = Settings.from_env(env(MODE="admin", ENABLE_WRITE_TOOLS="true"))
    assert both.write_tools_registered
    with pytest.raises(ConfigError, match="requires OPENSTACK_MCP_MODE=admin"):
        Settings.from_env(env(ENABLE_WRITE_TOOLS="true"))


def test_tr_3_remote_http_bind_needs_opt_in() -> None:
    with pytest.raises(ConfigError, match="OPENSTACK_MCP_HTTP_HOST"):
        Settings.from_env(env(TRANSPORT="streamable-http", HTTP_HOST="0.0.0.0"))
    allowed = Settings.from_env(
        env(TRANSPORT="streamable-http", HTTP_HOST="0.0.0.0", HTTP_ALLOW_REMOTE="true")
    )
    assert allowed.http_host == "0.0.0.0"
    assert Settings.from_env(env(HTTP_HOST="0.0.0.0")).transport == "stdio"
