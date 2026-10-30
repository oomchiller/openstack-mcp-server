"""Smoke-test a server command over stdio: initialize, tools/list, get_scope.

Usage: python scripts/smoke_stdio.py <command> [args...]
The command must already carry its environment (for example docker run -e ...).
"""

import json
import subprocess
import sys

REQUESTS = [
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "smoke", "version": "0"},
        },
    },
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "get_scope", "arguments": {}},
    },
]


def main() -> int:
    process = subprocess.Popen(
        sys.argv[1:], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write("".join(json.dumps(r) + "\n" for r in REQUESTS))
    process.stdin.flush()
    replies = [json.loads(process.stdout.readline()) for _ in range(3)]
    process.stdin.close()
    process.wait(timeout=60)
    tools = {tool["name"] for tool in replies[1]["result"]["tools"]}
    scope = replies[2]["result"]["structuredContent"]
    summary = {
        "server": replies[0]["result"]["serverInfo"],
        "tools": len(tools),
        "write_tools": sorted(t for t in tools if t.startswith(("create_", "delete_"))),
        "configured": scope["configured"],
        "mode": scope["mode"],
        "tls": scope["tls"],
    }
    print(json.dumps(summary))
    ok = (
        process.returncode == 0
        and len(tools) == 32
        and not summary["write_tools"]
        and scope["mode"] == "readonly"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
