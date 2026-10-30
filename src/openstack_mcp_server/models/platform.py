"""Identity and service inventory. Only the declared fields are exported."""

from . import Model


class Region(Model):
    id: str
    description: str | None = None
    parent_region_id: str | None = None


class Domain(Model):
    id: str
    name: str | None = None
    description: str | None = None
    is_enabled: bool | None = None


class Project(Model):
    id: str
    name: str | None = None
    description: str | None = None
    is_enabled: bool | None = None
    domain_id: str | None = None
    parent_id: str | None = None


class CatalogService(Model):
    id: str
    name: str | None = None
    type: str | None = None
    description: str | None = None
    is_enabled: bool | None = None


class Endpoint(Model):
    id: str
    service_id: str | None = None
    region_id: str | None = None
    interface: str | None = None
    url: str | None = None
    is_enabled: bool | None = None


class Hypervisor(Model):
    id: str
    name: str | None = None
    hypervisor_type: str | None = None
    hypervisor_version: int | None = None
    state: str | None = None
    status: str | None = None
    vcpus: int | None = None
    vcpus_used: int | None = None
    memory_size: int | None = None
    memory_used: int | None = None
    local_disk_size: int | None = None
    running_vms: int | None = None


class ComputeService(Model):
    id: str | None = None
    binary: str | None = None
    host: str | None = None
    availability_zone: str | None = None
    state: str | None = None
    status: str | None = None
    updated_at: str | None = None


class Aggregate(Model):
    id: str
    name: str | None = None
    availability_zone: str | None = None
    hosts: list[str] | None = None


class NetworkAgent(Model):
    id: str
    agent_type: str | None = None
    binary: str | None = None
    host: str | None = None
    availability_zone: str | None = None
    is_alive: bool | None = None
    is_admin_state_up: bool | None = None


class VolumeService(Model):
    binary: str | None = None
    host: str | None = None
    availability_zone: str | None = None
    state: str | None = None
    status: str | None = None
    updated_at: str | None = None
