from typing import Any

from pydantic import field_validator

from . import Model


class Image(Model):
    id: str
    name: str | None = None
    status: str | None = None
    visibility: str | None = None
    owner: str | None = None
    container_format: str | None = None
    disk_format: str | None = None
    size: int | None = None
    virtual_size: int | None = None
    min_disk: int | None = None
    min_ram: int | None = None
    checksum: str | None = None
    hash_algo: str | None = None
    hash_value: str | None = None
    is_protected: bool | None = None
    is_hidden: bool | None = None
    tags: list[str] | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator("size", "virtual_size", mode="before")
    @classmethod
    def _sizes(cls, value: Any) -> Any:
        return None if value == "" else value
