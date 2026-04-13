#!/bin/bash
set -e

echo "Waiting for Postgres..."
python /app/scripts/wait_for_postgres.py

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting FastAPI..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload