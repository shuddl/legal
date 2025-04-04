.PHONY: help clean lint format test test-unit test-integration coverage install dev-install run update-config

# Default target
.DEFAULT_GOAL := help

# Python binary
PYTHON := python
PIP := pip

# Project directories
SRC_DIR := src
TEST_DIR := tests
CONFIG_DIR := config
DATA_DIR := data
LOGS_DIR := logs

# Python package
PACKAGE := perera_lead_scraper

# Create required directories
$(shell mkdir -p $(CONFIG_DIR) $(DATA_DIR) $(LOGS_DIR))

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install package
	$(PIP) install -e .

dev-install: ## Install package with development dependencies
	$(PIP) install -e ".[dev]"

clean: ## Remove build artifacts and cache files
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf **/__pycache__/
	rm -rf **/*.pyc
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/

lint: ## Run linters (ruff, mypy)
	ruff $(SRC_DIR) $(TEST_DIR)
	mypy $(SRC_DIR)

format: ## Format code with black and isort
	black $(SRC_DIR) $(TEST_DIR)
	ruff --select I --fix $(SRC_DIR) $(TEST_DIR)

test: ## Run all tests
	pytest

test-unit: ## Run unit tests
	pytest $(TEST_DIR)/unit

test-integration: ## Run integration tests
	pytest $(TEST_DIR)/integration

coverage: ## Generate test coverage report
	pytest --cov=$(SRC_DIR) --cov-report=html
	@echo "Coverage report available at htmlcov/index.html"

run: ## Run the application
	$(PYTHON) -m $(PACKAGE).main run

status: ## Show application status
	$(PYTHON) -m $(PACKAGE).main status

test-sources: ## Test source availability
	$(PYTHON) -m $(PACKAGE).main test-sources

export: ## Export leads to CSV
	$(PYTHON) -m $(PACKAGE).main export

update-config: ## Update configuration files with latest templates
	@echo "Creating default configuration files if they don't exist"
	@if [ ! -f $(CONFIG_DIR)/sources.json ]; then \
		echo '{"sources": []}' > $(CONFIG_DIR)/sources.json; \
		echo "Created $(CONFIG_DIR)/sources.json"; \
	fi
	@if [ ! -f $(CONFIG_DIR)/rss_sources.json ]; then \
		echo '{"sites": []}' > $(CONFIG_DIR)/rss_sources.json; \
		echo "Created $(CONFIG_DIR)/rss_sources.json"; \
	fi
	@if [ ! -f $(CONFIG_DIR)/city_portals.json ]; then \
		echo '{"cities": []}' > $(CONFIG_DIR)/city_portals.json; \
		echo "Created $(CONFIG_DIR)/city_portals.json"; \
	fi
	@if [ ! -f $(CONFIG_DIR)/news_sources.json ]; then \
		echo '{"sites": []}' > $(CONFIG_DIR)/news_sources.json; \
		echo "Created $(CONFIG_DIR)/news_sources.json"; \
	fi
	@if [ ! -f $(CONFIG_DIR)/hubspot_config.json ]; then \
		echo '{}' > $(CONFIG_DIR)/hubspot_config.json; \
		echo "Created $(CONFIG_DIR)/hubspot_config.json"; \
	fi