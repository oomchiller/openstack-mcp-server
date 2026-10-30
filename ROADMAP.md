# Roadmap

## 0.1.0

- Implement `docs/SPEC.md`: configuration, read-only default, project
  allowlist, bounded typed results, error categories, prompt and resource
  switches, stdio and Streamable HTTP.
- Replace `fastmcp` with the `mcp` SDK, `setuptools-scm` with a static
  version, `tox`/`requirements*.txt`/pre-commit export with `uv` only.
- Strict mypy, ruff lint and format, pytest with coverage in CI.
- Image in `ghcr.io/oomchiller/openstack-mcp-server`, published from
  `vX.Y.Z` tags; the upstream PyPI release workflow is removed.

## Before 1.0

- Validate the read surface against at least one live cloud per supported
  OpenStack release and record it in `docs/COMPATIBILITY.md`.
- Exercise write tools against a non-production cloud; until then they stay
  experimental.
- Decide on `mcp` 2.x.

## Short-term improvements

- `get_identity`: token user, project and role names for the current session,
  so an agent can check that it runs with a reader role.
- Marker paging for APIs that support it but are not wired yet.
- Optional system-scoped session for platform tools on clouds whose policy
  requires system scope.
- More services as read tools: Placement, Octavia, Heat, Swift containers.
- Instance-scoped resource URIs so resources need not be disabled in
  multi-instance gateways.

## Not planned

- Raw API passthrough or arbitrary SDK method calls.
- Cloud switching at runtime.
- Built-in authentication for the HTTP transport; put it behind a proxy.
- A CMDB or cross-provider inventory.
