"""CLI entry point: ``chipmunk-dashboard run``."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="chipmunk-dashboard")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Launch the dashboard")
    run_p.add_argument("--port", type=int, default=8050, help="Port (default: 8050)")
    run_p.add_argument("--debug", action="store_true", help="Enable Dash debug mode")

    args = parser.parse_args()

    if args.command == "run":
        from .app import create_app

        app = create_app()
        print(f"Starting Chipmunk Dashboard on http://localhost:{args.port}")
        app.run(port=args.port, debug=args.debug)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
