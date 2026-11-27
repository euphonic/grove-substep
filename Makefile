# The Grove — one-command dev and verification. POSIX make (macOS ships GNU Make 3.81).
# `make check` needs no Docker and no API keys. `make check-db` needs `supabase start`.

SHELL := /bin/bash
UV    := env -u VIRTUAL_ENV uv
API   := cd api &&
WEB   := cd web &&

.PHONY: help install env db db-stop db-reset dev api worker web seed \
        lint typecheck test evals check check-db check-live

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-12s %s\n", $$1, $$2}'

install: ## Install API and web dependencies
	$(API) $(UV) sync
	$(WEB) pnpm install

env: ## Create .env files from .env.example where missing (never overwrites)
	@for d in api web; do \
	  if [ -e $$d/.env ]; then echo "$$d/.env exists, leaving it alone"; \
	  else cp $$d/.env.example $$d/.env && echo "created $$d/.env (fill in keys from 'supabase status -o env')"; fi; \
	done

db: ## Start local Supabase (Postgres, auth, Studio, Mailpit)
	supabase start

db-stop: ## Stop local Supabase
	supabase stop

db-reset: ## Recreate the local database from migrations
	supabase db reset

dev: db ## Start Supabase, API, worker and web together (Ctrl-C stops all)
	@trap 'kill 0' INT TERM EXIT; \
	  (cd api && $(UV) run fastapi dev app/main.py --port 8000) & \
	  (cd api && $(UV) run python -m app.worker) & \
	  (cd web && pnpm dev) & \
	  wait

api: ## Run only the API
	$(API) $(UV) run fastapi dev app/main.py --port 8000

worker: ## Run only the worker
	$(API) $(UV) run python -m app.worker

web: ## Run only the web app
	$(WEB) pnpm dev

seed: ## Create synthetic test users, profiles and journal entries
	$(API) $(UV) run python -m app.scripts.seed

lint: ## Ruff + Prettier + ESLint
	$(API) $(UV) run ruff check .
	$(API) $(UV) run ruff format --check .
	$(WEB) pnpm lint

typecheck: ## mypy + svelte-check
	$(API) $(UV) run mypy
	$(WEB) pnpm check

test: ## pytest (no DB) + Vitest
	$(API) $(UV) run pytest -m "not db"
	$(WEB) pnpm test

evals: ## Safety and tradition evals in mock mode
	$(API) $(UV) run python -m evals.safety
	$(API) $(UV) run python -m evals.traditions

check: lint typecheck test evals ## Full offline verification suite (used by the Stop hook and CI)
	@echo "make check: all passed"

check-db: ## Reset local DB from migrations and run RLS tests (needs supabase start)
	supabase db reset
	$(API) $(UV) run pytest -m db

check-live: ## Tradition evals against real models and voices (costs money; manual only)
	@echo "check-live: nothing to run until M5 (tradition packs and guide)"
