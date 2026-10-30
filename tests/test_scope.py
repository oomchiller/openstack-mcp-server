"""SPEC SCOPE-2 … SCOPE-5, CFG-3: which project a call reaches."""

from openstack_mcp_server.cloud import CloudState
from openstack_mcp_server.config import Settings

from .conftest import PROJECT_A, PROJECT_B, FakeCloud, call, failed, make_server, ok

PROJECT_C = "c" * 32
TWO = Settings(project_ids=(PROJECT_A, PROJECT_B))


def test_scope_2_allowlisted_projects_get_their_own_session(fake: FakeCloud) -> None:
    fake.respond("compute", "servers", [{"id": "1", "name": "vm"}])
    server = make_server(fake, TWO)
    for project in (PROJECT_A, PROJECT_B):
        assert (
            ok(call(server, "list_servers", {"project_id": project}))["project_id"]
            == project
        )
    assert [c["auth"]["project_id"] for c in fake.configs] == [PROJECT_A, PROJECT_B]


def test_scope_2_default_is_first_allowlisted_project(fake: FakeCloud) -> None:
    assert ok(call(make_server(fake, TWO), "list_flavors"))["project_id"] == PROJECT_A


def test_scope_2_outside_allowlist_fails_before_authentication(fake: FakeCloud) -> None:
    failed(
        call(make_server(fake, TWO), "list_servers", {"project_id": PROJECT_C}),
        "project_not_allowed",
    )
    assert fake.configs == [] and fake.calls == []


def test_scope_3_without_allowlist_only_configured_project(fake: FakeCloud) -> None:
    server = make_server(fake)
    assert (
        ok(call(server, "list_servers", {"project_id": PROJECT_A}))["project_id"]
        == PROJECT_A
    )
    failed(
        call(server, "list_servers", {"project_id": PROJECT_B}), "project_not_allowed"
    )
    assert len(fake.configs) == 1


def test_cfg_3_unconfigured_cloud_tools_fail(fake: FakeCloud) -> None:
    server = make_server(
        fake, state=CloudState(configured=False, reason="missing_credentials")
    )
    message = failed(call(server, "list_servers"), "not_configured")
    assert "retrying will not help" in message
    scope = ok(call(server, "get_scope"))
    assert (scope["configured"], scope["reason"]) == (False, "missing_credentials")
    assert fake.configs == []


def test_scope_5_network_lists_are_project_filtered(fake: FakeCloud) -> None:
    server = make_server(fake, TWO)
    for tool in (
        "list_networks",
        "list_subnets",
        "list_ports",
        "list_floating_ips",
        "list_routers",
        "list_security_groups",
    ):
        call(server, tool, {"project_id": PROJECT_B})
    assert all(c.kwargs["project_id"] == PROJECT_B for c in fake.calls)


def test_scope_5_shared_networks_are_not_owner_filtered(fake: FakeCloud) -> None:
    call(make_server(fake), "list_networks", {"shared": True})
    (listing,) = fake.calls
    assert listing.kwargs["is_shared"] is True
    assert "project_id" not in listing.kwargs


def test_ro_4_no_tool_forwards_all_projects(fake: FakeCloud) -> None:
    server = make_server(fake)
    for tool in ("list_servers", "list_volumes", "list_images", "list_ports"):
        call(server, tool)
    for listing in fake.calls:
        assert not {"all_projects", "all_tenants"} & set(listing.kwargs)
