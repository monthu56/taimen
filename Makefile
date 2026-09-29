# Запуск и проверка платформы Taimen.
#   make submodules           → сабмодули компонентов на закреплённых ревизиях
#   make secrets              → .env и ключ подписи IAM со случайными секретами
#   make up                   → поднять профили compose (по умолчанию core edge)
#   make bootstrap            → первичная инициализация (tenant, оператор, PAT, workspace)
#   make smoke                → healthz поднятых сервисов
#   make check                → ruff + unit-тесты компонентов (как CI)
#   make guide                → собрать руководство guide/

SHELL := /bin/bash
.DEFAULT_GOAL := help
PROFILES ?= core edge
COMPOSE := docker compose $(foreach p,$(PROFILES),--profile $(p))
COMPONENTS_PY := platform-auth-sdk platform-llm skill-sdk iam-service control-plane memory-service notification-service
ENV_NAME ?= $(or $(shell sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env 2>/dev/null),taimen)
GUIDE_MISSING = echo "каталога guide/ нет: руководство кладётся в репозиторий отдельно (guide/mkdocs.yml)"

.PHONY: help submodules status secrets config build up down ps logs smoke bootstrap reset-state \
        check check-% lint-% test-% tools-check linkcheck oss-check guide guide-serve \
        packages-check packages-plan packages-apply

help: ## Список целей
	@grep -E '^[a-zA-Z_%-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

submodules: ## Инициализировать сабмодули на закреплённых ревизиях
	git submodule update --init --recursive

status: ## Указатели сабмодулей и незакоммиченные изменения
	@git submodule status
	@git status --short

secrets: ## Создать .env из .env.example и ключ подписи IAM (существующее не трогает)
	@test -f .env || { cp .env.example .env && chmod 600 .env && echo "создан .env"; }
	@python3 tools/fill_secrets.py .env
	@mkdir -p secrets
	@test -f secrets/iam-signing.pem || openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out secrets/iam-signing.pem 2>/dev/null
	@chmod 600 secrets/*.pem
	@echo "секреты на месте: .env, secrets/iam-signing.pem (на Linux: chown 10001 secrets/*.pem)"

config: ## Проверить compose.yml после интерполяции
	$(COMPOSE) config --quiet && echo "compose.yml корректен для профилей: $(PROFILES)"

build: ## Собрать образы выбранных профилей
	$(COMPOSE) build

up: ## Поднять выбранные профили: make up PROFILES="core notify edge"
	@if [[ " $(PROFILES) " == *" edge "* && ! -f guide/mkdocs.yml ]]; then \
	  $(GUIDE_MISSING); echo "профиль edge собирает сервис guide — без него: make up PROFILES=core"; exit 1; fi
	$(COMPOSE) up -d --build

down: ## Остановить всё (данные в volumes остаются)
	docker compose --profile "*" down

ps: ## Состояние контейнеров
	docker compose --profile "*" ps

logs: ## Логи сервиса: make logs svc=control-plane-api
	docker compose --profile "*" logs -f $(svc)

smoke: ## Проверить healthz поднятых сервисов через порты 127.0.0.1
	@python3 tools/smoke.py

bootstrap: ## Первичная инициализация; ARGS="--agents agents.json" — ещё и агенты
	@python3 deploy/bootstrap.py --env .env $(ARGS)

reset-state: ## После сброса volumes: убрать state bootstrap и выданные им credentials (в secrets/stale-<время>/)
	@ts=$$(date +%Y%m%d-%H%M%S); dir=secrets/stale-$$ts; mkdir -p $$dir; \
	for f in deploy/state/$(ENV_NAME).json secrets/harness-pat secrets/control-plane-iam.env \
	         secrets/notification-iam.env secrets/agents; do \
	  test -e $$f && mv $$f $$dir/ && echo "  → $$dir/$$(basename $$f)"; done; \
	rmdir $$dir 2>/dev/null && echo "нечего убирать" || echo "state сброшен; ключ подписи и .env не тронуты — дальше make bootstrap"

check: $(addprefix check-,$(COMPONENTS_PY)) tools-check ## ruff + unit-тесты всех компонентов и tools/

check-%: lint-% test-% ## ruff + тесты одного компонента: make check-control-plane
	@true

lint-%:
	@echo "== ruff: $*"; cd $* && uv run --quiet ruff check . && uv run --quiet ruff format --check .

test-control-plane:
	@echo "== pytest (unit, client; db-test на 5434): control-plane"; cd control-plane && docker compose --profile test up -d --wait db-test >/dev/null && uv run --quiet pytest -q tests/unit tests/client; status=$$?; docker compose --profile test down >/dev/null 2>&1; exit $$status
test-skill-sdk:
	@echo "== pytest: skill-sdk"; cd skill-sdk && uv run --quiet --all-extras pytest -q
test-memory-service:
	@echo "== pytest (unit): memory-service"; cd memory-service && uv run --quiet --extra mcp pytest -q --ignore=tests/integration
test-%:
	@echo "== pytest: $*"; cd $* && uv run --quiet pytest -q

tools-check: ## ruff + тесты скриптов tools/ и deploy/
	@uvx ruff check tools deploy
	@uv run --quiet --no-project --with pytest python -m pytest -q tools/tests

linkcheck: ## Проверить относительные ссылки в документации umbrella
	@python3 tools/linkcheck.py

INSTALL ?= deploy/packages.yaml
SERVER ?= http://taimen.localhost
CP_PACKAGES := uv run --quiet --no-project --with pyyaml --with jsonschema python tools/cp_packages.py

packages-check: ## Проверить пакеты каталога без стенда: make packages-check [INSTALL=deploy/packages.yaml]
	@$(CP_PACKAGES) check --install $(INSTALL)

packages-plan: ## Сверить установку с живым Control Plane: make packages-plan [SERVER=…]
	@$(CP_PACKAGES) plan --install $(INSTALL) --server $(SERVER)

packages-apply: ## Применить установку каталога: make packages-apply [SERVER=…]
	@$(CP_PACKAGES) apply --install $(INSTALL) --server $(SERVER)

oss-check: ## Проверка публикуемости umbrella (без gitleaks): make oss-check STOPLIST=<файл>
	@python3 tools/oss_check.py . --skip-gitleaks $(if $(STOPLIST),--stoplist $(STOPLIST))

guide: ## Собрать руководство guide/ в guide/site (MkDocs Material)
	@test -f guide/mkdocs.yml || { $(GUIDE_MISSING); exit 1; }
	cd guide && uv run --quiet --no-project --with-requirements requirements.txt mkdocs build --strict

guide-serve: ## Руководство с живой перезагрузкой на http://127.0.0.1:8008
	@test -f guide/mkdocs.yml || { $(GUIDE_MISSING); exit 1; }
	cd guide && uv run --quiet --no-project --with-requirements requirements.txt mkdocs serve -a 127.0.0.1:8008
