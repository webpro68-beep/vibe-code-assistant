#!/usr/bin/env python3
import sys
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

URLS = [
    "http://localhost:8000/healthz",
    "http://localhost:3000",
    "http://localhost:8080/healthz",
]

timeout_seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 240
deadline = time.time() + timeout_seconds
pending = set(URLS)

while time.time() < deadline and pending:
    for url in list(pending):
        try:
            req = Request(url, headers={"User-Agent": "ci-waiter"})
            with urlopen(req, timeout=5) as resp:
                if 200 <= resp.status < 500:
                    pending.remove(url)
        except Exception:
            pass
    if pending:
        time.sleep(3)

if pending:
    print("Timed out waiting for URLs:")
    for url in sorted(pending):
        print(f"- {url}")
    sys.exit(1)

print("All endpoints are reachable.")
