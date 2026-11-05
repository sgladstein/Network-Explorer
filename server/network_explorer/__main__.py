"""Command line: `network-explorer serve` (or `python -m network_explorer serve`)."""

from __future__ import annotations

import argparse
import socket


def lan_ip() -> str | None:
    """Best guess at this machine's LAN address (no packets are sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # TEST-NET address; connect() on UDP only picks a route
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="network-explorer")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Run the survey server")
    serve.add_argument("--host", default="0.0.0.0", help="Address to listen on (default: all interfaces)")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--data-dir", default=None, help="Where to keep the database and floor plans "
                                                        "(default: $NETWORK_EXPLORER_DATA or ~/.network-explorer)")
    args = parser.parse_args(argv)

    import uvicorn

    from .app import create_app

    app = create_app(args.data_dir)
    ip = lan_ip()
    print("\nNetwork Explorer survey server")
    if ip:
        print(f"  In the Android app, set the server to:  http://{ip}:{args.port}")
        print(f"  Heatmaps and reports in a browser:      http://{ip}:{args.port}/")
    print("  Keep this on your home network only; don't port-forward it.\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
