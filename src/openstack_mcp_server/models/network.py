from pydantic import AliasChoices, Field

from . import Model


class AllocationPool(Model):
    start: str
    end: str


class HostRoute(Model):
    destination: str
    nexthop: str


class FixedIP(Model):
    subnet_id: str | None = None
    ip_address: str | None = None


class AddressPair(Model):
    ip_address: str
    mac_address: str | None = None


class Network(Model):
    id: str
    name: str | None = None
    status: str | None = None
    description: str | None = None
    project_id: str | None = None
    is_admin_state_up: bool | None = None
    is_shared: bool | None = None
    is_router_external: bool | None = None
    mtu: int | None = None
    subnet_ids: list[str] | None = None
    availability_zones: list[str] | None = None
    provider_network_type: str | None = None
    provider_physical_network: str | None = None
    provider_segmentation_id: int | None = None


class Subnet(Model):
    id: str
    name: str | None = None
    description: str | None = None
    project_id: str | None = None
    network_id: str | None = None
    cidr: str | None = None
    ip_version: int | None = None
    gateway_ip: str | None = None
    is_dhcp_enabled: bool | None = None
    allocation_pools: list[AllocationPool] | None = None
    dns_nameservers: list[str] | None = None
    host_routes: list[HostRoute] | None = None


class Port(Model):
    id: str
    name: str | None = None
    status: str | None = None
    description: str | None = None
    project_id: str | None = None
    network_id: str | None = None
    is_admin_state_up: bool | None = None
    device_id: str | None = None
    device_owner: str | None = None
    mac_address: str | None = None
    fixed_ips: list[FixedIP] | None = None
    security_group_ids: list[str] | None = None
    allowed_address_pairs: list[AddressPair] | None = None


class ExternalGatewayInfo(Model):
    network_id: str | None = None
    enable_snat: bool | None = None
    external_fixed_ips: list[FixedIP] | None = None


class Router(Model):
    id: str
    name: str | None = None
    status: str | None = None
    description: str | None = None
    project_id: str | None = None
    is_admin_state_up: bool | None = None
    external_gateway_info: ExternalGatewayInfo | None = None
    is_distributed: bool | None = None
    is_ha: bool | None = None
    routes: list[HostRoute] | None = None


class RouterInterface(Model):
    router_id: str
    port_id: str
    subnet_id: str | None = None
    ip_address: str | None = None


class FloatingIP(Model):
    id: str
    status: str | None = None
    description: str | None = None
    project_id: str | None = None
    floating_ip_address: str | None = None
    floating_network_id: str | None = None
    fixed_ip_address: str | None = None
    port_id: str | None = None
    router_id: str | None = None


class SecurityGroupRule(Model):
    id: str
    direction: str | None = None
    ether_type: str | None = Field(
        default=None, validation_alias=AliasChoices("ether_type", "ethertype")
    )
    protocol: str | None = None
    port_range_min: int | None = None
    port_range_max: int | None = None
    remote_ip_prefix: str | None = None
    remote_group_id: str | None = None
    description: str | None = None


class SecurityGroup(Model):
    id: str
    name: str | None = None
    description: str | None = None
    project_id: str | None = None
    stateful: bool | None = None
    security_group_rules: list[SecurityGroupRule] | None = None
