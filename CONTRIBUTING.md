# Contributing

## Local checks

```bash
uv sync --locked
uv run pytest --cov
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

Tests never contact a cloud. Use the fakes in `tests/conftest.py`.

## Behaviour changes start in the specification

1. Change `docs/SPEC.md` (add or edit a requirement with an ID).
2. Add or change tests that name the ID.
3. Change the code.
4. Record decisions that should not be reversed casually in `DECISIONS.md`.

## Safety rules

- Keep `readonly` the default. Write tools stay unregistered unless
  `OPENSTACK_MCP_MODE=admin` and `OPENSTACK_MCP_ENABLE_WRITE_TOOLS=true`.
- A read tool calls one named SDK list or get operation. No tool accepts SDK
  method names, raw API paths, cloud names, auth parameters or `all_projects`.
- Results are models with explicit fields. Never return raw SDK resources.
- Errors go through `errors.classify()`; never put exception text in a result.
- Never enable SDK debug logging.

## Dependencies

`uv.lock` pins every dependency. `[tool.uv] exclude-newer` keeps resolution to
releases at least two weeks old; move the date forward when upgrading
(`uv lock --upgrade`).

## Releases

Set `version` in `pyproject.toml`, add a `CHANGELOG.md` entry, and push a tag
`vX.Y.Z` with the same version. The release workflow checks the match, runs
CI and publishes `ghcr.io/oomchiller/openstack-mcp-server`. Published tags are
not moved.
