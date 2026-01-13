"""Entry point for the web UI: python -m importer.web"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="dbt Platform Account Exploration and Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to run the server on (default: 8080)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't automatically open browser",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes (development mode)",
    )

    args = parser.parse_args()

    # Import here to avoid slow startup for --help
    from importer.web.app import run_app

    run_app(
        host=args.host,
        port=args.port,
        show=not args.no_open,
        reload=args.reload,
    )


if __name__ == "__main__":
    sys.exit(main())
