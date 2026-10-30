"""Entry point for `openstack-mcp-server` and `python -m openstack_mcp_server`."""

import os
import signal
import sys
from collections.abc import Sequence
from types import FrameType

from . import log
from .cloud import CaBundle, Cloud, load_cloud
from .config import ConfigError, Settings
from .server import build_server


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args in (["--version"], ["-V"]):
        from . import __version__

        print(f"openstack-mcp-server {__version__}")
        return 0
    if args:
        print(
            "openstack-mcp-server takes no arguments; configure it through "
            "OS_* and OPENSTACK_MCP_* environment variables",
            file=sys.stderr,
        )
        return 2

    try:
        settings = Settings.from_env(os.environ)
    except ConfigError as error:
        print(f"openstack-mcp-server: invalid configuration: {error}", file=sys.stderr)
        return 2

    log.configure(settings.log_level)
    bundle = CaBundle(settings.cacert_pem) if settings.cacert_pem else None

    def stop(signum: int, frame: FrameType | None) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        state, base = load_cloud(settings)
        cloud = Cloud(
            settings, state, base, cacert_path=bundle.path if bundle else None
        )
        build_server(cloud).run(transport=settings.transport)
    except KeyboardInterrupt:
        pass
    finally:
        if bundle is not None:
            bundle.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
