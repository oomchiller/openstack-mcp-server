from pydantic import Field

from . import Model


class VolumeAttachment(Model):
    server_id: str | None = None
    device: str | None = None
    attachment_id: str | None = None


class Volume(Model):
    id: str
    name: str | None = None
    status: str | None = None
    size: int | None = None
    volume_type: str | None = None
    availability_zone: str | None = None
    is_bootable: bool | None = None
    is_encrypted: bool | None = None
    description: str | None = None
    attachments: list[VolumeAttachment] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class Attachment(Model):
    """Cinder attachment record. Connection info and connector are not exported."""

    id: str
    instance: str | None = None
    volume_id: str | None = None
    status: str | None = None
    attach_mode: str | None = None
    attached_at: str | None = None
    detached_at: str | None = None
