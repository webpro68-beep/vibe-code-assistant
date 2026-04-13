#!/usr/bin/env bash
set -euo pipefail

echo "=== migration PR guard: topology summary ==="
python -m alembic current || true
python -m alembic heads --verbose || python -m alembic heads
python -m alembic branches --verbose || python -m alembic branches || true
python -m alembic history | tail -n 80 || true

echo "=== migration PR guard: lineage validator ==="
python scripts/check_single_alembic_head.py

echo "=== migration PR guard: done ==="
