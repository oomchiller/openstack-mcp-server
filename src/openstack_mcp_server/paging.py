"""Bounded listing, the list envelope and the response size limit (SPEC OUT)."""

from collections.abc import Iterable
from datetime import datetime, timezone
from itertools import islice
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from .errors import ToolFailure
from .models import convert

T = TypeVar("T", bound=BaseModel)


class ListResult(BaseModel, Generic[T]):
    resource: str = Field(description="Resource type of the items.")
    project_id: str | None = Field(
        description="Project whose session produced the list."
    )
    observed_at: str = Field(description="UTC time the list was read.")
    limit: int = Field(description="Maximum number of items requested.")
    items: list[T]
    complete: bool = Field(
        description="True when no more items exist beyond this page."
    )
    next_marker: str | None = Field(
        default=None,
        description="Pass as marker to read the next page; null when complete or "
        "when the API has no marker paging.",
    )


def bounded(items: Iterable[Any], limit: int) -> tuple[list[Any], bool]:
    """Consume at most ``limit + 1`` items (OUT-3)."""
    taken = list(islice(iter(items), limit + 1))
    return taken[:limit], len(taken) <= limit


def list_result(
    model: type[T],
    resource: str,
    project_id: str | None,
    limit: int,
    items: Iterable[Any],
    *,
    markers: bool,
) -> ListResult[T]:
    raw, complete = bounded(items, limit)
    rows = [convert(model, item) for item in raw]
    next_marker = None
    if markers and not complete and rows:
        next_marker = getattr(rows[-1], "id", None)
    return ListResult[model](  # type: ignore[valid-type]
        resource=resource,
        project_id=project_id,
        observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        limit=limit,
        items=rows,
        complete=complete,
        next_marker=next_marker,
    )


def check_size(result: BaseModel, max_bytes: int) -> None:
    """Reject results larger than the configured limit (OUT-7)."""
    if len(result.model_dump_json().encode()) > max_bytes:
        raise ToolFailure("response_too_large")
