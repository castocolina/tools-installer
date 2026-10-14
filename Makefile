.DEFAULT_GOAL := help
.PHONY: help install build setup run doctor fix uninstall guard unguard validate test e2e

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

doctor:  ## Audit PATH (read-only report; `make fix` applies changes)
	uv run setup.py --doctor

fix:  ## Wire PATH into your shell (~/.myshellrc + rc files)
	uv run setup.py --fix

uninstall:  ## Remove userspace artifacts: ~/.local/opt/* dirs, ~/.local/bin symlinks, and the managed ~/.myshellrc PATH block (previews, then asks to confirm)
	uv run setup.py --uninstall

guard:  ## Ban bare pip/npm (shims + aliases steering to uv/pnpm; opt-in, removable)
	uv run setup.py --guard

unguard:  ## Remove the pip/npm ban
	uv run setup.py --unguard

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
	# install.sh is the curl|bash bootstrap; lint it as part of the gate.
	# scripts/lib/prune-tmp-common.sh is a sourced-only library (15.7-07);
	# -x follows the wrappers' `source` into it so shellcheck sees the real
	# call graph instead of reporting an unfollowable SC1091.
	uv run shellcheck -x install.sh scripts/lib/prune-tmp-common.sh scripts/prune-tmp-linux.sh scripts/prune-user-tmpdir.sh

test:  ## Run tests with coverage, in parallel (pytest-xdist)
	uv run pytest -n auto --cov

e2e:  ## Real install/uninstall in a disposable Fedora container (podman/docker, never the host)
	scripts/container-e2e-verify.sh all
