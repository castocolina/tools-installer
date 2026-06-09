.DEFAULT_GOAL := help
.PHONY: help install build setup run doctor uninstall validate test

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

install:  ## Create .venv and install runtime + dev deps (uv)
	uv sync

build:  ## Build the wheel + sdist
	uv build

setup:  ## Launch the setup wizard (pass flags via ARGS, e.g. ARGS="--all --yes")
	uv run setup.py $(ARGS)

run: setup  ## Alias for `setup`

doctor:  ## Audit PATH and wire ~/.myshellrc + shell rc files
	uv run setup.py --doctor

uninstall:  ## Remove installed artifacts (implemented in a later plan)
	@echo "uninstall: not yet implemented"

validate:  ## Lint, format-check, type-check, security, dead-code
	# setup.py (composition root) is lint/format-gated but stays out of pyright/coverage:
	# it imports the untyped, TTY-only questionary, which is isolated there by design.
	uv run ruff check installer tests setup.py
	uv run ruff format --check installer tests setup.py
	uv run pyright
	# B404/B603 (subprocess) and B310 (urlopen) are inherent to this installer; all
	# args/URLs come from the trusted registry, never external input. Skipped deliberately.
	uv run bandit -q -r installer --skip B404,B603,B310
	uv run vulture

test:  ## Run tests with coverage
	uv run pytest --cov
