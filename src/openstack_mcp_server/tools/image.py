"""Image (Glance) tools."""

from typing import Annotated, Literal

from pydantic import Field

from ..models import convert
from ..models.image import Image
from ..paging import ListResult, list_result
from .base import ActionResult, Registrar, page_query

ImageStatus = Literal[
    "queued",
    "saving",
    "uploading",
    "importing",
    "active",
    "deactivated",
    "killed",
    "deleted",
    "pending_delete",
]
Visibility = Literal["public", "private", "shared", "community"]
DiskFormat = Literal[
    "ami", "ari", "aki", "vhd", "vhdx", "vmdk", "raw", "qcow2", "vdi", "iso", "ploop"
]
ContainerFormat = Literal["ami", "ari", "aki", "bare", "ovf", "ova", "docker"]
Id = Annotated[str, Field(min_length=1, max_length=255)]


def register_read(reg: Registrar) -> None:
    @reg.read("list_images", "List images")
    def list_images(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        marker: Annotated[str | None, reg.marker] = None,
        name: Annotated[str | None, Field(max_length=255)] = None,
        status: ImageStatus | None = None,
        visibility: Visibility | None = None,
    ) -> ListResult[Image]:
        """List images visible to the project, optionally filtered.

        Paged with limit and marker.
        """
        pid, conn = reg.cloud.connection(project_id)
        query = page_query(
            limit, marker, name=name, status=status, visibility=visibility
        )
        return list_result(
            Image, "images", pid, limit, conn.image.images(**query), markers=True
        )

    @reg.read("get_image", "Get image")
    def get_image(
        image_id: Id, project_id: Annotated[str | None, reg.project] = None
    ) -> Image:
        """Get one image by ID."""
        _, conn = reg.cloud.connection(project_id)
        return convert(Image, conn.image.get_image(image_id))


def register_write(reg: Registrar) -> None:
    @reg.write("create_image", "Create image", destructive=False, idempotent=False)
    def create_image(
        name: Id,
        disk_format: DiskFormat,
        source_url: Annotated[
            str,
            Field(
                pattern=r"^https?://",
                max_length=2048,
                description="Glance downloads the image data from this URL.",
            ),
        ],
        container_format: ContainerFormat = "bare",
        visibility: Visibility = "private",
        project_id: Annotated[str | None, reg.project] = None,
    ) -> Image:
        """Create an image and start a web-download import from a URL.

        The image stays in importing state until Glance has fetched the data.
        """
        _, conn = reg.cloud.connection(project_id)
        created = conn.image.create_image(
            name=name,
            disk_format=disk_format,
            container_format=container_format,
            visibility=visibility,
        )
        conn.image.import_image(created, method="web-download", uri=source_url)
        return convert(Image, conn.image.get_image(created.id))

    @reg.write("delete_image", "Delete image", destructive=True, idempotent=True)
    def delete_image(
        image_id: Id, project_id: Annotated[str | None, reg.project] = None
    ) -> ActionResult:
        """Delete an image."""
        pid, conn = reg.cloud.connection(project_id)
        conn.image.delete_image(image_id, ignore_missing=False)
        return ActionResult(
            resource="image", id=image_id, action="delete", project_id=pid
        )
