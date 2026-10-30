"""Identity catalog and service inventory. These APIs have no marker paging."""

from collections.abc import Callable
from typing import Annotated, Any, Literal, TypeVar

from pydantic import BaseModel, Field

from ..models.platform import (
    Aggregate,
    CatalogService,
    ComputeService,
    Domain,
    Endpoint,
    Hypervisor,
    NetworkAgent,
    Project,
    Region,
    VolumeService,
)
from ..paging import ListResult, list_result
from .base import Registrar, filters

M = TypeVar("M", bound=BaseModel)
Interface = Literal["public", "internal", "admin"]
_NOTE = (
    "Usually needs more than a project reader role; forbidden means the role is "
    "missing, not that the list is empty. Not paged; narrow with filters."
)


def register_read(reg: Registrar) -> None:
    def run(
        model: type[M],
        resource: str,
        project_id: str | None,
        limit: int,
        listing: Callable[[Any], Any],
    ) -> ListResult[M]:
        pid, conn = reg.cloud.connection(project_id)
        return list_result(model, resource, pid, limit, listing(conn), markers=False)

    @reg.read("list_regions", "List regions")
    def list_regions(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
    ) -> ListResult[Region]:
        """List Keystone regions. Not paged."""
        return run(Region, "regions", project_id, limit, lambda c: c.identity.regions())

    @reg.read("list_domains", "List domains", note=_NOTE)
    def list_domains(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        name: Annotated[str | None, Field(max_length=255)] = None,
    ) -> ListResult[Domain]:
        """List Keystone domains."""
        return run(
            Domain,
            "domains",
            project_id,
            limit,
            lambda c: c.identity.domains(**filters(name=name)),
        )

    @reg.read("list_projects", "List projects", note=_NOTE)
    def list_projects(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        name: Annotated[str | None, Field(max_length=255)] = None,
        domain_id: str | None = None,
    ) -> ListResult[Project]:
        """List Keystone projects."""
        return run(
            Project,
            "projects",
            project_id,
            limit,
            lambda c: c.identity.projects(**filters(name=name, domain_id=domain_id)),
        )

    @reg.read("list_services", "List catalog services", note=_NOTE)
    def list_services(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        type: Annotated[
            str | None, Field(max_length=64, description="Service type, e.g. compute.")
        ] = None,
    ) -> ListResult[CatalogService]:
        """List services registered in the Keystone catalog."""
        return run(
            CatalogService,
            "services",
            project_id,
            limit,
            lambda c: c.identity.services(**filters(type=type)),
        )

    @reg.read("list_endpoints", "List catalog endpoints", note=_NOTE)
    def list_endpoints(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        interface: Interface | None = None,
        service_id: str | None = None,
        region_id: str | None = None,
    ) -> ListResult[Endpoint]:
        """List Keystone catalog endpoints with interface and URL."""
        return run(
            Endpoint,
            "endpoints",
            project_id,
            limit,
            lambda c: c.identity.endpoints(
                **filters(
                    interface=interface, service_id=service_id, region_id=region_id
                )
            ),
        )

    @reg.read("list_hypervisors", "List hypervisors", note=_NOTE)
    def list_hypervisors(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
    ) -> ListResult[Hypervisor]:
        """List Nova hypervisors with state and capacity."""
        return run(
            Hypervisor,
            "hypervisors",
            project_id,
            limit,
            lambda c: c.compute.hypervisors(details=True),
        )

    @reg.read("list_compute_services", "List compute services", note=_NOTE)
    def list_compute_services(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        host: str | None = None,
        binary: str | None = None,
    ) -> ListResult[ComputeService]:
        """List Nova services such as nova-compute, with host and state."""
        return run(
            ComputeService,
            "compute_services",
            project_id,
            limit,
            lambda c: c.compute.services(**filters(host=host, binary=binary)),
        )

    @reg.read("list_aggregates", "List host aggregates", note=_NOTE)
    def list_aggregates(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
    ) -> ListResult[Aggregate]:
        """List Nova host aggregates with availability zone and hosts."""
        return run(
            Aggregate,
            "aggregates",
            project_id,
            limit,
            lambda c: c.compute.aggregates(),
        )

    @reg.read("list_network_agents", "List network agents", note=_NOTE)
    def list_network_agents(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        host: str | None = None,
        agent_type: str | None = None,
    ) -> ListResult[NetworkAgent]:
        """List Neutron agents with host and liveness."""
        return run(
            NetworkAgent,
            "network_agents",
            project_id,
            limit,
            lambda c: c.network.agents(**filters(host=host, agent_type=agent_type)),
        )

    @reg.read("list_volume_services", "List volume services", note=_NOTE)
    def list_volume_services(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        host: str | None = None,
        binary: str | None = None,
    ) -> ListResult[VolumeService]:
        """List Cinder services such as cinder-volume, with host and state."""
        return run(
            VolumeService,
            "volume_services",
            project_id,
            limit,
            lambda c: c.block_storage.services(**filters(host=host, binary=binary)),
        )
