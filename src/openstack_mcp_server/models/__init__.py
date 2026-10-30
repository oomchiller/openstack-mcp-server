"""Typed result models. Fields are explicit; anything else is dropped (OUT-6)."""

from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict

M = TypeVar("M", bound=BaseModel)


class Model(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_by_name=True)


def as_mapping(resource: Any) -> Mapping[str, Any]:
    """Return an SDK resource (a mapping of attribute names) or object as a mapping."""
    if isinstance(resource, Mapping):
        return resource
    return {key: value for key, value in vars(resource).items() if key[0] != "_"}


def convert(model: type[M], resource: Any) -> M:
    return model.model_validate(dict(as_mapping(resource)))
