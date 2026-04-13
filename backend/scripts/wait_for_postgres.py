from __future__ import annotations

import os
import time

import psycopg


DATABASE_URL = os.environ["DATABASE_URL"]

max_attempts = 60
attempt = 0

while attempt < max_attempts:
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                print("Postgres is ready.")
                raise SystemExit(0)
    except Exception as exc:
        attempt += 1
        print(f"Waiting for Postgres... attempt={attempt} error={exc}")
        time.sleep(2)

raise SystemExit("Postgres did not become ready in time.")