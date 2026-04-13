#!/bin/bash
set -e

echo "Waiting for Postgres..."
python /app/scripts/wait_for_postgres.py

echo "Starting Celery worker..."
celery -A app.core.celery_app.celery_app worker -l info