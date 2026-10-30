"""SPEC OUT-1 … OUT-7: bounded lists, envelope and size limit."""

from collections.abc import Iterator
from datetime import datetime

import pytest

from openstack_mcp_server.config import Settings
from openstack_mcp_server.paging import bounded

from .conftest import FakeCloud, call, failed, make_server, ok


def servers(count: int) -> list[dict[str, str]]:
    return [{"id": f"s{i}", "name": f"vm-{i}"} for i in range(count)]


def test_out_3_consumes_at_most_limit_plus_one() -> None:
    seen: list[int] = []

    def endless() -> Iterator[int]:
        for i in range(10_000):
            seen.append(i)
            yield i

    items, complete = bounded(endless(), 2)
    assert (items, complete, len(seen)) == ([0, 1], False, 3)
    assert bounded(iter([1, 2]), 2) == ([1, 2], True)


def test_out_1_envelope_and_marker(fake: FakeCloud) -> None:
    fake.respond("compute", "servers", servers(1000))
    data = ok(call(make_server(fake), "list_servers", {"limit": 3}))
    assert data["resource"] == "servers"
    assert [item["id"] for item in data["items"]] == ["s0", "s1", "s2"]
    assert (data["limit"], data["complete"], data["next_marker"]) == (3, False, "s2")
    datetime.fromisoformat(data["observed_at"])
    assert fake.consumed == [4]
    assert fake.calls[0].kwargs == {"limit": 4}


def test_out_4_marker_is_forwarded(fake: FakeCloud) -> None:
    fake.respond("compute", "servers", servers(2))
    data = ok(call(make_server(fake), "list_servers", {"limit": 5, "marker": "s9"}))
    assert fake.calls[0].kwargs == {"limit": 6, "marker": "s9"}
    assert (data["complete"], data["next_marker"]) == (True, None)


def test_out_4_unpaged_api_has_no_marker(fake: FakeCloud) -> None:
    fake.respond("compute", "hypervisors", [{"id": str(i)} for i in range(5)])
    server = make_server(fake)
    data = ok(call(server, "list_hypervisors", {"limit": 2}))
    assert (data["complete"], data["next_marker"]) == (False, None)
    assert call(server, "list_hypervisors", {"marker": "x"}).isError


def test_out_2_default_limit(fake: FakeCloud) -> None:
    fake.respond("image", "images", [{"id": str(i)} for i in range(30)])
    data = ok(call(make_server(fake, Settings(default_limit=7)), "list_images"))
    assert len(data["items"]) == 7


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_out_2_limit_bounds(fake: FakeCloud, limit: int) -> None:
    assert call(make_server(fake), "list_servers", {"limit": limit}).isError
    assert fake.calls == []


def test_out_6_fields_are_explicit(fake: FakeCloud) -> None:
    fake.respond(
        "compute",
        "hypervisors",
        [
            {
                "id": "1",
                "name": "hv",
                "state": "up",
                "password": "must-not-export",
                "links": [{"href": "https://internal.example"}],
                "cpu_info": {"x": 1},
            }
        ],
    )
    data = ok(call(make_server(fake), "list_hypervisors"))
    (item,) = data["items"]
    assert "password" not in item and "links" not in item and "cpu_info" not in item
    assert "must-not-export" not in str(data)


def test_out_5_get_returns_single_model(fake: FakeCloud) -> None:
    fake.respond(
        "compute", "get_server", {"id": "s1", "name": "vm", "status": "ACTIVE"}
    )
    data = ok(call(make_server(fake), "get_server", {"server_id": "s1"}))
    assert (data["id"], data["status"]) == ("s1", "ACTIVE")
    assert fake.calls[0].args == ("s1",)


def test_out_7_oversized_result_is_refused(fake: FakeCloud) -> None:
    fake.respond("compute", "servers", [{"id": "x", "name": "x" * 10_000}])
    result = call(make_server(fake, Settings(max_response_bytes=4096)), "list_servers")
    failed(result, "response_too_large")
    assert "x" * 100 not in result.content[0].text  # type: ignore[union-attr]
