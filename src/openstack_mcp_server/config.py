"""Server settings from ``OPENSTACK_MCP_*`` environment variables (SPEC CFG)."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

Mode = Literal["readonly", "admin"]
Transport = Literal["stdio", "streamable-http"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

MAX_PROJECTS = 100
LIMIT_CEILING = 1000
RESPONSE_BYTES_RANGE = (4096, 8 * 1024 * 1024)
API_TIMEOUT_RANGE = (1, 120)

_TRUE = {"true", "1", "yes"}
_FALSE = {"false", "0", "no"}
_PROJECT_ID = re.compile(
    r"[0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class ConfigError(ValueError):
    """Invalid server setting. The message names the variable, never its value."""

    def __init__(self, variable: str, rule: str) -> None:
        super().__init__(f"{variable}: {rule}")
        self.variable = variable


@dataclass(frozen=True)
class Settings:
    mode: Mode = "readonly"
    enable_write_tools: bool = False
    project_ids: tuple[str, ...] = ()
    default_limit: int = 50
    max_limit: int = 100
    max_response_bytes: int = 524288
    api_timeout: int = 10
    cacert_pem: str | None = field(default=None, repr=False)
    allow_insecure: bool = False
    enable_prompts: bool = True
    enable_resources: bool = True
    transport: Transport = "stdio"
    http_host: str = "127.0.0.1"
    http_port: int = 8000
    http_allow_remote: bool = False
    log_level: LogLevel = "WARNING"

    @property
    def write_tools_registered(self) -> bool:
        return self.mode == "admin" and self.enable_write_tools

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        def raw(name: str) -> str | None:
            value = env.get(f"OPENSTACK_MCP_{name}")
            return None if value is None or value.strip() == "" else value.strip()

        def boolean(name: str, default: bool) -> bool:
            value = raw(name)
            if value is None:
                return default
            if value.lower() in _TRUE:
                return True
            if value.lower() in _FALSE:
                return False
            raise ConfigError(f"OPENSTACK_MCP_{name}", "must be true or false")

        def integer(name: str, default: int, low: int, high: int) -> int:
            value = raw(name)
            if value is None:
                return default
            if not re.fullmatch(r"\d+", value) or not low <= int(value) <= high:
                raise ConfigError(
                    f"OPENSTACK_MCP_{name}", f"must be an integer from {low} to {high}"
                )
            return int(value)

        def choice(name: str, default: str, allowed: tuple[str, ...]) -> str:
            value = raw(name)
            if value is None:
                return default
            if value not in allowed:
                raise ConfigError(
                    f"OPENSTACK_MCP_{name}", "must be one of " + ", ".join(allowed)
                )
            return value

        mode = choice("MODE", "readonly", ("readonly", "admin"))
        enable_write_tools = boolean("ENABLE_WRITE_TOOLS", False)
        if enable_write_tools and mode != "admin":
            raise ConfigError(
                "OPENSTACK_MCP_ENABLE_WRITE_TOOLS",
                "true requires OPENSTACK_MCP_MODE=admin",
            )

        max_limit = integer("MAX_LIMIT", 100, 1, LIMIT_CEILING)
        default_limit = integer("DEFAULT_LIMIT", min(50, max_limit), 1, LIMIT_CEILING)
        if default_limit > max_limit:
            raise ConfigError(
                "OPENSTACK_MCP_DEFAULT_LIMIT",
                "must not exceed OPENSTACK_MCP_MAX_LIMIT",
            )

        cacert_pem = env.get("OPENSTACK_MCP_CACERT_PEM") or None
        if cacert_pem is not None and "-----BEGIN CERTIFICATE-----" not in cacert_pem:
            raise ConfigError(
                "OPENSTACK_MCP_CACERT_PEM", "must contain a PEM certificate"
            )

        http_host = raw("HTTP_HOST") or "127.0.0.1"
        http_allow_remote = boolean("HTTP_ALLOW_REMOTE", False)
        transport = choice("TRANSPORT", "stdio", ("stdio", "streamable-http"))
        if (
            transport == "streamable-http"
            and http_host not in _LOOPBACK
            and not http_allow_remote
        ):
            raise ConfigError(
                "OPENSTACK_MCP_HTTP_HOST",
                "non-loopback address requires OPENSTACK_MCP_HTTP_ALLOW_REMOTE=true",
            )

        return cls(
            mode=mode,  # type: ignore[arg-type]
            enable_write_tools=enable_write_tools,
            project_ids=_project_ids(raw("PROJECT_IDS")),
            default_limit=default_limit,
            max_limit=max_limit,
            max_response_bytes=integer(
                "MAX_RESPONSE_BYTES", 524288, *RESPONSE_BYTES_RANGE
            ),
            api_timeout=integer("API_TIMEOUT", 10, *API_TIMEOUT_RANGE),
            cacert_pem=cacert_pem,
            allow_insecure=boolean("ALLOW_INSECURE", False),
            enable_prompts=boolean("ENABLE_PROMPTS", True),
            enable_resources=boolean("ENABLE_RESOURCES", True),
            transport=transport,  # type: ignore[arg-type]
            http_host=http_host,
            http_port=integer("HTTP_PORT", 8000, 1, 65535),
            http_allow_remote=http_allow_remote,
            log_level=choice(  # type: ignore[arg-type]
                "LOG_LEVEL",
                "WARNING",
                ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
            ),
        )


def _project_ids(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    variable = "OPENSTACK_MCP_PROJECT_IDS"
    entries = [entry.strip() for entry in value.split(",")]
    if any(not entry for entry in entries):
        raise ConfigError(variable, "must not contain empty entries")
    if len(entries) > MAX_PROJECTS:
        raise ConfigError(variable, f"must list at most {MAX_PROJECTS} projects")
    if any(not _PROJECT_ID.fullmatch(entry) for entry in entries):
        raise ConfigError(variable, "entries must be 32-character hex IDs or UUIDs")
    if len(set(entries)) != len(entries):
        raise ConfigError(variable, "must not contain duplicates")
    return tuple(entries)
