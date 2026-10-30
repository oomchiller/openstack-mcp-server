# Changelog

## 0.1.0 (unreleased)

First release of this fork of `openstack-kr/python-openstackmcp-server` at
`eba3e6f`.

- Renamed distribution, command and image to `openstack-mcp-server`.
- Read-only by default; write tools are registered only with
  `OPENSTACK_MCP_MODE=admin` and `OPENSTACK_MCP_ENABLE_WRITE_TOOLS=true`.
- Removed `get_cloud_config`, `get_cloud_names`, `get_cloud_name`,
  `set_cloud_name`, identity writes, `set_port_binding`,
  `create_floating_ips_bulk` and `assign_first_available_floating_ip`.
- Renamed tools to `list_*` / `get_*` (for example `get_volumes` →
  `list_volumes`, `get_network_detail` → `get_network`, `action_server` →
  `server_action`).
- Added `get_scope`, service inventory tools and catalog tools.
- Added project allowlist with per-project sessions, `limit`/`marker` paging
  with `complete` and `next_marker`, response size limit, typed results,
  categorized errors, server instructions, prompt and resource switches.
- Configuration through `OS_*`/`clouds.yaml` and `OPENSTACK_MCP_*`; dropped
  `CLOUD_NAME`, `TRANSPORT` and `DEBUG_MODE`. Added
  `OPENSTACK_MCP_CACERT_PEM`.
- Replaced `fastmcp` with the `mcp` SDK, setuptools-scm with a static version,
  and tox/requirements files with `uv`.
- Container image on GHCR; the PyPI release workflow was removed.
