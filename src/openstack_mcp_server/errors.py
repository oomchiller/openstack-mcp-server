"""Closed error categories with fixed, agent-facing messages (SPEC ERR)."""

from typing import Literal

import pydantic
import requests.exceptions
from keystoneauth1 import exceptions as ks
from mcp.server.fastmcp.exceptions import ToolError
from openstack import exceptions as sdk

Category = Literal[
    "not_configured",
    "project_not_allowed",
    "invalid_argument",
    "auth_failed",
    "forbidden",
    "not_found",
    "conflict",
    "service_unavailable",
    "unavailable",
    "response_too_large",
    "incompatible_response",
    "internal",
]

_MESSAGES: dict[Category, str] = {
    "not_configured": (
        "OpenStack credentials are not configured or not usable. Set OS_CLOUD "
        "with clouds.yaml or OS_* variables; retrying will not help"
    ),
    "project_not_allowed": (
        "The project is outside the configured scope. Call get_scope for the "
        "allowed project IDs"
    ),
    "invalid_argument": "An argument is invalid. Correct it and call again",
    "auth_failed": (
        "Authentication to OpenStack failed. Check the configured credentials; "
        "retrying will not help"
    ),
    "forbidden": (
        "The configured identity is not allowed this operation. Do not retry; "
        "the cloud operator must grant a role"
    ),
    "not_found": "The resource was not found. Check the ID and the project",
    "conflict": (
        "OpenStack rejected the request because of the resource state. Inspect "
        "the resource before trying again"
    ),
    "service_unavailable": (
        "This cloud's catalog does not offer the required service. Do not retry"
    ),
    "unavailable": (
        "OpenStack did not respond or returned a server error. Retry later"
    ),
    "response_too_large": (
        "The result exceeds the configured response size. Use a smaller limit or "
        "narrower filters"
    ),
    "incompatible_response": (
        "OpenStack returned data in an unexpected shape. Report a bug with the "
        "cloud's OpenStack release"
    ),
    "internal": "The server failed unexpectedly. Report a bug",
}


class ToolFailure(ToolError):
    """A tool failure the client sees as ``[category] message``."""

    def __init__(self, category: Category, detail: str | None = None) -> None:
        text = f"[{category}] {_MESSAGES[category]}."
        if detail:
            text = f"[{category}] {detail}. {_MESSAGES[category]}."
        super().__init__(text)
        self.category: Category = category


def classify(error: BaseException) -> ToolFailure:
    """Map any exception to a category without using its text (ERR-2)."""
    if isinstance(error, ToolFailure):
        return error
    return ToolFailure(_category(error))


def _category(error: BaseException) -> Category:
    if isinstance(error, (ks.MissingRequiredOptions, ks.MissingAuthPlugin)):
        return "not_configured"
    if isinstance(error, (ks.EndpointNotFound, sdk.EndpointNotFound, ks.EmptyCatalog)):
        return "service_unavailable"
    if isinstance(error, (ks.Unauthorized, ks.AuthorizationFailure)):
        return "auth_failed"
    if isinstance(error, (ks.ConnectionError, requests.exceptions.ConnectionError)):
        return "unavailable"
    if isinstance(error, (requests.exceptions.Timeout, ks.RequestTimeout)):
        return "unavailable"
    if isinstance(error, (sdk.InvalidResponse, ks.InvalidResponse)):
        return "incompatible_response"
    if isinstance(error, pydantic.ValidationError):
        return "incompatible_response"
    for kind, category in _SDK_CLASSES:
        if isinstance(error, kind):
            return category
    status = _status(error)
    if status is not None:
        return _http_category(status)
    return "internal"


_SDK_CLASSES: tuple[tuple[type[BaseException], Category], ...] = (
    (sdk.ForbiddenException, "forbidden"),
    (sdk.NotFoundException, "not_found"),
    (sdk.ResourceNotFound, "not_found"),
    (sdk.ConflictException, "conflict"),
    (sdk.BadRequestException, "invalid_argument"),
)


def _status(error: BaseException) -> int | None:
    for attribute in ("status_code", "http_status"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            return value
    return None


def _http_category(status: int) -> Category:
    if status == 401:
        return "auth_failed"
    if status == 403:
        return "forbidden"
    if status == 404:
        return "not_found"
    if status == 409:
        return "conflict"
    if status in (400, 422):
        return "invalid_argument"
    if status >= 500 or status == 408:
        return "unavailable"
    return "internal"
