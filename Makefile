# Running and checking the Taimen platform.
#   make submodules           → component submodules at their pinned revisions
#   make secrets              → .env and the key files with random secrets
#   make up                   → start compose profiles (core edge by default)
#   make bootstrap            → initial setup (tenant, operator, PAT, workspace, catalog, services)
#   make smoke                → healthz of the running services
#   make check                → ruff + unit tests of the components (as in CI)
#   make guide                → build the guide guide/
#
# Compose runs from the root with deploy/local/compose.yml (TAI-ADR-0064): the targets
# below and the tools/compose wrapper. A root compose.override.yml (settings of your
# installation) is added as a second file when it exists.

SHELL := /bin/bash
.DEFAULT_GOAL := help
PROFILES ?= core edge
COMPOSE_BASE := docker compose --project-directory . -f deploy/local/compose.yml $(if $(wildcard compose.override.yml),-f compose.override.yml)
COMPOSE := $(COMPOSE_BASE) $(foreach p,$(PROFILES),--profile $(p))
ALL_PROFILES := core notify idp console harness fleet edge
ENV_NAME ?= $(or $(shell sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env 2>/dev/null),taimen)

# Components and their directories (the layout of .gitmodules: services/, sdk/, apps/).
SERVICES := control-plane iam-service memory-service notification-service fleet human-harness
SDKS := platform-auth-sdk platform-llm skill-sdk package-sdk
COMPONENTS_PY := platform-auth-sdk platform-llm skill-sdk package-sdk iam-service control-plane memory-service notification-service fleet
component_dir = $(if $(filter $(1),$(SERVICES)),services/$(1),$(if $(filter $(1),$(SDKS)),sdk/$(1),$(if $(filter $(1),console),apps/console,$(error unknown component $(1)))))
SUBMAKE := $(MAKE) --no-print-directory -C

GUIDE_MISSING = echo "there is no guide/ directory: the guide is added to the repository separately (guide/mkdocs.yml)"
PACKAGE_SDK_DIR := $(call component_dir,package-sdk)
# The package SDK is the sdk/package-sdk submodule; until it is checked out, the package
# targets and bootstrap step 5b stop with this hint.
PACKAGE_SDK_MISSING = echo "there is no $(PACKAGE_SDK_DIR)/ submodule: the package SDK is needed for packages (make submodules)"

.PHONY: help submodules status secrets config config-all build up down ps logs smoke bootstrap reset-state \
        check check-% lint-% test-% tools-check linkcheck oss-check guide guide-serve \
        packages-check packages-plan packages-apply

help: ## List of targets
	@grep -E '^[a-zA-Z_%-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

submodules: ## Initialize submodules at their pinned revisions
	git submodule update --init --recursive

status: ## Submodule pointers and uncommitted changes
	@git submodule status
	@git status --short

secrets: ## Create .env from .env.example and the key files (leaves existing files alone)
	@test -f .env || { cp .env.example .env && chmod 600 .env && echo "created .env"; }
	@python3 tools/fill_secrets.py .env
	@mkdir -p secrets
	@test -f secrets/iam-signing.pem || openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out secrets/iam-signing.pem 2>/dev/null
	@chmod 600 secrets/*.pem
	@# the console's OIDC client secret: realm-render puts it into the Keycloak realm on the first start
	@test -f secrets/runtime-console-oidc-secret || { umask 077; openssl rand -base64 32 | tr '+/' '-_' | tr -d '=' > secrets/runtime-console-oidc-secret; }
	@test -f secrets/runtime-console-cookie-secret || { umask 077; openssl rand -base64 48 | tr '+/' '-_' | tr -d '=' > secrets/runtime-console-cookie-secret; }
	@echo "secrets in place: .env, secrets/iam-signing.pem, secrets/runtime-console-{oidc,cookie}-secret (on Linux: chown 10001 secrets/*.pem secrets/runtime-console-*-secret)"

config: ## Validate deploy/local/compose.yml after interpolation for PROFILES
	$(COMPOSE) config --quiet && echo "deploy/local/compose.yml is valid for profiles: $(PROFILES)"

config-all: ## Validate deploy/local/compose.yml for every profile, one by one and all together
	@for p in $(ALL_PROFILES); do $(COMPOSE_BASE) --profile $$p config --quiet || exit 1; echo "  $$p: ok"; done
	@$(COMPOSE_BASE) $(foreach p,$(ALL_PROFILES),--profile $(p)) config --quiet && echo "  all profiles: ok"

build: ## Build the images of the selected profiles
	$(COMPOSE) build

up: ## Start the selected profiles: make up PROFILES="core notify console edge"
	@if [[ " $(PROFILES) " == *" edge "* && ! -f guide/mkdocs.yml ]]; then \
	  $(GUIDE_MISSING); echo "the edge profile builds the guide service — without it: make up PROFILES=core"; exit 1; fi
	$(COMPOSE) up -d --build

down: ## Stop everything (data stays in the volumes)
	$(COMPOSE_BASE) --profile "*" down

ps: ## Container status
	$(COMPOSE_BASE) --profile "*" ps

logs: ## Service logs: make logs svc=control-plane-api
	$(COMPOSE_BASE) --profile "*" logs -f $(svc)

smoke: ## Check healthz of the running services via the 127.0.0.1 ports
	@python3 tools/smoke.py

# PyYAML and jsonschema are needed by the catalog-from-packages step (package-sdk): through uv
# they are not installed into the system python3; without uv, the system python3 must have them.
BOOTSTRAP_PY = $(if $(shell command -v uv 2>/dev/null),uv run --no-project --quiet --with pyyaml --with jsonschema python3,python3)

bootstrap: ## Initial setup, catalog from deploy/packages.yaml; ARGS="--harness-people deploy/harness-people.json" — assistants as well
	@$(BOOTSTRAP_PY) deploy/bootstrap.py --env .env $(ARGS)

reset-state: ## After resetting volumes: move away the bootstrap state and the credentials it issued (to secrets/stale-<time>/)
	@ts=$$(date +%Y%m%d-%H%M%S); dir=secrets/stale-$$ts; mkdir -p $$dir; \
	for f in deploy/state/$(ENV_NAME).json deploy/state/$(ENV_NAME).packages-plan.json secrets/harness-pat \
	         secrets/control-plane-iam.env secrets/notification-iam.env secrets/fleet-iam.env secrets/harness; do \
	  test -e $$f && mv $$f $$dir/ && echo "  → $$dir/$$(basename $$f)"; done; \
	rmdir $$dir 2>/dev/null && echo "nothing to move" || echo "state reset; the signing key, the console secrets and .env are untouched — next: make bootstrap"

check: $(addprefix check-,$(COMPONENTS_PY)) tools-check ## ruff + unit tests of all components and tools/

check-%: lint-% test-% ## ruff + tests of one component: make check-control-plane
	@true

# Components with their own make targets: the umbrella calls them instead of copying the
# commands — the same targets are called by the component's CI.
MAKE_COMPONENTS := control-plane skill-sdk package-sdk iam-service memory-service notification-service fleet

$(addprefix lint-,$(MAKE_COMPONENTS)): lint-%:
	@echo "== lint: $*"; $(SUBMAKE) $(call component_dir,$*) lint

lint-%:
	@echo "== ruff: $*"; cd $(call component_dir,$*) && uv run --quiet ruff check . && uv run --quiet ruff format --check .

test-control-plane:
	@echo "== pytest (unit, client; db-test on 5434): control-plane"; $(SUBMAKE) $(call component_dir,control-plane) test PYTEST_ARGS="-q tests/unit tests/client"; status=$$?; $(SUBMAKE) $(call component_dir,control-plane) test-db-down >/dev/null 2>&1; exit $$status
test-skill-sdk:
	@echo "== pytest: skill-sdk (+ through the core's skill executor)"; $(SUBMAKE) $(call component_dir,skill-sdk) test test-e2e
# package-sdk: the moved tools' tests run on the component's fixture snapshot of the packages —
# PACKAGE_SDK_UMBRELLA over the whole suite expects the platform packages, and the umbrella ships
# only packages/example; the umbrella's packages and installation go against the format's schema.
test-package-sdk:
	@echo "== pytest: package-sdk (+ umbrella packages against the schema)"; cd $(PACKAGE_SDK_DIR) && uv run --quiet --all-extras pytest -q && PACKAGE_SDK_UMBRELLA=$(CURDIR) uv run --quiet --all-extras pytest -q tests/test_umbrella_packages.py
test-memory-service:
	@echo "== pytest (unit): memory-service"; $(SUBMAKE) $(call component_dir,memory-service) test PYTEST_ARGS="tests --ignore=tests/integration"
# notification-service: all tests need PostgreSQL in NS_TEST_DATABASE_URL (see the CI job).
test-iam-service test-fleet test-notification-service: test-%:
	@echo "== pytest: $*"; $(SUBMAKE) $(call component_dir,$*) test
test-%:
	@echo "== pytest: $*"; cd $(call component_dir,$*) && uv run --quiet pytest -q

# The bootstrap tests run deploy/bootstrap.py against in-process fake IAM and Control Plane
# servers (no stack, no network) and import the package SDK from sdk/package-sdk.
TOOLS_TEST_PY = uv run --quiet --no-project --with pytest --with pyyaml --with jsonschema --with ruamel.yaml python

tools-check: ## ruff + tests of the tools/ and deploy/ scripts (bootstrap against fake servers)
	@uvx ruff check tools deploy
	@$(TOOLS_TEST_PY) -m pytest -q tools/tests

linkcheck: ## Check relative links in the umbrella documentation
	@python3 tools/linkcheck.py

INSTALL ?= deploy/packages.yaml
SERVER ?= http://taimen.localhost
PLAN ?= deploy/state/$(ENV_NAME).packages-plan.json
# The package SDK from its submodule with the core's code (extra sandbox): check also runs the core's validators.
PACKAGE_SDK = uv run --quiet --project $(PACKAGE_SDK_DIR) --all-extras package-sdk
REQUIRE_PACKAGE_SDK = test -f $(PACKAGE_SDK_DIR)/pyproject.toml || { $(PACKAGE_SDK_MISSING); exit 1; }

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
