.PHONY: up down clean-volumes restart build logs help run test setup install-dev clean-env verify experiment experiment-down

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
	@if [ "$(build)" = "true" ]; then \
		echo "🔨 Rebuilding Docker images (no cache)..."; \
		CONFIG_PATH=$(config) docker compose build --no-cache; \
		echo "✅ Images rebuilt!"; \
	fi
	CONFIG_PATH=$(config) docker compose up -d
	@echo "✅ Services started!"
	@echo ""
	@echo "Available services:"
	@echo "  - Frontend:    http://localhost:3000"
	@echo "  - API:         http://localhost:8000"
	@echo "  - API Docs:    http://localhost:8000/docs"
	@echo "  - Postgres:    localhost:5432"
	@echo "  - Kafka:       localhost:9092"
	@echo ""
	@echo "View logs: make logs"

## up-debug: Start services in DEBUG mode (sim-worker writes results to ./output/ instead of Kafka)
up-debug: clean-volumes
	@echo "🐛 Starting OpenDT services in DEBUG MODE..."
	@echo "📋 Using config: $(config)"
	@mkdir -p output
	@if [ ! -f "$(config)" ]; then \
		echo "❌ Error: Config file not found: $(config)"; \
		exit 1; \
	fi
	@if [ "$(build)" = "true" ]; then \
		echo "🔨 Rebuilding Docker images (no cache)..."; \
		CONFIG_PATH=$(config) DEBUG_MODE=true docker compose build --no-cache; \
		echo "✅ Images rebuilt!"; \
	fi
	CONFIG_PATH=$(config) DEBUG_MODE=true docker compose up -d
	@echo "✅ Services started in DEBUG mode!"
	@echo ""
	@echo "🐛 DEBUG MODE: sim-worker will write results to ./output/"
	@echo "   Kafka publishing is DISABLED for sim-worker"
	@echo ""
	@echo "Available services:"
	@echo "  - Frontend:    http://localhost:3000"
	@echo "  - API:         http://localhost:8000"
	@echo "  - Postgres:    localhost:5432"
	@echo "  - Kafka:       localhost:9092"
	@echo ""
	@echo "View logs: make logs-sim-worker"
	@echo "View results: ls -la output/"

## run: Alias for 'up' (accepts config parameter)
run: up

## experiment: Run an experiment (make experiment name=<experiment_name>)
experiment: clean-volumes
	@if [ -z "$(name)" ]; then \
		echo "❌ Error: Please provide experiment name: make experiment name=my_experiment"; \
		exit 1; \
	fi
	@if [ ! -f "config/experiments/$(name).yaml" ]; then \
		echo "❌ Error: Experiment config not found: config/experiments/$(name).yaml"; \
		echo ""; \
		echo "Available experiments:"; \
		ls -1 config/experiments/*.yaml 2>/dev/null | xargs -n 1 basename | sed 's/.yaml//' | sed 's/^/  - /' || echo "  (none)"; \
		exit 1; \
	fi
	@echo "🧪 Starting experiment: $(name)"
	@echo "📋 Using config: config/experiments/$(name).yaml"
	@mkdir -p output/$(name)
	EXPERIMENT_NAME=$(name) CONFIG_PATH=./config/experiments/$(name).yaml docker compose up -d
	@echo "✅ Experiment started!"
	@echo ""
	@echo "Experiment: $(name)"
	@echo "Output: output/$(name)/"
	@echo ""
	@echo "View logs: make logs-sim-worker"

## experiment-debug: Run an experiment with debug mode enabled (make experiment-debug name=<experiment_name>)
experiment-debug: clean-volumes
	@if [ -z "$(name)" ]; then \
		echo "❌ Error: Please provide experiment name: make experiment-debug name=my_experiment"; \
		exit 1; \
	fi
	@if [ ! -f "config/experiments/$(name).yaml" ]; then \
		echo "❌ Error: Experiment config not found: config/experiments/$(name).yaml"; \
		echo ""; \
		echo "Available experiments:"; \
		ls -1 config/experiments/*.yaml 2>/dev/null | xargs -n 1 basename | sed 's/.yaml//' | sed 's/^/  - /' || echo "  (none)"; \
		exit 1; \
	fi
	@echo "🧪🐛 Starting experiment with DEBUG mode: $(name)"
	@echo "📋 Using config: config/experiments/$(name).yaml"
	@mkdir -p output/$(name)
	EXPERIMENT_NAME=$(name) DEBUG_MODE=true CONFIG_PATH=./config/experiments/$(name).yaml docker compose up -d
	@echo "✅ Experiment started in debug mode!"
	@echo ""
	@echo "Experiment: $(name)"
	@echo "Output: output/$(name)/"
	@echo "Debug files: output/$(name)/run_*/"
	@echo ""
	@echo "View logs: make logs-sim-worker"

## experiment-down: Stop experiment services
experiment-down:
	docker compose down
	@echo "✅ Experiment stopped"

## down: Stop all containers
down:
	@echo "⏹️  Stopping OpenDT services..."
	CONFIG_PATH=$(config) docker compose down
	@echo "✅ Services stopped!"

## clean-volumes: Stop containers and delete persistent volumes (Kafka & Postgres)
clean-volumes:
	@echo "🧹 Stopping containers and cleaning persistent volumes..."
	CONFIG_PATH=$(config) docker compose down -v
	@echo "🗑️  Removing named volumes..."
	-docker volume rm opendt-postgres-data 2>/dev/null || true
	-docker volume rm opendt-kafka-data 2>/dev/null || true
	@echo "✅ Clean slate ready!"

## restart: Restart all services (without cleaning volumes)
restart:
	@echo "♻️  Restarting OpenDT services..."
	CONFIG_PATH=$(config) docker compose restart
	@echo "✅ Services restarted!"

## build: Rebuild all Docker images
build:
	@echo "🔨 Building Docker images..."
	CONFIG_PATH=$(config) docker compose build --no-cache
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

## verify: Verify development environment setup
verify:
	@echo "🔍 Verifying development environment..."
	@if [ ! -d "$(VENV)" ]; then \
		echo "❌ Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@$(PYTHON) scripts/verify_setup.py

## logs: Tail logs for all services
logs:
	CONFIG_PATH=$(config) docker compose logs -f

## logs-api: Tail logs for API service only
logs-api:
	CONFIG_PATH=$(config) docker compose logs -f opendt-api

## logs-frontend: Tail logs for frontend service only
logs-frontend:
	CONFIG_PATH=$(config) docker compose logs -f frontend

## logs-kafka: Tail logs for Kafka service only
logs-kafka:
	CONFIG_PATH=$(config) docker compose logs -f kafka

## logs-dc-mock: Tail logs for dc-mock service only
logs-dc-mock:
	CONFIG_PATH=$(config) docker compose logs -f dc-mock

## logs-sim-worker: Tail logs for sim-worker service only
logs-sim-worker:
	CONFIG_PATH=$(config) docker compose logs -f sim-worker

## ps: Show running containers
ps:
	CONFIG_PATH=$(config) docker compose ps

## shell-api: Open a shell in the API container
shell-api:
	CONFIG_PATH=$(config) docker compose exec opendt-api /bin/bash

## shell-frontend: Open a shell in the frontend container
shell-frontend:
	CONFIG_PATH=$(config) docker compose exec frontend /bin/sh

## shell-postgres: Open psql in the Postgres container
shell-postgres:
	CONFIG_PATH=$(config) docker compose exec postgres psql -U opendt -d opendt

## kafka-topics: List Kafka topics
kafka-topics:
	CONFIG_PATH=$(config) docker compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list

## help: Show this help message
help:
	@echo "OpenDT Makefile Commands"
	@echo "========================"
	@echo ""
	@sed -n 's/^##//p' ${MAKEFILE_LIST} | column -t -s ':' | sed -e 's/^/ /'
