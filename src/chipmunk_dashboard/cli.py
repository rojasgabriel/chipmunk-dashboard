"""CLI entry point: ``chipmunk-dashboard run``."""

import argparse
import os
import threading
import webbrowser


def main() -> None:
    parser = argparse.ArgumentParser(prog="chipmunk-dashboard")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Launch the dashboard")
    run_p.add_argument("--port", type=int, default=8050, help="Port (default: 8050)")
    run_p.add_argument(
        "--host", type=str, default="localhost", help="Host (default: localhost)"
    )
    run_p.add_argument("--debug", action="store_true", help="Enable Dash debug mode")
    run_p.add_argument(
        "--no-open",
        action="store_true",
        help="Do not automatically open the dashboard in a browser",
    )

    args = parser.parse_args()

    if args.command == "run":
        from .app import create_app

        app = create_app()
        url = f"http://{args.host}:{args.port}"
        print(f"Starting Chipmunk Dashboard on {url}")

        # In debug mode with reloader, only open browser from the reloader child.
        should_open = (not args.no_open) and (
            (not args.debug) or os.environ.get("WERKZEUG_RUN_MAIN") == "true"
        )
        if should_open:
            threading.Timer(0.8, lambda: webbrowser.open(url)).start()

        app.run(host=args.host, port=args.port, debug=args.debug)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
