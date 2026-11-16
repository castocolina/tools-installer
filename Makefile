.DEFAULT_GOAL := help
.PHONY: help dev-setup build run doctor fix uninstall lint format-check typecheck security dead-code shellcheck validate test hooks-e2e e2e verify-registry audit-catalog

help:  ## Show available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

dev-setup:  ## Create .venv and install deps (uv), then the commit hook and the push gate
	uv sync
	uv run python -m devtools.hooks install

build:  ## Build the wheel + sdist
	uv build

run:  ## Launch the setup wizard (pass flags via ARGS, e.g. ARGS="--all --yes")
	uv run --isolated --no-dev setup.py $(ARGS)

doctor:  ## Audit PATH (report; launch repairs aside, `make fix` applies changes)
	uv run --isolated --no-dev setup.py --doctor

fix:  ## Wire PATH into your shell (~/.myshellrc + rc files)
	uv run --isolated --no-dev setup.py --fix

uninstall:  ## Remove userspace artifacts: ~/.local/opt/* dirs, ~/.local/bin symlinks, and the managed ~/.myshellrc PATH block (previews, then asks to confirm)
	uv run --isolated --no-dev setup.py --uninstall

verify-registry:  ## Check release assets and pins against upstream (read-only; needs network)
	uv run --isolated --no-dev python -m installer.verify_registry $(ARGS)

audit-catalog:  ## Audit the catalog for the catalog-audit skill (read-only facts; writes only .planning/audits/catalog)
	uv run --isolated --no-dev python -m installer.catalog_audit $(ARGS)

lint:  ## [gate] Lint with ruff check
	# The composition root lives in installer/compose.py, under pyright, coverage, bandit and
	# vulture. setup.py is lint/format-gated but stays out of pyright/coverage: it imports the
	# untyped, TTY-only questionary and holds only argument parsing, prompts and the calls.
	uv run ruff check installer tests devtools setup.py

format-check:  ## [gate] Check formatting with ruff format (no rewrite)
	uv run ruff format --check installer tests devtools setup.py

typecheck:  ## [gate] Type-check with pyright (strict)
	uv run pyright

security:  ## [gate] Security scan with bandit
	# B404/B603 (subprocess) and B310 (urlopen) are inherent to this installer; all
	# args/URLs come from the trusted registry, never external input. Skipped deliberately.
	uv run bandit -q -r installer devtools --skip B404,B603,B310

dead-code:  ## [gate] Find dead code with vulture
	uv run vulture

shellcheck:  ## [gate] Lint the shell scripts with shellcheck
	# install.sh is the curl|bash bootstrap; lint it as part of the gate.
	# scripts/lib/prune-tmp-common.sh is a sourced-only library (15.7-07);
	# -x follows the wrappers' `source` into it so shellcheck sees the real
	# call graph instead of reporting an unfollowable SC1091.
	uv run shellcheck -x install.sh scripts/lib/prune-tmp-common.sh scripts/prune-tmp-linux.sh scripts/prune-user-tmpdir.sh scripts/container-e2e-verify.sh scripts/hooks-e2e.sh

validate:  ## Run every commit-stage gate through pre-commit
	uv run pre-commit run --all-files

test:  ## [gate] Run tests with coverage, in parallel (pytest-xdist)
	uv run pytest -n auto --cov

hooks-e2e:  ## Prove the commit hook and the push gate with real git in scratch repos (never this checkout)
	uv run scripts/hooks-e2e.sh

e2e:  ## Real install/uninstall in a disposable container (ARGS="--distro debian"; podman/docker, never the host)
	scripts/container-e2e-verify.sh all $(ARGS)
