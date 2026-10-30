"""stderr logging with SDK loggers capped (SPEC LOG)."""

import logging
import sys

# openstacksdk and keystoneauth log request bodies and tokens at DEBUG.
SDK_LOGGERS = ("openstack", "keystoneauth", "keystoneauth1", "urllib3", "stevedore")


def configure(level: str) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    cap_sdk_loggers()


def cap_sdk_loggers() -> None:
    for name in SDK_LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL)
        logger.propagate = False
