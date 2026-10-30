"""Network (Neutron) tools. Lists are filtered to the session project (SCOPE-5)."""

from collections.abc import Iterator
from typing import Annotated, Any, Literal

from pydantic import Field

from ..errors import ToolFailure
from ..models import as_mapping, convert
from ..models.network import (
    FloatingIP,
    Network,
    Port,
    Router,
    RouterInterface,
    SecurityGroup,
    Subnet,
)
from ..paging import ListResult, list_result
from .base import ActionResult, Registrar, filters, page_query

NetworkStatus = Literal["ACTIVE", "DOWN", "BUILD", "ERROR"]
FloatingIPStatus = Literal["ACTIVE", "DOWN", "ERROR"]
RouterStatus = Literal["ACTIVE", "ALLOCATING", "ERROR"]
IpVersion = Literal[4, 6]
Id = Annotated[str, Field(min_length=1, max_length=255)]
_INTERFACE_OWNERS = (
    "network:router_interface",
    "network:router_interface_distributed",
    "network:ha_router_replicated_interface",
)


def register_read(reg: Registrar) -> None:
    @reg.read("list_networks", "List networks")
    def list_networks(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        marker: Annotated[str | None, reg.marker] = None,
        status: NetworkStatus | None = None,
        shared: Annotated[
            bool,
            Field(
                description="List shared networks visible to the project, "
                "whatever their owner, instead of the project's own networks."
            ),
        ] = False,
    ) -> ListResult[Network]:
        """List the project's networks, or shared networks with shared=true.

        Paged with limit and marker.
        """
        pid, conn = reg.cloud.connection(project_id)
        scope: dict[str, Any] = {"is_shared": True} if shared else {"project_id": pid}
        query = page_query(limit, marker, status=status, **scope)
        return list_result(
            Network,
            "networks",
            pid,
            limit,
            conn.network.networks(**query),
            markers=True,
        )

    @reg.read("get_network", "Get network")
    def get_network(
        network_id: Id, project_id: Annotated[str | None, reg.project] = None
    ) -> Network:
        """Get one network by ID."""
        _, conn = reg.cloud.connection(project_id)
        return convert(Network, conn.network.get_network(network_id))

    @reg.read("list_subnets", "List subnets")
    def list_subnets(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        marker: Annotated[str | None, reg.marker] = None,
        network_id: str | None = None,
        ip_version: IpVersion | None = None,
    ) -> ListResult[Subnet]:
        """List the project's subnets with CIDR, gateway and DHCP settings.

        Paged with limit and marker.
        """
        pid, conn = reg.cloud.connection(project_id)
        query = page_query(
            limit, marker, project_id=pid, network_id=network_id, ip_version=ip_version
        )
        return list_result(
            Subnet, "subnets", pid, limit, conn.network.subnets(**query), markers=True
        )

    @reg.read("get_subnet", "Get subnet")
    def get_subnet(
        subnet_id: Id, project_id: Annotated[str | None, reg.project] = None
    ) -> Subnet:
        """Get one subnet by ID."""
        _, conn = reg.cloud.connection(project_id)
        return convert(Subnet, conn.network.get_subnet(subnet_id))

    @reg.read("list_ports", "List ports")
    def list_ports(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        marker: Annotated[str | None, reg.marker] = None,
        network_id: str | None = None,
        device_id: Annotated[
            str | None, Field(description="Server or router ID owning the port.")
        ] = None,
        status: NetworkStatus | None = None,
    ) -> ListResult[Port]:
        """List the project's ports with fixed IPs and security groups.

        Paged with limit and marker.
        """
        pid, conn = reg.cloud.connection(project_id)
        query = page_query(
            limit,
            marker,
            project_id=pid,
            network_id=network_id,
            device_id=device_id,
            status=status,
        )
        return list_result(
            Port, "ports", pid, limit, conn.network.ports(**query), markers=True
        )

    @reg.read("get_port", "Get port")
    def get_port(
        port_id: Id, project_id: Annotated[str | None, reg.project] = None
    ) -> Port:
        """Get one port by ID, including allowed address pairs."""
        _, conn = reg.cloud.connection(project_id)
        return convert(Port, conn.network.get_port(port_id))

    @reg.read("list_floating_ips", "List floating IPs")
    def list_floating_ips(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        marker: Annotated[str | None, reg.marker] = None,
        status: FloatingIPStatus | None = None,
        port_id: str | None = None,
        floating_network_id: str | None = None,
    ) -> ListResult[FloatingIP]:
        """List the project's floating IPs and the ports they map to.

        Paged with limit and marker.
        """
        pid, conn = reg.cloud.connection(project_id)
        query = page_query(
            limit,
            marker,
            project_id=pid,
            status=status,
            port_id=port_id,
            floating_network_id=floating_network_id,
        )
        return list_result(
            FloatingIP,
            "floating_ips",
            pid,
            limit,
            conn.network.ips(**query),
            markers=True,
        )

    @reg.read("list_routers", "List routers")
    def list_routers(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        marker: Annotated[str | None, reg.marker] = None,
        status: RouterStatus | None = None,
    ) -> ListResult[Router]:
        """List the project's routers with gateway and static routes.

        Paged with limit and marker.
        """
        pid, conn = reg.cloud.connection(project_id)
        query = page_query(limit, marker, project_id=pid, status=status)
        return list_result(
            Router, "routers", pid, limit, conn.network.routers(**query), markers=True
        )

    @reg.read("get_router", "Get router")
    def get_router(
        router_id: Id, project_id: Annotated[str | None, reg.project] = None
    ) -> Router:
        """Get one router by ID."""
        _, conn = reg.cloud.connection(project_id)
        return convert(Router, conn.network.get_router(router_id))

    @reg.read("list_router_interfaces", "List router interfaces")
    def list_router_interfaces(
        router_id: Id,
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
    ) -> ListResult[RouterInterface]:
        """List a router's internal interfaces: port, subnet and IP address.

        Not paged; complete=false means the router has more interfaces.
        """
        pid, conn = reg.cloud.connection(project_id)
        ports = conn.network.ports(device_id=router_id)
        return list_result(
            RouterInterface,
            "router_interfaces",
            pid,
            limit,
            _interfaces(router_id, ports),
            markers=False,
        )

    @reg.read("list_security_groups", "List security groups")
    def list_security_groups(
        project_id: Annotated[str | None, reg.project] = None,
        limit: Annotated[int, reg.limit] = reg.default_limit,
        marker: Annotated[str | None, reg.marker] = None,
        name: Annotated[str | None, Field(max_length=255)] = None,
    ) -> ListResult[SecurityGroup]:
        """List the project's security groups with their rules.

        Paged with limit and marker.
        """
        pid, conn = reg.cloud.connection(project_id)
        query = page_query(limit, marker, project_id=pid, name=name)
        return list_result(
            SecurityGroup,
            "security_groups",
            pid,
            limit,
            conn.network.security_groups(**query),
            markers=True,
        )

    @reg.read("get_security_group", "Get security group")
    def get_security_group(
        security_group_id: Id, project_id: Annotated[str | None, reg.project] = None
    ) -> SecurityGroup:
        """Get one security group by ID with its rules."""
        _, conn = reg.cloud.connection(project_id)
        return convert(
            SecurityGroup, conn.network.get_security_group(security_group_id)
        )


def _interfaces(router_id: str, ports: Any) -> Iterator[dict[str, Any]]:
    for port in ports:
        data = as_mapping(port)
        if data.get("device_owner") not in _INTERFACE_OWNERS:
            continue
        for fixed in data.get("fixed_ips") or [{}]:
            yield {
                "router_id": router_id,
                "port_id": data.get("id"),
                "subnet_id": fixed.get("subnet_id"),
                "ip_address": fixed.get("ip_address"),
            }


def register_write(reg: Registrar) -> None:
    project = reg.project

    @reg.write("create_network", "Create network", destructive=False, idempotent=False)
    def create_network(
        name: Id,
        project_id: Annotated[str | None, project] = None,
        description: str | None = None,
        is_admin_state_up: bool = True,
    ) -> Network:
        """Create a network in the project."""
        _, conn = reg.cloud.connection(project_id)
        created = conn.network.create_network(
            **filters(
                name=name,
                description=description,
                is_admin_state_up=is_admin_state_up,
            )
        )
        return convert(Network, created)

    @reg.write("update_network", "Update network", destructive=False, idempotent=True)
    def update_network(
        network_id: Id,
        project_id: Annotated[str | None, project] = None,
        name: str | None = None,
        description: str | None = None,
        is_admin_state_up: bool | None = None,
    ) -> Network:
        """Change a network's name, description or admin state."""
        _, conn = reg.cloud.connection(project_id)
        updated = conn.network.update_network(
            network_id,
            **filters(
                name=name, description=description, is_admin_state_up=is_admin_state_up
            ),
        )
        return convert(Network, updated)

    @reg.write("delete_network", "Delete network", destructive=True, idempotent=True)
    def delete_network(
        network_id: Id, project_id: Annotated[str | None, project] = None
    ) -> ActionResult:
        """Delete a network. It must have no ports in use."""
        pid, conn = reg.cloud.connection(project_id)
        conn.network.delete_network(network_id, ignore_missing=False)
        return ActionResult(
            resource="network", id=network_id, action="delete", project_id=pid
        )

    @reg.write("create_subnet", "Create subnet", destructive=False, idempotent=False)
    def create_subnet(
        network_id: Id,
        cidr: Annotated[str, Field(max_length=64)],
        project_id: Annotated[str | None, project] = None,
        name: str | None = None,
        ip_version: IpVersion = 4,
        gateway_ip: str | None = None,
        is_dhcp_enabled: bool = True,
        dns_nameservers: list[str] | None = None,
    ) -> Subnet:
        """Create a subnet on a network."""
        _, conn = reg.cloud.connection(project_id)
        created = conn.network.create_subnet(
            **filters(
                network_id=network_id,
                cidr=cidr,
                name=name,
                ip_version=ip_version,
                gateway_ip=gateway_ip,
                is_dhcp_enabled=is_dhcp_enabled,
                dns_nameservers=dns_nameservers,
            )
        )
        return convert(Subnet, created)

    @reg.write("update_subnet", "Update subnet", destructive=False, idempotent=True)
    def update_subnet(
        subnet_id: Id,
        project_id: Annotated[str | None, project] = None,
        name: str | None = None,
        description: str | None = None,
        is_dhcp_enabled: bool | None = None,
        dns_nameservers: list[str] | None = None,
    ) -> Subnet:
        """Change a subnet's name, description, DHCP or DNS servers."""
        _, conn = reg.cloud.connection(project_id)
        updated = conn.network.update_subnet(
            subnet_id,
            **filters(
                name=name,
                description=description,
                is_dhcp_enabled=is_dhcp_enabled,
                dns_nameservers=dns_nameservers,
            ),
        )
        return convert(Subnet, updated)

    @reg.write("delete_subnet", "Delete subnet", destructive=True, idempotent=True)
    def delete_subnet(
        subnet_id: Id, project_id: Annotated[str | None, project] = None
    ) -> ActionResult:
        """Delete a subnet. It must have no allocated IPs in use."""
        pid, conn = reg.cloud.connection(project_id)
        conn.network.delete_subnet(subnet_id, ignore_missing=False)
        return ActionResult(
            resource="subnet", id=subnet_id, action="delete", project_id=pid
        )

    @reg.write("create_port", "Create port", destructive=False, idempotent=False)
    def create_port(
        network_id: Id,
        project_id: Annotated[str | None, project] = None,
        name: str | None = None,
        description: str | None = None,
        subnet_id: Annotated[
            str | None, Field(description="Allocate the fixed IP from this subnet.")
        ] = None,
        ip_address: Annotated[
            str | None, Field(description="Request this fixed IP address.")
        ] = None,
        security_group_ids: list[str] | None = None,
    ) -> Port:
        """Create a port on a network, optionally with a fixed IP."""
        _, conn = reg.cloud.connection(project_id)
        fixed = filters(subnet_id=subnet_id, ip_address=ip_address)
        created = conn.network.create_port(
            **filters(
                network_id=network_id,
                name=name,
                description=description,
                fixed_ips=[fixed] if fixed else None,
                security_group_ids=security_group_ids,
            )
        )
        return convert(Port, created)

    @reg.write("update_port", "Update port", destructive=False, idempotent=True)
    def update_port(
        port_id: Id,
        project_id: Annotated[str | None, project] = None,
        name: str | None = None,
        description: str | None = None,
        is_admin_state_up: bool | None = None,
        security_group_ids: list[str] | None = None,
    ) -> Port:
        """Change a port's name, description, admin state or security groups."""
        _, conn = reg.cloud.connection(project_id)
        updated = conn.network.update_port(
            port_id,
            **filters(
                name=name,
                description=description,
                is_admin_state_up=is_admin_state_up,
                security_group_ids=security_group_ids,
            ),
        )
        return convert(Port, updated)

    @reg.write("delete_port", "Delete port", destructive=True, idempotent=True)
    def delete_port(
        port_id: Id, project_id: Annotated[str | None, project] = None
    ) -> ActionResult:
        """Delete a port."""
        pid, conn = reg.cloud.connection(project_id)
        conn.network.delete_port(port_id, ignore_missing=False)
        return ActionResult(
            resource="port", id=port_id, action="delete", project_id=pid
        )

    @reg.write(
        "create_floating_ip", "Create floating IP", destructive=False, idempotent=False
    )
    def create_floating_ip(
        floating_network_id: Id,
        project_id: Annotated[str | None, project] = None,
        port_id: Annotated[
            str | None, Field(description="Associate the address with this port.")
        ] = None,
        description: str | None = None,
    ) -> FloatingIP:
        """Allocate a floating IP from an external network."""
        _, conn = reg.cloud.connection(project_id)
        created = conn.network.create_ip(
            **filters(
                floating_network_id=floating_network_id,
                port_id=port_id,
                description=description,
            )
        )
        return convert(FloatingIP, created)

    @reg.write(
        "update_floating_ip", "Update floating IP", destructive=False, idempotent=True
    )
    def update_floating_ip(
        floating_ip_id: Id,
        project_id: Annotated[str | None, project] = None,
        port_id: Annotated[
            str | None, Field(description="Associate with this port.")
        ] = None,
        disassociate: Annotated[
            bool, Field(description="Remove the port association.")
        ] = False,
        description: str | None = None,
    ) -> FloatingIP:
        """Associate a floating IP with a port, or disassociate it."""
        if disassociate and port_id is not None:
            raise ToolFailure(
                "invalid_argument", "Give port_id or disassociate, not both"
            )
        _, conn = reg.cloud.connection(project_id)
        changes = filters(port_id=port_id, description=description)
        if disassociate:
            changes["port_id"] = None
        return convert(FloatingIP, conn.network.update_ip(floating_ip_id, **changes))

    @reg.write(
        "delete_floating_ip", "Delete floating IP", destructive=True, idempotent=True
    )
    def delete_floating_ip(
        floating_ip_id: Id, project_id: Annotated[str | None, project] = None
    ) -> ActionResult:
        """Release a floating IP back to the pool."""
        pid, conn = reg.cloud.connection(project_id)
        conn.network.delete_ip(floating_ip_id, ignore_missing=False)
        return ActionResult(
            resource="floating_ip", id=floating_ip_id, action="delete", project_id=pid
        )

    @reg.write("create_router", "Create router", destructive=False, idempotent=False)
    def create_router(
        name: Id,
        project_id: Annotated[str | None, project] = None,
        description: str | None = None,
        external_network_id: Annotated[
            str | None, Field(description="Set the gateway on this external network.")
        ] = None,
    ) -> Router:
        """Create a router, optionally with an external gateway."""
        _, conn = reg.cloud.connection(project_id)
        gateway = {"network_id": external_network_id} if external_network_id else None
        created = conn.network.create_router(
            **filters(name=name, description=description, external_gateway_info=gateway)
        )
        return convert(Router, created)

    @reg.write("update_router", "Update router", destructive=False, idempotent=True)
    def update_router(
        router_id: Id,
        project_id: Annotated[str | None, project] = None,
        name: str | None = None,
        description: str | None = None,
        external_network_id: Annotated[
            str | None, Field(description="Move the gateway to this network.")
        ] = None,
        clear_gateway: bool = False,
    ) -> Router:
        """Change a router's name, description or external gateway."""
        if clear_gateway and external_network_id is not None:
            raise ToolFailure(
                "invalid_argument",
                "Give external_network_id or clear_gateway, not both",
            )
        _, conn = reg.cloud.connection(project_id)
        changes = filters(name=name, description=description)
        if external_network_id is not None:
            changes["external_gateway_info"] = {"network_id": external_network_id}
        if clear_gateway:
            changes["external_gateway_info"] = {}
        return convert(Router, conn.network.update_router(router_id, **changes))

    @reg.write("delete_router", "Delete router", destructive=True, idempotent=True)
    def delete_router(
        router_id: Id, project_id: Annotated[str | None, project] = None
    ) -> ActionResult:
        """Delete a router. It must have no interfaces."""
        pid, conn = reg.cloud.connection(project_id)
        conn.network.delete_router(router_id, ignore_missing=False)
        return ActionResult(
            resource="router", id=router_id, action="delete", project_id=pid
        )

    @reg.write(
        "add_router_interface",
        "Add router interface",
        destructive=False,
        idempotent=False,
    )
    def add_router_interface(
        router_id: Id,
        project_id: Annotated[str | None, project] = None,
        subnet_id: str | None = None,
        port_id: str | None = None,
    ) -> ActionResult:
        """Connect a subnet or port to a router. Give exactly one of them."""
        if (subnet_id is None) == (port_id is None):
            raise ToolFailure(
                "invalid_argument", "Give exactly one of subnet_id and port_id"
            )
        pid, conn = reg.cloud.connection(project_id)
        conn.network.add_interface_to_router(
            router_id, **filters(subnet_id=subnet_id, port_id=port_id)
        )
        return ActionResult(
            resource="router", id=router_id, action="add_interface", project_id=pid
        )

    @reg.write(
        "remove_router_interface",
        "Remove router interface",
        destructive=True,
        idempotent=False,
    )
    def remove_router_interface(
        router_id: Id,
        project_id: Annotated[str | None, project] = None,
        subnet_id: str | None = None,
        port_id: str | None = None,
    ) -> ActionResult:
        """Disconnect a subnet or port from a router. Give exactly one of them."""
        if (subnet_id is None) == (port_id is None):
            raise ToolFailure(
                "invalid_argument", "Give exactly one of subnet_id and port_id"
            )
        pid, conn = reg.cloud.connection(project_id)
        conn.network.remove_interface_from_router(
            router_id, **filters(subnet_id=subnet_id, port_id=port_id)
        )
        return ActionResult(
            resource="router", id=router_id, action="remove_interface", project_id=pid
        )

    @reg.write(
        "create_security_group",
        "Create security group",
        destructive=False,
        idempotent=False,
    )
    def create_security_group(
        name: Id,
        project_id: Annotated[str | None, project] = None,
        description: str | None = None,
    ) -> SecurityGroup:
        """Create a security group with the default egress rules."""
        _, conn = reg.cloud.connection(project_id)
        created = conn.network.create_security_group(
            **filters(name=name, description=description)
        )
        return convert(SecurityGroup, created)

    @reg.write(
        "update_security_group",
        "Update security group",
        destructive=False,
        idempotent=True,
    )
    def update_security_group(
        security_group_id: Id,
        project_id: Annotated[str | None, project] = None,
        name: str | None = None,
        description: str | None = None,
    ) -> SecurityGroup:
        """Change a security group's name or description."""
        _, conn = reg.cloud.connection(project_id)
        updated = conn.network.update_security_group(
            security_group_id, **filters(name=name, description=description)
        )
        return convert(SecurityGroup, updated)

    @reg.write(
        "delete_security_group",
        "Delete security group",
        destructive=True,
        idempotent=True,
    )
    def delete_security_group(
        security_group_id: Id, project_id: Annotated[str | None, project] = None
    ) -> ActionResult:
        """Delete a security group that no port uses."""
        pid, conn = reg.cloud.connection(project_id)
        conn.network.delete_security_group(security_group_id, ignore_missing=False)
        return ActionResult(
            resource="security_group",
            id=security_group_id,
            action="delete",
            project_id=pid,
        )
