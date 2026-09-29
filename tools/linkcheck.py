#!/usr/bin/env python3
"""Проверка относительных ссылок в документации umbrella (make linkcheck).

Смотрит *.md в корне, deploy/**/*.md и .github/**/*.md; ссылки на http(s), mailto и
якоря пропускает. Руководство guide/ проверяет сам MkDocs (make guide, режим strict).
Ссылки внутрь сабмодулей проверяются по файловой системе, поэтому сабмодули должны
быть инициализированы (make submodules).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def documents() -> list[Path]:
    files = sorted(ROOT.glob("*.md"))
    for folder in ("deploy", ".github"):
        files += sorted((ROOT / folder).rglob("*.md"))
    return files


def main() -> int:
    files = documents()
    broken = total = 0
    for file in files:
        text = file.read_text(encoding="utf-8")
        for match in LINK.finditer(text):
            link = match.group(1)
            if link.startswith(("http://", "https://", "mailto:", "#")):
                continue
            total += 1
            target = link.split("#")[0]
            if not target:
                continue
            if not (file.parent / target).resolve().exists():
                broken += 1
                line = text[: match.start()].count("\n") + 1
                print(f"BROKEN {file.relative_to(ROOT)}:{line} -> {link}")
    print(f"проверено ссылок: {total} в {len(files)} файлах, битых: {broken}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
