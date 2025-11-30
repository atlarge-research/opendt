.PHONY: up down clean-volumes restart build logs help run test setup install-dev clean-env experiment experiment-down

# Default target
.DEFAULT_GOAL := help

# =============================================================================
# Configuration Variables
# =============================================================================

# Configuration file path (can be overridden: make up config=config/custom.yaml)
config ?= ./config/default.yaml

# Build flag - set to 'true' to rebuild images without cache
# Usage: make up build=true
build ?= false

# Virtual environment detection
VENV := .venv
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest
UV := $(shell command -v uv 2> /dev/null)

## up: Stop containers, delete volumes (clean slate), and start fresh (use build=true to rebuild images)
up: clean-volumes
	@echo "🚀 Starting OpenDT services with clean slate..."
	@echo "📋 Using config: $(config)"
	@if [ ! -f "$(config)" ]; then \
		echo "❌ Error: Config file not found: $(config)"; \
		exit 1; \
	fi
	@echo "🔧 Initializing run..."
	@$(PYTHON) scripts/opendt_cli.py init --config $(config)
	@RUN_ID=$$(cat .run_id) && \
	if [ ! -f "data/$$RUN_ID/.env" ]; then \
		echo "❌ Error: data/$$RUN_ID/.env not found after initialization"; \
		exit 1; \
	fi && \
	set -a && . ./data/$$RUN_ID/.env && set +a && \
	if [ "$(build)" = "true" ]; then \
		echo "🔨 Rebuilding Docker images (no cache)..."; \
		docker compose $$PROFILE_FLAG build --no-cache; \
	fi && \
	docker compose $$PROFILE_FLAG up -d
	@echo "✅ Services started!"
	@echo ""
	@echo "Available services:"
	@echo "  - Dashboard:   http://localhost:8000"
	@echo "  - API Docs:    http://localhost:8000/docs"
	@echo "  - Postgres:    localhost:5432"
	@echo "  - Kafka:       localhost:9092"
	@echo ""
	@echo "View logs: make logs"

## run: Alias for 'up' (accepts config parameter)
run: up

## down: Stop all containers
down:
	@echo "⏹️  Stopping OpenDT services..."
	@RUN_ID=$$(cat .run_id 2>/dev/null || true); \
	if [ -n "$$RUN_ID" ] && [ -f "data/$$RUN_ID/.env" ]; then \
		set -a && . ./data/$$RUN_ID/.env && set +a && docker compose $$PROFILE_FLAG down; \
	else \
		docker compose down; \
	fi
	@echo "✅ Services stopped!"

## clean-volumes: Stop containers and delete persistent volumes (Kafka & Postgres)
clean-volumes:
	@echo "🧹 Stopping containers and cleaning persistent volumes..."
	@RUN_ID=$$(cat .run_id 2>/dev/null || true); \
	if [ -n "$$RUN_ID" ] && [ -f "data/$$RUN_ID/.env" ]; then \
		set -a && . ./data/$$RUN_ID/.env && set +a && docker compose $$PROFILE_FLAG down -v; \
	else \
		docker compose down -v; \
	fi
	@echo "🗑️  Removing named volumes..."
	-docker volume rm opendt-postgres-data 2>/dev/null || true
	-docker volume rm opendt-kafka-data 2>/dev/null || true
	@echo "✅ Clean slate ready!"

## restart: Restart all services (without cleaning volumes)
restart:
	@echo "♻️  Restarting OpenDT services..."
	@RUN_ID=$$(cat .run_id 2>/dev/null || true); \
	if [ -n "$$RUN_ID" ] && [ -f "data/$$RUN_ID/.env" ]; then \
		set -a && . ./data/$$RUN_ID/.env && set +a && docker compose $$PROFILE_FLAG restart; \
	else \
		echo "⚠️  Run environment not found, restarting without profile"; \
		docker compose restart; \
	fi
	@echo "✅ Services restarted!"

## build: Rebuild all Docker images
build:
	@echo "🔨 Building Docker images..."
	@RUN_ID=$$(cat .run_id 2>/dev/null || true); \
	if [ -n "$$RUN_ID" ] && [ -f "data/$$RUN_ID/.env" ]; then \
		set -a && . ./data/$$RUN_ID/.env && set +a && docker compose $$PROFILE_FLAG build --no-cache; \
	else \
		echo "⚠️  Run environment not found, building without profile"; \
		docker compose build --no-cache; \
	fi
	@echo "✅ Images built!"

## rebuild: Clean, rebuild (no cache), and start (alias for make up build=true)
rebuild:
	@$(MAKE) up build=true

## setup: Create virtual environment and install all dependencies
setup:
	@echo "🔧 Setting up development environment..."
	@if [ -z "$(UV)" ]; then \
		echo "❌ uv not found. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	@echo "Creating virtual environment with uv..."
	uv venv
	@echo "Installing dependencies..."
	uv pip install -e libs/common
	uv pip install -e "libs/common[test]"
	uv pip install -e ".[dev]"
	@echo "✅ Development environment ready!"
	@echo ""
	@echo "Activate with: source .venv/bin/activate"

## install-dev: Install dependencies in existing venv (for CI or manual setup)
install-dev:
	@echo "📦 Installing development dependencies..."
	@if [ ! -d "$(VENV)" ]; then \
		echo "❌ Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	$(PYTHON) -m pip install -e libs/common
	$(PYTHON) -m pip install -e "libs/common[test]"
	$(PYTHON) -m pip install -e ".[dev]"
	@echo "✅ Dependencies installed!"

## test: Run tests for shared library
test:
	@echo "🧪 Running tests..."
	@if [ ! -d "$(VENV)" ]; then \
		echo "Virtual environment not found. Running 'make setup'..."; \
		$(MAKE) setup; \
	fi
	@if [ ! -f "$(PYTEST)" ]; then \
		echo "pytest not found. Running 'make install-dev'..."; \
		$(MAKE) install-dev; \
	fi
	$(PYTEST) libs/common/tests/ -v --tb=short
	@echo "✅ Tests passed!"

## clean-env: Remove virtual environment
clean-env:
	@echo "🧹 Removing virtual environment..."
	rm -rf $(VENV)
	rm -rf .uv
	@echo "✅ Environment cleaned!"

## logs: Tail logs for all services
logs:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose $$PROFILE_FLAG logs -f

## logs-dashboard: Tail logs for dashboard service only
logs-dashboard:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose logs -f dashboard

## logs-kafka: Tail logs for Kafka service only
logs-kafka:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose logs -f kafka

## logs-dc-mock: Tail logs for dc-mock service only
logs-dc-mock:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose logs -f dc-mock

## logs-simulator: Tail logs for simulator service only
logs-simulator:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose logs -f simulator

## logs-calibrator: Tail logs for calibrator service only
logs-calibrator:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose --profile calibration logs -f calibrator

## up-with-calibration: Start services including calibrator
# up-with-calibration: clean-volumes
# 	@echo "🚀 Starting OpenDT services with calibration enabled..."
# 	@echo "📋 Using config: $(config)"
# 	@if [ ! -f "$(config)" ]; then \
# 		echo "❌ Error: Config file not found: $(config)"; \
# 		exit 1; \
# 	fi
# 	@if [ "$(build)" = "true" ]; then \
# 		echo "🔨 Rebuilding Docker images (no cache)..."; \
# 		CONFIG_PATH=$(config) docker compose --profile calibration build --no-cache; \
# 		echo "✅ Images rebuilt!"; \
# 	fi
# 	CONFIG_PATH=$(config) docker compose --profile calibration up -d
# 	@echo "✅ Services started with calibration!"
# 	@echo ""
# 	@echo "Available services:"
# 	@echo "  - Dashboard:   http://localhost:8000"
# 	@echo "  - Calibrator:  Automatic power model calibration"
# 	@echo "  - Postgres:    localhost:5432"
# 	@echo "  - Kafka:       localhost:9092"
# 	@echo ""
# 	@echo "View logs: make logs-calibrator"

## ps: Show running containers
ps:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose $$PROFILE_FLAG ps

## shell-dashboard: Open a shell in the dashboard container
shell-dashboard:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose exec dashboard /bin/bash

## shell-postgres: Open psql in the Postgres container
shell-postgres:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose exec postgres psql -U opendt -d opendt

## kafka-topics: List Kafka topics
kafka-topics:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list

## help: Show this help message
help:
	@echo "OpenDT Makefile Commands"
	@echo "========================"
	@echo ""
	@sed -n 's/^##//p' ${MAKEFILE_LIST} | column -t -s ':' | sed -e 's/^/ /'
