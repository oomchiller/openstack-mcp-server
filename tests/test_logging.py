"""SPEC LOG-1, LOG-2, CFG-4: what the server logs."""

import logging

import pytest
from openstack import exceptions as sdk

from openstack_mcp_server import log

from .conftest import SECRET, FakeCloud, call, make_server


def test_log_2_sdk_loggers_capped() -> None:
    log.configure("DEBUG")
    for name in log.SDK_LOGGERS:
        logger = logging.getLogger(name)
        assert logger.level == logging.CRITICAL
        assert not logger.propagate
    assert not logging.getLogger("openstack.config").isEnabledFor(logging.ERROR)


def test_log_1_tool_calls_logged_without_arguments(
    fake: FakeCloud, caplog: pytest.LogCaptureFixture
) -> None:
    fake.respond("compute", "servers", sdk.ForbiddenException(f"token {SECRET}"))
    with caplog.at_level(logging.DEBUG, logger="openstack_mcp_server.calls"):
        call(make_server(fake), "list_servers", {"name": "needle-argument"})
    records = [r for r in caplog.records if r.name == "openstack_mcp_server.calls"]
    summary = [r.getMessage() for r in records if r.levelno == logging.INFO]
    assert len(summary) == 1
    assert "tool=list_servers" in summary[0] and "outcome=forbidden" in summary[0]
    everything = " ".join(r.getMessage() for r in caplog.records)
    assert SECRET not in everything
    assert "needle-argument" not in everything
