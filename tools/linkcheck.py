#!/usr/bin/env python3
"""Check relative links in the umbrella documentation (make linkcheck).

Looks at *.md at the root, deploy/**/*.md and .github/**/*.md; skips http(s), mailto and
anchor links. The guide guide/ is checked by MkDocs itself (make guide, strict mode).
Links into submodules are checked against the file system, so the submodules must
be initialized (make submodules).
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
    print(f"links checked: {total} in {len(files)} files, broken: {broken}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
