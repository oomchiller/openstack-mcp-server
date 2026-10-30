"""SPEC ERR-1 … ERR-3, MCP-5, CFG-4: closed categories, nothing leaked."""

import pydantic
import pytest
import requests
from keystoneauth1 import exceptions as ks
from openstack import exceptions as sdk

from openstack_mcp_server.errors import ToolFailure, classify

from .conftest import SECRET, FakeCloud, call, failed, make_server

LEAK = f"https://keystone.internal.example token={SECRET} body"


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (sdk.ForbiddenException(LEAK), "forbidden"),
        (sdk.NotFoundException(LEAK), "not_found"),
        (sdk.ConflictException(LEAK), "conflict"),
        (sdk.BadRequestException(LEAK), "invalid_argument"),
        (sdk.HttpException(LEAK, http_status=503), "unavailable"),
        (sdk.HttpException(LEAK, http_status=401), "auth_failed"),
        (sdk.HttpException(LEAK, http_status=418), "internal"),
        (ks.Unauthorized(LEAK), "auth_failed"),
        (ks.EndpointNotFound(LEAK), "service_unavailable"),
        (sdk.EndpointNotFound(LEAK), "service_unavailable"),
        (ks.ConnectFailure(LEAK), "unavailable"),
        (ks.ConnectTimeout(LEAK), "unavailable"),
        (requests.exceptions.ReadTimeout(LEAK), "unavailable"),
        (ks.MissingRequiredOptions([]), "not_configured"),
        (sdk.InvalidResponse(LEAK), "incompatible_response"),
        (RuntimeError(LEAK), "internal"),
    ],
)
def test_err_1_mapping(error: BaseException, category: str) -> None:
    failure = classify(error)
    assert failure.category == category
    assert str(failure).startswith(f"[{category}] ")
    assert SECRET not in str(failure) and "internal.example" not in str(failure)


def test_err_1_validation_error_is_incompatible_response() -> None:
    class Strict(pydantic.BaseModel):
        id: str

    with pytest.raises(pydantic.ValidationError) as caught:
        Strict.model_validate({"id": None})
    assert classify(caught.value).category == "incompatible_response"


def test_err_1_failures_pass_through() -> None:
    failure = ToolFailure("not_found", "Volume v1 does not exist")
    assert classify(failure) is failure
    assert str(failure).startswith("[not_found] Volume v1 does not exist. ")


@pytest.mark.parametrize(
    "error", [sdk.ForbiddenException(LEAK), RuntimeError(LEAK), ks.ConnectFailure(LEAK)]
)
def test_err_2_mcp_result_has_no_upstream_text(
    fake: FakeCloud, error: BaseException
) -> None:
    fake.respond("compute", "servers", error)
    result = call(make_server(fake), "list_servers")
    assert result.isError
    message = result.content[0].text  # type: ignore[union-attr]
    assert SECRET not in message and "keystone.internal" not in message
    assert "Traceback" not in message


def test_err_3_forbidden_is_not_an_empty_list(fake: FakeCloud) -> None:
    fake.respond("compute", "hypervisors", sdk.ForbiddenException("policy"))
    message = failed(call(make_server(fake), "list_hypervisors"), "forbidden")
    assert "Do not retry" in message


def test_err_1_incompatible_item_shape(fake: FakeCloud) -> None:
    fake.respond("compute", "servers", [{"id": None, "name": 5}])
    failed(call(make_server(fake), "list_servers"), "incompatible_response")


def test_cfg_4_credentials_never_in_results(fake: FakeCloud) -> None:
    server = make_server(fake)
    for tool in ("get_scope", "list_servers"):
        result = call(server, tool)
        assert SECRET not in result.model_dump_json()
