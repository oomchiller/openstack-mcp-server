"""SPEC TOOL-4, OUT-5, OUT-6 per service: SDK dispatch and model conversion.

Cases are adapted from upstream tests at upstream-eba3e6f (tests/tools/).
"""

from typing import Any

import pytest

from openstack_mcp_server.config import Settings

from ..conftest import PROJECT_A, FakeCloud, call, make_server, ok

SERVER = {
    "id": "srv-1",
    "name": "web-1",
    "status": "ACTIVE",
    "flavor": {"original_name": "m1.small", "vcpus": 1, "ram": 2048, "disk": 20},
    "image": {"id": "img-1"},
    "addresses": {
        "private": [{"addr": "10.0.0.5", "version": 4, "OS-EXT-IPS:type": "fixed"}]
    },
    "security_groups": [{"name": "default"}],
    "attached_volumes": [{"id": "vol-1", "delete_on_termination": False}],
    "adminPass": "must-not-export",
}

CASES: list[tuple[str, dict[str, Any], str, str, Any, dict[str, Any]]] = [
    # tool, arguments, service, method, response, expected subset of first item
    (
        "list_servers",
        {"status": "ACTIVE"},
        "compute",
        "servers",
        [SERVER],
        {
            "flavor": {"name": "m1.small", "vcpus": 1, "ram": 2048, "disk": 20},
            "image": {"id": "img-1"},
            "addresses": {
                "private": [{"addr": "10.0.0.5", "version": 4, "type": "fixed"}]
            },
        },
    ),
    (
        "list_servers",
        {},
        "compute",
        "servers",
        [{**SERVER, "image": ""}],
        {"image": None},
    ),
    (
        "list_flavors",
        {},
        "compute",
        "flavors",
        [
            {
                "id": "1",
                "name": "m1.tiny",
                "vcpus": 1,
                "ram": 512,
                "disk": 1,
                "is_public": True,
            }
        ],
        {"name": "m1.tiny", "is_public": True},
    ),
    (
        "list_images",
        {"visibility": "public", "status": "active"},
        "image",
        "images",
        [
            {
                "id": "img",
                "name": "cirros",
                "size": "",
                "is_protected": False,
                "tags": ["x"],
                "owner_specified.openstack.object": "images/cirros",
            }
        ],
        {"size": None, "tags": ["x"]},
    ),
    (
        "list_volumes",
        {"status": "in-use"},
        "block_storage",
        "volumes",
        [
            {
                "id": "v",
                "name": "data",
                "status": "in-use",
                "size": 10,
                "attachments": [
                    {"server_id": "s", "device": "/dev/vdb", "attachment_id": "a"}
                ],
            }
        ],
        {
            "attachments": [
                {"server_id": "s", "device": "/dev/vdb", "attachment_id": "a"}
            ]
        },
    ),
    (
        "list_volume_attachments",
        {"volume_id": "v"},
        "block_storage",
        "attachments",
        [
            {
                "id": "a",
                "instance": "s",
                "volume_id": "v",
                "status": "attached",
                "connection_info": {"auth_password": "must-not-export"},
                "connector": {"initiator": "iqn"},
            }
        ],
        {"instance": "s", "status": "attached"},
    ),
    (
        "list_networks",
        {"status": "ACTIVE"},
        "network",
        "networks",
        [
            {
                "id": "n",
                "name": "net",
                "status": "ACTIVE",
                "is_shared": False,
                "mtu": 1450,
            }
        ],
        {"mtu": 1450},
    ),
    (
        "list_subnets",
        {"ip_version": 4, "network_id": "n"},
        "network",
        "subnets",
        [
            {
                "id": "sn",
                "cidr": "10.0.0.0/24",
                "ip_version": 4,
                "allocation_pools": [{"start": "10.0.0.2", "end": "10.0.0.254"}],
            }
        ],
        {"allocation_pools": [{"start": "10.0.0.2", "end": "10.0.0.254"}]},
    ),
    (
        "list_ports",
        {"device_id": "srv-1"},
        "network",
        "ports",
        [
            {
                "id": "p",
                "fixed_ips": [{"subnet_id": "sn", "ip_address": "10.0.0.5"}],
                "binding:profile": {"x": 1},
            }
        ],
        {"fixed_ips": [{"subnet_id": "sn", "ip_address": "10.0.0.5"}]},
    ),
    (
        "list_floating_ips",
        {"status": "ACTIVE"},
        "network",
        "ips",
        [{"id": "f", "floating_ip_address": "203.0.113.10", "port_id": "p"}],
        {"floating_ip_address": "203.0.113.10"},
    ),
    (
        "list_routers",
        {},
        "network",
        "routers",
        [
            {
                "id": "r",
                "external_gateway_info": {"network_id": "ext", "enable_snat": True},
            }
        ],
        {
            "external_gateway_info": {
                "network_id": "ext",
                "enable_snat": True,
                "external_fixed_ips": None,
            }
        },
    ),
    (
        "list_security_groups",
        {"name": "default"},
        "network",
        "security_groups",
        [
            {
                "id": "sg",
                "name": "default",
                "security_group_rules": [
                    {
                        "id": "r1",
                        "direction": "ingress",
                        "ethertype": "IPv4",
                        "protocol": "tcp",
                        "port_range_min": 22,
                        "port_range_max": 22,
                    }
                ],
            }
        ],
        {
            "security_group_rules": [
                {
                    "id": "r1",
                    "direction": "ingress",
                    "ether_type": "IPv4",
                    "protocol": "tcp",
                    "port_range_min": 22,
                    "port_range_max": 22,
                    "remote_ip_prefix": None,
                    "remote_group_id": None,
                    "description": None,
                }
            ]
        },
    ),
    (
        "list_regions",
        {},
        "identity",
        "regions",
        [{"id": "RegionOne"}],
        {"id": "RegionOne"},
    ),
    (
        "list_domains",
        {"name": "Default"},
        "identity",
        "domains",
        [{"id": "default", "name": "Default", "is_enabled": True}],
        {"is_enabled": True},
    ),
    (
        "list_projects",
        {"domain_id": "default"},
        "identity",
        "projects",
        [{"id": PROJECT_A, "name": "demo", "domain_id": "default"}],
        {"name": "demo"},
    ),
    (
        "list_services",
        {"type": "compute"},
        "identity",
        "services",
        [{"id": "svc", "name": "nova", "type": "compute"}],
        {"type": "compute"},
    ),
    (
        "list_endpoints",
        {"interface": "public"},
        "identity",
        "endpoints",
        [{"id": "e", "interface": "public", "url": "https://nova.example"}],
        {"url": "https://nova.example"},
    ),
    (
        "list_hypervisors",
        {},
        "compute",
        "hypervisors",
        [{"id": "h", "name": "cmp1", "state": "up", "vcpus": 64}],
        {"vcpus": 64},
    ),
    (
        "list_compute_services",
        {"binary": "nova-compute"},
        "compute",
        "services",
        [{"id": "c", "binary": "nova-compute", "host": "cmp1", "state": "up"}],
        {"host": "cmp1"},
    ),
    (
        "list_aggregates",
        {},
        "compute",
        "aggregates",
        [{"id": "1", "name": "ssd", "hosts": ["cmp1"], "metadata": {"secret": "x"}}],
        {"hosts": ["cmp1"]},
    ),
    (
        "list_network_agents",
        {"agent_type": "L3 agent"},
        "network",
        "agents",
        [
            {
                "id": "ag",
                "agent_type": "L3 agent",
                "is_alive": True,
                "configurations": {"x": 1},
            }
        ],
        {"is_alive": True},
    ),
    (
        "list_volume_services",
        {"host": "ctl1"},
        "block_storage",
        "services",
        [{"binary": "cinder-volume", "host": "ctl1", "state": "up"}],
        {"state": "up"},
    ),
]


@pytest.mark.parametrize(
    ("tool", "arguments", "service", "method", "response", "expected"),
    CASES,
    ids=[f"{case[0]}-{i}" for i, case in enumerate(CASES)],
)
def test_list_tool_dispatch_and_model(
    fake: FakeCloud,
    tool: str,
    arguments: dict[str, Any],
    service: str,
    method: str,
    response: Any,
    expected: dict[str, Any],
) -> None:
    fake.respond(service, method, response)
    data = ok(call(make_server(fake), tool, arguments))
    (listing,) = fake.calls
    assert (listing.service, listing.method) == (service, method)
    for key, value in arguments.items():
        target = "is_shared" if key == "shared" else key
        assert listing.kwargs[target] == value
    (item,) = data["items"]
    for key, value in expected.items():
        assert item[key] == value, key
    assert "must-not-export" not in str(data)
    assert "configurations" not in item and "metadata" not in item


GETS = [
    ("get_server", {"server_id": "srv-1"}, "compute", SERVER),
    ("get_image", {"image_id": "img"}, "image", {"id": "img", "name": "cirros"}),
    ("get_volume", {"volume_id": "v"}, "block_storage", {"id": "v", "size": 1}),
    ("get_volume_attachment", {"attachment_id": "a"}, "block_storage", {"id": "a"}),
    ("get_network", {"network_id": "n"}, "network", {"id": "n"}),
    ("get_subnet", {"subnet_id": "sn"}, "network", {"id": "sn"}),
    (
        "get_port",
        {"port_id": "p"},
        "network",
        {"id": "p", "allowed_address_pairs": [{"ip_address": "10.0.0.9"}]},
    ),
    ("get_router", {"router_id": "r"}, "network", {"id": "r"}),
    ("get_security_group", {"security_group_id": "sg"}, "network", {"id": "sg"}),
]


@pytest.mark.parametrize(
    ("tool", "arguments", "service", "response"), GETS, ids=[g[0] for g in GETS]
)
def test_get_tool_dispatch(
    fake: FakeCloud, tool: str, arguments: dict[str, Any], service: str, response: Any
) -> None:
    method = {"get_volume_attachment": "get_attachment"}.get(tool, tool)
    fake.respond(service, method, response)
    data = ok(call(make_server(fake), tool, arguments))
    (got,) = fake.calls
    assert (got.service, got.method, got.args) == (
        service,
        method,
        tuple(arguments.values()),
    )
    assert data["id"] == response["id"]
    assert "must-not-export" not in str(data)


def test_router_interfaces_from_ports(fake: FakeCloud) -> None:
    fake.respond(
        "network",
        "ports",
        [
            {
                "id": "p1",
                "device_owner": "network:router_interface",
                "fixed_ips": [{"subnet_id": "s1", "ip_address": "10.0.0.1"}],
            },
            {
                "id": "p2",
                "device_owner": "network:router_gateway",
                "fixed_ips": [{"subnet_id": "ext", "ip_address": "203.0.113.1"}],
            },
            {
                "id": "p3",
                "device_owner": "network:ha_router_replicated_interface",
                "fixed_ips": [
                    {"subnet_id": "s2", "ip_address": "10.0.1.1"},
                    {"subnet_id": "s3", "ip_address": "fd00::1"},
                ],
            },
        ],
    )
    data = ok(call(make_server(fake), "list_router_interfaces", {"router_id": "r"}))
    assert [(i["port_id"], i["subnet_id"]) for i in data["items"]] == [
        ("p1", "s1"),
        ("p3", "s2"),
        ("p3", "s3"),
    ]
    assert fake.calls[0].kwargs == {"device_id": "r"}
    assert data["complete"] is True and data["next_marker"] is None


def test_sdk_resources_are_converted(fake: FakeCloud) -> None:
    from openstack.compute.v2.server import Server

    fake.respond("compute", "servers", [Server(id="s", name="vm", status="ACTIVE")])
    data = ok(call(make_server(fake), "list_servers"))
    assert data["items"][0]["status"] == "ACTIVE"


def test_plain_objects_are_converted(fake: FakeCloud) -> None:
    class Obj:
        def __init__(self) -> None:
            self.id = "f"
            self.name = "m1"
            self._private = "hidden"

    fake.respond("compute", "flavors", [Obj()])
    data = ok(call(make_server(fake, Settings()), "list_flavors"))
    assert data["items"][0]["name"] == "m1"
