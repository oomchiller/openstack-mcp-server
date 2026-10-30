"""Compute (Nova) tools."""

from typing import Annotated, Literal

from pydantic import Field

from ..models import convert
from ..models.compute import Flavor, Server
from ..paging import ListResult, list_result
from .base import ActionResult, Registrar, filters, page_query

ServerStatus = Literal[
    "ACTIVE",
    "BUILD",
    "DELETED",
    "ERROR",
    "HARD_REBOOT",
    "MIGRATING",
    "PAUSED",
    "REBOOT",
    "REBUILD",
    "RESCUE",
    "RESIZE",
    "REVERT_RESIZE",
    "SHELVED",
    "SHELVED_OFFLOADED",
    "SHUTOFF",
    "SOFT_DELETED",
    "SUSPENDED",
    "UNKNOWN",
    "VERIFY_RESIZE",
]
ServerAction = Literal[
    "start",
    "stop",
    "pause",
    "unpause",
    "suspend",
    "resume",
    "lock",
    "unlock",
    "rescue",
    "unrescue",
    "shelve",
    "shelve_offload",
    "unshelve",
]
Id = Annotated[str, Field(min_length=1, max_length=255)]


def register_read(reg: Registrar) -> None:
    @reg.read("list_servers", "List servers")
    def list_servers(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        marker: Annotated[str | None, reg.marker] = None,
        status: ServerStatus | None = None,
        name: Annotated[
            str | None, Field(max_length=255, description="Name regex filter.")
        ] = None,
    ) -> ListResult[Server]:
        """List servers in the project with flavor, image, addresses and volumes.

        Paged with limit and marker.
        """
        pid, conn = reg.cloud.connection(project_id)
        query = page_query(limit, marker, status=status, name=name)
        return list_result(
            Server, "servers", pid, limit, conn.compute.servers(**query), markers=True
        )

    @reg.read("get_server", "Get server")
    def get_server(
        server_id: Id, project_id: Annotated[str | None, reg.project] = None
    ) -> Server:
        """Get one server by ID."""
        _, conn = reg.cloud.connection(project_id)
        return convert(Server, conn.compute.get_server(server_id))

    @reg.read("list_flavors", "List flavors")
    def list_flavors(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        marker: Annotated[str | None, reg.marker] = None,
    ) -> ListResult[Flavor]:
        """List flavors visible to the project: vCPUs, RAM (MiB), disk (GiB).

        Paged with limit and marker.
        """
        pid, conn = reg.cloud.connection(project_id)
        return list_result(
            Flavor,
            "flavors",
            pid,
            limit,
            conn.compute.flavors(**page_query(limit, marker)),
            markers=True,
        )


def register_write(reg: Registrar) -> None:
    @reg.write("create_server", "Create server", destructive=False, idempotent=False)
    def create_server(
        name: Id,
        image_id: Id,
        flavor_id: Id,
        network_id: Id,
        project_id: Annotated[str | None, reg.project] = None,
        key_name: str | None = None,
        security_groups: list[str] | None = None,
    ) -> Server:
        """Create a server from an image on one network and return it."""
        _, conn = reg.cloud.connection(project_id)
        created = conn.compute.create_server(
            **filters(
                name=name,
                image_id=image_id,
                flavor_id=flavor_id,
                networks=[{"uuid": network_id}],
                key_name=key_name,
                security_groups=[{"name": group} for group in security_groups]
                if security_groups
                else None,
            )
        )
        return convert(Server, conn.compute.get_server(created.id))

    @reg.write("update_server", "Update server", destructive=False, idempotent=True)
    def update_server(
        server_id: Id,
        project_id: Annotated[str | None, reg.project] = None,
        name: str | None = None,
        description: str | None = None,
    ) -> Server:
        """Change a server's name or description."""
        _, conn = reg.cloud.connection(project_id)
        updated = conn.compute.update_server(
            server_id, **filters(name=name, description=description)
        )
        return convert(Server, updated)

    @reg.write("delete_server", "Delete server", destructive=True, idempotent=True)
    def delete_server(
        server_id: Id, project_id: Annotated[str | None, reg.project] = None
    ) -> ActionResult:
        """Delete a server. Its ephemeral disk is lost."""
        pid, conn = reg.cloud.connection(project_id)
        conn.compute.delete_server(server_id, ignore_missing=False)
        return ActionResult(
            resource="server", id=server_id, action="delete", project_id=pid
        )

    @reg.write("server_action", "Run server action", destructive=True, idempotent=False)
    def server_action(
        server_id: Id,
        action: ServerAction,
        project_id: Annotated[str | None, reg.project] = None,
    ) -> ActionResult:
        """Run a power or state action on a server, such as stop or shelve."""
        pid, conn = reg.cloud.connection(project_id)
        getattr(conn.compute, f"{action}_server")(server_id)
        return ActionResult(
            resource="server", id=server_id, action=action, project_id=pid
        )

    @reg.write("attach_volume", "Attach volume", destructive=False, idempotent=False)
    def attach_volume(
        server_id: Id,
        volume_id: Id,
        project_id: Annotated[str | None, reg.project] = None,
        device: str | None = None,
    ) -> ActionResult:
        """Attach a volume to a server, optionally at a device such as /dev/vdb."""
        pid, conn = reg.cloud.connection(project_id)
        conn.compute.create_volume_attachment(
            server_id, volume=volume_id, **filters(device=device)
        )
        return ActionResult(
            resource="server", id=server_id, action="attach_volume", project_id=pid
        )

    @reg.write("detach_volume", "Detach volume", destructive=True, idempotent=False)
    def detach_volume(
        server_id: Id,
        volume_id: Id,
        project_id: Annotated[str | None, reg.project] = None,
    ) -> ActionResult:
        """Detach a volume from a server."""
        pid, conn = reg.cloud.connection(project_id)
        conn.compute.delete_volume_attachment(server_id, volume_id)
        return ActionResult(
            resource="server", id=server_id, action="detach_volume", project_id=pid
        )
