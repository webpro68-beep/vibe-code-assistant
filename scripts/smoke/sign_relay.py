#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import sys
import time
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: sign_relay.py <secret> <payload.json> [timestamp]", file=sys.stderr)
        return 1
    secret = sys.argv[1]
    payload_path = Path(sys.argv[2])
    timestamp = sys.argv[3] if len(sys.argv) > 3 else str(int(time.time()))
    raw = payload_path.read_bytes()
    message = timestamp.encode("utf-8") + b"." + raw
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    print(timestamp)
    print(f"sha256={signature}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
