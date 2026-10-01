# Running and checking the Taimen platform.
#   make submodules           → component submodules at their pinned revisions
#   make secrets              → .env and the IAM signing key with random secrets
#   make up                   → start compose profiles (core edge by default)
#   make bootstrap            → initial setup (tenant, operator, PAT, workspace, catalog)
#   make smoke                → healthz of the running services
#   make check                → ruff + unit tests of the components (as in CI)
#   make guide                → build the guide guide/

SHELL := /bin/bash
.DEFAULT_GOAL := help
PROFILES ?= core edge
COMPOSE := docker compose $(foreach p,$(PROFILES),--profile $(p))
COMPONENTS_PY := platform-auth-sdk platform-llm skill-sdk iam-service control-plane memory-service notification-service
ENV_NAME ?= $(or $(shell sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env 2>/dev/null),taimen)
GUIDE_MISSING = echo "there is no guide/ directory: the guide is added to the repository separately (guide/mkdocs.yml)"
# The package SDK is the package-sdk/ submodule; until it is checked out, the package targets
# and bootstrap step 5b stop with this hint.
PACKAGE_SDK_MISSING = echo "there is no package-sdk/ submodule: the package SDK is needed for packages (make submodules)"

.PHONY: help submodules status secrets config build up down ps logs smoke bootstrap reset-state \
        check check-% lint-% test-% tools-check linkcheck oss-check guide guide-serve \
        packages-check packages-plan packages-apply

help: ## List of targets
	@grep -E '^[a-zA-Z_%-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

submodules: ## Initialize submodules at their pinned revisions
	git submodule update --init --recursive

status: ## Submodule pointers and uncommitted changes
	@git submodule status
	@git status --short

secrets: ## Create .env from .env.example and the IAM signing key (leaves existing files alone)
	@test -f .env || { cp .env.example .env && chmod 600 .env && echo "created .env"; }
	@python3 tools/fill_secrets.py .env
	@mkdir -p secrets
	@test -f secrets/iam-signing.pem || openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out secrets/iam-signing.pem 2>/dev/null
	@chmod 600 secrets/*.pem
	@echo "secrets in place: .env, secrets/iam-signing.pem (on Linux: chown 10001 secrets/*.pem)"

config: ## Validate compose.yml after interpolation
	$(COMPOSE) config --quiet && echo "compose.yml is valid for profiles: $(PROFILES)"

build: ## Build the images of the selected profiles
	$(COMPOSE) build

up: ## Start the selected profiles: make up PROFILES="core notify edge"
	@if [[ " $(PROFILES) " == *" edge "* && ! -f guide/mkdocs.yml ]]; then \
	  $(GUIDE_MISSING); echo "the edge profile builds the guide service — without it: make up PROFILES=core"; exit 1; fi
	$(COMPOSE) up -d --build

down: ## Stop everything (data stays in the volumes)
	docker compose --profile "*" down

ps: ## Container status
	docker compose --profile "*" ps

logs: ## Service logs: make logs svc=control-plane-api
	docker compose --profile "*" logs -f $(svc)

smoke: ## Check healthz of the running services via the 127.0.0.1 ports
	@python3 tools/smoke.py

# PyYAML and jsonschema are needed by the catalog-from-packages step (package-sdk): through uv
# they are not installed into the system python3; without uv, the system python3 must have them.
BOOTSTRAP_PY = $(if $(shell command -v uv 2>/dev/null),uv run --no-project --quiet --with pyyaml --with jsonschema python3,python3)

bootstrap: ## Initial setup, catalog from deploy/packages.yaml; ARGS="--agents agents.json" — agents as well
	@$(BOOTSTRAP_PY) deploy/bootstrap.py --env .env $(ARGS)

reset-state: ## After resetting volumes: move away the bootstrap state and the credentials it issued (to secrets/stale-<time>/)
	@ts=$$(date +%Y%m%d-%H%M%S); dir=secrets/stale-$$ts; mkdir -p $$dir; \
	for f in deploy/state/$(ENV_NAME).json secrets/harness-pat secrets/control-plane-iam.env \
	         secrets/notification-iam.env secrets/memory-service-iam.env secrets/agents; do \
	  test -e $$f && mv $$f $$dir/ && echo "  → $$dir/$$(basename $$f)"; done; \
	rmdir $$dir 2>/dev/null && echo "nothing to move" || echo "state reset; the signing key and .env are untouched — next: make bootstrap"

check: $(addprefix check-,$(COMPONENTS_PY)) tools-check ## ruff + unit tests of all components and tools/

check-%: lint-% test-% ## ruff + tests of one component: make check-control-plane
	@true

lint-%:
	@echo "== ruff: $*"; cd $* && uv run --quiet ruff check . && uv run --quiet ruff format --check .

test-control-plane:
	@echo "== pytest (unit, client; db-test on 5434): control-plane"; cd control-plane && docker compose --profile test up -d --wait db-test >/dev/null && uv run --quiet pytest -q tests/unit tests/client; status=$$?; docker compose --profile test down >/dev/null 2>&1; exit $$status
test-skill-sdk:
	@echo "== pytest: skill-sdk"; cd skill-sdk && uv run --quiet --all-extras pytest -q
test-memory-service:
	@echo "== pytest (unit): memory-service"; cd memory-service && uv run --quiet --extra mcp pytest -q --ignore=tests/integration
test-%:
	@echo "== pytest: $*"; cd $* && uv run --quiet pytest -q

tools-check: ## ruff + tests of the tools/ and deploy/ scripts
	@uvx ruff check tools deploy
	@uv run --quiet --no-project --with pytest python -m pytest -q tools/tests

linkcheck: ## Check relative links in the umbrella documentation
	@python3 tools/linkcheck.py

INSTALL ?= deploy/packages.yaml
SERVER ?= http://taimen.localhost
PLAN ?= deploy/state/$(ENV_NAME).packages-plan.json
# The package SDK from its submodule with the core's code (extra sandbox): check also runs the core's validators.
PACKAGE_SDK = uv run --quiet --project package-sdk --all-extras package-sdk
REQUIRE_PACKAGE_SDK = test -f package-sdk/pyproject.toml || { $(PACKAGE_SDK_MISSING); exit 1; }

packages-check: ## Check catalog packages without a running installation: make packages-check [INSTALL=deploy/packages.yaml]
	@$(REQUIRE_PACKAGE_SDK)
	@$(PACKAGE_SDK) check --install $(INSTALL)

packages-plan: ## Build the installation plan against a live Control Plane, writes nothing to it: make packages-plan [SERVER=…]
	@$(REQUIRE_PACKAGE_SDK)
	@mkdir -p $(dir $(PLAN))
	@$(PACKAGE_SDK) plan --install $(INSTALL) --server $(SERVER) --out $(PLAN)

packages-apply: ## Apply exactly the plan of packages-plan after review: make packages-apply [SERVER=…]
	@$(REQUIRE_PACKAGE_SDK)
	@$(PACKAGE_SDK) apply --plan $(PLAN) --server $(SERVER)

oss-check: ## Check that the umbrella is publishable (without gitleaks): make oss-check STOPLIST=<file>
	@python3 tools/oss_check.py . --skip-gitleaks $(if $(STOPLIST),--stoplist $(STOPLIST))

guide: ## Build the guide guide/ into guide/site (MkDocs Material)
	@test -f guide/mkdocs.yml || { $(GUIDE_MISSING); exit 1; }
	cd guide && uv run --quiet --no-project --with-requirements requirements.txt mkdocs build --strict

guide-serve: ## The guide with live reload at http://127.0.0.1:8008
	@test -f guide/mkdocs.yml || { $(GUIDE_MISSING); exit 1; }
	cd guide && uv run --quiet --no-project --with-requirements requirements.txt mkdocs serve -a 127.0.0.1:8008
