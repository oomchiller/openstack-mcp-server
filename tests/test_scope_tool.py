"""SPEC TOOL-3, MCP-4, MCP-6, MCP-7: scope document, instructions, prompt, resource."""

import json
from typing import Any

from openstack_mcp_server import __version__
from openstack_mcp_server.cloud import CloudState
from openstack_mcp_server.config import Settings
from openstack_mcp_server.server import INSTRUCTIONS

from .conftest import (
    PROJECT_A,
    PROJECT_B,
    FakeCloud,
    call,
    make_server,
    ok,
    session_run,
)


def test_tool_3_scope_document(fake: FakeCloud) -> None:
    settings = Settings(
        project_ids=(PROJECT_B, PROJECT_A), max_limit=80, default_limit=20
    )
    data = ok(call(make_server(fake, settings), "get_scope"))
    assert data == {
        "server_version": __version__,
        "mode": "readonly",
        "write_tools_registered": False,
        "configured": True,
        "reason": None,
        "credential_source": "environment",
        "region_name": "RegionOne",
        "interface": "public",
        "tls": "system",
        "project_ids": [PROJECT_B, PROJECT_A],
        "default_project_id": PROJECT_B,
        "limits": {
            "default_limit": 20,
            "max_limit": 80,
            "max_response_bytes": 524288,
            "api_timeout_seconds": 10,
        },
        "cloud_access_verified": False,
    }
    assert fake.configs == []


def test_tool_3_scope_without_allowlist_uses_configured_project(
    fake: FakeCloud,
) -> None:
    data = ok(call(make_server(fake), "get_scope"))
    assert (data["project_ids"], data["default_project_id"]) == ([], PROJECT_A)


def test_tool_3_scope_admin_mode(fake: FakeCloud) -> None:
    settings = Settings(mode="admin", enable_write_tools=True)
    data = ok(call(make_server(fake, settings), "get_scope"))
    assert (data["mode"], data["write_tools_registered"]) == ("admin", True)


def test_mcp_4_instructions_on_initialize() -> None:
    async def initialize(session: Any) -> Any:
        return None

    server = make_server()
    assert server.instructions == INSTRUCTIONS
    for phrase in ("get_scope", "next_marker", "[forbidden]", "Read-only"):
        assert phrase in INSTRUCTIONS
    session_run(server, initialize)


def test_mcp_7_scope_resource_matches_tool(fake: FakeCloud) -> None:
    server = make_server(
        fake, state=CloudState(configured=False, reason="insecure_transport")
    )

    async def read(session: Any) -> Any:
        return await session.read_resource("openstack://scope")

    contents = session_run(server, read).contents
    document = json.loads(contents[0].text)
    assert document["reason"] == "insecure_transport"
    assert document == ok(call(server, "get_scope"))


def test_mcp_6_prompt_uses_new_tool_names() -> None:
    async def get(session: Any) -> Any:
        return await session.get_prompt(
            "find_servers_by_security_group", {"security_group_name": "web"}
        )

    prompt = session_run(make_server(), get)
    body = prompt.messages[0].content.text
    assert "list_servers" in body and "next_marker" in body and "'web'" in body
    assert "get_servers" not in body
