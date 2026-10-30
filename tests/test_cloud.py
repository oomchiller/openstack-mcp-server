"""SPEC CFG-1, CFG-3, CFG-5 … CFG-7, SCOPE-1, SCOPE-4: credentials and sessions."""

import os
import stat
from pathlib import Path

import pytest

from openstack_mcp_server.cloud import (
    CaBundle,
    Cloud,
    load_cloud,
    project_config,
    sdk_connection,
)
from openstack_mcp_server.config import ConfigError, Settings
from openstack_mcp_server.errors import ToolFailure

from .conftest import BASE_CONFIG, CONFIGURED, PROJECT_A, PROJECT_B, SECRET, FakeCloud

PEM = "-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----"


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for key in list(os.environ):
        if key.startswith("OS_"):
            monkeypatch.delenv(key)
    return monkeypatch


def os_env(monkeypatch: pytest.MonkeyPatch, **values: str) -> None:
    base = {
        "OS_AUTH_URL": "https://keystone.example/v3",
        "OS_USERNAME": "reader",
        "OS_PASSWORD": SECRET,
        "OS_USER_DOMAIN_ID": "default",
        "OS_PROJECT_ID": PROJECT_A,
        "OS_REGION_NAME": "RegionOne",
        "OS_INTERFACE": "internal",
    }
    for key, value in {**base, **values}.items():
        monkeypatch.setenv(key, value)


def test_cfg_3_missing_credentials_is_not_configured(
    clean_env: pytest.MonkeyPatch,
) -> None:
    state, base = load_cloud(Settings(), config_files=[])
    assert not state.configured
    assert state.reason == "missing_credentials"
    assert base is None


def test_cfg_1_environment_cloud(clean_env: pytest.MonkeyPatch) -> None:
    os_env(clean_env)
    state, base = load_cloud(Settings(), config_files=[])
    assert state.configured
    assert state.source == "environment"
    assert state.region_name == "RegionOne"
    assert state.interface == "internal"
    assert state.configured_project_id == PROJECT_A
    assert state.tls == "system"
    assert base is not None and base["auth"]["password"] == SECRET
    assert SECRET not in repr(state)


def test_cfg_1_clouds_yaml(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clouds = tmp_path / "clouds.yaml"
    clouds.write_text(
        "clouds:\n  lab:\n    auth:\n      auth_url: https://keystone.example/v3\n"
        "      username: reader\n      password: x\n      user_domain_id: default\n"
        "      project_name: demo\n      project_domain_id: default\n"
        "    region_name: RegionTwo\n    cacert: /etc/ssl/lab.pem\n"
    )
    clean_env.setenv("OS_CLOUD", "lab")
    state, _ = load_cloud(Settings(), config_files=[str(clouds)])
    assert state.configured
    assert state.source == "clouds.yaml:lab"
    assert state.region_name == "RegionTwo"
    assert state.tls == "file"
    assert state.configured_project_id is None


def test_cfg_1_unknown_cloud_is_invalid(
    clean_env: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clouds = tmp_path / "clouds.yaml"
    clouds.write_text(
        "clouds:\n  other:\n    auth:\n      auth_url: https://k.example/v3\n"
    )
    clean_env.setenv("OS_CLOUD", "missing")
    state, _ = load_cloud(Settings(), config_files=[str(clouds)])
    assert (state.configured, state.reason) == (False, "invalid_cloud_config")


@pytest.mark.parametrize(
    "extra",
    [{"OS_INSECURE": "true"}, {"OS_AUTH_URL": "http://keystone.example/v3"}],
)
def test_cfg_7_insecure_transport_refused(
    clean_env: pytest.MonkeyPatch, extra: dict[str, str]
) -> None:
    os_env(clean_env, **extra)
    state, base = load_cloud(Settings(), config_files=[])
    assert (state.configured, state.reason, base) == (False, "insecure_transport", None)
    allowed, _ = load_cloud(Settings(allow_insecure=True), config_files=[])
    assert allowed.configured


def test_cfg_6_pem_source(clean_env: pytest.MonkeyPatch) -> None:
    os_env(clean_env, OS_CACERT="/etc/ssl/other.pem")
    state, _ = load_cloud(Settings(cacert_pem=PEM), config_files=[])
    assert state.tls == "pem"


def test_cfg_6_ca_bundle_file_is_private_and_removed() -> None:
    bundle = CaBundle(PEM)
    path = Path(bundle.path)
    assert path.read_text() == PEM + "\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    bundle.cleanup()
    assert not path.parent.exists()


def test_scope_4_project_override_drops_competing_selectors() -> None:
    base = {
        **BASE_CONFIG,
        "auth": {
            **BASE_CONFIG["auth"],
            "project_name": "demo",
            "project_domain_id": "default",
            "tenant_name": "t",
        },
    }
    config = project_config(base, PROJECT_B, Settings(api_timeout=7), "/tmp/ca.pem")
    assert config["auth"]["project_id"] == PROJECT_B
    for key in ("project_name", "project_domain_id", "tenant_name"):
        assert key not in config["auth"]
    assert config["api_timeout"] == 7
    assert (config["connect_retries"], config["status_code_retries"]) == (0, 0)
    assert (config["cacert"], config["verify"]) == ("/tmp/ca.pem", True)
    assert base["auth"]["project_name"] == "demo"


def test_scope_4_no_override_keeps_configured_project() -> None:
    config = project_config(BASE_CONFIG, None, Settings(), None)
    assert config["auth"] == BASE_CONFIG["auth"]
    assert "cacert" not in config


def test_scope_1_sessions_are_per_project_and_cached() -> None:
    fake = FakeCloud()
    cloud = Cloud(
        Settings(project_ids=(PROJECT_A, PROJECT_B)),
        CONFIGURED,
        BASE_CONFIG,
        fake.factory,
    )
    for project in (PROJECT_A, PROJECT_B, PROJECT_A, None):
        cloud.connection(project)
    assert [c["auth"]["project_id"] for c in fake.configs] == [PROJECT_A, PROJECT_B]


def test_scope_1_wrong_token_scope_is_refused() -> None:
    fake = FakeCloud(project_override=PROJECT_B)
    cloud = Cloud(
        Settings(project_ids=(PROJECT_A,)), CONFIGURED, BASE_CONFIG, fake.factory
    )
    with pytest.raises(ToolFailure) as caught:
        cloud.connection(PROJECT_A)
    assert caught.value.category == "project_not_allowed"


def test_scope_3_configured_project_by_name_resolves_after_auth() -> None:
    fake = FakeCloud(project_override=PROJECT_B)
    state = CONFIGURED.__class__(configured=True, configured_project_id=None)
    cloud = Cloud(Settings(), state, BASE_CONFIG, fake.factory)
    assert cloud.connection(None)[0] == PROJECT_B
    with pytest.raises(ToolFailure):
        cloud.connection(PROJECT_B)


def test_scope_4_real_sdk_connection_uses_explicit_config(
    clean_env: pytest.MonkeyPatch,
) -> None:
    """Building a Connection does not authenticate; it must keep our settings."""
    clean_env.setenv("OS_PROJECT_NAME", "from-environment")
    config = project_config(BASE_CONFIG, PROJECT_B, Settings(api_timeout=9), None)
    conn = sdk_connection(config)
    region = conn.config
    assert region.config["auth"]["project_id"] == PROJECT_B
    assert "project_name" not in region.config["auth"]
    assert region.config["api_timeout"] == 9
    assert region.get_connect_retries("compute") == 0
    assert region.get_status_code_retries("compute") == 0


def test_cfg_6_ca_bundle_falls_back_when_tmp_is_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tempfile

    real = tempfile.mkdtemp
    parents: list[str | None] = []

    def mkdtemp(prefix: str, dir: str | None = None) -> str:
        parents.append(dir)
        if dir is None:
            raise OSError("read-only file system")
        return real(prefix=prefix)

    monkeypatch.setattr(tempfile, "mkdtemp", mkdtemp)
    bundle = CaBundle(PEM)
    assert parents == [None, "/dev/shm"]
    bundle.cleanup()


def test_cfg_6_ca_bundle_without_writable_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tempfile

    def mkdtemp(prefix: str, dir: str | None = None) -> str:
        raise OSError("read-only file system")

    monkeypatch.setattr(tempfile, "mkdtemp", mkdtemp)
    with pytest.raises(ConfigError, match="OPENSTACK_MCP_CACERT_PEM"):
        CaBundle(PEM)
