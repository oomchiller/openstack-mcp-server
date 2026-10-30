"""Tool registration: annotations, error mapping, size limit and call logging."""

import functools
import inspect
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

import anyio.to_thread
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from ..cloud import Cloud
from ..config import Settings
from ..errors import classify
from ..models import Model
from ..paging import check_size

F = TypeVar("F", bound=Callable[..., Any])
log = logging.getLogger("openstack_mcp_server.calls")


class ActionResult(Model):
    """Outcome of a write that returns no resource."""

    resource: str
    id: str
    action: str
    project_id: str


def page_query(limit: int, marker: str | None, **filters: Any) -> dict[str, Any]:
    """SDK list arguments: page size ``limit + 1``, marker and non-null filters."""
    query = {key: value for key, value in filters.items() if value is not None}
    query["limit"] = limit + 1
    if marker is not None:
        query["marker"] = marker
    return query


def filters(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


class Registrar:
    """Registers tools on a server with the shared argument fields."""

    def __init__(self, server: FastMCP, cloud: Cloud) -> None:
        self.server = server
        self.cloud = cloud
        self.settings: Settings = cloud.settings
        self.names: list[str] = []
        allowed = list(self.settings.project_ids)
        project_extra: dict[str, Any] = {"enum": [*allowed, None]} if allowed else {}
        self.project = Field(
            description=(
                "Project ID to work in; omit for the default project. "
                "Allowed values are listed by get_scope."
            ),
            json_schema_extra=project_extra or None,
        )
        self.limit = Field(
            ge=1,
            le=self.settings.max_limit,
            description=(
                f"Maximum items to return (1-{self.settings.max_limit}, "
                f"default {self.settings.default_limit})."
            ),
        )
        self.default_limit = self.settings.default_limit
        self.marker = Field(
            max_length=255,
            description="next_marker from the previous page; omit for the first page.",
        )

    def read(
        self, name: str, title: str, *, cloud: bool = True, note: str | None = None
    ) -> Callable[[F], F]:
        annotations = ToolAnnotations(
            title=title,
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=cloud,
        )
        return functools.partial(self._add, name, title, annotations, note)

    def write(
        self, name: str, title: str, *, destructive: bool, idempotent: bool
    ) -> Callable[[F], F]:
        annotations = ToolAnnotations(
            title=title,
            readOnlyHint=False,
            destructiveHint=destructive,
            idempotentHint=idempotent,
            openWorldHint=True,
        )
        return functools.partial(self._add, name, title, annotations, None)

    def _add(
        self,
        name: str,
        title: str,
        annotations: ToolAnnotations,
        note: str | None,
        fn: F,
    ) -> F:
        max_bytes = self.settings.max_response_bytes

        @functools.wraps(fn)
        async def call(**kwargs: Any) -> Any:
            started = time.monotonic()
            outcome = "ok"
            try:
                result = await anyio.to_thread.run_sync(functools.partial(fn, **kwargs))
                if isinstance(result, BaseModel):
                    check_size(result, max_bytes)
                return result
            except Exception as error:
                failure = classify(error)
                outcome = failure.category
                if failure is not error:
                    log.debug("tool=%s error_type=%s", name, type(error).__name__)
                raise failure from None
            finally:
                log.info(
                    "tool=%s project=%s outcome=%s ms=%d",
                    name,
                    kwargs.get("project_id") or "-",
                    outcome,
                    (time.monotonic() - started) * 1000,
                )

        self.server.add_tool(
            call,
            name=name,
            title=title,
            description=" ".join(
                part for part in (inspect.cleandoc(fn.__doc__ or title), note) if part
            ),
            annotations=annotations,
            structured_output=True,
        )
        _forbid_extra_arguments(self.server, name)
        self.names.append(name)
        return fn


def _forbid_extra_arguments(server: FastMCP, name: str) -> None:
    """Reject unknown arguments instead of silently ignoring them (TOOL-4)."""
    tool = server._tool_manager.get_tool(name)
    if tool is None:  # pragma: no cover - add_tool just registered it
        raise RuntimeError(name)
    base = tool.fn_metadata.arg_model
    strict: type[ArgModelBase] = type(
        base.__name__,
        (base,),
        {
            "__module__": base.__module__,
            "model_config": ConfigDict(**{**base.model_config, "extra": "forbid"}),
        },
    )
    tool.fn_metadata.arg_model = strict
    tool.parameters = strict.model_json_schema(by_alias=True)
