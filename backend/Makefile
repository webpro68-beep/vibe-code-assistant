COMPOSE=docker compose -f docker-compose.dev.yml

.PHONY: bootstrap up down restart build logs logs-api logs-worker logs-beat logs-db ps \
        shell-api shell-worker migrate downgrade revision revision-auto \
        check-head check-db-head check-drift health api-health worker-health \
        flower-health reset clean first-run

bootstrap:
	./scripts/bootstrap-env.sh

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) down
	$(COMPOSE) up --build

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f

logs-api:
	$(COMPOSE) logs -f api

logs-worker:
	$(COMPOSE) logs -f worker

logs-beat:
	$(COMPOSE) logs -f beat

logs-db:
	$(COMPOSE) logs -f postgres

ps:
	$(COMPOSE) ps

shell-api:
	$(COMPOSE) exec api /bin/bash

shell-worker:
	$(COMPOSE) exec worker /bin/bash

migrate:
	$(COMPOSE) exec api alembic upgrade head

downgrade:
	$(COMPOSE) exec api alembic downgrade -1

revision:
	$(COMPOSE) exec api alembic revision -m "$(m)"

revision-auto:
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"

check-head:
	$(COMPOSE) exec api python scripts/check_migration_head.py

check-db-head:
	$(COMPOSE) exec api python scripts/check_missing_migration.py

check-drift:
	$(COMPOSE) exec api python scripts/check_autogenerate_clean.py

health:
	curl -s http://localhost:8000/healthz

api-health:
	curl -s http://localhost:8000/healthz

worker-health:
	curl -s http://localhost:8000/healthz/workers

flower-health:
	curl -I http://localhost:5555 || true

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

reset:
	$(COMPOSE) down -v
	$(COMPOSE) up --build

first-run:
	./scripts/bootstrap-env.sh
	$(COMPOSE) up --build

seed-assets:
	python scripts/seed_mock_render_assets.py

seed-job:
	python scripts/seed_mock_job.py	
	
makemigration:
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"	
	
db-reset:
	$(COMPOSE) down -v
	$(COMPOSE) up --build -d postgres redis
	sleep 5
	$(COMPOSE) up --build -d api worker beat flower	

test:
	$(COMPOSE) exec api pytest -q