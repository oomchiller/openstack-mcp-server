"""Block storage (Cinder) tools."""

from typing import Annotated, Literal

from pydantic import Field

from ..models import convert
from ..models.block_storage import Attachment, Volume
from ..paging import ListResult, list_result
from .base import ActionResult, Registrar, filters, page_query

VolumeStatus = Literal[
    "available",
    "in-use",
    "creating",
    "deleting",
    "attaching",
    "detaching",
    "extending",
    "maintenance",
    "reserved",
    "retyping",
    "backing-up",
    "restoring-backup",
    "downloading",
    "uploading",
    "awaiting-transfer",
    "error",
    "error_deleting",
    "error_backing-up",
    "error_restoring",
    "error_extending",
    "error_managing",
]
Id = Annotated[str, Field(min_length=1, max_length=255)]


def register_read(reg: Registrar) -> None:
    @reg.read("list_volumes", "List volumes")
    def list_volumes(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        marker: Annotated[str | None, reg.marker] = None,
        status: VolumeStatus | None = None,
        name: Annotated[str | None, Field(max_length=255)] = None,
    ) -> ListResult[Volume]:
        """List volumes in the project with size (GiB), type and attachments.

        Paged with limit and marker.
        """
        pid, conn = reg.cloud.connection(project_id)
        query = page_query(limit, marker, status=status, name=name)
        return list_result(
            Volume,
            "volumes",
            pid,
            limit,
            conn.block_storage.volumes(details=True, **query),
            markers=True,
        )

    @reg.read("get_volume", "Get volume")
    def get_volume(
        volume_id: Id, project_id: Annotated[str | None, reg.project] = None
    ) -> Volume:
        """Get one volume by ID."""
        _, conn = reg.cloud.connection(project_id)
        return convert(Volume, conn.block_storage.get_volume(volume_id))

    @reg.read("list_volume_attachments", "List volume attachments")
    def list_volume_attachments(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        marker: Annotated[str | None, reg.marker] = None,
        volume_id: str | None = None,
        instance_id: Annotated[
            str | None, Field(description="Server ID the volume is attached to.")
        ] = None,
    ) -> ListResult[Attachment]:
        """List Cinder attachment records (API microversion 3.27 or later).

        Connection details are not returned. Paged with limit and marker.
        """
        pid, conn = reg.cloud.connection(project_id)
        query = page_query(limit, marker, volume_id=volume_id, instance_id=instance_id)
        return list_result(
            Attachment,
            "volume_attachments",
            pid,
            limit,
            conn.block_storage.attachments(**query),
            markers=True,
        )

    @reg.read("get_volume_attachment", "Get volume attachment")
    def get_volume_attachment(
        attachment_id: Id, project_id: Annotated[str | None, reg.project] = None
    ) -> Attachment:
        """Get one Cinder attachment record by ID, without connection details."""
        _, conn = reg.cloud.connection(project_id)
        return convert(Attachment, conn.block_storage.get_attachment(attachment_id))


def register_write(reg: Registrar) -> None:
    @reg.write("create_volume", "Create volume", destructive=False, idempotent=False)
    def create_volume(
        name: Id,
        size: Annotated[int, Field(ge=1, description="Size in GiB.")],
        project_id: Annotated[str | None, reg.project] = None,
        description: str | None = None,
        volume_type: str | None = None,
        availability_zone: str | None = None,
        image_id: Annotated[
            str | None, Field(description="Create the volume from this image.")
        ] = None,
    ) -> Volume:
        """Create a volume, empty or from an image, and return it."""
        _, conn = reg.cloud.connection(project_id)
        created = conn.block_storage.create_volume(
            **filters(
                name=name,
                size=size,
                description=description,
                volume_type=volume_type,
                availability_zone=availability_zone,
                image_id=image_id,
            )
        )
        return convert(Volume, created)

    @reg.write("delete_volume", "Delete volume", destructive=True, idempotent=True)
    def delete_volume(
        volume_id: Id, project_id: Annotated[str | None, reg.project] = None
    ) -> ActionResult:
        """Delete a volume and its data."""
        pid, conn = reg.cloud.connection(project_id)
        conn.block_storage.delete_volume(volume_id, ignore_missing=False)
        return ActionResult(
            resource="volume", id=volume_id, action="delete", project_id=pid
        )

    @reg.write("extend_volume", "Extend volume", destructive=True, idempotent=True)
    def extend_volume(
        volume_id: Id,
        new_size: Annotated[int, Field(ge=1, description="New size in GiB.")],
        project_id: Annotated[str | None, reg.project] = None,
    ) -> ActionResult:
        """Grow a volume to a larger size. Volumes cannot shrink."""
        pid, conn = reg.cloud.connection(project_id)
        conn.block_storage.extend_volume(volume_id, new_size)
        return ActionResult(
            resource="volume", id=volume_id, action="extend", project_id=pid
        )
