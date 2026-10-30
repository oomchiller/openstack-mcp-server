"""Fakes and an in-memory MCP client. No test contacts a cloud."""

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import anyio
import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult

from openstack_mcp_server.cloud import Cloud, CloudState
from openstack_mcp_server.config import Settings
from openstack_mcp_server.server import build_server

PROJECT_A = "a" * 32
PROJECT_B = "b" * 32
SECRET = "synthetic-secret-value"


@dataclass
class Call:
    service: str
    method: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


@dataclass
class FakeCloud:
    """Records every SDK call and connection configuration."""

    responses: dict[tuple[str, str], Any] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)
    configs: list[dict[str, Any]] = field(default_factory=list)
    consumed: list[int] = field(default_factory=list)
    project_override: str | None = None

    def factory(self, config: dict[str, Any]) -> "FakeConnection":
        self.configs.append(config)
        project = self.project_override or config["auth"].get("project_id")
        return FakeConnection(self, project or PROJECT_A)

    def respond(self, service: str, method: str, value: Any) -> None:
        self.responses[(service, method)] = value

    def methods(self) -> list[tuple[str, str]]:
        return [(call.service, call.method) for call in self.calls]


class FakeService:
    def __init__(self, cloud: FakeCloud, name: str) -> None:
        self._cloud = cloud
        self._name = name

    def __getattr__(self, method: str) -> Callable[..., Any]:
        def invoke(*args: Any, **kwargs: Any) -> Any:
            cloud = self._cloud
            cloud.calls.append(Call(self._name, method, args, kwargs))
            value = cloud.responses.get((self._name, method), [])
            if isinstance(value, BaseException):
                raise value
            if callable(value):
                value = value(*args, **kwargs)
            if isinstance(value, list):
                return _counting(value, cloud.consumed)
            return value

        return invoke


def _counting(items: list[Any], consumed: list[int]) -> Iterator[Any]:
    consumed.append(0)
    for item in items:
        consumed[-1] += 1
        yield item


class FakeConnection:
    def __init__(self, cloud: FakeCloud, project_id: str) -> None:
        self.current_project_id = project_id
        for service in ("compute", "image", "block_storage", "network", "identity"):
            setattr(self, service, FakeService(cloud, service))


CONFIGURED = CloudState(
    configured=True,
    source="environment",
    region_name="RegionOne",
    interface="public",
    configured_project_id=PROJECT_A,
)
BASE_CONFIG: dict[str, Any] = {
    "auth_type": "password",
    "auth": {
        "auth_url": "https://keystone.example/v3",
        "username": "reader",
        "password": SECRET,
        "user_domain_id": "default",
        "project_id": PROJECT_A,
    },
    "region_name": "RegionOne",
}


def make_server(
    fake: FakeCloud | None = None,
    settings: Settings | None = None,
    state: CloudState = CONFIGURED,
    base: dict[str, Any] | None = BASE_CONFIG,
) -> FastMCP:
    fake = fake or FakeCloud()
    settings = settings or Settings()
    cloud = Cloud(settings, state, base if state.configured else None, fake.factory)
    return build_server(cloud)


def call(
    server: FastMCP, tool: str, arguments: dict[str, Any] | None = None
) -> CallToolResult:
    async def go() -> CallToolResult:
        async with create_connected_server_and_client_session(server) as session:
            return await session.call_tool(tool, arguments or {})

    return anyio.run(go)


def session_run(server: FastMCP, action: Callable[[Any], Any]) -> Any:
    async def go() -> Any:
        async with create_connected_server_and_client_session(server) as session:
            return await action(session)

    return anyio.run(go)


def text(result: CallToolResult) -> str:
    return " ".join(getattr(block, "text", "") for block in result.content)


def ok(result: CallToolResult) -> dict[str, Any]:
    assert not result.isError, text(result)
    assert result.structuredContent is not None
    return result.structuredContent


def failed(result: CallToolResult, category: str) -> str:
    assert result.isError, json.dumps(result.structuredContent)
    message = text(result)
    assert f"[{category}]" in message, message
    return message


@pytest.fixture
def fake() -> FakeCloud:
    return FakeCloud()
