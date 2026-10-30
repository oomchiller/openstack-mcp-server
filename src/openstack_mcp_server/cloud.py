"""Credential resolution, TLS and per-project connections (SPEC CFG, SCOPE)."""

import copy
import os
import shutil
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from keystoneauth1 import exceptions as ks
from openstack import exceptions as sdk
from openstack.config.loader import OpenStackConfig

from .config import Settings
from .errors import ToolFailure

Reason = Literal["missing_credentials", "insecure_transport", "invalid_cloud_config"]
TlsSource = Literal["system", "file", "pem"]
ConnectionFactory = Callable[[dict[str, Any]], Any]

# Selectors that would compete with an overriding project_id (SCOPE-4).
_PROJECT_SELECTORS = (
    "project_name",
    "project_domain_id",
    "project_domain_name",
    "tenant_id",
    "tenant_name",
)


@dataclass(frozen=True)
class CloudState:
    configured: bool
    reason: Reason | None = None
    source: str = "none"
    region_name: str | None = None
    interface: str | None = None
    tls: TlsSource = "system"
    configured_project_id: str | None = None


class CaBundle:
    """PEM text written to a private file for the lifetime of the process (CFG-6)."""

    def __init__(self, pem: str) -> None:
        self._directory = tempfile.mkdtemp(prefix="openstack-mcp-")
        self.path = os.path.join(self._directory, "ca.pem")
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(pem if pem.endswith("\n") else pem + "\n")

    def cleanup(self) -> None:
        shutil.rmtree(self._directory, ignore_errors=True)


def load_cloud(
    settings: Settings,
    config_files: Sequence[str] | None = None,
) -> tuple[CloudState, dict[str, Any] | None]:
    """Resolve credentials without network access.

    Returns the public state and the private base configuration, or ``None``
    when the cloud is not usable.
    """
    try:
        loader = OpenStackConfig(
            config_files=list(config_files) if config_files is not None else None,
            load_envvars=True,
        )
        # Validation normalizes auth options and checks a plugin can be built.
        region = loader.get_one()
    except (ks.MissingRequiredOptions, ks.MissingAuthPlugin):
        return CloudState(configured=False, reason="missing_credentials"), None
    except (sdk.ConfigException, ks.AuthPluginException, ValueError, OSError):
        return CloudState(configured=False, reason="invalid_cloud_config"), None

    config: dict[str, Any] = copy.deepcopy(dict(region.config))
    config.pop("auth_plugin", None)
    auth = dict(config.get("auth") or {})
    source = "environment" if region.name == "envvars" else f"clouds.yaml:{region.name}"
    tls: TlsSource = "system"
    if settings.cacert_pem:
        tls = "pem"
    elif config.get("cacert"):
        tls = "file"
    state = CloudState(
        configured=True,
        source=source,
        region_name=region.region_name or None,
        interface=config.get("interface"),
        tls=tls,
        configured_project_id=auth.get("project_id") or auth.get("tenant_id"),
    )

    insecure = region.get_requests_verify_args()[0] is False
    plain_http = str(auth.get("auth_url", "")).lower().startswith("http://")
    if (insecure or plain_http) and not settings.allow_insecure:
        return (
            CloudState(
                configured=False,
                reason="insecure_transport",
                source=source,
                region_name=state.region_name,
                interface=state.interface,
                tls=tls,
            ),
            None,
        )
    return state, config


def project_config(
    base: dict[str, Any],
    project_id: str | None,
    settings: Settings,
    cacert_path: str | None,
) -> dict[str, Any]:
    """Connection configuration for one project with fixed timeouts."""
    config = copy.deepcopy(base)
    auth = dict(config.get("auth") or {})
    if project_id is not None:
        for key in _PROJECT_SELECTORS:
            auth.pop(key, None)
        auth["project_id"] = project_id
    config["auth"] = auth
    config["api_timeout"] = settings.api_timeout
    config["connect_retries"] = 0
    config["status_code_retries"] = 0
    if cacert_path is not None:
        config["cacert"] = cacert_path
        config["verify"] = True
    return config


def sdk_connection(config: dict[str, Any]) -> Any:
    """Build a Connection from an explicit configuration, ignoring OS_* and YAML."""
    import openstack.connection

    region = OpenStackConfig(load_yaml_config=False, load_envvars=False).get_one(
        **config
    )
    return openstack.connection.Connection(config=region)


class Cloud:
    """Per-project connections, created on first use and cached (SCOPE-1)."""

    def __init__(
        self,
        settings: Settings,
        state: CloudState,
        base_config: dict[str, Any] | None,
        factory: ConnectionFactory = sdk_connection,
        cacert_path: str | None = None,
    ) -> None:
        self.settings = settings
        self.state = state
        self._base = base_config
        self._factory = factory
        self._cacert_path = cacert_path
        self._connections: dict[str | None, Any] = {}
        self._lock = threading.Lock()

    @property
    def default_project_id(self) -> str | None:
        if self.settings.project_ids:
            return self.settings.project_ids[0]
        return self.state.configured_project_id

    def resolve_project(self, requested: str | None) -> str | None:
        """Project for a call, checked before any authentication (SCOPE-2, -3).

        ``None`` means the configured project, whose ID is only known after
        authentication.
        """
        if not self.state.configured or self._base is None:
            raise ToolFailure("not_configured")
        allowlist = self.settings.project_ids
        if allowlist:
            if requested is None:
                return allowlist[0]
            if requested in allowlist:
                return requested
            raise ToolFailure("project_not_allowed")
        if requested is None or requested == self.state.configured_project_id:
            return None
        raise ToolFailure("project_not_allowed")

    def connection(self, requested: str | None) -> tuple[str, Any]:
        """Return ``(project_id, connection)`` for the requested project."""
        project = self.resolve_project(requested)
        base = self._base
        if base is None:  # pragma: no cover - resolve_project checked it
            raise ToolFailure("not_configured")
        with self._lock:
            conn = self._connections.get(project)
            if conn is None:
                conn = self._factory(
                    project_config(base, project, self.settings, self._cacert_path)
                )
                self._connections[project] = conn
        actual = conn.current_project_id
        # Application credentials cannot be rescoped; never answer for the
        # wrong project.
        if project is not None and actual != project:
            raise ToolFailure("project_not_allowed")
        if not isinstance(actual, str) or not actual:
            raise ToolFailure("auth_failed")
        return actual, conn
