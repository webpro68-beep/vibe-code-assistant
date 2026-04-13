.PHONY: bootstrap up down logs backend-logs frontend-logs health test-backend tree smoke-sign-runway smoke-sign-kling smoke-sign-veo e2e-up e2e-test e2e-local e2e-down ci-e2e ci-report

bootstrap:
	cp backend/.env.example backend/.env.dev || true
	cp frontend/.env.local.example frontend/.env.local || true

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

backend-logs:
	docker compose logs -f api worker beat flower

frontend-logs:
	docker compose logs -f frontend

health:
	curl -fsS http://localhost:8000/healthz && echo
	curl -fsS http://localhost:8000/healthz/postgres && echo
	curl -fsS http://localhost:8000/healthz/redis && echo
	curl -fsS http://localhost:8000/healthz/workers && echo

test-backend:
	cd backend && python -m compileall app && pytest -q

tree:
	find . -maxdepth 4 | sort

smoke-sign-runway:
	python scripts/smoke/sign_relay.py "$$PROVIDER_RELAY_SHARED_SECRET" ./scripts/smoke/runway_success.json

smoke-sign-kling:
	python scripts/smoke/sign_relay.py "$$PROVIDER_RELAY_SHARED_SECRET" ./scripts/smoke/kling_success.json

smoke-sign-veo:
	python scripts/smoke/sign_relay.py "$$PROVIDER_RELAY_SHARED_SECRET" ./scripts/smoke/veo_success.json


e2e-up:
	docker compose up --build -d postgres redis minio minio-init api worker beat flower frontend edge-relay

e2e-test:
	docker compose run --rm --profile e2e playwright

e2e-local:
	docker compose up --build -d postgres redis minio minio-init api worker beat flower frontend edge-relay
	docker compose run --rm --profile e2e playwright

e2e-down:
	docker compose down -v


ci-e2e:
	mkdir -p artifacts/playwright artifacts/ci
	docker compose config
	docker compose up --build -d postgres redis minio minio-init api worker beat flower frontend edge-relay
	python scripts/ci/wait_for_stack.py 300
	docker compose run --rm --profile e2e playwright || (python scripts/ci/export_fail_fast_report.py && exit 1)
	python scripts/ci/export_fail_fast_report.py

ci-report:
	python scripts/ci/export_fail_fast_report.py

ci-e2e-matrix:
	mkdir -p artifacts/playwright artifacts/ci
	for provider in runway veo kling; do \
	  for mode in poll direct-relay edge-callback; do \
	    echo "=== Running $$provider / $$mode ==="; \
	    export E2E_PROVIDER=$$provider; \
	    export E2E_DELIVERY_MODE=$$mode; \
	    export ARTIFACT_SHARD=$${provider}-$${mode}; \
	    docker compose config; \
	    docker compose up --build -d postgres redis minio minio-init api worker beat flower frontend edge-relay; \
	    python scripts/ci/wait_for_stack.py 300; \
	    docker compose run --rm --profile e2e \
	      -e E2E_PROVIDER=$$provider \
	      -e E2E_DELIVERY_MODE=$$mode \
	      -e ARTIFACT_SHARD=$${provider}-$${mode} \
	      playwright || true; \
	    ARTIFACT_SHARD=$${provider}-$${mode} python scripts/ci/export_fail_fast_report.py; \
	    docker compose down -v; \
	  done; \
	done


ci-e2e-optimized:
	@echo "Optimized CI path is intended for GitHub Actions matrix workflow."
	@echo "Use: push branch / open PR / workflow_dispatch"


ci-smart-note:
	@echo "Smart CI is configured in GitHub Actions with path filters and conditional matrix."
	@echo "Local full run: make ci-e2e-matrix"


ci-quarantine-note:
	@echo "Use GitHub Actions workflow: flaky-test-quarantine"
	@echo "Optional workflow_dispatch input: grep"


migration-heads:
	cd backend && alembic heads

migration-check-single-head:
	python backend/scripts/check_single_alembic_head.py
