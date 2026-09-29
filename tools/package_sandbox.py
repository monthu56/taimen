#!/usr/bin/env python3
"""Тесты пакета процессов песочницей ядра — без стенда и без базы (TAI-ADR-0054 п.8).

`cp_packages.py test` отправляет пакет ядру (`POST /packages:test`, CP-ADR-0074 §10).
Этот инструмент делает то же самое в процессе: берёт доменные модули control-plane
(`package_source`, `process_definition`, `process_engine`, `process_sandbox`) и
вместо каталога стенда собирает каталог из объектов пакета и его `requires` —
скиллы, типы задач, агенты, роли, типы артефактов, календари, процессы. Так
тесты пакета повторяются в CI и на машине автора, пока ядра с этим кодом нет на
стенде, и проверяют пакет вместе с тем, что он реально требует.

Чем отличается от `POST /packages:test`:

- каталог — только объекты пакетов (`requires` по файлам), а не каталог tenant'а;
  чего нет в пакетах, того нет и в песочнице;
- `governedBy` не сверяется с памятью: памяти нет, предупреждение ядра
  «документа нет в базе знаний» здесь не появится;
- переменные установки `${…}` подставляются из `--env` (файл .env) и окружения, как у
  `cp_packages test`; незаданные остаются, а `workspaceId` вида `${…}` снимается, как это
  делает ядро без `workspaceId` запроса.

Нужен control-plane в `PYTHONPATH` (или интерпретатор его uv-окружения):

    PYTHONPATH=control-plane/src:control-plane/client/src python3 tools/package_sandbox.py <пакет>
    python3 tools/package_sandbox.py <пакет> --test tests/cancel.test.yaml --json
    cd control-plane && uv run python ../tools/package_sandbox.py      # все пакеты с тестами (CI)

Код выхода 0 — все тесты зелёные и находок-ошибок нет.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cp_packages as cp  # noqa: E402

# Виды, которые песочница берёт из пакетов в каталог.
_CATALOG_KINDS = ("Skill", "TaskType", "Agent", "ArtifactType", "Role", "Calendar", "Process")


class CoreMissing(RuntimeError):
    """control-plane с движком процессов не импортируется."""


def _domain() -> Any:
    try:
        from control_plane.domain import process_definition as pd
        from control_plane.domain import process_engine as engine
        from control_plane.domain import process_sandbox as sandbox
        from control_plane.domain.calendar import Calendar, CalendarError
        from control_plane.domain.package_source import parse_package, select_tests
    except ImportError as exc:  # pragma: no cover - зависит от окружения
        raise CoreMissing(
            "нужен control-plane с движком процессов в PYTHONPATH "
            "(control-plane/src и control-plane/client/src): " + str(exc)
        ) from exc
    return {
        "pd": pd,
        "engine": engine,
        "sandbox": sandbox,
        "Calendar": Calendar,
        "CalendarError": CalendarError,
        "parse_package": parse_package,
        "select_tests": select_tests,
    }


def _files(package: cp.Package, env: dict[str, str]) -> list[tuple[str, str]]:
    return [(f["path"], f["content"]) for f in cp.package_files(package, env, strict=False)]


def _skill_entry(pd: Any, spec: dict[str, Any]) -> Any:
    contract = spec.get("contract")
    if isinstance(contract, dict):
        return pd.SkillEntry(contract.get("inputs"), contract.get("outputs"))
    return pd.SkillEntry(spec.get("inputSchema"), spec.get("outputSchema"))


def _without_install_workspace(spec: dict[str, Any]) -> dict[str, Any]:
    raw = spec.get("workspaceId")
    if isinstance(raw, str) and raw.startswith("${") and raw.endswith("}"):
        return {k: v for k, v in spec.items() if k != "workspaceId"}
    return spec


def run_package(
    key: str, *, tests: list[str] | None = None, env: dict[str, str] | None = None
) -> dict[str, Any]:
    """PackageTestOut пакета `key`: находки, результаты тестов, покрытие.

    `env` — переменные установки: `${…}` подставляются в текст файлов пакета и его
    `requires`, как у `cp_packages test`; незаданные остаются как есть."""
    d = _domain()
    pd, engine, sandbox = d["pd"], d["engine"], d["sandbox"]
    started = time.monotonic()
    installation = cp.resolve([key])
    target = installation.packages[-1]
    parsed = {package.key: d["parse_package"](_files(package, env or {})) for package in installation.packages}
    own = parsed[target.key]
    problems = list(own.problems)
    chosen, missing = d["select_tests"](own, tests)
    problems.extend(missing)

    objects = [obj for package in parsed.values() for obj in package.objects if obj.kind in _CATALOG_KINDS]
    calendars: dict[str, Any] = {}
    for obj in objects:
        if obj.kind != "Calendar":
            continue
        try:
            calendars[obj.key] = d["Calendar"].from_spec(obj.spec)
        except d["CalendarError"] as exc:
            problems.append(obj.place(pd.Problem("invalid_calendar", "error", "/spec", str(exc))))
    skills = {f"{o.key}@{o.spec.get('version')}": _skill_entry(pd, o.spec) for o in objects if o.kind == "Skill"}
    task_types = {o.key: o.spec.get("fieldSchema") or None for o in objects if o.kind == "TaskType"}
    agents = frozenset(o.key for o in objects if o.kind == "Agent")
    catalog = pd.Catalog(
        skills=skills,
        task_types=task_types,
        agents=agents,
        calendars=frozenset(calendars),
        artifact_types=frozenset(o.key for o in objects if o.kind == "ArtifactType"),
        processes=frozenset(o.key for o in objects if o.kind == "Process"),
    )
    definitions: dict[str, Any] = {}
    for package in parsed.values():
        for obj in package.of_kind("Process"):
            try:
                spec = _without_install_workspace(pd.normalized_spec(obj.spec))
            except pd.SpecError as exc:
                if package is own:
                    problems.append(obj.place(pd.Problem("invalid_document", "error", exc.path, exc.message)))
                continue
            checked = pd.check_process(obj.key, spec, catalog, file=obj.file, locate=obj.locate)
            if package is own:
                problems.extend(checked.problems)
            if not checked.errors:
                definitions[obj.key] = engine.Definition.build(obj.key, spec, catalog)

    results: list[Any] = []
    coverage: list[Any] = []
    if not any(p.error for p in problems):
        world = sandbox.World(
            definitions=definitions,
            skills=skills,
            task_types=task_types,
            agents=agents,
            roles=frozenset(o.key for o in objects if o.kind == "Role"),
            calendars=calendars,
        )
        results = [sandbox.run_test(world, t.file, t.data) for t in chosen]
        coverage = sandbox.package_coverage(
            [definitions[o.key] for o in own.of_kind("Process") if o.key in definitions], results
        )
    problems.sort(key=lambda p: (not p.error, p.file or "", p.line or 0, p.path, p.code))
    status = "invalid" if any(p.error for p in problems) else (
        "failed" if any(r.status != "passed" for r in results) else "passed")
    return {
        "status": status,
        "checkOnly": False,
        "problems": [p.out() for p in problems],
        "tests": [r.out() for r in results],
        "coverage": [c.out() for c in coverage],
        "durationMs": int((time.monotonic() - started) * 1000),
    }


def packages_with_tests() -> list[str]:
    """Ключи пакетов, у которых есть тесты процессов (tests/*.test.yaml)."""
    return sorted(d.name for d in cp.all_package_dirs() if any((d / "tests").glob("*.test.yaml")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("packages", nargs="*", help="ключи пакетов; по умолчанию — все пакеты с тестами")
    parser.add_argument("--test", action="append", help="путь файла теста в пакете (tests/<имя>.test.yaml)")
    parser.add_argument("--json", action="store_true", help="ответы PackageTestOut в JSON")
    parser.add_argument("--env", type=Path, default=ROOT / ".env", help="файл переменных установки")
    args = parser.parse_args(argv)
    env = {**cp.read_env_file(args.env), **os.environ}
    keys = args.packages or packages_with_tests()
    ok = True
    reports = []
    for key in keys:
        try:
            report = run_package(key, tests=args.test, env=env)
        except (CoreMissing, cp.PackageError) as exc:
            print("ошибка:", exc, file=sys.stderr)
            return 2
        reports.append(report)
        ok = ok and report["status"] == "passed"
        if not args.json:
            print(f"== {key} (песочница ядра в процессе, {report['durationMs']} мс)")
            cp.print_test_report(report)
    if args.json:
        print(json.dumps(reports if len(reports) != 1 else reports[0], ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
