# Security Policy

## Reporting vulnerabilities

Do not open public issues for problems that could expose credentials, reach a
write operation in read-only mode, escape the project allowlist or leak cloud
responses through errors or logs.

Report privately through GitHub Security Advisories on this repository.
Include the affected version or commit, the tool involved, the OpenStack
release if known, reproduction steps, and expected and actual behaviour.

## The security boundary is the Keystone role

Read-only mode in this server is a convenience. It reduces the chance that an
agent changes a cloud by accident. It is not a security boundary:

- the credential the server uses works with any other OpenStack client;
- a defect in this server or its dependencies could reach a write API;
- tool annotations such as `readOnlyHint` are advisory for clients.

Give the server an identity whose role assignments allow only what you accept
an agent doing. For read-only use that is the `reader` role on the intended
projects, with no admin, member, system or domain roles, and no group or
inherited assignments that add them. Prefer an application credential
restricted to that identity and project.

## Implemented safeguards

- Write tools are not registered unless `OPENSTACK_MCP_MODE=admin` and
  `OPENSTACK_MCP_ENABLE_WRITE_TOOLS=true`.
- Read tools call only fixed SDK list/get operations; no tool accepts cloud
  names, auth parameters, SDK method names, raw paths or `all_projects`.
- `OPENSTACK_MCP_PROJECT_IDS` limits the projects a session may be scoped to;
  the check runs before authentication.
- TLS verification is required and `http://` auth URLs are rejected unless
  `OPENSTACK_MCP_ALLOW_INSECURE=true`.
- Results are typed models with explicit fields, limited in item count and
  bytes.
- Errors carry a fixed category and sentence; SDK exception text, HTTP bodies
  and URLs are not returned.
- SDK loggers are capped at `CRITICAL`; tool arguments other than IDs and
  results are not logged.
- The container image runs as an unprivileged user and contains no
  credentials.

## Not safeguards

- Agent judgement, prompt text or server instructions.
- Read-only mode without a reader-only identity.
- The Streamable HTTP transport: it has no authentication. It binds to
  loopback by default; expose it only behind an authenticating proxy.

## Operator guidance

- Pass credentials through `OS_*` variables or a `clouds.yaml` readable only
  by the server's user. Never put them in tool arguments or prompts.
- Pin the container image by digest.
- Keep `OPENSTACK_MCP_ENABLE_WRITE_TOOLS=false` unless a person is supervising
  write operations.
