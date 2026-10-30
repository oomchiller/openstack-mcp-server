# Behaviour Specification

Status: specification for 0.1.0, written before the refactor. Code that
predates it (upstream `eba3e6f`) does not yet conform. Every requirement has an
ID; tests reference the ID in their name or docstring, and the traceability
table at the end maps IDs to test modules.

Keywords: **must** is a release blocker, **should** is expected unless a
decision in `DECISIONS.md` says otherwise.

## 1. Configuration (CFG)

All configuration comes from the environment and from OpenStack's own
configuration mechanisms. The server has no configuration file of its own and
no required command-line argument.

### Cloud credentials

- **CFG-1** Credentials are resolved by openstacksdk's loader, in its usual
  order: `OS_CLOUD` selects an entry in `clouds.yaml` (located by
  `OS_CLIENT_CONFIG_FILE` or the standard search path); without `OS_CLOUD`,
  `OS_*` variables (`OS_AUTH_URL`, `OS_USERNAME`, `OS_PASSWORD`,
  `OS_USER_DOMAIN_ID`/`OS_USER_DOMAIN_NAME`, `OS_PROJECT_ID`,
  `OS_REGION_NAME`, `OS_INTERFACE`, application credentials, …) form the
  environment cloud. The environment-only form is the supported container
  configuration.
- **CFG-2** The upstream variable `CLOUD_NAME` is not read. `OS_CLOUD` replaces
  it.
- **CFG-3** Missing or unresolvable credentials do not stop the server. It
  starts, `get_scope` reports `configured: false` with a reason category, and
  every cloud tool returns the `not_configured` error (ERR-2). This keeps
  gateways that host several servers working when one is unconfigured.
- **CFG-4** Credential values (passwords, application credential secrets,
  tokens) never appear in tool output, error text, logs or exceptions raised
  to the client.

### TLS

- **CFG-5** `OS_CACERT` (or `cacert` in `clouds.yaml`) names a CA bundle file,
  as in openstacksdk.
- **CFG-6** `OPENSTACK_MCP_CACERT_PEM` carries one or more PEM certificates as
  text. At startup the server writes it to a file created with mode `0600`
  inside a private `0700` temporary directory, passes that path as the CA
  bundle and removes it at exit. It takes precedence over `OS_CACERT` and
  `cacert`. Text without a `-----BEGIN CERTIFICATE-----` block is a startup
  error (CFG-12).
- **CFG-7** TLS verification is on. A cloud with `verify: false`, `insecure:
  true`, `OS_INSECURE=true` or an `http://` auth URL is reported as
  `configured: false` (reason `insecure_transport`) unless
  `OPENSTACK_MCP_ALLOW_INSECURE=true`.

### Server settings

| Variable | Default | Allowed | Meaning |
| --- | --- | --- | --- |
| `OPENSTACK_MCP_MODE` | `readonly` | `readonly`, `admin` | Operating mode (RO-1). |
| `OPENSTACK_MCP_ENABLE_WRITE_TOOLS` | `false` | boolean | Second write gate (RO-2). |
| `OPENSTACK_MCP_PROJECT_IDS` | empty | comma-separated project IDs | Project allowlist (SCOPE). |
| `OPENSTACK_MCP_DEFAULT_LIMIT` | `50` | 1 … max limit | Items per list call when `limit` is omitted. |
| `OPENSTACK_MCP_MAX_LIMIT` | `100` | 1 … 1000 | Largest accepted `limit`. |
| `OPENSTACK_MCP_MAX_RESPONSE_BYTES` | `524288` | 4096 … 8388608 | Largest serialized tool result. |
| `OPENSTACK_MCP_API_TIMEOUT` | `10` | 1 … 120 seconds | Per-request OpenStack API timeout. |
| `OPENSTACK_MCP_CACERT_PEM` | unset | PEM text | CA bundle as content (CFG-6). |
| `OPENSTACK_MCP_ALLOW_INSECURE` | `false` | boolean | Permit unverified TLS or `http://` (CFG-7). |
| `OPENSTACK_MCP_ENABLE_PROMPTS` | `true` | boolean | Register prompts (MCP-8). |
| `OPENSTACK_MCP_ENABLE_RESOURCES` | `true` | boolean | Register resources (MCP-8). |
| `OPENSTACK_MCP_TRANSPORT` | `stdio` | `stdio`, `streamable-http` | Transport (TR). |
| `OPENSTACK_MCP_HTTP_HOST` | `127.0.0.1` | host or address | HTTP bind address. |
| `OPENSTACK_MCP_HTTP_PORT` | `8000` | 1 … 65535 | HTTP port. |
| `OPENSTACK_MCP_HTTP_ALLOW_REMOTE` | `false` | boolean | Permit a non-loopback bind (TR-3). |
| `OPENSTACK_MCP_LOG_LEVEL` | `WARNING` | `DEBUG` … `CRITICAL` | Server log level (LOG). |

- **CFG-8** Booleans accept `true`/`false`/`1`/`0`/`yes`/`no`, case-insensitive.
- **CFG-9** `OPENSTACK_MCP_PROJECT_IDS` entries are 32-character hex IDs or
  dashed UUIDs, at most 100, without duplicates. Whitespace around commas is
  ignored; an empty entry is an error.
- **CFG-10** The upstream variables `TRANSPORT` and `DEBUG_MODE` are not read.
- **CFG-11** `OPENSTACK_MCP_DEFAULT_LIMIT` must not exceed
  `OPENSTACK_MCP_MAX_LIMIT`.
- **CFG-12** An invalid `OPENSTACK_MCP_*` value stops the server before it
  speaks MCP, with exit code 2 and one stderr line naming the variable and the
  rule, never the value.

## 2. Read-only default and write mode (RO)

- **RO-1** In the default configuration only read tools (section 5) are
  registered. Write tools do not appear in `tools/list` and calling one by
  name returns the protocol's unknown-tool error.
- **RO-2** Write tools are registered only when `OPENSTACK_MCP_MODE=admin` and
  `OPENSTACK_MCP_ENABLE_WRITE_TOOLS=true`. `admin` alone registers no write
  tool. `OPENSTACK_MCP_ENABLE_WRITE_TOOLS=true` with `readonly` is a startup
  error (CFG-12), because the operator's intent is contradictory.
- **RO-3** Read tools only call SDK list/get operations from a fixed table.
  No read tool reaches a create, update, delete or action SDK call, whatever
  its arguments.
- **RO-4** No tool accepts or forwards `all_projects`, `all_tenants`,
  `project_id` filters for other projects, cloud names, auth parameters, SDK
  method names or raw API paths.
- **RO-5** No tool reads, changes or lists the cloud configuration: the
  upstream `get_cloud_config`, `get_cloud_names`, `get_cloud_name` and
  `set_cloud_name` tools are removed in every mode.
- **RO-6** Read-only mode is a convenience. The security boundary is the
  Keystone role of the configured identity; `SECURITY.md` states this.

## 3. Project scope (SCOPE)

- **SCOPE-1** Every cloud tool takes an optional `project_id`. Each project
  uses its own project-scoped Keystone session; sessions are created on first
  use and cached for the process lifetime.
- **SCOPE-2** With an allowlist, `project_id` must be one of its entries;
  without `project_id` the first entry is used. Any other value returns
  `project_not_allowed` before any authentication.
- **SCOPE-3** Without an allowlist the server uses the project from the cloud
  configuration. A `project_id` argument is accepted only when it equals that
  project; otherwise `project_not_allowed`. Switching projects requires an
  allowlist.
- **SCOPE-4** When a project is overridden, other project selectors from the
  configuration (`project_name`, `project_domain_*`, `tenant_*`) are dropped
  so that Keystone scopes the token to exactly that ID.
- **SCOPE-5** Network-service lists (networks, subnets, ports, routers,
  floating IPs, security groups) are filtered by the session project.
  `list_networks(shared=true)` returns shared networks visible to the project
  regardless of owner and says so in the tool description.

## 4. Results, paging and limits (OUT)

- **OUT-1** List tools return a structured envelope, declared as the tool's
  `outputSchema` and returned as `structuredContent` (with the same JSON as
  text content for older clients):

  ```json
  {
    "resource": "servers",
    "project_id": "…",
    "observed_at": "2026-10-30T12:00:00+00:00",
    "limit": 50,
    "items": [ … ],
    "complete": false,
    "next_marker": "…"
  }
  ```

- **OUT-2** `limit` defaults to `OPENSTACK_MCP_DEFAULT_LIMIT` and must be
  between 1 and `OPENSTACK_MCP_MAX_LIMIT`; the JSON schema states both bounds.
- **OUT-3** The server consumes at most `limit + 1` items from the SDK
  iterator and never materializes a full listing. `complete` is `true` only
  when fewer than `limit + 1` items arrived.
- **OUT-4** Tools whose API supports markers accept `marker` and return
  `next_marker` (the ID of the last returned item) when `complete` is false;
  otherwise `next_marker` is `null`. A tool whose API has no marker paging
  does not accept `marker` and describes that narrowing filters are the way
  to see more.
- **OUT-5** Get tools return the single resource model as structured content.
- **OUT-6** Items are typed models with an explicit field list. Platform
  resources (hypervisors, services, endpoints, agents, aggregates) export only
  their declared fields; unknown attributes, links and anything named like a
  credential are never exported.
- **OUT-7** A result whose serialized size exceeds
  `OPENSTACK_MCP_MAX_RESPONSE_BYTES` is not returned; the call fails with
  `response_too_large`.

## 5. Tool surface (TOOL)

- **TOOL-1** Tool names follow `list_<plural>`, `get_<singular>` and, for
  write tools, `<verb>_<singular>`. The read surface for 0.1.0 is:

  | Group | Tools |
  | --- | --- |
  | Scope | `get_scope` (no cloud call) |
  | Compute | `list_servers`, `get_server`, `list_flavors` |
  | Image | `list_images`, `get_image` |
  | Block storage | `list_volumes`, `get_volume`, `list_volume_attachments`, `get_volume_attachment` |
  | Network | `list_networks`, `get_network`, `list_subnets`, `get_subnet`, `list_ports`, `get_port`, `list_floating_ips`, `list_routers`, `get_router`, `list_router_interfaces`, `list_security_groups`, `get_security_group` |
  | Identity | `list_regions`, `list_domains`, `list_projects`, `list_services`, `list_endpoints` |
  | Platform | `list_hypervisors`, `list_compute_services`, `list_aggregates`, `list_network_agents`, `list_volume_services` |

- **TOOL-2** Write tools (admin mode, RO-2) carry over the upstream mutating
  operations under the same naming: server create/update/delete/action and
  volume attach/detach; volume create/delete/extend; image create/delete;
  network, subnet, port, router, floating IP and security group
  create/update/delete; router interface add/remove. Upstream identity writes
  (regions, domains, projects), `set_port_binding`,
  `create_floating_ips_bulk` and `assign_first_available_floating_ip` are not
  carried over (`DECISIONS.md`). Write tools are experimental in 0.1.0.
- **TOOL-3** `get_scope` returns, without contacting the cloud: server
  version, mode, whether write tools are registered, `configured` and its
  reason, credential source (`clouds.yaml` entry name or `environment`),
  region, interface, TLS source (`system`, `file`, `pem`), allowlisted
  project IDs and the default project ID, limits, and
  `cloud_access_verified: false`.
- **TOOL-4** Arguments with a closed value set use enums in the input schema
  (server action, image visibility, IP version, resource status filters where
  OpenStack documents the set). Unknown arguments are rejected by schema
  validation.

## 6. MCP behaviour (MCP)

- **MCP-1** Every read tool has `readOnlyHint: true`, `destructiveHint:
  false`, `idempotentHint: true`, `openWorldHint: true`; `get_scope` has
  `openWorldHint: false`.
- **MCP-2** Write tools have `readOnlyHint: false`; delete, extend, action,
  detach and interface removal tools have `destructiveHint: true`; updates are
  `idempotentHint: true`, creates `false`.
- **MCP-3** Each tool has a title and a description of at most three
  sentences that says what it returns, its scope, and its paging behaviour.
  Parameter descriptions are part of the schema.
- **MCP-4** The server sends `instructions` on initialize: read-only by
  default, call `get_scope` first, how projects and paging work, that
  `forbidden` means a missing role rather than an empty inventory.
- **MCP-5** Tool failures are returned as results with `isError: true`, not as
  protocol errors, except for unknown tools and schema validation which the
  protocol layer reports.
- **MCP-6** Prompts: the upstream security-group prompt is kept, renamed to
  `find_servers_by_security_group` and updated to the new tool names and
  paging.
- **MCP-7** Resources: `openstack://scope` returns the `get_scope` document.
- **MCP-8** `OPENSTACK_MCP_ENABLE_PROMPTS=false` and
  `OPENSTACK_MCP_ENABLE_RESOURCES=false` remove prompts and resources
  respectively; tool names and schemas are identical in every combination.
  Gateways that host several instances without prefixing prompt names or
  resource URIs set both to `false`.

## 7. Errors (ERR)

- **ERR-1** Error text has the form `[<category>] <sentence>. <action>.` The
  category set is closed:

  | Category | Cause | Action stated to the agent |
  | --- | --- | --- |
  | `not_configured` | CFG-3, CFG-7 | Configure credentials; do not retry. |
  | `project_not_allowed` | SCOPE-2, SCOPE-3 | Call `get_scope` for allowed IDs. |
  | `invalid_argument` | Out-of-range value not caught by the schema | Fix the argument. |
  | `auth_failed` | HTTP 401, authentication plugin failure | Check credentials; do not retry. |
  | `forbidden` | HTTP 403 | The role lacks this permission; do not retry. |
  | `not_found` | HTTP 404 | Check the ID and project. |
  | `conflict` | HTTP 409 (write tools) | Inspect the resource state first. |
  | `service_unavailable` | Endpoint missing from the catalog | The cloud does not offer this service. |
  | `unavailable` | Timeout, connection error, HTTP 5xx | Retry later. |
  | `response_too_large` | OUT-7 | Use a smaller limit or filters. |
  | `incompatible_response` | Response does not fit the model | Report a bug with the cloud version. |
  | `internal` | Anything else | Report a bug. |

- **ERR-2** Error text never contains exception messages, HTTP bodies, URLs,
  request IDs, tokens, credential values or stack traces from the SDK. The
  project ID and resource ID supplied by the caller may appear.
- **ERR-3** `forbidden` is never converted into an empty list.

## 8. Transport (TR)

- **TR-1** stdio is the default transport. Nothing but MCP messages is written
  to stdout; logs go to stderr.
- **TR-2** `OPENSTACK_MCP_TRANSPORT=streamable-http` serves Streamable HTTP on
  `OPENSTACK_MCP_HTTP_HOST:OPENSTACK_MCP_HTTP_PORT` at path `/mcp`.
- **TR-3** A non-loopback HTTP bind is a startup error unless
  `OPENSTACK_MCP_HTTP_ALLOW_REMOTE=true`. The HTTP transport has no
  authentication of its own (`SECURITY.md`).
- **TR-4** SIGINT and SIGTERM end the process with exit code 0 and remove the
  CFG-6 temporary file.

## 9. Logging (LOG)

- **LOG-1** The server logs to stderr at `OPENSTACK_MCP_LOG_LEVEL`. A tool call
  is logged at `INFO` as tool name, project ID, outcome category and duration;
  arguments other than IDs and results are not logged.
- **LOG-2** The `openstack`, `keystoneauth1`, `urllib3` and `stevedore`
  loggers are capped at `CRITICAL` regardless of the server level, and
  `openstack.enable_logging(debug=True)` is never called, because SDK debug
  logs contain request bodies and tokens.

## 10. Packaging and image (PKG)

- **PKG-1** Distribution, CLI and image are named `openstack-mcp-server`; the
  import package stays `openstack_mcp_server`. `python -m openstack_mcp_server`
  is equivalent to the CLI.
- **PKG-2** `uv.lock` pins every dependency; the image installs with
  `uv sync --locked --no-dev`.
- **PKG-3** The image runs as an unprivileged user, has the stdio server as its
  entrypoint, sets `OPENSTACK_MCP_MODE=readonly` and
  `OPENSTACK_MCP_ENABLE_WRITE_TOOLS=false`, and contains no credentials,
  `clouds.yaml` or CA other than the base image's trust store.
- **PKG-4** A `vX.Y.Z` tag whose version equals `pyproject.toml` publishes
  `ghcr.io/oomchiller/openstack-mcp-server:X.Y.Z` for `linux/amd64` and
  `linux/arm64`. Consumers pin the image by digest.
- **PKG-5** CI on every push and pull request runs ruff lint, ruff format
  check, mypy strict, pytest with coverage, an image build and a stdio smoke
  test of the built image (initialize and `tools/list` with environment-only
  configuration and no cloud).

## 11. Traceability

Tests carry the requirement ID in the test name (`test_ro_1_…`) or in the
first line of the docstring.

| Requirements | Test module |
| --- | --- |
| CFG-1 … CFG-12 | `tests/test_config.py` |
| CFG-5 … CFG-7, SCOPE-1, SCOPE-4 | `tests/test_cloud.py` |
| RO-1 … RO-5, MCP-1, MCP-2, MCP-8, TOOL-1, TOOL-2 | `tests/test_surface.py` |
| SCOPE-2 … SCOPE-5, RO-4 | `tests/test_scope.py` |
| OUT-1 … OUT-7 | `tests/test_paging.py` |
| TOOL-3, MCP-4, MCP-6, MCP-7 | `tests/test_scope_tool.py`, `tests/test_prompts_resources.py` |
| TOOL-4, OUT-5, OUT-6 per service | `tests/tools/test_<service>.py` (adapted from upstream) |
| ERR-1 … ERR-3, MCP-5, CFG-4 | `tests/test_errors.py` |
| TR-1 … TR-4 | `tests/test_transport.py` |
| LOG-1, LOG-2, CFG-4 | `tests/test_logging.py` |
| PKG-1 | `tests/test_cli.py` |
| PKG-2 … PKG-5 | CI workflow (`.github/workflows/ci.yml`, `release.yml`) |

Tests never contact a cloud: SDK connections are replaced by fakes that record
calls, and MCP behaviour is exercised through an in-memory client session.
