#!/usr/bin/env python3
"""Пакеты каталога Control Plane (TAI-ADR-0044): загрузка, проверка, применение, экспорт.

Пакет — каталог packages/<key>/ с package.yaml и YAML-файлами объектов в обёртке
{apiVersion, kind, key, spec}; spec — тело запроса API control-plane. Установка —
файл окружения (kind: Installation): какие пакеты ставить и какие ключи вывести
из оборота. Bootstrap вызывает apply() на шаге 5b; здесь же CLI:

    python3 tools/cp_packages.py check                              # все пакеты, без стенда
    python3 tools/cp_packages.py check --install deploy/packages.yaml
    python3 tools/cp_packages.py plan  --install deploy/packages.yaml --server https://cp.example.com
    python3 tools/cp_packages.py apply --install deploy/packages.yaml --server https://cp.example.com
    python3 tools/cp_packages.py export --server https://cp.example.com --kind TaskType --key <ключ> \\
        --package packages/<пакет>

Процессы и календари (TAI-ADR-0054, виды Process и Calendar) проверяет и применяет ядро
по плану, а тесты пакета (tests/*.test.yaml) прогоняет его песочница:

    python3 tools/cp_packages.py check --install deploy/packages.yaml --server https://cp.example.com
    python3 tools/cp_packages.py test  --package packages/<пакет> --server https://cp.example.com
    python3 tools/cp_packages.py plan  --install deploy/packages.yaml --server https://cp.example.com \\
        --out plan.json
    python3 tools/cp_packages.py apply --plan plan.json
    python3 tools/cp_packages.py migrate-expr --package packages/<пакет> [--write]

Токен для plan/apply/export: переменная CP_TOKEN (access token audience control-plane)
или credential MCP-плагина через control_plane_client — запускать тогда
интерпретатором uv-tool control-plane (~/.local/share/uv/tools/control-plane/bin/python).

Вид NotificationRule (TAI-ADR-0053, ADR-0005 notification-service) применяется не к
ядру, а к сервису уведомлений: адрес — переменная установки NOTIFICATION_SERVICE_URL,
токен — NOTIFY_TOKEN (audience notification-service, scope notifications:admin) или
обмен того же IAM credential на этот audience через control_plane_client.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

try:
    import yaml
except ImportError:  # pragma: no cover - окружение без PyYAML
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = ROOT / "packages"
SCHEMA_PATH = PACKAGES_DIR / "schema" / "v1" / "object.schema.json"
API_VERSION = "taimen.ai/v1"
API = "/api/v1"

# Порядок применения: на что ссылаются, то раньше (execution и invokeSkill → Skill,
# ensureWork → TaskType, allowedChildTypes → WorkspaceType; WorkRule → Skill и TaskType;
# artifactSchema → ArtifactType; Agent → Role, Skill, TaskType; WorkRule.identity → Agent).
# NotificationRule — последним: правила уведомлений ни на что в ядре не ссылаются, но живут
# в другом сервисе и начинают исполняться сразу — пусть ядро к этому моменту уже приведено.
# Calendar и Process (TAI-ADR-0054): календарь раньше процесса (cal.* и spec.calendar), процесс —
# после TaskType и Agent (шаги human/approve ссылаются на типы задач, identity — на агента).
CATALOG_KINDS = ("WorkspaceType", "Capability", "Role", "Skill", "ArtifactType", "TaskType", "Agent",
                 "ProjectTemplate", "Calendar", "Process", "WorkRule", "NotificationRule")
# Виды, которые применяет только ядро по плану (POST /packages:plan → apply --plan): их
# определения, версии и судьбу открытых экземпляров знает ядро, а не установщик.
PLAN_KINDS = ("Calendar", "Process")
# Поле идентичности объекта в API.
IDENTITY = {"Agent": "key", "ArtifactType": "key", "TaskType": "key", "ProjectTemplate": "key", "WorkspaceType": "key",
            "Role": "slug", "Capability": "name", "Skill": "name", "WorkRule": "key", "NotificationRule": "key",
            "Process": "key", "Calendar": "key"}
FOLDERS = {"Agent": "agents", "ArtifactType": "artifact-types", "TaskType": "task-types", "ProjectTemplate": "project-templates",
           "WorkspaceType": "workspace-types", "Role": "roles", "Capability": "capabilities",
           "Skill": "skills", "WorkRule": "rules", "NotificationRule": "notification-rules",
           "Process": "processes", "Calendar": "calendars"}
SYSTEM_TASK_TYPE = "task"  # ядро держит одну его активную версию всегда
DEFAULT_EXECUTION_INPUTS = "$.customFields"
ENV_REF = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
# CP-ADR-0073 А1: поле назначения — UUID principal'а или ссылка на агента реестра по ключу
AGENT_REF = re.compile(r"^agent:([a-z0-9][a-z0-9-]{0,62})$")
# Сервис уведомлений (ADR-0005 notification-service §7): адрес из установки, свой audience
NOTIFY_URL_ENV = "NOTIFICATION_SERVICE_URL"
NOTIFY_TOKEN_ENV = "NOTIFY_TOKEN"
NOTIFY_AUDIENCE = "notification-service"
NOTIFY_SCOPES = ("notifications:admin",)
# Корни условия on.when правила уведомления (ADR-0005 §4)
NOTIFY_CONDITION_ROOTS = frozenset({"payload", "event", "task"})

# Поля spec и их значения по умолчанию в API. SERVER_DEFAULTED — поле, которое
# сервер заполняет сам (lifecycle, конфигурация шаблона): сравнивается, только
# если задано в файле.
SERVER_DEFAULTED = object()
SPEC_FIELDS: dict[str, dict[str, Any]] = {
    "TaskType": {"displayName": "", "description": "", "fieldSchema": {},
                 "lifecycleSchema": SERVER_DEFAULTED, "execution": None, "approvalSchema": {},
                 # CP-ADR-0064: сравнивается, только если задан в файле — ядро старше
                 # профиля контекста поле не знает, и пустое значение не повод для версии
                 "contextSchema": SERVER_DEFAULTED,
                 # CP-ADR-0066: инструкции исполнителю — тоже только если заданы; ядро
                 # старше поля его не отдаёт
                 "instructions": SERVER_DEFAULTED,
                 # CP-ADR-0061, амендмент 2026-09-25: работа после завершения задачи
                 "completionSchema": SERVER_DEFAULTED,
                 # CP-ADR-0072: входы и выходы — только если заданы в файле
                 "artifactSchema": SERVER_DEFAULTED,
                 # CP-ADR-0067 В5 (TAI-ADR-0053): критерии приёмки по умолчанию у типа
                 "acceptance": SERVER_DEFAULTED},
    # CP-ADR-0072 §6: версии неизменяемы, как у TaskType; maxBytes без значения в файле —
    # глобальный лимит установки на момент публикации, поэтому сравнивается, только если задан.
    "ArtifactType": {"displayName": "", "description": "", "metadataSchema": {}, "mediaTypes": ["*/*"],
                     "maxBytes": SERVER_DEFAULTED},
    "ProjectTemplate": {"displayName": "", "description": "", "fieldSchema": {},
                        "lifecycleSchema": SERVER_DEFAULTED, "defaultConfig": SERVER_DEFAULTED,
                        "defaultViews": [], "governanceSchema": {}, "memoryDefaults": {}},
    "WorkspaceType": {"displayName": "", "description": "", "fieldSchema": {}, "allowedChildTypes": []},
    "Role": {"name": "", "description": ""},
    "Capability": {"description": ""},
}
SKILL_IMMUTABLE = ("protocol", "sideEffects", "riskLevel", "contract")
SKILL_MUTABLE = ("description", "config", "inputSchema", "outputSchema")
# WorkRule (CP-ADR-0063 §11): изменяемый вид, PATCH с If-Match; key и workspaceId неизменны.
# identity (амендмент 2026-09-27, Г1) — тоже PATCH; null снимает личность.
RULE_MUTABLE = ("description", "trigger", "condition", "interpretation", "action", "identity")
RETIRABLE = ("TaskType", "ProjectTemplate", "WorkRule", "Agent", "NotificationRule", "Process", "Calendar")
TEST_SCHEMA_PATH = PACKAGES_DIR / "schema" / "v1" / "test.schema.json"
# Каталоги пакета, в которых лежат не объекты каталога: тесты процессов, JSON Schema данных
# (на них ссылается data: {$ref}) и раскладка схемы для визуального редактора.
TESTS_DIR, SCHEMAS_DIR, LAYOUT_DIR = "tests", "schemas", ".layout"


class PackageError(Exception):
    """Ошибка формата или установки пакета — с понятным человеку текстом."""


# --- модель -------------------------------------------------------------------


@dataclass
class Obj:
    kind: str
    key: str
    spec: dict[str, Any]
    package: str
    path: Path

    @property
    def ref(self) -> str:
        if self.kind == "Skill":
            return f"Skill/{self.key}@{self.spec.get('version')}"
        return f"{self.kind}/{self.key}"


@dataclass
class PackageTest:
    """Тест процесса пакета (tests/<имя>.test.yaml, packages/schema/v1/test.schema.json)."""
    package: str
    path: Path
    data: Any

    @property
    def name(self) -> str:
        return str(self.data.get("name")) if isinstance(self.data, dict) else self.path.name


@dataclass
class Package:
    key: str
    spec: dict[str, Any]
    path: Path
    objects: list[Obj] = field(default_factory=list)
    tests: list[PackageTest] = field(default_factory=list)

    @property
    def renames(self) -> list[dict[str, Any]]:
        return list(self.spec.get("renames") or [])

    @property
    def requires(self) -> list[str]:
        return list(self.spec.get("requires") or [])


@dataclass
class Installation:
    packages: list[Package]            # в порядке зависимостей
    retire: dict[str, list[str]]
    path: Path | None = None

    @property
    def objects(self) -> list[Obj]:
        return [obj for package in self.packages for obj in package.objects]

    @property
    def tests(self) -> list[PackageTest]:
        return [test for package in self.packages for test in package.tests]


def _yaml12_loader() -> Any:
    """SafeLoader с булевыми значениями YAML 1.2: только true/false.

    PyYAML следует YAML 1.1 и читает `on`, `off`, `yes`, `no` как bool — ключ `on`
    правил уведомлений и процессов (TAI-ADR-0054) превращался бы в True. Язык
    пакетов — YAML 1.2, как у ruamel.yaml и редакторов."""
    class Loader(yaml.SafeLoader):
        pass

    Loader.yaml_implicit_resolvers = {
        first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
        for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    Loader.add_implicit_resolver(
        "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
    )
    return Loader


def _read_yaml(path: Path) -> Any:
    if yaml is None:
        raise PackageError("нужен PyYAML: pip install pyyaml (на Ubuntu он уже стоит — python3-yaml)")
    try:
        return yaml.load(path.read_text(encoding="utf-8"), Loader=_yaml12_loader())
    except yaml.YAMLError as error:
        raise PackageError(f"{_rel(path)}: не YAML: {error}") from error


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _envelope(doc: Any, path: Path) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(doc, dict) or doc.get("apiVersion") != API_VERSION:
        raise PackageError(f"{_rel(path)}: нужна обёртка apiVersion: {API_VERSION}, kind, key, spec")
    kind, key, spec = doc.get("kind"), doc.get("key"), doc.get("spec")
    if not isinstance(kind, str) or not isinstance(key, str) or not isinstance(spec, dict):
        raise PackageError(f"{_rel(path)}: kind и key — строки, spec — объект")
    return kind, key, spec


def load_package(directory: Path) -> Package:
    manifest_path = directory / "package.yaml"
    if not manifest_path.exists():
        raise PackageError(f"{_rel(directory)}: нет package.yaml")
    kind, key, spec = _envelope(_read_yaml(manifest_path), manifest_path)
    if kind != "Package":
        raise PackageError(f"{_rel(manifest_path)}: kind должен быть Package")
    if key != directory.name:
        raise PackageError(f"{_rel(manifest_path)}: key {key!r} не совпадает с именем каталога {directory.name!r}")
    package = Package(key=key, spec=spec, path=directory)
    for path in sorted(directory.rglob("*.yaml")):
        if path == manifest_path:
            continue
        inner = path.relative_to(directory).parts
        if inner[0] in (SCHEMAS_DIR, LAYOUT_DIR):
            continue
        if inner[0] == TESTS_DIR:
            if path.name.endswith(".test.yaml"):
                package.tests.append(PackageTest(key, path, _read_yaml(path)))
            continue
        obj_kind, obj_key, obj_spec = _envelope(_read_yaml(path), path)
        if obj_kind not in CATALOG_KINDS:
            raise PackageError(f"{_rel(path)}: неизвестный kind {obj_kind!r}; ожидается один из {list(CATALOG_KINDS)}")
        if obj_kind == "Process":
            obj_spec = expand_data_ref(obj_spec, path, directory)
        package.objects.append(Obj(obj_kind, obj_key, obj_spec, key, path))
    return package


def expand_data_ref(spec: dict[str, Any], path: Path, package_dir: Path) -> dict[str, Any]:
    """data: {$ref: <файл пакета>} → схема данных из файла (JSON или YAML) внутри пакета.

    Ядру уходят файлы пакета как есть — ссылку оно раскрывает само; раскрытая схема нужна
    статической проверке здесь."""
    data = spec.get("data")
    if not (isinstance(data, dict) and set(data) == {"$ref"} and isinstance(data["$ref"], str)):
        return spec
    ref = data["$ref"]
    if ref.startswith("#") or "://" in ref:
        return spec  # ссылка внутрь документа или удалённая — решает ядро (удалённые оно отвергает)
    target = (path.parent / ref).resolve()
    if not target.is_relative_to(package_dir.resolve()):
        raise PackageError(f"{_rel(path)}: data.$ref {ref!r} ведёт за пределы пакета")
    if not target.is_file():
        raise PackageError(f"{_rel(path)}: data.$ref {ref!r} — нет такого файла в пакете")
    try:
        schema = json.loads(target.read_text(encoding="utf-8")) if target.suffix == ".json" else _read_yaml(target)
    except json.JSONDecodeError as error:
        raise PackageError(f"{_rel(target)}: не JSON: {error}") from error
    if not isinstance(schema, dict):
        raise PackageError(f"{_rel(target)}: схема данных процесса — объект JSON Schema")
    return {**spec, "data": schema}


def all_package_dirs() -> list[Path]:
    return sorted(p.parent for p in PACKAGES_DIR.glob("*/package.yaml"))


def resolve(keys: list[str], retire: dict[str, list[str]] | None = None, path: Path | None = None) -> Installation:
    """Пакеты по ключам вместе с requires, в порядке зависимостей."""
    loaded: dict[str, Package] = {}
    order: list[Package] = []
    visiting: set[str] = set()

    def visit(key: str, chain: tuple[str, ...]) -> None:
        if key in loaded:
            return
        if key in visiting:
            raise PackageError(f"цикл requires: {' → '.join(chain + (key,))}")
        directory = PACKAGES_DIR / key
        if not (directory / "package.yaml").exists():
            raise PackageError(f"пакет {key!r} не найден в {_rel(PACKAGES_DIR)}" + (f" (нужен {chain[-1]})" if chain else ""))
        visiting.add(key)
        package = load_package(directory)
        for required in package.requires:
            visit(required, chain + (key,))
        visiting.discard(key)
        loaded[key] = package
        order.append(package)

    for key in keys:
        visit(key, ())
    return Installation(packages=order, retire=dict(retire or {}), path=path)


def load_installation(path: Path) -> Installation:
    kind, _key, spec = _envelope(_read_yaml(path), path)
    if kind != "Installation":
        raise PackageError(f"{_rel(path)}: kind должен быть Installation")
    packages = spec.get("packages")
    # Пустой список — законная установка: ядро без доменных пакетов знает только
    # системный тип task (пакета core нет, амендмент TAI-ADR-0044 2026-09-25).
    if not isinstance(packages, list):
        raise PackageError(f"{_rel(path)}: spec.packages — список ключей пакетов")
    return resolve(packages, spec.get("retire") or {}, path)


# --- проверка -----------------------------------------------------------------


def substitute(value: Any, env: dict[str, str], *, missing: Callable[[str], str] | None = None) -> Any:
    """${NAME} в строках spec → значение окружения инсталляции."""
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name in env:
                return env[name]
            if missing is not None:
                return missing(name)
            raise PackageError(f"переменная окружения {name} не задана (нужна пакету)")
        return ENV_REF.sub(replace, value)
    if isinstance(value, dict):
        return {k: substitute(v, env, missing=missing) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, env, missing=missing) for v in value]
    return value


def _format_schema_error(error: Any) -> str:
    where = "/".join(str(p) for p in error.absolute_path) or "(корень)"
    return f"{where}: {error.message}"


def _schema_validator() -> Any:
    try:
        import jsonschema
    except ImportError as error:
        raise PackageError("нужен jsonschema: pip install jsonschema") from error
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def _domain() -> Any:
    """Доменные валидаторы control-plane (сабмодуль рядом); None — если не импортируются."""
    src = ROOT / "control-plane" / "src"
    if str(src) not in sys.path and src.exists():
        sys.path.insert(0, str(src))
    try:
        from control_plane.domain import (
            approval_outcomes,
            project,
            skill_contract,
            task_execution,
            work_item,
            work_rules,
        )
        from control_plane.domain.errors import DomainError
    except ImportError:
        return None

    class Domain:
        pass

    domain = Domain()
    domain.approval_outcomes = approval_outcomes
    domain.project = project
    domain.skill_contract = skill_contract
    domain.task_execution = task_execution
    domain.work_item = work_item
    domain.work_rules = work_rules
    domain.DomainError = DomainError
    try:  # профиль контекста — control-plane с CP-ADR-0064
        from control_plane.domain import context_schema
    except ImportError:
        context_schema = None
    domain.context_schema = context_schema
    try:  # CP-ADR-0066: ядро старше инструкций исполнителю этого модуля не знает
        from control_plane.domain import agent_instructions
    except ImportError:
        agent_instructions = None
    domain.agent_instructions = agent_instructions
    try:  # CP-ADR-0061, амендмент 2026-09-25: работа после завершения задачи
        from control_plane.domain import completion_work
    except ImportError:
        completion_work = None
    domain.completion_work = completion_work
    try:  # CP-ADR-0072: типы артефактов и входы/выходы типа задачи
        from control_plane.domain import artifact_schema, artifact_type
    except ImportError:
        artifact_schema = artifact_type = None
    domain.artifact_schema = artifact_schema
    domain.artifact_type = artifact_type
    try:  # CP-ADR-0073: общие разделы описания агента проверяет модель API ядра
        from control_plane.api.v1.schemas import AgentSpec as agent_spec
    except ImportError:
        agent_spec = None
    domain.agent_spec = agent_spec
    return domain


def _literal(value: Any) -> bool:
    return isinstance(value, str) and "$" not in value


def _flatten(items: Any) -> list[tuple[str, dict[str, Any]]]:
    """Действия списка вместе с реакциями invokeSkill (onSuccess/onFailure)."""
    actions: list[tuple[str, dict[str, Any]]] = []
    for action in items or []:
        if isinstance(action, dict) and len(action) == 1:
            name, inputs = next(iter(action.items()))
            inputs = inputs if isinstance(inputs, dict) else {}
            actions.append((name, inputs))
            for reaction in ("onSuccess", "onFailure"):
                actions += _flatten(inputs.get(reaction))
    return actions


def _outcome_actions(approval_schema: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    actions = []
    for gate in (approval_schema.get("gates") or {}).values():
        for items in ((gate or {}).get("outcomes") or {}).values():
            actions += _flatten(items)
    return actions


def _completion_actions(completion_schema: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return _flatten(((completion_schema or {}).get("onComplete") or {}).get("actions"))


def _domain_check(obj: Obj, spec: dict[str, Any], domain: Any) -> None:
    """Те же проверки, что делает ядро при создании (раньше, чем их сделает стенд)."""
    work_item, project = domain.work_item, domain.project
    if obj.kind == "TaskType":
        project.validate_json_schema_document(spec.get("fieldSchema") or {}, field_name="fieldSchema")
        lifecycle = work_item.parse_work_item_lifecycle(spec.get("lifecycleSchema") or work_item.SYSTEM_TASK_LIFECYCLE)
        domain.approval_outcomes.parse_approval_schema(
            spec.get("approvalSchema") or {}, statuses=frozenset(lifecycle.lifecycle.categories))
        domain.task_execution.normalize_execution(spec.get("execution"))
        if spec.get("contextSchema") is not None and domain.context_schema is not None:
            domain.context_schema.parse_context_schema(spec["contextSchema"])
        if spec.get("completionSchema") is not None and domain.completion_work is not None:
            domain.completion_work.parse_completion_schema(spec["completionSchema"])
        if spec.get("instructions") is not None and domain.agent_instructions is not None:
            domain.agent_instructions.validate_instructions(spec["instructions"], field="instructions")
        if spec.get("artifactSchema") is not None and domain.artifact_schema is not None:
            domain.artifact_schema.parse_artifact_schema(spec["artifactSchema"])
    elif obj.kind == "Agent":
        if domain.agent_spec is not None:
            try:
                domain.agent_spec.model_validate(spec)
            except Exception as error:  # pydantic.ValidationError: сообщение ядра как есть
                raise PackageError(f"ядро не принимает описание агента: {error}") from error
    elif obj.kind == "ArtifactType":
        if domain.artifact_type is not None:
            # потолок установки знает только стенд — здесь проверяется всё, кроме него
            domain.artifact_type.validate_artifact_type_definition(
                metadata_schema=spec.get("metadataSchema") or {}, media_types=spec.get("mediaTypes") or ["*/*"],
                max_bytes=spec.get("maxBytes"), global_max_bytes=max(int(spec.get("maxBytes") or 1), 1))
    elif obj.kind == "ProjectTemplate":
        project.validate_json_schema_document(spec.get("fieldSchema") or {}, field_name="fieldSchema")
        if spec.get("lifecycleSchema") is not None:
            project.parse_lifecycle(spec["lifecycleSchema"])
        project.validate_config_document(spec.get("defaultConfig") or {}, field_name="defaultConfig")
        project.validate_governance(spec.get("governanceSchema") or {})
        project.validate_config_document({"memory": spec.get("memoryDefaults") or {}}, field_name="memoryDefaults")
    elif obj.kind == "WorkspaceType":
        project.validate_json_schema_document(spec.get("fieldSchema") or {}, field_name="fieldSchema")
    elif obj.kind == "Skill":
        contract = domain.skill_contract
        if spec.get("contract") is not None:
            normalized = contract.normalize_contract(spec["contract"])
            side_effects, _risk = contract.validate_policy_columns(spec.get("sideEffects"), spec.get("riskLevel"))
            contract.require_safe_retries(normalized, side_effects)
        elif spec.get("sideEffects") is not None or spec.get("riskLevel") is not None:
            contract.validate_policy_columns(spec.get("sideEffects"), spec.get("riskLevel"))
        for name in ("inputSchema", "outputSchema"):
            if spec.get(name) is not None:
                project.validate_json_schema_document(spec[name], field_name=name)
    elif obj.kind == "WorkRule":
        domain.work_rules.normalize_rule_key(obj.key)
        normalize_rule(spec, domain)
    elif obj.kind == "NotificationRule":
        # Грамматика условия общая с правилами ядра (ADR-0005 §6 п.4); типы событий и пути
        # шаблонов знает только сервис — их проверит :validate перед записью.
        domain.work_rules.normalize_rule_key(obj.key)
        when = (spec.get("on") or {}).get("when")
        if when is not None:
            domain.work_rules.validate_expression(when, roots=NOTIFY_CONDITION_ROOTS, where="on.when")


def _without_fields_workspace(action: Any) -> tuple[Any, Any]:
    """action без fields.workspaceId и сам шаблон (None — поля нет)."""
    if not isinstance(action, dict) or not isinstance(action.get("fields"), dict) \
            or "workspaceId" not in action["fields"]:
        return action, None
    fields = dict(action["fields"])
    template = fields.pop("workspaceId")
    return {**action, "fields": fields}, template


def normalize_rule(spec: dict[str, Any], domain: Any) -> dict[str, Any]:
    """Документы правила в том виде, в каком их хранит ядро (normalize_rule_spec).

    ``fields.workspaceId`` — workspace заводимой работы (амендмент CP-ADR-0063,
    process-packages P012). Ядро до P012 поля не знает (``unknown keys``): тогда оно
    проверяется здесь — строка-шаблон с корнями действия — а остальное действие — ядром."""
    work_rules = domain.work_rules
    action = spec.get("action")
    try:
        normalized = work_rules.normalize_rule_spec(
            trigger=spec.get("trigger"),
            condition=spec.get("condition", True),
            interpretation=spec.get("interpretation"),
            action=action,
        )
    except domain.DomainError as error:
        bare, template = _without_fields_workspace(action)
        if template is None or "workspaceId" not in ((error.details or {}).get("unknown") or []):
            raise
        normalized = work_rules.normalize_rule_spec(
            trigger=spec.get("trigger"),
            condition=spec.get("condition", True),
            interpretation=spec.get("interpretation"),
            action=bare,
        )
        if not isinstance(template, str) or not template.strip():
            raise PackageError("action.fields.workspaceId: ожидается шаблон — непустая строка") from error
        roots = work_rules.action_roots(interpreted=spec.get("interpretation") is not None,
                                        for_each=bare.get("forEach") is not None)
        work_rules.template_paths(template, roots=roots, where="action.fields.workspaceId",
                                  code="invalid_rule_action")
        normalized.action.setdefault("fields", {})["workspaceId"] = template
    return {
        "description": domain.work_rules.normalize_description(spec.get("description", "")),
        "trigger": normalized.trigger,
        "condition": normalized.condition,
        "interpretation": normalized.interpretation,
        "action": normalized.action,
        # личность ядро хранит как есть: {agent: <key>} или null
        "identity": spec.get("identity"),
    }


def check(installation: Installation, *, env: dict[str, str] | None = None) -> tuple[list[str], list[str]]:
    """Ошибки и предупреждения без обращения к стенду."""
    errors: list[str] = []
    warnings: list[str] = []
    validator = _schema_validator()
    domain = _domain()
    if domain is None:
        warnings.append("доменные валидаторы control-plane не импортируются (нет сабмодуля или jsonschema) — "
                        "проверена только схема формата")

    for package in installation.packages:
        manifest = {"apiVersion": API_VERSION, "kind": "Package", "key": package.key, "spec": package.spec}
        for error in validator.iter_errors(manifest):
            errors.append(f"{_rel(package.path / 'package.yaml')}: {_format_schema_error(error)}")

    seen: dict[tuple[str, str], Obj] = {}
    by_package: dict[str, list[Obj]] = {p.key: p.objects for p in installation.packages}
    requires: dict[str, list[str]] = {p.key: p.requires for p in installation.packages}

    def closure(package: str) -> list[Obj]:
        result, stack, visited = [], [package], set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            result.extend(by_package.get(current, []))
            stack.extend(requires.get(current, []))
        return result

    placeholder_env = dict(env or {})
    retired_agents = set(installation.retire.get("Agent") or [])
    for obj in installation.objects:
        where = _rel(obj.path)
        doc = {"apiVersion": API_VERSION, "kind": obj.kind, "key": obj.key, "spec": obj.spec}
        schema_errors = [_format_schema_error(e) for e in validator.iter_errors(doc)]
        errors.extend(f"{where}: {message}" for message in schema_errors)
        identity = (obj.kind, obj.ref)
        if identity in seen:
            errors.append(f"{where}: {obj.ref} уже объявлен в {_rel(seen[identity].path)}")
        seen[identity] = obj
        if schema_errors:
            continue
        spec = substitute(obj.spec, placeholder_env, missing=lambda _name: "http://env.invalid")
        if domain is not None and obj.kind == "TaskType" and spec.get("contextSchema") is not None \
                and domain.context_schema is None:
            warnings.append(f"{where}: contextSchema не проверен — модуль профиля контекста control-plane "
                            "не импортируется (релиз старше CP-ADR-0064 или нет зависимости regex); "
                            "проверит ядро при публикации")
        if domain is not None:
            try:
                _domain_check(obj, spec, domain)
            except domain.DomainError as error:
                details = f" {error.details}" if error.details else ""
                errors.append(f"{where}: {error.code}: {error.message}{details}")
            except PackageError as error:
                errors.append(f"{where}: {error}")

        # Замкнутость ссылок: только свой пакет и его requires (TAI-ADR-0044 п.3).
        visible = closure(obj.package)
        task_types = {o.key for o in visible if o.kind == "TaskType"} | {SYSTEM_TASK_TYPE}
        skills = {f"{o.key}@{o.spec.get('version')}" for o in visible if o.kind == "Skill"}
        workspace_types = {o.key for o in visible if o.kind == "WorkspaceType"}
        artifact_types = {o.key: o for o in visible if o.kind == "ArtifactType"}
        agents = {o.key for o in visible if o.kind == "Agent"}

        def agent_ref(key: str, field: str) -> None:
            """Ссылка на агента — описание Agent своего пакета или его requires (как у остальных
            ссылок); выведенный из оборота этой же установкой — тоже ошибка (ядро: unknown_agent)."""
            if key in retired_agents:
                errors.append(f"{where}: {field} ссылается на агента {key!r}, которого установка выводит "
                              "из оборота (retire)")
            elif key not in agents:
                errors.append(f"{where}: {field} ссылается на агента {key!r} — такого Agent нет "
                              f"в пакете {obj.package} и его requires")

        def assignee_ref(value: Any, field: str) -> None:
            # agent:<key> литералом; шаблон ({{…}}, $.path, ${…}) разрешит ядро при исполнении
            if isinstance(value, str) and "{{" not in value and "$" not in value:
                match = AGENT_REF.match(value)
                if match:
                    agent_ref(match.group(1), field)
                elif value.startswith("agent:"):
                    errors.append(f"{where}: {field} {value!r} — ссылка на агента пишется agent:<key> "
                                  "(ключ — slug агента)")

        if obj.kind == "TaskType":
            errors.extend(f"{where}: {message}" for message in
                          _artifact_schema_refs(obj.spec.get("artifactSchema") or {}, artifact_types, obj.package))
            execution = obj.spec.get("execution")
            if execution and f"{execution.get('skill')}@{execution.get('version')}" not in skills:
                errors.append(f"{where}: execution ссылается на Skill {execution.get('skill')}@{execution.get('version')}, "
                              f"которого нет ни в пакете {obj.package}, ни в его requires")
            for name, inputs in _outcome_actions(obj.spec.get("approvalSchema") or {}) + \
                    _completion_actions(obj.spec.get("completionSchema") or {}):
                if name == "ensureWork" and _literal(inputs.get("type")) and inputs["type"] not in task_types:
                    errors.append(f"{where}: ensureWork.type {inputs['type']!r} — такого TaskType нет "
                                  f"в пакете {obj.package} и его requires")
                if name == "invokeSkill" and _literal(inputs.get("skill")) and inputs["skill"] not in skills:
                    errors.append(f"{where}: invokeSkill.skill {inputs['skill']!r} — такого Skill (name@version) "
                                  f"нет в пакете {obj.package} и его requires")
                if name == "ensureWork":
                    assignee_ref(inputs.get("assignee"), "ensureWork.assignee")
        if obj.kind == "Agent":
            roles = {o.key for o in visible if o.kind == "Role"}
            for role in (obj.spec.get("identity") or {}).get("roles") or []:
                if role not in roles:
                    warnings.append(f"{where}: роль {role!r} не объявлена в пакетах — должна уже быть в tenant")
            for task_type in (obj.spec.get("work") or {}).get("taskTypes") or []:
                if task_type not in task_types:
                    errors.append(f"{where}: work.taskTypes {task_type!r} — такого TaskType нет "
                                  f"в пакете {obj.package} и его requires")
        if obj.kind == "WorkRule":
            skill = (obj.spec.get("interpretation") or {}).get("skill")
            if skill and skill not in skills:
                errors.append(f"{where}: interpretation.skill {skill!r} — такого Skill (name@version) "
                              f"нет в пакете {obj.package} и его requires")
            action = obj.spec.get("action") or {}
            task_type = action.get("taskType")
            # шаблон {{item.…}} допустим только рядом с taskTypes (CP-ADR-0063 Г2) — ссылки тогда
            # проверяются по списку, а сам шаблон рендерит ядро
            if _literal(task_type) and "{{" not in task_type and task_type not in task_types:
                errors.append(f"{where}: action.taskType {task_type!r} — такого TaskType нет "
                              f"в пакете {obj.package} и его requires")
            for allowed in action.get("taskTypes") or []:
                if allowed not in task_types:
                    errors.append(f"{where}: action.taskTypes {allowed!r} — такого TaskType нет "
                                  f"в пакете {obj.package} и его requires")
            rule_identity = obj.spec.get("identity")
            if isinstance(rule_identity, dict) and isinstance(rule_identity.get("agent"), str):
                agent_ref(rule_identity["agent"], "identity.agent")
            assignee_ref(((obj.spec.get("action") or {}).get("fields") or {}).get("assignee"), "action.fields.assignee")
        if obj.kind == "WorkspaceType":
            for child in obj.spec.get("allowedChildTypes") or []:
                if child not in workspace_types:
                    warnings.append(f"{where}: allowedChildTypes {child!r} не объявлен в пакетах — "
                                    "должен уже быть в tenant")
        if obj.kind == "Process":
            calendars = {o.key for o in visible if o.kind == "Calendar"}
            process_errors, process_warnings = _process_refs(obj.spec, task_types=task_types, skills=skills,
                                                             calendars=calendars, package=obj.package)
            errors.extend(f"{where}: {message}" for message in process_errors)
            warnings.extend(f"{where}: {message}" for message in process_warnings)
            agent = (obj.spec.get("identity") or {}).get("agent")
            if isinstance(agent, str):
                agent_ref(agent, "identity.agent")
            for candidate in obj.spec.get("owner") or []:
                if isinstance(candidate, dict) and isinstance(candidate.get("agent"), str):
                    agent_ref(candidate["agent"], "owner.agent")

    errors.extend(_test_errors(installation))
    for package in installation.packages:
        for rename in package.renames:
            if rename.get("kind") not in CATALOG_KINDS:
                errors.append(f"{_rel(package.path / 'package.yaml')}: renames: вид {rename.get('kind')!r} "
                              "не объект каталога")
            elif not any(o.kind == rename["kind"] and o.key == rename.get("to") for o in package.objects):
                errors.append(f"{_rel(package.path / 'package.yaml')}: renames: {rename['kind']}/{rename.get('to')} "
                              "— такого объекта в пакете нет")

    known = {(o.kind, o.key) for o in installation.objects}
    for kind, keys in installation.retire.items():
        if kind not in RETIRABLE:
            errors.append(f"retire: вид {kind} не выводится из оборота (только {', '.join(RETIRABLE)})")
            continue
        for key in keys:
            if kind == "TaskType" and key == SYSTEM_TASK_TYPE:
                errors.append("retire: системный тип task вывести нельзя — ядро держит его активную версию")
            if (kind, key) in known:
                errors.append(f"retire: {kind}/{key} одновременно объявлен в пакете и выводится из оборота")
    return errors, warnings


# --- процессы: статическая часть проверки ---------------------------------------
# Схема проверяет форму; типы CEL, достижимость, тупики и схемы скиллов — ядро
# (check --server). Здесь — то, что видно без ядра: уникальность id, ссылки на таблицы,
# типы задач, скиллы и календари пакета, тесты против процесса.


def process_elements(spec: Any, path: str = "spec") -> list[tuple[str, str]]:
    """(id, путь) элементов процесса: стадии, шаги любой вложенности, вехи, таймеры, ветви
    fork, таблицы решений (их входы и выходы — столбцы, не элементы)."""
    skip = {"data", "form", "memory", "input", "set", "output", "export", "migrations", "governedBy",
            "retrospective", "context"}
    found: list[tuple[str, str]] = []

    def walk(node: Any, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in skip:
                    continue
                if key == "decisions" and isinstance(value, list):
                    found.extend((t["id"], f"{where}.decisions[{i}]") for i, t in enumerate(value)
                                 if isinstance(t, dict) and isinstance(t.get("id"), str))
                    continue
                walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    found.append((item["id"], f"{where}[{index}]"))
                walk(item, f"{where}[{index}]")

    walk(spec, path)
    return found


def _process_steps(spec: Any) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("id"), str):
                steps.append(node)
            for key, value in node.items():
                if key not in ("data", "form", "memory"):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(spec.get("stages"))
    walk(spec.get("onEvent"))
    walk(spec.get("timers"))
    walk(spec.get("correlate"))
    return steps


def _process_refs(spec: dict[str, Any], *, task_types: set[str], skills: set[str], calendars: set[str],
                  package: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen: dict[str, str] = {}
    for element_id, where in process_elements(spec):
        if element_id in seen:
            errors.append(f"{where}: id {element_id!r} уже занят ({seen[element_id]}) — id элемента уникален в процессе")
        else:
            seen[element_id] = where
    tables = {t.get("id") for t in spec.get("decisions") or []}
    for step in _process_steps(spec):
        sid = step.get("id")
        for verb in ("human", "approve"):
            task_type = (step.get(verb) or {}).get("taskType") if isinstance(step.get(verb), dict) else None
            if isinstance(task_type, str) and task_type not in task_types:
                errors.append(f"шаг {sid}: {verb}.taskType {task_type!r} — такого TaskType нет "
                              f"в пакете {package} и его requires")
        call = step.get("call")
        if isinstance(call, dict) and isinstance(call.get("skill"), str) and call["skill"] not in skills:
            errors.append(f"шаг {sid}: call.skill {call['skill']!r} — такого Skill (name@version) нет "
                          f"в пакете {package} и его requires")
        decide = step.get("decide")
        if isinstance(decide, dict) and decide.get("table") not in tables:
            errors.append(f"шаг {sid}: decide.table {decide.get('table')!r} — такой таблицы нет в spec.decisions")
        compensate = step.get("compensate")
        if isinstance(compensate, list):
            for target in compensate:
                if target not in seen:
                    errors.append(f"шаг {sid}: compensate {target!r} — такого элемента в процессе нет")
    retrospective = spec.get("retrospective") or {}
    if isinstance(retrospective.get("taskType"), str) and retrospective["taskType"] not in task_types:
        errors.append(f"retrospective.taskType {retrospective['taskType']!r} — такого TaskType нет "
                      f"в пакете {package} и его requires")
    if not spec.get("owner"):
        # владелец процесса (TAI-ADR-0054 п.5, амендмент 2026-09-27): кому адресовать задачи о
        # процессе — расхождение с регламентом (regulation-drift), ошибки экземпляров
        warnings.append("owner не задан — задачам о процессе (расхождение с регламентом, ошибки "
                        "экземпляров) некому адресоваться")
    calendar = spec.get("calendar")
    if isinstance(calendar, str) and calendar not in calendars:
        warnings.append(f"calendar {calendar!r} не объявлен в пакете и его requires — должен уже быть в tenant")
    version = spec.get("version")
    for migration in spec.get("migrations") or []:
        for target in (migration.get("map") or {}).values():
            if migration.get("to") == version and target not in seen:
                errors.append(f"migrations {migration.get('from')}→{migration.get('to')}: {target!r} — такого "
                              "элемента в процессе нет")
    return errors, warnings


def _test_validator() -> Any:
    import jsonschema

    return jsonschema.Draft202012Validator(json.loads(TEST_SCHEMA_PATH.read_text(encoding="utf-8")))


def _test_errors(installation: Installation) -> list[str]:
    """Тесты пакета: форма по test.schema.json, процесс — свой в пакете, шаги — его элементы."""
    errors: list[str] = []
    if not installation.tests:
        return errors
    validator = _test_validator()
    processes = {(o.package, o.key): o for o in installation.objects if o.kind == "Process"}
    for test in installation.tests:
        where = _rel(test.path)
        schema_errors = [_format_schema_error(e) for e in validator.iter_errors(test.data)]
        errors.extend(f"{where}: {message}" for message in schema_errors)
        if schema_errors:
            continue
        process = processes.get((test.package, test.data["process"]))
        if process is None:
            errors.append(f"{where}: process {test.data['process']!r} — такого Process нет в пакете {test.package}")
            continue
        elements = {element_id for element_id, _ in process_elements(process.spec)}
        for index, step in enumerate(test.data.get("steps") or []):
            for verb in ("complete", "approve"):
                target = (step.get(verb) or {}).get("step")
                if target is not None and target not in elements:
                    errors.append(f"{where}: steps[{index}].{verb}.step {target!r} — такого шага в процессе "
                                  f"{process.key} нет")
    return errors


def _artifact_schema_refs(schema: dict[str, Any], artifact_types: dict[str, Obj], package: str) -> list[str]:
    """Входы и выходы ссылаются на ArtifactType своего пакета или его requires; сужение
    mediaTypes слота — подмножество mediaTypes типа (ядро проверит то же при публикации)."""
    domain = _domain()
    errors = []
    for side in ("inputs", "outputs"):
        for slot in schema.get(side) or []:
            declared = artifact_types.get(slot.get("type"))
            if declared is None:
                errors.append(f"artifactSchema.{side} {slot.get('key')!r}: тип артефакта {slot.get('type')!r} "
                              f"не объявлен ни в пакете {package}, ни в его requires")
                continue
            narrowed = slot.get("mediaTypes")
            if narrowed and domain is not None and domain.artifact_type is not None:
                allowed = [m.strip().lower() for m in declared.spec.get("mediaTypes") or ["*/*"]]
                wide = [m for m in narrowed if not domain.artifact_type.pattern_covered(allowed, m.strip().lower())]
                if wide:
                    errors.append(f"artifactSchema.{side} {slot.get('key')!r}: mediaTypes {wide} шире, "
                                  f"чем у типа {declared.key} ({allowed})")
    return errors


# --- применение ---------------------------------------------------------------


class HttpLike(Protocol):
    def call(self, method: str, path: str, body: Any = None, headers: dict | None = None) -> dict: ...


class HttpError(RuntimeError):
    """Ответ с ошибкой: текст как прежде ("… HTTP <код>: <тело>"), плюс код и разобранное тело."""

    def __init__(self, message: str, status: int, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class Http:
    """Минимальный HTTP-клиент CLI; bootstrap передаёт свой с тем же call()."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, body: Any = None, headers: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raw = error.read().decode(errors="replace")
            try:
                body = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                body = None
            raise HttpError(f"{method} {path}: HTTP {error.code}: {raw[:400]}", error.code, body) from error


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _moved_endpoint(wanted: Any, actual: Any) -> str | None:
    """Новый implementation.endpoint, если контракт wanted отличается от опубликованного
    только им; иначе None — это другое обещание и нужна новая версия."""
    if not isinstance(wanted, dict) or not isinstance(actual, dict):
        return None
    endpoint = (wanted.get("implementation") or {}).get("endpoint")
    published = (actual.get("implementation") or {}).get("endpoint")
    if not isinstance(endpoint, str) or endpoint == published:
        return None
    moved = copy.deepcopy(wanted)
    moved["implementation"]["endpoint"] = published
    return endpoint if is_subset(moved, actual) else None


def is_subset(wanted: Any, actual: Any) -> bool:
    """wanted ⊆ actual: в словарях сравниваются только ключи wanted (сервер мог
    заполнить значения по умолчанию), списки и скаляры — точно."""
    if isinstance(wanted, dict):
        return isinstance(actual, dict) and all(k in actual and is_subset(v, actual[k]) for k, v in wanted.items())
    return canonical(wanted) == canonical(actual)


def _desired(kind: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Поля spec, которые сравниваются с сервером, с умолчаниями API."""
    result = {}
    for name, default in SPEC_FIELDS[kind].items():
        if name in spec:
            result[name] = copy.deepcopy(spec[name])
        elif default is not SERVER_DEFAULTED:
            result[name] = copy.deepcopy(default)
    if kind == "TaskType" and result.get("execution"):
        result["execution"].setdefault("inputs", DEFAULT_EXECUTION_INPUTS)
    if kind == "ArtifactType":
        # ядро хранит media types в нижнем регистре, без параметров и повторов
        result["mediaTypes"] = list(dict.fromkeys(m.split(";", 1)[0].strip().lower() for m in result["mediaTypes"]))
    return result


def _differences(kind: str, desired: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    changed = []
    for name, value in desired.items():
        current = actual.get(name)
        if kind == "ProjectTemplate" and name == "defaultConfig":
            same = is_subset(value, current)
        else:
            same = canonical(value) == canonical(current)
        if not same:
            changed.append(name)
    return changed


@dataclass
class Applier:
    http: HttpLike
    headers: dict[str, str]
    env: dict[str, str] = field(default_factory=dict)
    dry_run: bool = False
    log: Callable[[str], None] = print
    result: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Сервис уведомлений (NotificationRule): свой адрес и свой токен; None — не задан
    notify: HttpLike | None = None
    notify_headers: dict[str, str] = field(default_factory=dict)
    _notify_checks: dict[str, dict[str, Any]] = field(default_factory=dict)

    # -- транспорт --

    def _get(self, path: str) -> dict:
        return self.http.call("GET", API + path, None, self.headers)

    @staticmethod
    def _pages(get: Callable[[str], dict], path: str, params: dict[str, Any]) -> list[dict]:
        items: list[dict] = []
        cursor = None
        while True:
            query = {k: v for k, v in {**params, "limit": 100, "cursor": cursor}.items() if v is not None}
            page = get(f"{path}?{urllib.parse.urlencode(query)}")
            items.extend(page.get("items") or [])
            cursor = page.get("nextCursor")
            if not cursor:
                return items

    def _list(self, path: str, **params: Any) -> list[dict]:
        return self._pages(self._get, path, params)

    def _notify_call(self, method: str, path: str, body: Any = None) -> dict:
        if self.notify is None:
            raise PackageError(f"сервис уведомлений не задан — нужен {NOTIFY_URL_ENV} и токен audience "
                               f"{NOTIFY_AUDIENCE}")
        return self.notify.call(method, API + path, body, self.notify_headers)

    def _notify_list(self, **params: Any) -> list[dict]:
        return self._pages(lambda path: self._notify_call("GET", path), "/notification-rules", params)

    def _write(self, method: str, path: str, body: Any = None, extra: dict | None = None) -> dict:
        headers = {**self.headers, "Idempotency-Key": str(uuid.uuid4()), **(extra or {})}
        return self.http.call(method, API + path, body, headers)

    def _say(self, obj_ref: str, message: str) -> None:
        self.log(f"   {obj_ref}: {'(план) ' if self.dry_run else ''}{message}")

    # -- установка --

    def apply(self, installation: Installation) -> dict[str, dict[str, Any]]:
        objects = installation.objects
        skip = self._check_notification_rules(installation) | set(PLAN_KINDS)
        planned = sorted({o.ref for o in objects if o.kind in PLAN_KINDS} |
                         {f"{kind}/{key}" for kind in PLAN_KINDS for key in installation.retire.get(kind) or []})
        if planned:
            self.log(f"   ! {', '.join(planned)}: процессы и календари применяет ядро по плану — "
                     "tools/cp_packages.py plan --install … --out plan.json, затем apply --plan plan.json")
        for kind in CATALOG_KINDS:
            for obj in objects:
                if obj.kind == kind and kind not in skip:
                    spec = substitute(obj.spec, self.env)
                    getattr(self, f"_apply_{kind}")(obj, spec)
        for kind, keys in installation.retire.items():
            if kind in skip:
                continue
            for key in keys:
                self._retire(kind, key)
        return self.result

    # NotificationRule — в сервисе уведомлений (ADR-0005 notification-service §5–7)
    def _check_notification_rules(self, installation: Installation) -> set[str]:
        """:validate всех правил уведомлений до первой записи — и в ядро, и в сервис: правило,
        которое сервис не примет, останавливает установку целиком. Без сервиса (bootstrap
        до шага уведомлений) вид пропускается с предупреждением."""
        rules = [o for o in installation.objects if o.kind == "NotificationRule"]
        if not rules and not installation.retire.get("NotificationRule"):
            return set()
        if self.notify is None:
            self.log(f"   ! NotificationRule не применены: не задан сервис уведомлений ({NOTIFY_URL_ENV} и токен "
                     f"audience {NOTIFY_AUDIENCE}) — примените их tools/cp_packages.py apply")
            return {"NotificationRule"}
        for obj in rules:
            body = {"key": obj.key, "spec": substitute(obj.spec, self.env)}
            try:
                self._notify_checks[obj.key] = self._notify_call("POST", "/notification-rules:validate", body)
            except RuntimeError as error:
                raise PackageError(f"{obj.ref}: сервис уведомлений не принимает правило — {error}") from error
        return set()

    def _apply_NotificationRule(self, obj: Obj, spec: dict[str, Any]) -> None:
        """Версию считает сервис по хэшу спецификации: запись — только если :validate сказал
        changed; без изменений ничего не пишется."""
        current = next((r for r in self._notify_list(key=obj.key) if r["key"] == obj.key), None)
        if not self._notify_checks[obj.key].get("changed"):
            self._say(obj.ref, f"v{current['version'] if current else '?'} без изменений")
            if current is not None:
                self.result[obj.ref] = {"version": current["version"]}
            return
        reason = "нет в сервисе" if current is None else "изменилась спецификация"
        if self.dry_run:
            self._say(obj.ref, f"новая версия ({reason})")
            return
        rule = self._notify_call("POST", "/notification-rules", {"key": obj.key, "spec": spec})
        self._say(obj.ref, f"опубликована v{rule['version']} ({reason})")
        self.result[obj.ref] = {"version": rule["version"]}

    # версии неизменяемы: TaskType и ProjectTemplate
    def _apply_versioned(self, obj: Obj, spec: dict[str, Any], collection: str, entity: str) -> None:
        desired = _desired(obj.kind, spec)
        active = sorted(self._list(f"/{collection}", key=obj.key, status="active"), key=lambda i: i["version"])
        latest = self._get(f"/{collection}/{active[-1]['id']}") if active else None
        if latest is not None and not _differences(obj.kind, desired, latest):
            keep = latest
            self._say(obj.ref, f"v{latest['version']} без изменений")
        else:
            reason = "нет в tenant" if latest is None else "изменились " + ", ".join(_differences(obj.kind, desired, latest))
            if self.dry_run:
                self._say(obj.ref, f"новая версия ({reason})")
                keep = None
            else:
                keep = self._write("POST", f"/{collection}", {"key": obj.key, **spec})
                if obj.kind == "TaskType" and spec.get("execution") and not keep.get("execution"):
                    raise PackageError(f"{obj.ref}: control-plane не сохранил execution — релиз ядра старше CP-ADR-0056 §3")
                self._say(obj.ref, f"опубликована v{keep['version']} ({reason})")
        for item in active:
            if keep is None or item["id"] != keep["id"]:
                if not self.dry_run:
                    self._write("POST", f"/{collection}/{item['id']}:deprecate")
                self._say(obj.ref, f"v{item['version']} → deprecated")
        if keep is not None:
            self.result[obj.ref] = {"id": keep["id"], "version": keep["version"]}

    def _apply_ArtifactType(self, obj: Obj, spec: dict[str, Any]) -> None:
        """Версии неизменяемы и из оборота не выводятся (CP-ADR-0072 §6: у API нет
        :deprecate) — новая версия публикуется, только если файл отличается от последней."""
        desired = _desired(obj.kind, spec)
        versions = self._list("/artifact-types", key=obj.key)
        latest = max(versions, key=lambda i: i["version"]) if versions else None
        changed = _differences(obj.kind, desired, latest) if latest is not None else []
        if latest is not None and not changed:
            keep = latest
            self._say(obj.ref, f"v{latest['version']} без изменений")
        else:
            reason = "нет в tenant" if latest is None else "изменились " + ", ".join(changed)
            if self.dry_run:
                self._say(obj.ref, f"новая версия ({reason})")
                return
            keep = self._write("POST", "/artifact-types", {"key": obj.key, **desired})
            self._say(obj.ref, f"опубликована v{keep['version']} ({reason})")
        self.result[obj.ref] = {"id": keep["id"], "version": keep["version"]}

    def _apply_Agent(self, obj: Obj, spec: dict[str, Any]) -> None:
        """Ревизию считает ядро по хэшу описания (CP-ADR-0073): сначала :validate — без
        изменений ничего не пишется; state и число экземпляров меняются без новой ревизии."""
        body = {"key": obj.key, "spec": spec}
        check = self._write("POST", "/agents:validate", body)
        current = check.get("currentRevision")
        if not check.get("wouldCreateRevision") and not check.get("wouldChangeState"):
            self._say(obj.ref, f"ревизия {current} без изменений")
            self.result[obj.ref] = {"revision": current}
            return
        reason = ("нет в tenant" if current is None else
                  "новая ревизия" if check.get("wouldCreateRevision") else "меняется состояние")
        if self.dry_run:
            self._say(obj.ref, reason)
            return
        agent = self._write("POST", "/agents", body)
        what = f"ревизия {agent['currentRevision']}" + (f" ({reason})" if reason != "новая ревизия" else "")
        self._say(obj.ref, f"опубликована {what}, {agent['state']} × {agent['replicas']}")
        self.result[obj.ref] = {"id": agent["id"], "revision": agent["currentRevision"]}

    def _apply_TaskType(self, obj: Obj, spec: dict[str, Any]) -> None:
        self._apply_versioned(obj, spec, "task-types", "task_type")

    def _apply_ProjectTemplate(self, obj: Obj, spec: dict[str, Any]) -> None:
        self._apply_versioned(obj, spec, "project-templates", "project_template")

    def _retire(self, kind: str, key: str) -> None:
        if kind == "NotificationRule":
            current = next((r for r in self._notify_list(key=key, includeRetired="true") if r["key"] == key), None)
            if current is None:
                self._say(f"{kind}/{key}", "нет в сервисе уведомлений")
            elif current.get("state") == "retired":
                self._say(f"{kind}/{key}", "уже выведено из оборота")
            else:
                if not self.dry_run:
                    self._notify_call("POST", f"/notification-rules/{key}:retire")
                self._say(f"{kind}/{key}", f"v{current['version']} → retired: уведомлений по нему больше нет, "
                                           "отправленные остаются")
            return
        if kind == "Agent":
            try:
                agent = self._get(f"/agents/{key}")
            except Exception as error:
                if "404" not in str(error):
                    raise
                self._say(f"{kind}/{key}", "нет в tenant")
                return
            if agent.get("status") == "retired":
                self._say(f"{kind}/{key}", "уже выведен из оборота")
                return
            if not self.dry_run:
                self._write("POST", f"/agents/{key}:retire", {"reason": "retire в установке пакетов"})
            self._say(f"{kind}/{key}", "→ retired: исполнитель остановлен, credential отозван")
            return
        if kind == "WorkRule":
            # DELETE архивирует: правило больше не оценивается, заведённая им работа остаётся.
            live = [r for r in self._list("/rules", key=key) if r.get("status") != "archived"]
            if not live:
                self._say(f"{kind}/{key}", "уже в архиве")
            for rule in live:
                if not self.dry_run:
                    self._write("DELETE", f"/rules/{rule['id']}")
                self._say(f"{kind}/{key}", "→ archived (retire)")
            return
        collection = {"TaskType": "task-types", "ProjectTemplate": "project-templates"}[kind]
        active = self._list(f"/{collection}", key=key, status="active")
        if not active:
            self._say(f"{kind}/{key}", "уже выведен из оборота")
        for item in sorted(active, key=lambda i: i["version"]):
            if not self.dry_run:
                self._write("POST", f"/{collection}/{item['id']}:deprecate")
            self._say(f"{kind}/{key}", f"v{item['version']} → deprecated (retire)")

    # изменяемые: WorkspaceType, Role
    def _apply_mutable(self, obj: Obj, spec: dict[str, Any], current: dict | None, create_path: str,
                       update_path: Callable[[dict], str], etag: Callable[[dict], str]) -> None:
        desired = _desired(obj.kind, spec)
        identity = IDENTITY[obj.kind]
        if current is None:
            if self.dry_run:
                self._say(obj.ref, "будет создан")
                return
            current = self._write("POST", create_path, {identity: obj.key, **desired})
            self._say(obj.ref, "создан")
        else:
            changed = _differences(obj.kind, desired, current)
            if not changed:
                self._say(obj.ref, "без изменений")
            elif self.dry_run:
                self._say(obj.ref, "изменятся " + ", ".join(changed))
            else:
                current = self._write("PATCH", update_path(current), {name: desired[name] for name in changed},
                                      {"If-Match": etag(current)})
                self._say(obj.ref, "обновлены " + ", ".join(changed))
        self.result[obj.ref] = {"id": current["id"]}

    def _apply_WorkspaceType(self, obj: Obj, spec: dict[str, Any]) -> None:
        current = next((t for t in self._list("/workspace-types") if t["key"] == obj.key), None)
        if current is not None and current.get("status") != "active":
            raise PackageError(f"{obj.ref}: тип workspace в статусе {current.get('status')} — вернуть его пакет не может")
        self._apply_mutable(obj, spec, current, "/workspace-types", lambda c: f"/workspace-types/{c['id']}",
                            lambda c: f'"workspace_type-{c["version"]}"')

    def _apply_Role(self, obj: Obj, spec: dict[str, Any]) -> None:
        # Роли пакета — уровня tenant; роль workspace с тем же slug — чужая топология.
        current = next((r for r in self._list("/roles") if r["slug"] == obj.key and r.get("workspaceId") is None), None)
        self._apply_mutable(obj, spec, current, "/roles", lambda c: f"/roles/{c['id']}",
                            lambda c: f'"role-{c["version"]}"')

    # только добавление: Capability
    def _apply_Capability(self, obj: Obj, spec: dict[str, Any]) -> None:
        current = next((c for c in self._list("/capabilities") if c["name"] == obj.key), None)
        description = spec.get("description", "")
        if current is None:
            if self.dry_run:
                self._say(obj.ref, "будет создана")
                return
            current = self._write("POST", "/capabilities", {"name": obj.key, "description": description})
            self._say(obj.ref, "создана")
        elif current.get("description", "") != description:
            self._say(obj.ref, "!! описание в tenant отличается, а API его не меняет — оставлено как есть")
        else:
            self._say(obj.ref, "без изменений")
        self.result[obj.ref] = {"id": current["id"]}

    # Skill: версия задана пакетом, контракт неизменяем
    def _apply_Skill(self, obj: Obj, spec: dict[str, Any]) -> None:
        version = spec["version"]
        current = next((s for s in self._list("/skills", name=obj.key) if s.get("version") == version), None)
        if current is None:
            if self.dry_run:
                self._say(obj.ref, "будет зарегистрирован")
                return
            current = self._write("POST", "/skills", {"name": obj.key, **spec})
            self._say(obj.ref, "зарегистрирован")
            self.result[obj.ref] = {"id": current["id"]}
            return
        current = self._get(f"/skills/{current['id']}")
        immutable = []
        endpoint = None
        for name in SKILL_IMMUTABLE:
            if name not in spec:
                continue
            wanted = spec[name]
            if name == "contract":
                domain = _domain()
                if domain is not None:
                    wanted = domain.skill_contract.normalize_contract(wanted)
                same = is_subset(wanted, current.get(name))
                if not same:
                    # адрес реализации — свойство инсталляции, не версии (амендмент ADR-0056
                    # от 2026-09-29): отличие только в нём переводится PATCH'ем
                    endpoint = _moved_endpoint(wanted, current.get(name))
                    same = endpoint is not None
            else:
                same = canonical(wanted) == canonical(current.get(name))
            if not same:
                immutable.append(name)
        if immutable:
            raise PackageError(f"{obj.ref}: в опубликованной версии отличаются {', '.join(immutable)} — "
                               "контракт версии неизменяем, поднимите spec.version")
        changes = {name: spec[name] for name in SKILL_MUTABLE
                   if name in spec and not (spec.get("contract") and name in ("inputSchema", "outputSchema"))
                   and canonical(spec[name]) != canonical(current.get(name))}
        if endpoint is not None:
            changes["endpoint"] = endpoint
        if not changes:
            self._say(obj.ref, "без изменений")
        elif self.dry_run:
            self._say(obj.ref, "изменятся " + ", ".join(changes))
        else:
            current = self._write("PATCH", f"/skills/{current['id']}", changes,
                                  {"If-Match": f'"skill-{current["rowVersion"]}"'})
            self._say(obj.ref, "обновлены " + ", ".join(changes))
        self.result[obj.ref] = {"id": current["id"]}


    # WorkRule: изменяемый, как WorkspaceType; статус — через :enable / :disable
    def _apply_WorkRule(self, obj: Obj, spec: dict[str, Any]) -> None:
        live = [r for r in self._list("/rules", key=obj.key) if r.get("status") != "archived"]
        current = live[0] if live else None
        status = spec.get("status", "enabled")
        body = {name: spec[name] for name in RULE_MUTABLE if name in spec}
        workspace = spec.get("workspaceId")
        if current is None:
            if self.dry_run:
                self._say(obj.ref, f"будет создано ({status})")
                return
            payload = {"key": obj.key, **body, "status": status}
            if workspace:
                payload["workspaceId"] = workspace
            current = self._rule_write(obj, "POST", "/rules", payload)
            self._say(obj.ref, f"создано ({current['status']}, v{current['version']})")
            self.result[obj.ref] = {"id": current["id"], "version": current["version"]}
            return
        if (workspace or None) != current.get("workspaceId"):
            raise PackageError(f"{obj.ref}: workspaceId правила неизменяем (в tenant {current.get('workspaceId')}, "
                               f"в пакете {workspace}) — выведите правило через retire и заведите заново")
        domain = _domain()
        wanted = normalize_rule(spec, domain) if domain is not None else {
            "description": spec.get("description", ""), "condition": spec.get("condition", True), **body}
        changed = [name for name in RULE_MUTABLE if canonical(wanted.get(name)) != canonical(current.get(name))]
        if not changed:
            self._say(obj.ref, f"v{current['version']} без изменений")
        elif self.dry_run:
            self._say(obj.ref, "изменятся " + ", ".join(changed))
        else:
            current = self._rule_write(obj, "PATCH", f"/rules/{current['id']}",
                                       {name: wanted[name] for name in changed},
                                       {"If-Match": f'"rule-{current["version"]}"'})
            self._say(obj.ref, f"обновлены {', '.join(changed)} → v{current['version']}")
        if current.get("status") != status:
            verb = "enable" if status == "enabled" else "disable"
            if not self.dry_run:
                current = self._write("POST", f"/rules/{current['id']}:{verb}")
            self._say(obj.ref, f"→ {status}")
        self.result[obj.ref] = {"id": current["id"], "version": current["version"]}

    def _rule_write(self, obj: Obj, method: str, path: str, body: dict, extra: dict | None = None) -> dict:
        try:
            return self._write(method, path, body, extra)
        except RuntimeError as error:
            # Контракт identity и agent:<key> опубликован раньше реализации (declarative-cycle
            # C002): до C005/C006 ядро отвечает 501 not_implemented и ничего не пишет.
            if "HTTP 501" in str(error):
                raise PackageError(f"{obj.ref}: ядро ещё не исполняет поле правила — {error}") from error
            raise


def apply(installation: Installation, http: HttpLike, headers: dict[str, str], *, env: dict[str, str] | None = None,
          dry_run: bool = False, log: Callable[[str], None] = print,
          notify: tuple[HttpLike, dict[str, str]] | None = None) -> dict[str, dict[str, Any]]:
    """Установить пакеты в tenant, от имени которого выдан токен в headers.

    notify — клиент и заголовки сервиса уведомлений для вида NotificationRule; без него
    правила уведомлений пропускаются с предупреждением (bootstrap до шага уведомлений)."""
    errors, warnings = check(installation, env=env)
    for warning in warnings:
        log(f"   ! {warning}")
    if errors:
        raise PackageError("пакеты не прошли проверку:\n  " + "\n  ".join(errors))
    names = ", ".join(f"{p.key} {p.spec.get('version')}" for p in installation.packages)
    log(f"   пакеты: {names}")
    notify_http, notify_headers = notify if notify is not None else (None, {})
    return Applier(http, headers, env=dict(env or {}), dry_run=dry_run, log=log, notify=notify_http,
                   notify_headers=dict(notify_headers)).apply(installation)


# --- экспорт ------------------------------------------------------------------


EXPORT_FIELDS = {
    "TaskType": ("displayName", "description", "fieldSchema", "lifecycleSchema", "execution", "approvalSchema",
                 "contextSchema", "instructions", "completionSchema", "artifactSchema", "acceptance"),
    "ArtifactType": ("displayName", "description", "metadataSchema", "mediaTypes", "maxBytes"),
    # Agent выгружается из ревизии; state и число экземпляров — из желаемого состояния агента
    "Agent": ("displayName", "description", "identity", "work", "executor", "workingCopy", "skills", "placement",
              "state"),
    "ProjectTemplate": ("displayName", "description", "fieldSchema", "lifecycleSchema", "defaultConfig",
                        "defaultViews", "governanceSchema", "memoryDefaults"),
    "WorkspaceType": ("displayName", "description", "fieldSchema", "allowedChildTypes"),
    "Role": ("name", "description"),
    "Capability": ("description",),
    "Skill": ("version", "description", "protocol", "config", "inputSchema", "outputSchema",
              "sideEffects", "riskLevel", "contract"),
    # workspaceId — топология установки, в пакет не выгружается
    "WorkRule": ("description", "trigger", "condition", "interpretation", "action", "identity", "status"),
    # спецификация хранится сервисом как применена (ADR-0005 §5) — выгружается как есть
    "NotificationRule": ("description", "on", "recipient", "notification", "dedupKeyTemplate", "close", "status"),
}


def _fetch(applier: Applier, kind: str, key: str, version: str | None) -> dict:
    if kind == "NotificationRule":
        if version:
            raise PackageError("NotificationRule выгружается только действующей версией — без --version")
        current = next((r for r in applier._notify_list(key=key) if r["key"] == key), None)
        if current is None:
            raise PackageError(f"{kind}/{key} не найден в сервисе уведомлений")
        return {**current["spec"], "version": current["version"]}
    if kind in ("TaskType", "ProjectTemplate"):
        collection = "task-types" if kind == "TaskType" else "project-templates"
        items = applier._list(f"/{collection}", key=key)
        if version:
            items = [i for i in items if str(i["version"]) == version]
        else:
            items = [i for i in items if i.get("status") == "active"] or items
        if not items:
            raise PackageError(f"{kind}/{key}{'@' + version if version else ''} не найден")
        return applier._get(f"/{collection}/{max(items, key=lambda i: i['version'])['id']}")
    if kind == "Agent":
        try:
            return agent_body(applier._get(f"/agents/{key}{'@' + version if version else ''}"))
        except Exception as error:
            if "404" not in str(error):
                raise
            raise PackageError(f"{kind}/{key}{'@' + version if version else ''} не найден") from error
    if kind == "ArtifactType":
        try:
            return applier._get(f"/artifact-types/{key}{'@' + version if version else ''}")
        except Exception as error:  # 404 — не найден, остальное пусть видно как есть
            if "404" not in str(error):
                raise
            raise PackageError(f"{kind}/{key}{'@' + version if version else ''} не найден") from error
    if kind == "WorkspaceType":
        found = [t for t in applier._list("/workspace-types") if t["key"] == key]
    elif kind == "Role":
        found = [r for r in applier._list("/roles") if r["slug"] == key]
    elif kind == "Capability":
        found = [c for c in applier._list("/capabilities") if c["name"] == key]
    elif kind == "WorkRule":
        found = [r for r in applier._list("/rules", key=key) if r.get("status") != "archived"]
    else:
        found = [s for s in applier._list("/skills", name=key) if not version or s.get("version") == version]
        if found:
            found = [applier._get(f"/skills/{found[-1]['id']}")]
    if not found:
        raise PackageError(f"{kind}/{key} не найден")
    return found[-1]


def agent_body(agent: dict) -> dict:
    """Описание агента, как в пакете: спецификация ревизии плюс желаемое состояние."""
    spec = copy.deepcopy(agent["revision"]["spec"])
    # умолчания схемы (running, один экземпляр) в файл не пишутся — как в пакетах
    if agent["state"] != "running":
        spec["state"] = agent["state"]
    if isinstance(spec.get("placement"), dict) and agent["replicas"] != 1:
        spec["placement"]["replicas"] = agent["replicas"]
    return spec


def to_document(kind: str, key: str, body: dict) -> dict:
    spec: dict[str, Any] = {}
    for name in EXPORT_FIELDS[kind]:
        value = body.get(name)
        if value in (None, "", {}, []) and name not in ("fieldSchema", "approvalSchema"):
            continue
        if kind == "Skill" and body.get("contract") and name in ("inputSchema", "outputSchema", "protocol"):
            continue  # у скилла с контрактом они выводятся из контракта
        spec[name] = value
    if kind == "Skill" and spec.get("contract"):
        # Контракт на сервере нормализован: пустые значения по умолчанию в файле не нужны.
        contract = {k: v for k, v in spec["contract"].items() if v not in (None, [])}
        contract["implementation"] = {k: v for k, v in (contract.get("implementation") or {}).items()
                                      if v is not None}
        spec["contract"] = contract
    return {"apiVersion": API_VERSION, "kind": kind, "key": key, "spec": spec}


class _Dumper(yaml.SafeDumper if yaml else object):  # type: ignore[misc]
    pass


def _str_presenter(dumper: Any, data: str) -> Any:
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


if yaml is not None:
    _Dumper.add_representer(str, _str_presenter)


def dump_document(document: dict, schema_rel: str) -> str:
    header = f"# yaml-language-server: $schema={schema_rel}\n"
    return header + yaml.dump(document, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=100)


# --- процессы: проверка, тесты, план и применение ядром -----------------------
#
# Контракт ядра — CP-ADR-0074 §10–11, §16 и схемы api/v1/schemas.py control-plane
# (PackageSource, PackageTestRequest/Out, PackagePlanRequest/Out, PackageApplyRequest/Out,
# ProcessProblemOut, ProcessCoverageOut). Запрос — один пакет своими файлами; ядро само
# разбирает YAML, поэтому находка называет файл и строку. Пакеты из requires ядро берёт
# из каталога стенда, переименования — из renames в package.yaml среди файлов.
#
#   POST /packages:test[?checkOnly=true]  {package: {files: [{path, content}]}, tests?: [путь], workspaceId?}
#     → {status: passed|failed|invalid, checkOnly, problems[], tests[{file, name, process, status,
#        durationMs, failures[{step, message, expected, actual}]}], coverage[{process, version,
#        elements|transitions|decisionRows|handlers: {covered, total, missing[]}}], durationMs}
#   POST /packages:plan   {package, workspaceId?, replayLimit}
#     → {planHash, catalogEtag, package: {key, version}, changes[{kind, key, action:
#        create|update|rename|retire|unchanged, renamedFrom, fields[{path, before, after, owner:
#        package|console, applies}]}], processes[{key, fromVersion, toVersion, behaviour{replayed,
#        diverged, instanceIds}, instances[{version, open, fate: pin|migrate|unaffected,
#        migrationRequired}]}], regulationCoverage[{document, found, covered, uncovered}],
#        problems[], createdAt}
#   POST /packages:apply  {package, planHash, workspaceId?} → {planHash, catalogEtag, applied[{kind,
#        key, action, version}]}; стенд изменился — 409 plan_stale; 422 migration_required
#   Находка: {code, severity: error|warning, path (JSON pointer), file, line, message, hint}.
#   Ошибка: {error: {code, message, details, requestId}}; до своего шага маршрут отвечает
#   501 not_implemented с details {adr, implementedBy}.

PACKAGES_TEST = "/packages:test"
PACKAGES_PLAN = "/packages:plan"
PACKAGES_APPLY = "/packages:apply"
PLAN_FORMAT = "taimen.package-plan/v1"
PLAN_STALE = "plan_stale"
DEFAULT_REPLAY_LIMIT = 50
# Файлы пакета, которые уходят ядру: описания, схемы данных, тесты. Раскладка схемы
# (.layout) логики не несёт и не отправляется.
_SENT_SUFFIXES = (".yaml", ".yml", ".json")


class CoreUnsupported(PackageError):
    """Ядро не знает маршрута (404) или ещё не реализует его (501 not_implemented)."""


def package_files(package: Package, env: dict[str, str], *, strict: bool) -> list[dict[str, str]]:
    """PackageSource.files: [{path, content}] с подставленными ${ПЕРЕМЕННЫМИ} установки.
    strict — незаданная переменная — ошибка (план и применение); иначе остаётся как есть."""
    files: list[dict[str, str]] = []
    for path in sorted(package.path.rglob("*")):
        inner = path.relative_to(package.path)
        if not path.is_file() or path.suffix not in _SENT_SUFFIXES or \
                any(part.startswith(".") for part in inner.parts):
            continue
        text = path.read_text(encoding="utf-8")
        files.append({"path": inner.as_posix(),
                      "content": substitute(text, env, missing=None if strict else (lambda name: "${" + name + "}"))})
    return files


def package_source(package: Package, env: dict[str, str], *, strict: bool) -> dict[str, Any]:
    return {"files": package_files(package, env, strict=strict)}


def test_request(package: Package, env: dict[str, str], *, tests: list[PackageTest] | None = None,
                 workspace: str | None = None) -> dict[str, Any]:
    """PackageTestRequest; tests — фильтр путей файлов тестов (None — все)."""
    body: dict[str, Any] = {"package": package_source(package, env, strict=False)}
    if tests is not None:
        body["tests"] = [t.path.relative_to(package.path).as_posix() for t in tests]
    if workspace:
        body["workspaceId"] = workspace
    return body


test_request.__test__ = False  # не тест pytest


def plan_request(package: Package, env: dict[str, str], *, workspace: str | None = None,
                 replay_limit: int = DEFAULT_REPLAY_LIMIT) -> dict[str, Any]:
    body: dict[str, Any] = {"package": package_source(package, env, strict=True), "replayLimit": replay_limit}
    if workspace:
        body["workspaceId"] = workspace
    return body


def request_hash(body: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical(body).encode()).hexdigest()


def _error_envelope(body: Any) -> dict[str, Any]:
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        return body["error"]
    return body if isinstance(body, dict) else {}


@dataclass
class ProcessApi:
    """Вызовы ядра для пакетов с процессами; ошибки HTTP → понятные исключения."""
    http: HttpLike
    headers: dict[str, str]

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {**self.headers, "Idempotency-Key": str(uuid.uuid4())}
        try:
            return self.http.call("POST", API + path, body, headers)
        except HttpError as error:
            route = path.split("?", 1)[0]
            envelope = _error_envelope(error.body)
            if error.status == 404:
                raise CoreUnsupported(f"ядро не знает {route} — процессы на нём ещё не выкачены") from error
            if error.status == 501:
                step = (envelope.get("details") or {}).get("implementedBy")
                raise CoreUnsupported(f"ядро ещё не реализует {route}" + (f" ({step})" if step else "")) from error
            if envelope.get("code") == PLAN_STALE:
                raise PackageError("план устарел: каталог стенда изменился после построения плана — "
                                   "постройте план заново (cp_packages plan … --out) и примените новый") from error
            problems = core_errors(error.body)
            if problems:
                raise CoreRejected(problems) from error
            raise

    def test(self, body: dict[str, Any], *, check_only: bool = False) -> dict[str, Any]:
        return self._post(PACKAGES_TEST + ("?checkOnly=true" if check_only else ""), body)

    def plan(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._post(PACKAGES_PLAN, body)

    def apply(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._post(PACKAGES_APPLY, body)


class CoreRejected(PackageError):
    """Ядро отвергло пакет: находки проверки в машиночитаемом виде."""

    def __init__(self, problems: list[dict[str, Any]]) -> None:
        super().__init__("ядро не принимает пакет:\n  " + "\n  ".join(format_core_error(p) for p in problems))
        self.errors = problems


def core_problems(body: Any) -> list[dict[str, Any]]:
    """Все находки ответа ядра (ProcessProblemOut): problems в ответе или в details ошибки."""
    if not isinstance(body, dict):
        return []
    if isinstance(body.get("problems"), list):
        return [p for p in body["problems"] if isinstance(p, dict)]
    details = _error_envelope(body).get("details")
    if isinstance(details, dict) and isinstance(details.get("problems"), list):
        return [p for p in details["problems"] if isinstance(p, dict)]
    return []


def core_errors(body: Any) -> list[dict[str, Any]]:
    """Находки с severity error (без severity — тоже ошибка)."""
    return [p for p in core_problems(body) if p.get("severity", "error") == "error"]


def core_warnings(body: Any) -> list[dict[str, Any]]:
    return [p for p in core_problems(body) if p.get("severity") == "warning"]


def format_core_error(error: dict[str, Any]) -> str:
    """ProcessProblemOut → «файл:строка: код: сообщение [путь] (подсказка: …)»."""
    place = error.get("file") or ""
    if place and error.get("line") is not None:
        place += f":{error['line']}"
    text = f"{place + ': ' if place else ''}{error.get('code', 'error')}: {error.get('message', '')}"
    if error.get("path"):
        text += f" [{error['path']}]"
    if error.get("hint"):
        text += f" (подсказка: {error['hint']})"
    return text


def static_error(message: str) -> dict[str, Any]:
    """Ошибка статической проверки в форме находки ядра."""
    file, _, rest = message.partition(": ")
    if rest and ("/" in file or file.endswith((".yaml", ".yml"))):
        return {"code": "static_check", "severity": "error", "file": file, "message": rest}
    return {"code": "static_check", "severity": "error", "message": message}


_COUNTERS = ("elements", "transitions", "decisionRows", "handlers")


def print_test_report(response: dict[str, Any], log: Callable[[str], None] = print) -> bool:
    """PackageTestOut: находки, результаты тестов, покрытие; True — status passed."""
    for problem in core_errors(response):
        log(f"ошибка: {format_core_error(problem)}")
    for problem in core_warnings(response):
        log(f"предупреждение: {format_core_error(problem)}")
    results = response.get("tests") or []
    for result in results:
        status = result.get("status", "error")
        mark = {"passed": "ok  ", "failed": "FAIL", "error": "ERR "}.get(status, status)
        took = f" ({result['durationMs']} мс)" if result.get("durationMs") is not None else ""
        log(f"{mark} {result.get('file', '')}: {result.get('name', '')} [{result.get('process', '')}]{took}")
        for failure in result.get("failures") or []:
            log(f"     шаг {failure.get('step')}: {failure.get('message', '')}")
            if failure.get("expected") is not None or failure.get("actual") is not None:
                log(f"       ожидалось: {json.dumps(failure.get('expected'), ensure_ascii=False)}; "
                    f"получено: {json.dumps(failure.get('actual'), ensure_ascii=False)}")
    for coverage in response.get("coverage") or []:
        parts = [f"{name} {(coverage.get(name) or {}).get('covered', 0)}/{coverage[name]['total']}"
                 for name in _COUNTERS if isinstance(coverage.get(name), dict) and coverage[name].get("total")]
        log(f"покрытие {coverage.get('process')} v{coverage.get('version')}: {', '.join(parts) or 'нет данных'}")
        for name in _COUNTERS:
            missing = (coverage.get(name) or {}).get("missing") or []
            if missing:
                log(f"   не пройдены ({name}): {', '.join(str(m) for m in missing)}")
    status = response.get("status", "invalid")
    passed = sum(r.get("status") == "passed" for r in results)
    log(f"{'ok' if status == 'passed' else 'не пройдено'} ({status}): тестов {len(results)}, зелёных {passed}")
    return status == "passed"


def print_plan(response: dict[str, Any], log: Callable[[str], None] = print) -> bool:
    """PackagePlanOut: структурный и поведенческий diff, судьба экземпляров, покрытие
    регламентов; False — в плане ошибки (например migration_required)."""
    marks = {"create": "+", "update": "~", "retire": "-", "rename": "→", "unchanged": "="}
    package = response.get("package") or {}
    log(f"план {package.get('key', '?')} {package.get('version', '')}: {response.get('planHash', '?')} "
        f"(каталог {response.get('catalogEtag', '?')})")
    for change in response.get("changes") or []:
        ref = f"{change.get('kind')}/{change.get('key')}"
        if change.get("action") == "rename":
            ref = f"{change.get('kind')}/{change.get('renamedFrom')} → {ref}"
        line = f"  {marks.get(change.get('action'), '?')} {ref}"
        fields = change.get("fields") or []
        if fields:
            line += ": " + "; ".join(
                str(f.get("path")) + ("" if f.get("owner") != "console" else
                                      " (правлено в консоли, " + ("будет перезаписано)" if f.get("applies")
                                                                  else "не перезаписывается)"))
                for f in fields)
        log(line)
    for process in response.get("processes") or []:
        before = process.get("fromVersion")
        log(f"процесс {process.get('key')}: " + (f"v{before} → " if before is not None else "новый, ")
            + f"v{process.get('toVersion')}")
        behaviour = process.get("behaviour")
        if behaviour:
            diverged = behaviour.get("instanceIds") or []
            log(f"  поведение (replay): экземпляров {behaviour.get('replayed', 0)}, расхождений "
                f"{behaviour.get('diverged', 0)}" + (f": {', '.join(str(i) for i in diverged)}" if diverged else ""))
        for group in process.get("instances") or []:
            blocked = " — нужна миграция (migration_required)" if group.get("migrationRequired") else ""
            log(f"  открытые экземпляры v{group.get('version')}: {group.get('open', 0)} → {group.get('fate')}{blocked}")
    for coverage in response.get("regulationCoverage") or []:
        if not coverage.get("found"):
            log(f"регламент {coverage.get('document')}: нет в памяти")
            continue
        uncovered = coverage.get("uncovered") or []
        log(f"регламент {coverage.get('document')}: разделов с элементами {len(coverage.get('covered') or {})}"
            + (f", без элементов: {', '.join(uncovered)}" if uncovered else ""))
    errors = core_errors(response)
    for problem in errors:
        log(f"ошибка: {format_core_error(problem)}")
    for problem in core_warnings(response):
        log(f"предупреждение: {format_core_error(problem)}")
    return not errors and not any(g.get("migrationRequired") for p in response.get("processes") or []
                                  for g in p.get("instances") or [])


def save_plan(path: Path, server: str, plans: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    """Файл плана: по пакету запрос плана, его хэш и ответ ядра (planHash)."""
    entries = []
    for request, response in plans:
        if not response.get("planHash"):
            raise PackageError("ядро не вернуло planHash — применять нечего")
        entries.append({"package": (response.get("package") or {}).get("key"), "planHash": response["planHash"],
                        "requestHash": request_hash(request), "request": request, "plan": response})
    document = {"format": PLAN_FORMAT, "server": server.rstrip("/"),
                "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "plans": entries}
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document


def load_plan(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PackageError(f"{path}: не файл плана: {error}") from error
    if not isinstance(document, dict) or document.get("format") != PLAN_FORMAT or \
            not isinstance(document.get("plans"), list):
        raise PackageError(f"{path}: не файл плана {PLAN_FORMAT}")
    for entry in document["plans"]:
        if request_hash(entry.get("request") or {}) != entry.get("requestHash"):
            raise PackageError(f"{path}: план правили после построения (хэш не сходится) — постройте план заново")
    return document


def apply_plan(document: dict[str, Any], api: ProcessApi, log: Callable[[str], None] = print) -> list[dict[str, Any]]:
    """Применить ровно этот план: по пакету PackageApplyRequest {package, planHash, workspaceId};
    ядро строит план заново из тех же файлов и сверяет хэш."""
    responses = []
    for entry in document["plans"]:
        request = entry["request"]
        body = {"package": request["package"], "planHash": entry["planHash"]}
        if request.get("workspaceId"):
            body["workspaceId"] = request["workspaceId"]
        response = api.apply(body)
        for item in response.get("applied") or []:
            version = f" v{item['version']}" if item.get("version") is not None else ""
            log(f"   {item.get('kind')}/{item.get('key')}: {item.get('action')}{version}")
        log(f"применён план {entry.get('package')}: {entry['planHash']}")
        responses.append(response)
    return responses


# --- перевод прежних выражений в CEL (migrate-expr) ----------------------------
#
# Перевод — пара функций ядра в control_plane.domain.cel_profile (CP-ADR-0075 §7, Р7):
# legacy_expressions(kind, spec) находит прежние выражения объекта каталога — каждое
# LegacyExpression(pointer, syntax, source), pointer — JSON pointer от корня объекта
# (/spec/condition); translate(expression) даёт Translation(expression, bindings):
# текст CEL и переменные сверх профиля, которые он читает. Где выражения лежат и как
# их переводить, знает только ядро — здесь ни поиска, ни перевода нет.


class ExpressionTranslator(Protocol):
    def legacy_expressions(self, kind: str, spec: Any) -> Iterable[Any]: ...

    def translate(self, expression: Any) -> Any: ...


def _translator() -> ExpressionTranslator:
    _domain()  # кладёт control-plane/src в sys.path
    try:
        from control_plane.domain import cel_profile
    except ImportError as error:
        raise PackageError("перевод выражений в CEL даёт ядро (control_plane.domain.cel_profile), а его модуль "
                           "не импортируется — нужен control-plane с профилем CEL taimen/1 (CP-ADR-0075)") from error
    missing = [name for name in ("legacy_expressions", "translate") if not callable(getattr(cel_profile, name, None))]
    if missing:
        raise PackageError(f"в control_plane.domain.cel_profile нет {', '.join(missing)} — нужен control-plane "
                           "с переводом прежних синтаксисов (CP-ADR-0075 Р7)")
    return cel_profile  # type: ignore[return-value]


def _pointer_parts(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        raise PackageError(f"указатель выражения {pointer!r} — не JSON pointer")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]


def _replace_at(document: Any, pointer: str, value: Any) -> None:
    """Заменить значение по JSON pointer в разобранном файле (ruamel: списки — по номеру)."""
    parts = _pointer_parts(pointer)
    holder = document
    for part in parts[:-1]:
        holder = holder[int(part)] if isinstance(holder, list) else holder[part]
    last = parts[-1]
    if isinstance(holder, list):
        holder[int(last)] = value
    else:
        holder[last] = value


def migrate_expressions(package: Package, *, write: bool = False, log: Callable[[str], None] = print,
                        core: ExpressionTranslator | None = None) -> int:
    """Перевести прежние выражения пакета в CEL переводом ядра: печать diff по файлам;
    write — записать с сохранением файла (tools/pkg.py). Возвращает число переведённых
    выражений; то, что не переводится, печатается и остаётся как было."""
    import difflib

    import pkg

    core = core or _translator()
    total = 0
    for obj in package.objects:
        if obj.kind in PLAN_KINDS:
            continue  # процессы и календари уже на CEL
        doc = pkg.Document.load(obj.path)
        spec = pkg.to_plain(doc.data.get("spec"))
        found = list(core.legacy_expressions(obj.kind, spec if isinstance(spec, dict) else {}))
        changed = 0
        for expression in found:
            where = f"{_rel(obj.path)}: {expression.pointer} ({expression.syntax})"
            try:
                translation = core.translate(expression)
            except Exception as error:  # noqa: BLE001 — перевод не всегда возможен: показать и идти дальше
                log(f"   ! {where} не переводится: {error}")
                continue
            _replace_at(doc.data, expression.pointer, translation.expression)
            changed += 1
            bindings = tuple(getattr(translation, "bindings", ()) or ())
            if bindings:
                log(f"   {where}: читает переменные сверх профиля: {', '.join(bindings)}")
        if not changed:
            continue
        total += changed
        after = doc.dumps()
        log("".join(difflib.unified_diff(doc.text.splitlines(keepends=True), after.splitlines(keepends=True),
                                         f"a/{_rel(obj.path)}", f"b/{_rel(obj.path)}")).rstrip("\n"))
        if write:
            doc.save()
    log(f"{'записано' if write else 'к переводу'}: выражений {total}" + ("" if write or not total else
                                                                          " (--write — записать)"))
    return total


# --- CLI ----------------------------------------------------------------------


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _token(server: str) -> str:
    token = os.environ.get("CP_TOKEN")
    if token:
        return token
    try:
        import asyncio

        from control_plane_client.credentials import resolve_credential
    except ImportError as error:
        raise PackageError("нет CP_TOKEN и нет control_plane_client — задайте CP_TOKEN или запустите "
                           "интерпретатором uv-tool control-plane") from error
    credential = resolve_credential(server)
    if credential is None:
        raise PackageError(f"нет credential для {server} в ~/.config/iam/credentials.json")
    return asyncio.run(credential.token())


def _token_for(audience: str, scopes: tuple[str, ...], *, fallback: str, environ: dict[str, str]) -> str:
    """Токен другого audience тем же IAM credential: переменная fallback (как CP_TOKEN) или
    обмен PAT через control_plane_client — его IamCredential принимает audience и scopes
    (CONTROL_PLANE_IAM_AUDIENCE/SCOPES), обмен здесь не переписывается. Legacy API key ядра
    на другой audience не меняется — тогда только переменная. PAT должен допускать audience
    в потолке, иначе IAM ответит iam_audience_not_allowed."""
    token = environ.get(fallback)
    if token:
        return token
    try:
        import asyncio

        from control_plane_client.iam import ENV_IAM_AUDIENCE, ENV_IAM_SCOPES, iam_credential_from_environment
    except ImportError as error:
        raise PackageError(f"нет {fallback} и нет control_plane_client — задайте {fallback} (access token "
                           f"audience {audience}) или запустите интерпретатором uv-tool control-plane") from error
    credential = iam_credential_from_environment({**environ, ENV_IAM_AUDIENCE: audience,
                                                  ENV_IAM_SCOPES: " ".join(scopes)})
    if credential is None:
        raise PackageError(f"нет {fallback}, а IAM credential не настроен (CONTROL_PLANE_IAM_URL) — токен "
                           f"audience {audience} получить нечем")
    return asyncio.run(credential.token())


def _notify_target(environ: dict[str, str]) -> tuple[Http, dict[str, str]]:
    url = environ.get(NOTIFY_URL_ENV)
    if not url:
        raise PackageError(f"NotificationRule применяются к сервису уведомлений — задайте {NOTIFY_URL_ENV}")
    token = _token_for(NOTIFY_AUDIENCE, NOTIFY_SCOPES, fallback=NOTIFY_TOKEN_ENV, environ=environ)
    return Http(url), {"Authorization": f"Bearer {token}"}


def _installation_from(args: argparse.Namespace) -> tuple[Installation, list[str]]:
    """Установка из --install или пакеты из --package (путь каталога или ключ); второе —
    ключи пакетов, названных явно (их ядро и проверяет: запрос — один пакет)."""
    if getattr(args, "install", None):
        installation = load_installation(args.install)
        return installation, [p.key for p in installation.packages]
    names = [Path(value).name for value in (getattr(args, "package", None) or [])]
    if not names:
        installation = resolve([d.name for d in all_package_dirs()])
        return installation, [p.key for p in installation.packages]
    return resolve(names), names


def _named(installation: Installation, keys: list[str]) -> list[Package]:
    return [p for p in installation.packages if p.key in keys]


def _process_api(server: str) -> ProcessApi:
    return ProcessApi(Http(server), {"Authorization": f"Bearer {_token(server)}"})


def _check_command(args: argparse.Namespace) -> int:
    installation, named = _installation_from(args)
    env = {**(read_env_file(args.env) if args.env else {}), **os.environ}
    errors, warnings = check(installation, env=env)
    problems = [static_error(e) for e in errors]
    core = "skipped"
    if args.server:
        try:
            api = _process_api(args.server)
            for package in _named(installation, named):
                try:
                    response = api.test(test_request(package, env, workspace=args.workspace), check_only=True)
                except CoreRejected as error:
                    problems += error.errors
                    continue
                problems += core_errors(response)
                warnings += [format_core_error(w) for w in core_warnings(response)]
            core = "checked"
        except CoreUnsupported as error:
            core = "unsupported"
            warnings.append(f"ядро не поддерживает проверку процессов ({error}) — проверена только схема")
        except (urllib.error.URLError, OSError) as error:
            core = "unreachable"
            warnings.append(f"ядро недоступно ({error}) — проверена только схема")
    count = len(installation.objects)
    if args.json:
        print(json.dumps({"ok": not problems, "errors": problems, "warnings": warnings, "core": core,
                          "packages": len(installation.packages), "objects": count, "tests": len(installation.tests)},
                         ensure_ascii=False, indent=2))
    else:
        for warning in warnings:
            print("предупреждение:", warning)
        for problem in problems:
            print("ошибка:", format_core_error(problem) if problem.get("code") != "static_check" else
                  (f"{problem['file']}: " if problem.get("file") else "") + problem["message"])
        print(f"{'не пройдено' if problems else 'ok'}: пакетов {len(installation.packages)}, объектов {count}, "
              f"тестов {len(installation.tests)}" + {"checked": ", проверено ядром", "unsupported": ", ядро: только схема",
                                                     "unreachable": ", ядро недоступно", "skipped": ""}[core])
    return 1 if problems else 0


def _test_command(args: argparse.Namespace) -> int:
    installation, named = _installation_from(args)
    env = {**read_env_file(args.env), **os.environ}
    selected = {key: [t for t in installation.tests if t.package == key and
                      (not args.test or args.test in (t.name, t.path.name, t.path.stem.removesuffix(".test")))]
                for key in named}
    errors, _warnings = check(installation, env=env)
    if errors:
        for error in errors:
            print("ошибка:", error)
        print("не пройдено: статическая проверка — тесты не запускались")
        return 1
    if not any(selected.values()):
        print("нет тестов: в пакетах " + ", ".join(named) + " нет tests/*.test.yaml" +
              (f" с именем {args.test!r}" if args.test else ""))
        return 1
    api = _process_api(args.server)
    ok = True
    responses = []
    for package in _named(installation, named):
        if not selected[package.key]:
            continue
        response = api.test(test_request(package, env, tests=selected[package.key], workspace=args.workspace))
        responses.append(response)
        if args.json:
            ok = ok and response.get("status") == "passed"
        else:
            print(f"== {package.key}")
            ok = print_test_report(response) and ok
    if args.json:
        print(json.dumps(responses if len(responses) > 1 else responses[0], ensure_ascii=False, indent=2))
    return 0 if ok else 1


def _plan_command(args: argparse.Namespace, env: dict[str, str]) -> int:
    installation = load_installation(args.install)
    errors, warnings = check(installation, env=env)
    for warning in warnings:
        print("предупреждение:", warning)
    if errors:
        raise PackageError("пакеты не прошли проверку:\n  " + "\n  ".join(errors))
    if installation.retire:
        # PackagePlanRequest — один пакет своими файлами; retire установки в нём нет (CP-ADR-0074 §11)
        retired = ", ".join(f"{kind}/{key}" for kind, keys in installation.retire.items() for key in keys)
        print(f"предупреждение: retire установки ({retired}) в план ядра не входит — "
              "его выполняет apply --install", file=sys.stderr)
    api = _process_api(args.server)
    log = (lambda _m: None) if args.json else print
    plans, clean = [], True
    for package in installation.packages:
        request = plan_request(package, env, workspace=args.workspace, replay_limit=args.replay_limit)
        response = api.plan(request)
        plans.append((request, response))
        clean = print_plan(response, log=log) and clean
    if args.json:
        print(json.dumps([response for _request, response in plans], ensure_ascii=False, indent=2))
    if not clean:
        print("план с ошибками — не сохранён", file=sys.stderr)
        return 1
    save_plan(args.out, args.server, plans)
    if not args.json:
        print(f"план сохранён: {args.out} — применить: tools/cp_packages.py apply --plan {args.out}")
    return 0


def _apply_plan_command(args: argparse.Namespace) -> int:
    document = load_plan(args.plan)
    server = (args.server or document["server"]).rstrip("/")
    if server != document["server"]:
        raise PackageError(f"план построен для {document['server']}, а применяется к {server}")
    apply_plan(document, _process_api(server))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    check_cmd = sub.add_parser("check", help="проверить пакеты: схема и ссылки; с --server — ещё и ядром")
    check_cmd.add_argument("--install", type=Path, help="файл установки; без него — все пакеты packages/")
    check_cmd.add_argument("--package", action="append", help="пакет (каталог или ключ); можно несколько")
    check_cmd.add_argument("--server", help="Control Plane: проверка процессов ядром (checkOnly), если оно умеет")
    check_cmd.add_argument("--env", type=Path, help="откуда брать ${ПЕРЕМЕННЫЕ} пакета (по умолчанию — окружение)")
    check_cmd.add_argument("--workspace", help="workspace, чьи роли и календари читает проверка ядром")
    check_cmd.add_argument("--json", action="store_true",
                           help="ошибки — JSON {code, severity, path, file, line, message, hint}")
    test_cmd = sub.add_parser("test", help="прогнать тесты процессов пакета в песочнице ядра")
    test_cmd.add_argument("--install", type=Path)
    test_cmd.add_argument("--package", action="append", help="пакет (каталог или ключ); можно несколько")
    test_cmd.add_argument("--test", help="только тест с этим именем или файлом")
    test_cmd.add_argument("--server", required=True)
    test_cmd.add_argument("--env", type=Path, default=ROOT / ".env")
    test_cmd.add_argument("--workspace", help="workspace, чьи роли, календари и экземпляры читает прогон")
    test_cmd.add_argument("--json", action="store_true", help="ответ ядра как есть")
    plan_cmd = sub.add_parser("plan", help="сверить установку с Control Plane; --out — план ядра для apply --plan")
    plan_cmd.add_argument("--install", type=Path, required=True)
    plan_cmd.add_argument("--server", required=True)
    plan_cmd.add_argument("--env", type=Path, default=ROOT / ".env", help="откуда брать ${ПЕРЕМЕННЫЕ} пакета")
    plan_cmd.add_argument("--out", type=Path, help="построить план ядром (/packages:plan) и сохранить с хэшем")
    plan_cmd.add_argument("--workspace", help="с --out: workspace процессов пакета")
    plan_cmd.add_argument("--replay-limit", type=int, default=DEFAULT_REPLAY_LIMIT,
                          help="с --out: экземпляров на процесс для replay (0–200)")
    plan_cmd.add_argument("--json", action="store_true", help="с --out: ответ ядра как есть")
    apply_cmd = sub.add_parser("apply", help="установить; --plan — применить ровно сохранённый план")
    apply_cmd.add_argument("--install", type=Path)
    apply_cmd.add_argument("--server")
    apply_cmd.add_argument("--env", type=Path, default=ROOT / ".env", help="откуда брать ${ПЕРЕМЕННЫЕ} пакета")
    apply_cmd.add_argument("--plan", type=Path, help="файл плана от plan --out")
    migrate_cmd = sub.add_parser("migrate-expr", help="перевести прежние выражения пакета в CEL (diff; --write)")
    migrate_cmd.add_argument("--package", required=True, help="пакет (каталог или ключ)")
    migrate_cmd.add_argument("--write", action="store_true", help="записать с сохранением файла")
    export_cmd = sub.add_parser("export", help="выгрузить объекты из Control Plane в пакет")
    export_cmd.add_argument("--server", help="Control Plane; для NotificationRule не нужен")
    export_cmd.add_argument("--env", type=Path, default=ROOT / ".env",
                            help=f"откуда брать {NOTIFY_URL_ENV} (для NotificationRule)")
    export_cmd.add_argument("--kind", required=True, choices=[k for k in CATALOG_KINDS if k not in PLAN_KINDS])
    export_cmd.add_argument("--key", required=True, action="append")
    export_cmd.add_argument("--version", help="версия (по умолчанию новейшая активная)")
    export_cmd.add_argument("--package", type=Path, required=True, help="каталог пакета, например packages/<пакет>")
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            return _check_command(args)
        if args.command == "test":
            return _test_command(args)
        if args.command == "migrate-expr":
            package = resolve([Path(args.package).name]).packages[-1]
            migrate_expressions(package, write=args.write)
            return 0
        if args.command == "apply" and args.plan:
            if args.install:
                raise PackageError("apply --plan применяет сохранённый план — --install не нужен")
            return _apply_plan_command(args)
        if args.command == "apply" and not (args.install and args.server):
            raise PackageError("apply: нужны --install и --server (или --plan <файл>)")

        env = {**read_env_file(args.env), **os.environ}
        if args.command == "plan" and args.out:
            return _plan_command(args, env)
        if args.command == "export" and args.kind == "NotificationRule":
            notify_http, notify_headers = _notify_target(env)
            # ядро выгрузке правила уведомлений не нужно
            applier = Applier(None, {}, log=lambda _m: None,  # type: ignore[arg-type]
                              notify=notify_http, notify_headers=notify_headers)
        else:
            if not args.server:
                raise PackageError("нужен --server (адрес Control Plane)")
            http = Http(args.server)
            headers = {"Authorization": f"Bearer {_token(args.server)}"}
            if args.command in ("plan", "apply"):
                installation = load_installation(args.install)
                uses_notify = any(o.kind == "NotificationRule" for o in installation.objects) or \
                    bool(installation.retire.get("NotificationRule"))
                apply(installation, http, headers, env=env, dry_run=args.command == "plan",
                      notify=_notify_target(env) if uses_notify else None)
                return 0
            applier = Applier(http, headers, log=lambda _m: None)
        target = args.package / FOLDERS[args.kind]
        target.mkdir(parents=True, exist_ok=True)
        schema_rel = os.path.relpath(SCHEMA_PATH, target)
        for key in args.key:
            body = _fetch(applier, args.kind, key, args.version)
            path = target / f"{key}.yaml"
            path.write_text(dump_document(to_document(args.kind, key, body), schema_rel), encoding="utf-8")
            print("записан", _rel(path), f"(v{body.get('version')})" if "version" in body else "")
        return 0
    except CoreUnsupported as error:
        print(f"ошибка: {error} — проверьте, что Control Plane новее движка процессов (CP-ADR-0074)",
              file=sys.stderr)
        return 1
    except (PackageError, RuntimeError) as error:
        print("ошибка:", error, file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"ошибка: Control Plane недоступен: {error.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
