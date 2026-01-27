#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64


def build_basic_token(access_key: str, access_key_secret: str) -> str:
    token_bytes = f"{access_key}:{access_key_secret}".encode("utf-8")
    return base64.b64encode(token_bytes).decode("ascii")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Base64 basic token from access key and secret."
    )
    parser.add_argument("access_key", help="Access Key")
    parser.add_argument("access_key_secret", help="Access Key Secret")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = build_basic_token(args.access_key, args.access_key_secret)
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
