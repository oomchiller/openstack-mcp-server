"""SPEC TOOL-2, RO-2: write tools dispatch exactly one mutating SDK call each."""

from types import SimpleNamespace
from typing import Any

import pytest

from openstack_mcp_server.config import Settings

from ..conftest import PROJECT_A, PROJECT_B, FakeCloud, call, failed, make_server, ok

ADMIN = Settings(
    mode="admin", enable_write_tools=True, project_ids=(PROJECT_A, PROJECT_B)
)

CASES: list[tuple[str, dict[str, Any], str, str, tuple[Any, ...], dict[str, Any]]] = [
    (
        "update_server",
        {"server_id": "s", "name": "new"},
        "compute",
        "update_server",
        ("s",),
        {"name": "new"},
    ),
    (
        "delete_server",
        {"server_id": "s"},
        "compute",
        "delete_server",
        ("s",),
        {"ignore_missing": False},
    ),
    (
        "server_action",
        {"server_id": "s", "action": "stop"},
        "compute",
        "stop_server",
        ("s",),
        {},
    ),
    (
        "server_action",
        {"server_id": "s", "action": "shelve_offload"},
        "compute",
        "shelve_offload_server",
        ("s",),
        {},
    ),
    (
        "attach_volume",
        {"server_id": "s", "volume_id": "v", "device": "/dev/vdb"},
        "compute",
        "create_volume_attachment",
        ("s",),
        {"volume": "v", "device": "/dev/vdb"},
    ),
    (
        "detach_volume",
        {"server_id": "s", "volume_id": "v"},
        "compute",
        "delete_volume_attachment",
        ("s", "v"),
        {},
    ),
    (
        "create_volume",
        {"name": "data", "size": 10},
        "block_storage",
        "create_volume",
        (),
        {"name": "data", "size": 10},
    ),
    (
        "delete_volume",
        {"volume_id": "v"},
        "block_storage",
        "delete_volume",
        ("v",),
        {"ignore_missing": False},
    ),
    (
        "extend_volume",
        {"volume_id": "v", "new_size": 20},
        "block_storage",
        "extend_volume",
        ("v", 20),
        {},
    ),
    (
        "delete_image",
        {"image_id": "i"},
        "image",
        "delete_image",
        ("i",),
        {"ignore_missing": False},
    ),
    (
        "create_network",
        {"name": "n"},
        "network",
        "create_network",
        (),
        {"name": "n", "is_admin_state_up": True},
    ),
    (
        "update_network",
        {"network_id": "n", "description": "d"},
        "network",
        "update_network",
        ("n",),
        {"description": "d"},
    ),
    (
        "delete_network",
        {"network_id": "n"},
        "network",
        "delete_network",
        ("n",),
        {"ignore_missing": False},
    ),
    (
        "create_subnet",
        {"network_id": "n", "cidr": "10.0.0.0/24"},
        "network",
        "create_subnet",
        (),
        {
            "network_id": "n",
            "cidr": "10.0.0.0/24",
            "ip_version": 4,
            "is_dhcp_enabled": True,
        },
    ),
    (
        "update_subnet",
        {"subnet_id": "sn", "is_dhcp_enabled": False},
        "network",
        "update_subnet",
        ("sn",),
        {"is_dhcp_enabled": False},
    ),
    (
        "delete_subnet",
        {"subnet_id": "sn"},
        "network",
        "delete_subnet",
        ("sn",),
        {"ignore_missing": False},
    ),
    (
        "create_port",
        {"network_id": "n", "subnet_id": "sn", "ip_address": "10.0.0.9"},
        "network",
        "create_port",
        (),
        {
            "network_id": "n",
            "fixed_ips": [{"subnet_id": "sn", "ip_address": "10.0.0.9"}],
        },
    ),
    (
        "update_port",
        {"port_id": "p", "security_group_ids": ["sg"]},
        "network",
        "update_port",
        ("p",),
        {"security_group_ids": ["sg"]},
    ),
    (
        "delete_port",
        {"port_id": "p"},
        "network",
        "delete_port",
        ("p",),
        {"ignore_missing": False},
    ),
    (
        "create_floating_ip",
        {"floating_network_id": "ext"},
        "network",
        "create_ip",
        (),
        {"floating_network_id": "ext"},
    ),
    (
        "update_floating_ip",
        {"floating_ip_id": "f", "port_id": "p"},
        "network",
        "update_ip",
        ("f",),
        {"port_id": "p"},
    ),
    (
        "update_floating_ip",
        {"floating_ip_id": "f", "disassociate": True},
        "network",
        "update_ip",
        ("f",),
        {"port_id": None},
    ),
    (
        "delete_floating_ip",
        {"floating_ip_id": "f"},
        "network",
        "delete_ip",
        ("f",),
        {"ignore_missing": False},
    ),
    (
        "create_router",
        {"name": "r", "external_network_id": "ext"},
        "network",
        "create_router",
        (),
        {"name": "r", "external_gateway_info": {"network_id": "ext"}},
    ),
    (
        "update_router",
        {"router_id": "r", "clear_gateway": True},
        "network",
        "update_router",
        ("r",),
        {"external_gateway_info": {}},
    ),
    (
        "update_router",
        {"router_id": "r", "external_network_id": "ext2"},
        "network",
        "update_router",
        ("r",),
        {"external_gateway_info": {"network_id": "ext2"}},
    ),
    (
        "delete_router",
        {"router_id": "r"},
        "network",
        "delete_router",
        ("r",),
        {"ignore_missing": False},
    ),
    (
        "add_router_interface",
        {"router_id": "r", "subnet_id": "sn"},
        "network",
        "add_interface_to_router",
        ("r",),
        {"subnet_id": "sn"},
    ),
    (
        "remove_router_interface",
        {"router_id": "r", "port_id": "p"},
        "network",
        "remove_interface_from_router",
        ("r",),
        {"port_id": "p"},
    ),
    (
        "create_security_group",
        {"name": "web"},
        "network",
        "create_security_group",
        (),
        {"name": "web"},
    ),
    (
        "update_security_group",
        {"security_group_id": "sg", "name": "w"},
        "network",
        "update_security_group",
        ("sg",),
        {"name": "w"},
    ),
    (
        "delete_security_group",
        {"security_group_id": "sg"},
        "network",
        "delete_security_group",
        ("sg",),
        {"ignore_missing": False},
    ),
]
RESULT = {"id": "x", "name": "x"}


@pytest.mark.parametrize(
    ("tool", "arguments", "service", "method", "args", "kwargs"),
    CASES,
    ids=[f"{case[0]}-{i}" for i, case in enumerate(CASES)],
)
def test_tool_2_write_dispatch(
    fake: FakeCloud,
    tool: str,
    arguments: dict[str, Any],
    service: str,
    method: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    fake.respond(service, method, RESULT)
    data = ok(
        call(make_server(fake, ADMIN), tool, {**arguments, "project_id": PROJECT_B})
    )
    (mutation,) = fake.calls
    assert (mutation.service, mutation.method) == (service, method)
    assert mutation.args == args
    assert mutation.kwargs == kwargs
    assert fake.configs[0]["auth"]["project_id"] == PROJECT_B
    if "action" in data:
        assert data["project_id"] == PROJECT_B


def test_create_server_reads_back(fake: FakeCloud) -> None:
    fake.respond("compute", "create_server", SimpleNamespace(id="new"))
    fake.respond(
        "compute", "get_server", {"id": "new", "name": "vm", "status": "BUILD"}
    )
    data = ok(
        call(
            make_server(fake, ADMIN),
            "create_server",
            {
                "name": "vm",
                "image_id": "i",
                "flavor_id": "f",
                "network_id": "n",
                "security_groups": ["default"],
            },
        )
    )
    assert data["status"] == "BUILD"
    assert fake.methods() == [("compute", "create_server"), ("compute", "get_server")]
    assert fake.calls[0].kwargs == {
        "name": "vm",
        "image_id": "i",
        "flavor_id": "f",
        "networks": [{"uuid": "n"}],
        "security_groups": [{"name": "default"}],
    }


def test_create_image_imports_from_url(fake: FakeCloud) -> None:
    fake.respond("image", "create_image", SimpleNamespace(id="img"))
    fake.respond("image", "get_image", {"id": "img", "status": "importing"})
    data = ok(
        call(
            make_server(fake, ADMIN),
            "create_image",
            {
                "name": "cirros",
                "disk_format": "qcow2",
                "source_url": "https://download.example/cirros.img",
            },
        )
    )
    assert data["status"] == "importing"
    assert fake.methods() == [
        ("image", "create_image"),
        ("image", "import_image"),
        ("image", "get_image"),
    ]
    assert fake.calls[1].kwargs == {
        "method": "web-download",
        "uri": "https://download.example/cirros.img",
    }


def test_create_image_rejects_non_http_url(fake: FakeCloud) -> None:
    result = call(
        make_server(fake, ADMIN),
        "create_image",
        {"name": "x", "disk_format": "raw", "source_url": "file:///etc/passwd"},
    )
    assert result.isError and fake.calls == []


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("add_router_interface", {"router_id": "r"}),
        (
            "remove_router_interface",
            {"router_id": "r", "subnet_id": "s", "port_id": "p"},
        ),
        (
            "update_floating_ip",
            {"floating_ip_id": "f", "port_id": "p", "disassociate": True},
        ),
        (
            "update_router",
            {"router_id": "r", "external_network_id": "e", "clear_gateway": True},
        ),
    ],
)
def test_contradictory_arguments_fail_before_dispatch(
    fake: FakeCloud, tool: str, arguments: dict[str, Any]
) -> None:
    failed(call(make_server(fake, ADMIN), tool, arguments), "invalid_argument")
    assert fake.calls == []


def test_server_action_rejects_unknown_action(fake: FakeCloud) -> None:
    result = call(
        make_server(fake, ADMIN),
        "server_action",
        {"server_id": "s", "action": "evacuate"},
    )
    assert result.isError and fake.calls == []


def test_write_outside_allowlist_is_refused(fake: FakeCloud) -> None:
    failed(
        call(
            make_server(fake, ADMIN),
            "delete_server",
            {"server_id": "s", "project_id": "c" * 32},
        ),
        "project_not_allowed",
    )
    assert fake.calls == [] and fake.configs == []
