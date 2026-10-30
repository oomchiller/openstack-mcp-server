"""FastMCP server assembly: instructions, tools, prompts and resources."""

from mcp.server.fastmcp import FastMCP

from .cloud import Cloud
from .tools import register, scope_document
from .tools.base import Registrar

INSTRUCTIONS = """\
OpenStack inventory over MCP. Read-only unless the operator enabled write tools.
Call get_scope first: it lists the allowed project IDs, limits and whether
credentials are configured, without contacting the cloud.
Every cloud tool takes an optional project_id; omit it for the default project.
List tools return items with complete and next_marker. When complete is false,
pass next_marker as marker to read the next page, or narrow the filters.
Errors start with a category in brackets. [forbidden] means the identity lacks a
role for that call; it does not mean the inventory is empty. Do not retry
[forbidden], [auth_failed] or [not_configured].
"""


def build_server(cloud: Cloud) -> FastMCP:
    settings = cloud.settings
    server = FastMCP(
        "openstack-mcp-server",
        instructions=INSTRUCTIONS,
        host=settings.http_host,
        port=settings.http_port,
        log_level=settings.log_level,
        warn_on_duplicate_tools=False,
    )
    reg = Registrar(server, cloud)
    register(reg)

    if settings.enable_resources:

        @server.resource(
            "openstack://scope",
            name="scope",
            title="Server scope",
            description="Same document as the get_scope tool.",
            mime_type="application/json",
        )
        def scope_resource() -> str:
            return scope_document(reg).model_dump_json(indent=2)

    if settings.enable_prompts:

        @server.prompt(
            name="find_servers_by_security_group",
            title="Find servers by security group",
        )
        def find_servers_by_security_group(security_group_name: str) -> str:
            """Find servers that have a security group attached."""
            return (
                f"Find all servers that have the security group "
                f"'{security_group_name}' attached.\n\n"
                "Steps:\n"
                "1. Call get_scope and pick the project_id to search.\n"
                "2. Call list_servers for that project. While complete is false, "
                "call it again with marker set to next_marker.\n"
                "3. Keep servers whose security_groups contain an entry named "
                f"'{security_group_name}'.\n"
                "4. For each match show name, ID, status and all its security groups."
            )

    return server
