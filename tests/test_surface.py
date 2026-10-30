"""SPEC RO, MCP-1 … MCP-3, MCP-8, TOOL-1, TOOL-2: what a client can see and call."""

import re
from typing import Any

import pytest

from openstack_mcp_server.config import Settings

from .conftest import FakeCloud, call, make_server, session_run

READ_TOOLS = {
    "get_scope",
    "list_servers",
    "get_server",
    "list_flavors",
    "list_images",
    "get_image",
    "list_volumes",
    "get_volume",
    "list_volume_attachments",
    "get_volume_attachment",
    "list_networks",
    "get_network",
    "list_subnets",
    "get_subnet",
    "list_ports",
    "get_port",
    "list_floating_ips",
    "list_routers",
    "get_router",
    "list_router_interfaces",
    "list_security_groups",
    "get_security_group",
    "list_regions",
    "list_domains",
    "list_projects",
    "list_services",
    "list_endpoints",
    "list_hypervisors",
    "list_compute_services",
    "list_aggregates",
    "list_network_agents",
    "list_volume_services",
}
WRITE_TOOLS = {
    "create_server",
    "update_server",
    "delete_server",
    "server_action",
    "attach_volume",
    "detach_volume",
    "create_volume",
    "delete_volume",
    "extend_volume",
    "create_image",
    "delete_image",
    "create_network",
    "update_network",
    "delete_network",
    "create_subnet",
    "update_subnet",
    "delete_subnet",
    "create_port",
    "update_port",
    "delete_port",
    "create_floating_ip",
    "update_floating_ip",
    "delete_floating_ip",
    "create_router",
    "update_router",
    "delete_router",
    "add_router_interface",
    "remove_router_interface",
    "create_security_group",
    "update_security_group",
    "delete_security_group",
}
DESTRUCTIVE = {
    "delete_server",
    "server_action",
    "detach_volume",
    "delete_volume",
    "extend_volume",
    "delete_image",
    "delete_network",
    "delete_subnet",
    "delete_port",
    "delete_floating_ip",
    "delete_router",
    "remove_router_interface",
    "delete_security_group",
}
REMOVED = {
    "get_cloud_config",
    "get_cloud_names",
    "get_cloud_name",
    "set_cloud_name",
    "create_region",
    "delete_domain",
    "create_project",
    "set_port_binding",
    "create_floating_ips_bulk",
    "assign_first_available_floating_ip",
}
ADMIN = Settings(mode="admin", enable_write_tools=True)


def tools(settings: Settings) -> dict[str, Any]:
    async def listing(session: Any) -> Any:
        return (await session.list_tools()).tools

    return {
        tool.name: tool for tool in session_run(make_server(settings=settings), listing)
    }


def test_ro_1_default_lists_read_tools_only() -> None:
    assert set(tools(Settings())) == READ_TOOLS


def test_ro_2_admin_alone_registers_no_write_tool() -> None:
    assert set(tools(Settings(mode="admin"))) == READ_TOOLS


def test_ro_2_both_gates_register_write_tools() -> None:
    assert set(tools(ADMIN)) == READ_TOOLS | WRITE_TOOLS


@pytest.mark.parametrize("name", sorted(WRITE_TOOLS | REMOVED))
def test_ro_1_unregistered_tools_cannot_be_called(fake: FakeCloud, name: str) -> None:
    result = call(make_server(fake), name, {"server_id": "x", "volume_id": "x"})
    assert result.isError
    assert fake.calls == [] and fake.configs == []


def test_ro_5_cloud_config_tools_absent_in_every_mode() -> None:
    assert not REMOVED & set(tools(ADMIN))


def test_mcp_1_read_annotations() -> None:
    for name, tool in tools(Settings()).items():
        hints = tool.annotations
        assert hints.readOnlyHint is True, name
        assert hints.destructiveHint is False, name
        assert hints.idempotentHint is True, name
        assert hints.openWorldHint is (name != "get_scope"), name
        assert tool.title, name


def test_mcp_2_write_annotations() -> None:
    for name, tool in tools(ADMIN).items():
        if name in READ_TOOLS:
            continue
        hints = tool.annotations
        assert hints.readOnlyHint is False, name
        assert hints.destructiveHint is (name in DESTRUCTIVE), name
        assert hints.idempotentHint is name.startswith(
            ("update_", "delete_", "extend_")
        ), name


def test_mcp_3_descriptions_and_schemas() -> None:
    for name, tool in tools(ADMIN).items():
        assert tool.description and len(tool.description) <= 500, name
        sentences = re.findall(r"[.!?](?:\s|$)", tool.description)
        assert len(sentences) <= 3, name
        assert tool.inputSchema["additionalProperties"] is False, name
        assert tool.outputSchema is not None, name
        if name.startswith("list_"):
            assert {"items", "complete", "next_marker"} <= set(
                tool.outputSchema["properties"]
            ), name


def test_tool_1_names_follow_convention() -> None:
    for name in READ_TOOLS:
        assert name.startswith(("list_", "get_")), name


def test_tool_4_enums_and_bounds_in_schema() -> None:
    listed = tools(Settings(max_limit=40, default_limit=10))
    servers = listed["list_servers"].inputSchema["properties"]
    assert servers["limit"]["maximum"] == 40
    assert servers["limit"]["minimum"] == 1
    assert servers["limit"]["default"] == 10
    assert "SHUTOFF" in servers["status"]["anyOf"][0]["enum"]
    subnets = listed["list_subnets"].inputSchema["properties"]
    assert subnets["ip_version"]["anyOf"][0]["enum"] == [4, 6]


def test_tool_4_allowlist_is_enum() -> None:
    listed = tools(Settings(project_ids=("a" * 32, "b" * 32)))
    project = listed["list_servers"].inputSchema["properties"]["project_id"]
    assert project["enum"] == ["a" * 32, "b" * 32, None]


@pytest.mark.parametrize(
    ("prompts", "resources"),
    [(True, True), (False, True), (True, False), (False, False)],
)
def test_mcp_8_switches_keep_tools_identical(prompts: bool, resources: bool) -> None:
    settings = Settings(enable_prompts=prompts, enable_resources=resources)

    async def surface(session: Any) -> Any:
        return (
            (await session.list_tools()).tools,
            (await session.list_prompts()).prompts,
            (await session.list_resources()).resources,
        )

    listed, prompt_list, resource_list = session_run(
        make_server(settings=settings), surface
    )
    baseline = tools(Settings())
    assert [t.model_dump() for t in listed] == [
        t.model_dump() for t in baseline.values()
    ]
    assert len(prompt_list) == (1 if prompts else 0)
    assert len(resource_list) == (1 if resources else 0)


def test_ro_4_unknown_arguments_are_rejected_before_dispatch(fake: FakeCloud) -> None:
    server = make_server(fake)
    for extra in (
        {"all_projects": True},
        {"auth_url": "http://attacker.invalid"},
        {"password": "injected"},
        {"cloud": "other"},
        {"method": "delete_server"},
        {"path": "/v2.1/servers"},
    ):
        failed_result = call(server, "list_servers", extra)
        assert failed_result.isError
        assert "Extra inputs are not permitted" in failed_result.content[0].text  # type: ignore[union-attr]
    assert fake.calls == [] and fake.configs == []


def test_ro_3_read_tools_only_reach_list_and_get(fake: FakeCloud) -> None:
    server = make_server(fake)
    arguments = {
        "server_id": "x",
        "image_id": "x",
        "volume_id": "x",
        "attachment_id": "x",
        "network_id": "x",
        "subnet_id": "x",
        "port_id": "x",
        "router_id": "x",
        "security_group_id": "x",
    }
    for name in sorted(READ_TOOLS):
        schema = tools_cache()[name].inputSchema["properties"]
        call(server, name, {k: v for k, v in arguments.items() if k in schema})
    reads = {
        "servers",
        "flavors",
        "images",
        "volumes",
        "attachments",
        "networks",
        "subnets",
        "ports",
        "ips",
        "routers",
        "security_groups",
        "regions",
        "domains",
        "projects",
        "services",
        "endpoints",
        "hypervisors",
        "aggregates",
        "agents",
    }
    for service, method in fake.methods():
        assert method in reads or method.startswith("get_"), (service, method)
    assert len(fake.calls) == len(READ_TOOLS) - 1


_TOOLS: dict[str, Any] = {}


def tools_cache() -> dict[str, Any]:
    if not _TOOLS:
        _TOOLS.update(tools(Settings()))
    return _TOOLS


def test_err_unknown_tool_is_error_without_cloud_access(fake: FakeCloud) -> None:
    result = call(make_server(fake), "drop_everything")
    assert result.isError
    assert fake.configs == []
