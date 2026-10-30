# Decisions

## Decision: Fork With Full Upstream History

Rationale:

- Upstream `openstack-kr/python-openstackmcp-server` has had no commits since
  2026-04-04 (`eba3e6f`, head of `develop`).
- Keeping its history makes authorship and the Apache-2.0 obligations
  traceable.

Enforcement:

- Upstream commits are not rewritten. Tag `upstream-eba3e6f` marks the base.
- `LICENSE` stays Apache-2.0; `NOTICE` names the base and the modifications.
- Upstream release tags (`v0.0.0.dev1`, `v0.0.1.alpha`, `v1.0.0`) are not
  published here, so this project's own `v0.1.0` is not ordered below an
  unrelated upstream `v1.0.0`.

## Decision: Read-Only By Default, Writes Not Registered

Rationale:

- Agents choose tools from `tools/list`. A tool that is listed but refuses at
  runtime still invites calls, retries and prompt-injection attempts.

Enforcement:

- Write tools are registered only with `OPENSTACK_MCP_MODE=admin` and
  `OPENSTACK_MCP_ENABLE_WRITE_TOOLS=true` (SPEC RO-2).
- `OPENSTACK_MCP_ENABLE_WRITE_TOOLS=true` in `readonly` mode is a startup
  error rather than a silent no-op.

Tradeoff:

- Unlike `nexus-mcp-server`, there is no runtime gate on visible write tools;
  visibility is the gate.

## Decision: The Keystone Role Is The Security Boundary

Rationale:

- The server cannot prevent a credential from being used elsewhere, and a
  code defect could reach a write call.

Consequence:

- Documentation tells operators to use an identity with only the `reader`
  role on the intended projects. Read-only mode is described as a
  convenience, not as protection.

## Decision: Configuration Through OpenStack's Own Mechanisms

Rationale:

- `clouds.yaml`, `OS_CLOUD` and `OS_*` are what OpenStack users already have,
  and openstacksdk resolves them, including application credentials.
- Container gateways pass secrets as environment variables; `OS_*` covers
  that without a server-specific credential format.

Enforcement:

- The server defines no credential variables of its own. Server behaviour uses
  the `OPENSTACK_MCP_` prefix.
- The upstream `CLOUD_NAME`, `TRANSPORT` and `DEBUG_MODE` variables are
  dropped.

Rejected:

- A single JSON credential variable. It duplicates `OS_*` and requires custom validation of auth fields.

## Decision: CA Bundle As Environment Content

Rationale:

- Docker MCP Gateway passes secrets and settings as environment variables but
  does not mount arbitrary host paths, and containers do not inherit a host's
  corporate trust store.

Enforcement:

- `OPENSTACK_MCP_CACERT_PEM` is written to a private temporary file at
  startup and used as the CA bundle (SPEC CFG-6). `OS_CACERT` keeps working.

Tradeoff:

- The PEM bundle replaces the system trust store for OpenStack API calls; a
  cloud with a public certificate does not need it.

## Decision: Project Allowlist With Per-Project Sessions

Rationale:

- Reader roles are usually granted per project. A project-scoped token per
  project is the narrowest Keystone scope that still covers several projects.
- An allowlist turns "which projects may the agent see" into explicit
  operator configuration instead of whatever the identity happens to reach.

Enforcement:

- `OPENSTACK_MCP_PROJECT_IDS` (SPEC SCOPE). Without it, only the configured
  project is reachable.
- Tools never pass `all_projects`.

## Decision: Bounded, Typed Results

Rationale:

- Real clouds return thousands of ports or images. Unbounded lists exhaust
  agent context and server memory.
- Typed models give clients an `outputSchema` and keep credentials and
  unrelated attributes out of results.

Enforcement:

- `limit` with a configured ceiling, `limit + 1` consumption, `complete` and
  `next_marker`, and a byte ceiling (SPEC OUT).
- Platform resources export declared fields only.

## Decision: Official MCP SDK Instead Of `fastmcp`

Rationale:

- Upstream depends on `fastmcp>=2.11.3` without an upper bound; `fastmcp`
  has since released incompatible 3.x and 4.x lines; the last 2.x release
  is 2.14.7 (2026-04-13).
- `mcp` 1.x (`mcp.server.fastmcp`) provides tool annotations, structured
  output, instructions, prompts, resources, stdio and Streamable HTTP, with
  fewer transitive dependencies, and is what `nexus-mcp-server` uses.

Enforcement:

- `mcp>=1.27,<2`; exact version in `uv.lock`.

Tradeoff:

- Upstream's middleware (`ErrorHandlingMiddleware`, `LoggingMiddleware`) is
  replaced by the server's own error mapping and call logging. Moving to
  `mcp` 2.x is a separate decision.

## Decision: Consistent Tool Names For 0.1.0

Rationale:

- Upstream names mix `get_volumes`, `get_volume_details`,
  `get_network_detail` and `get_server`. 0.1.0 is the first public surface of
  this project, so the cost of renaming is lowest now.

Enforcement:

- `list_<plural>` for collections, `get_<singular>` for one resource,
  `<verb>_<singular>` for writes (SPEC TOOL-1).
- Names are stable within 0.x patch releases; renames are listed in
  `CHANGELOG.md`.

## Decision: Narrower Write Surface Than Upstream

Rationale:

- Region, domain and project management, port binding and bulk floating IP
  allocation are cloud-administrator operations. They do not fit a project
  reader or member identity and are hard to scope with a project allowlist.

Enforcement:

- These upstream tools are not carried over (SPEC TOOL-2). They can return in
  a later release with tests and a scope model.

## Decision: Prompts And Resources Behind Switches

Rationale:

- Docker MCP Gateway prefixes tool names per server but not prompt names or
  resource URIs; several instances of this server collide and duplicate them.

Enforcement:

- `OPENSTACK_MCP_ENABLE_PROMPTS` and `OPENSTACK_MCP_ENABLE_RESOURCES`, both
  default `true`, as in `nexus-mcp-server`. Tool names and schemas never
  depend on them.

## Decision: Stdio First, HTTP Local By Default

Rationale:

- stdio needs no network listener and suits local clients and container
  gateways.

Enforcement:

- `stdio` is the default. Streamable HTTP binds to loopback unless
  `OPENSTACK_MCP_HTTP_ALLOW_REMOTE=true`, because it has no authentication.

## Decision: SDK Logging Capped

Rationale:

- openstacksdk and keystoneauth debug logs include request bodies and tokens.
  Upstream enabled SDK debug logging by default (`DEBUG_MODE=true`).

Enforcement:

- SDK loggers are capped at `CRITICAL`; tool calls are logged by name,
  project and outcome only (SPEC LOG).

## Decision: Hatchling And A Static Version

Rationale:

- `setuptools-scm` derived the version from git tags and failed on
  non-version tags such as `upstream-eba3e6f`; editable setuptools installs
  also leave `*.egg-info` in the tree.
- Release tags must equal the version in `pyproject.toml`.

Enforcement:

- `hatchling` backend, static `version` in `pyproject.toml`, release workflow
  checks tag against it.
