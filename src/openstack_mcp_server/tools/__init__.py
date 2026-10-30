"""Tool tables. Write tools are registered only when both gates are open (RO-2)."""

from typing import Literal

from pydantic import Field

from .. import __version__
from ..models import Model
from . import block_storage, compute, image, network, platform
from .base import Registrar

_READ = (compute, image, block_storage, network, platform)
_WRITE = (compute, image, block_storage, network)


class Limits(Model):
    default_limit: int
    max_limit: int
    max_response_bytes: int
    api_timeout_seconds: int


class Scope(Model):
    server_version: str
    mode: Literal["readonly", "admin"]
    write_tools_registered: bool
    configured: bool
    reason: str | None = Field(
        description="Why the cloud is not usable: missing_credentials, "
        "insecure_transport or invalid_cloud_config."
    )
    credential_source: str
    region_name: str | None
    interface: str | None
    tls: Literal["system", "file", "pem"]
    project_ids: list[str] = Field(description="Allowlisted projects; empty if none.")
    default_project_id: str | None = Field(
        description="Project used when project_id is omitted; null when the "
        "configuration names the project only by name."
    )
    limits: Limits
    cloud_access_verified: bool = Field(
        description="Always false: get_scope does not contact the cloud."
    )


def scope_document(reg: Registrar) -> Scope:
    settings, state = reg.settings, reg.cloud.state
    return Scope(
        server_version=__version__,
        mode=settings.mode,
        write_tools_registered=settings.write_tools_registered,
        configured=state.configured,
        reason=state.reason,
        credential_source=state.source,
        region_name=state.region_name,
        interface=state.interface,
        tls=state.tls,
        project_ids=list(settings.project_ids),
        default_project_id=reg.cloud.default_project_id,
        limits=Limits(
            default_limit=settings.default_limit,
            max_limit=settings.max_limit,
            max_response_bytes=settings.max_response_bytes,
            api_timeout_seconds=settings.api_timeout,
        ),
        cloud_access_verified=False,
    )


def register(reg: Registrar) -> None:
    @reg.read("get_scope", "Show server scope", cloud=False)
    def get_scope() -> Scope:
        """Show mode, allowed projects, limits and whether credentials are configured.

        Does not contact the cloud. Call it first.
        """
        return scope_document(reg)

    for module in _READ:
        module.register_read(reg)
    if reg.settings.write_tools_registered:
        for module in _WRITE:
            module.register_write(reg)
