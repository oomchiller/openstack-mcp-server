"""SPEC PKG-1, CFG-12, TR-1, TR-4: the command-line entry point as a process."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from openstack_mcp_server import __version__
from openstack_mcp_server.__main__ import main

PEM = "-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n"


def clean_env(**extra: str) -> dict[str, str]:
    base = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("OS_", "OPENSTACK_MCP_"))
    }
    base["OS_CLIENT_CONFIG_FILE"] = os.devnull
    base["HOME"] = "/nonexistent"
    return {**base, **extra}


def run(
    *args: str, env: dict[str, str], stdin: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "openstack_mcp_server", *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )


def test_pkg_1_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"openstack-mcp-server {__version__}"


def test_pkg_1_arguments_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--cloud", "x"]) == 2
    assert "environment variables" in capsys.readouterr().err


def test_cfg_12_invalid_setting_exits_2_without_value() -> None:
    result = run(env=clean_env(OPENSTACK_MCP_MAX_LIMIT="secret-looking-9999"))
    assert result.returncode == 2
    assert "OPENSTACK_MCP_MAX_LIMIT" in result.stderr
    assert "secret-looking" not in result.stderr
    assert result.stdout == ""


def messages(*requests: dict[str, Any]) -> str:
    return "".join(json.dumps(r) + "\n" for r in requests)


INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
SCOPE = {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {"name": "get_scope", "arguments": {}},
}


def test_tr_1_stdio_speaks_only_json_rpc() -> None:
    env = clean_env(
        OS_AUTH_URL="https://keystone.example/v3",
        OS_USERNAME="u",
        OS_PASSWORD="synthetic-secret-value",
        OS_USER_DOMAIN_ID="default",
        OS_PROJECT_ID="a" * 32,
        OPENSTACK_MCP_LOG_LEVEL="INFO",
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "openstack_mcp_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(messages(INITIALIZE, INITIALIZED, LIST, SCOPE))
    process.stdin.flush()
    lines = [process.stdout.readline() for _ in range(3)]
    process.stdin.close()
    assert process.wait(timeout=30) == 0
    stdout = "".join(lines) + process.stdout.read()
    stderr = process.stderr.read() if process.stderr else ""
    replies = [json.loads(line) for line in stdout.splitlines()]
    assert [r["id"] for r in replies] == [1, 2, 3]
    assert replies[0]["result"]["serverInfo"]["name"] == "openstack-mcp-server"
    assert "get_scope" in replies[0]["result"]["instructions"]
    names = {tool["name"] for tool in replies[1]["result"]["tools"]}
    assert "list_servers" in names and "delete_server" not in names
    scope = replies[2]["result"]["structuredContent"]
    assert scope["configured"] is True and scope["credential_source"] == "environment"
    assert "synthetic-secret-value" not in stdout + stderr
    assert "tool=get_scope" in stderr


def test_tr_4_sigterm_exits_0_and_removes_ca_file(tmp_path: Path) -> None:
    env = clean_env(OPENSTACK_MCP_CACERT_PEM=PEM, TMPDIR=str(tmp_path))
    process = subprocess.Popen(
        [sys.executable, "-m", "openstack_mcp_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    deadline = time.monotonic() + 30
    while not list(tmp_path.glob("openstack-mcp-*/ca.pem")):
        assert time.monotonic() < deadline, "CA file was not written"
        time.sleep(0.05)
    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=30) == 0
    assert not list(tmp_path.glob("openstack-mcp-*"))
