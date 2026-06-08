.DEFAULT_GOAL := help
.PHONY: help install build run uninstall validate test

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

install:  ## Create .venv and install runtime + dev deps (uv)
	uv sync

build:  ## Build the wheel + sdist
	uv build

run:  ## Launch the wizard (available once setup.py ships)
	uv run setup.py

uninstall:  ## Remove installed artifacts (implemented in a later plan)
	@echo "uninstall: not yet implemented"

validate:  ## Lint, format-check, type-check, security, dead-code
	uv run ruff check installer tests
	uv run ruff format --check installer tests
	uv run pyright
	uv run bandit -q -r installer
	uv run vulture

test:  ## Run tests with coverage
	uv run pytest --cov
