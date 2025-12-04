.PHONY: up down clean-volumes help test setup clean-env

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

# =============================================================================
# Core Commands
# =============================================================================

## up: Start OpenDT services (use build=true to rebuild images)
up: clean-volumes
	@echo ""
	@echo "Starting OpenDT..."
	@echo "Config: $(config)"
	@echo ""
	@if [ ! -f "$(config)" ]; then \
		echo "Error: Config file not found: $(config)"; \
		exit 1; \
	fi
	@$(PYTHON) scripts/opendt_cli.py init --config $(config)
	@RUN_ID=$$(cat .run_id) && \
	if [ ! -f "data/$$RUN_ID/.env" ]; then \
		echo "Error: data/$$RUN_ID/.env not found after initialization"; \
		exit 1; \
	fi && \
	set -a && . ./data/$$RUN_ID/.env && set +a && \
	if [ "$(build)" = "true" ]; then \
		echo "Rebuilding Docker images..."; \
		docker compose $$PROFILE_FLAG build --no-cache; \
	fi && \
	echo "Starting containers..." && \
	docker compose $$PROFILE_FLAG up -d
	@echo ""
	@echo "Services started:"
	@echo "  Dashboard   http://localhost:3000"
	@echo "  API         http://localhost:3001"
	@echo ""
	@echo "View logs with: make logs-<service>"
	@echo ""

## down: Stop all containers
down:
	@echo ""
	@echo "Stopping OpenDT services..."
	@RUN_ID=$$(cat .run_id 2>/dev/null || true); \
	if [ -n "$$RUN_ID" ] && [ -f "data/$$RUN_ID/.env" ]; then \
		set -a && . ./data/$$RUN_ID/.env && set +a && docker compose $$PROFILE_FLAG down; \
	else \
		docker compose down; \
	fi
	@echo "Done."
	@echo ""

## clean-volumes: Stop containers and delete all persistent volumes
clean-volumes:
	@RUN_ID=$$(cat .run_id 2>/dev/null || true); \
	if [ -n "$$RUN_ID" ] && [ -f "data/$$RUN_ID/.env" ]; then \
		set -a && . ./data/$$RUN_ID/.env && set +a && docker compose $$PROFILE_FLAG down -v 2>/dev/null || true; \
	else \
		docker compose down -v 2>/dev/null || true; \
	fi
	@docker volume rm opendt-kafka-data 2>/dev/null || true
	@docker volume rm opendt-grafana-storage 2>/dev/null || true

# =============================================================================
# Development Commands
# =============================================================================

## setup: Create virtual environment and install dependencies
setup:
	@echo ""
	@echo "Setting up development environment..."
	@if [ -z "$(UV)" ]; then \
		echo "Error: uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	@echo "Creating virtual environment..."
	@uv venv
	@echo "Installing dependencies..."
	@uv pip install -e libs/common
	@uv pip install -e "libs/common[test]"
	@uv pip install -e ".[dev]"
	@echo ""
	@echo "Done. Activate with: source .venv/bin/activate"
	@echo ""

## test: Run tests
test:
	@echo ""
	@echo "Running tests..."
	@if [ ! -d "$(VENV)" ]; then \
		echo "Virtual environment not found. Running setup..."; \
		$(MAKE) setup; \
	fi
	@if [ ! -f "$(PYTEST)" ]; then \
		echo "pytest not found. Running setup..."; \
		$(MAKE) setup; \
	fi
	@$(PYTEST) libs/common/tests/ -v --tb=short
	@echo ""
	@echo "All tests passed."
	@echo ""

## clean-env: Remove virtual environment
clean-env:
	@echo ""
	@echo "Removing virtual environment..."
	@rm -rf $(VENV)
	@rm -rf .uv
	@echo "Done."
	@echo ""

# =============================================================================
# Logging Commands
# =============================================================================

## logs-dashboard: Tail logs for dashboard service
logs-dashboard:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose logs -f dashboard

## logs-dc-mock: Tail logs for dc-mock service
logs-dc-mock:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose logs -f dc-mock

## logs-simulator: Tail logs for simulator service
logs-simulator:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose logs -f simulator

## logs-calibrator: Tail logs for calibrator service
logs-calibrator:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose --profile calibration logs -f calibrator

# =============================================================================
# Shell Commands
# =============================================================================

## shell-dashboard: Open a shell in the dashboard container
shell-dashboard:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose exec dashboard /bin/bash

## shell-dc-mock: Open a shell in the dc-mock container
shell-dc-mock:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose exec dc-mock /bin/bash

## shell-simulator: Open a shell in the simulator container
shell-simulator:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose exec simulator /bin/bash

## shell-calibrator: Open a shell in the calibrator container
shell-calibrator:
	@RUN_ID=$$(cat .run_id) && set -a && . ./data/$$RUN_ID/.env && set +a && docker compose --profile calibration exec calibrator /bin/bash

# =============================================================================
# Help
# =============================================================================

## help: Show available commands
help:
	@echo ""
	@echo "OpenDT Commands"
	@echo "==============="
	@echo ""
	@sed -n 's/^##//p' ${MAKEFILE_LIST} | column -t -s ':' | sed -e 's/^/  /'
	@echo ""
