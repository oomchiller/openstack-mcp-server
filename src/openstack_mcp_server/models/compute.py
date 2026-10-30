from pydantic import Field, field_validator

from . import Model


class ServerFlavor(Model):
    name: str | None = Field(default=None, validation_alias="original_name")
    vcpus: int | None = None
    ram: int | None = None
    disk: int | None = None


class ServerImage(Model):
    id: str | None = None


class IPAddress(Model):
    addr: str
    version: int
    type: str | None = Field(default=None, validation_alias="OS-EXT-IPS:type")


class AttachedVolume(Model):
    id: str
    delete_on_termination: bool | None = None


class SecurityGroupName(Model):
    name: str


class Server(Model):
    id: str
    name: str
    status: str | None = None
    description: str | None = None
    hostname: str | None = None
    flavor: ServerFlavor | None = None
    image: ServerImage | None = None
    addresses: dict[str, list[IPAddress]] | None = None
    key_name: str | None = None
    security_groups: list[SecurityGroupName] | None = None
    attached_volumes: list[AttachedVolume] | None = None
    availability_zone: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator("image", mode="before")
    @classmethod
    def _empty_image(cls, value: object) -> object:
        # Volume-booted servers report image as "" or {}.
        return None if value in ("", {}) else value


class Flavor(Model):
    id: str
    name: str
    vcpus: int | None = None
    ram: int | None = None
    disk: int | None = None
    swap: int | None = None
    is_public: bool | None = None
