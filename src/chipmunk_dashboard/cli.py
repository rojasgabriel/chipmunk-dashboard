"""CLI entry point for running and registering chipmunk-dashboard."""

import argparse
import os
import threading
import webbrowser

from .labdata_setup import register_labdata_plugin


def main() -> None:
    """Parse CLI arguments and run the dashboard server.

    Supported commands:
        ``chipmunk-dashboard run``
        ``chipmunk-dashboard install-labdata``

    Runtime behavior:
        - Launches Dash on the requested host/port.
        - Optionally opens a browser tab unless ``--no-open`` is provided.
        - In debug mode, browser auto-open is restricted to the Werkzeug
          reloader child process.

    Returns:
        None.
    """
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
    run_p.add_argument(
        "--ui-debug",
        action="store_true",
        help="Use built-in fixture data so UI work can run without database access",
    )
    sub.add_parser(
        "install-labdata",
        help="Register the bundled dashboard tab with labdata",
    )

    args = parser.parse_args()

    if args.command == "run":
        if args.ui_debug:
            os.environ["CHIPMUNK_UI_DEBUG"] = "1"

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
    elif args.command == "install-labdata":
        preferences_path, changed = register_labdata_plugin()
        action = "Registered" if changed else "Already registered"
        print(f"{action} Chipmunk dashboard plugin in {preferences_path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
