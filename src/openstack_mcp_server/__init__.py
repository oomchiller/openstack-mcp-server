"""MCP server for OpenStack clouds, read-only by default."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("openstack-mcp-server")
except PackageNotFoundError:  # pragma: no cover - source tree without metadata
    __version__ = "0.0.0"
