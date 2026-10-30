"""SPEC TR-2: Streamable HTTP on loopback at /mcp."""

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from .test_cli import INITIALIZE, clean_env


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_tr_2_streamable_http_initialize() -> None:
    port = free_port()
    env = clean_env(
        OPENSTACK_MCP_TRANSPORT="streamable-http", OPENSTACK_MCP_HTTP_PORT=str(port)
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "openstack_mcp_server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/mcp",
            data=json.dumps(INITIALIZE).encode(),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            method="POST",
        )
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    body = response.read().decode()
                    break
            except (urllib.error.URLError, ConnectionError):
                assert time.monotonic() < deadline, "HTTP server did not start"
                time.sleep(0.1)
        payload = next(
            line[5:] for line in body.splitlines() if line.startswith("data:")
        )
        assert (
            json.loads(payload)["result"]["serverInfo"]["name"]
            == "openstack-mcp-server"
        )
    finally:
        process.terminate()
        process.wait(timeout=30)
