#!/usr/bin/env python3
"""oss-check: is a repository revision publishable?

Every Taimen repository (a component or the umbrella) is published only from a
revision that passed this check. The script inspects one repository at one ref:

1. **gitleaks** over the history reachable from the ref, with the repository's
   own ``.gitleaks.toml`` / ``.gitleaksignore``;
2. **stop-list** over tracked files (paths and contents): built-in rules
   (``docs/prompts/``) plus private patterns — client names, internal hosts —
   that are never committed to a public repository. They come from
   ``--stoplist FILE`` (repeatable), ``$OSS_CHECK_STOPLIST_FILE`` or the
   ``$OSS_CHECK_STOPLIST`` variable (one regex per line; a CI secret).
   Attribution is exempt, and only it: ``Copyright …`` in NOTICE / LICENSE /
   COPYING, the trademark-owner line of ``TRADEMARK.md``, ``authors = …`` of
   ``pyproject.toml``, the copyright-holder line of a CLA and the ``## Author``
   section of a README legitimately name the owner;
3. **no Cyrillic in English documents**. Which documents are English depends on
   the primary language of the repository: ``--lang``, else the first word of the
   ``.oss-language`` file at the ref (``en`` or ``ru``), else ``en``.

   - ``en`` (components): a ``*.md`` that has a ``*.ru.md`` sibling or starts with
     the ``*English.`` marker line;
   - ``ru`` (a repository written in Russian with short English companions): every
     ``*.en.md`` and every ``*.md`` that starts with the ``*English.`` marker line;
     Russian documents are not checked;
4. **licence kit**: ``LICENSE``, ``NOTICE``, ``THIRD_PARTY.md`` at the root and
   ``license = "Apache-2.0"`` in every tracked ``pyproject.toml``.

Usage::

    python tools/oss_check.py <repo-path> [--ref REF] [--stoplist FILE] [--lang en|ru]
                              [--skip-gitleaks] [--json]

Exit code 0 means publishable; 1 lists every finding; 2 is a usage error.
``--json`` prints one object ``{repo, ref, sha, ok, lang, gitleaks, findings}`` where a
finding is ``{check, path, line, rule, message}``: locations and rule numbers
only, never the matched text (the stop-list is private).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

BUILTIN_PATH_RULES = (re.compile(r"(^|/)docs/prompts/"),)
REQUIRED_FILES = ("LICENSE", "NOTICE", "THIRD_PARTY.md")
LICENSE_ID = "Apache-2.0"
EN_MARKER = re.compile(r"^\s*\*English\.")
CYRILLIC = re.compile(r"[\u0400-\u04FF]")
LANGUAGES = ("en", "ru")
LANGUAGE_FILE = ".oss-language"
MAX_TEXT_BYTES = 2_000_000
# Lines that legitimately name the owner: (file name predicate, line pattern).
ATTRIBUTION_RULES = (
    (re.compile(r"^(NOTICE|LICENSE|COPYING)(\.[A-Za-z]+)?$"), re.compile(r"\bCopyright\b")),
    (re.compile(r"^TRADEMARK\.md$"), re.compile(r"\btrademarks? of\b", re.IGNORECASE)),
    (re.compile(r"^pyproject\.toml$"), re.compile(r"^\s*authors\s*=")),
    (re.compile(r"^CLA[-\w]*\.md$"), re.compile(r"\bcopyright is held by\b", re.IGNORECASE)),
)
# The author section of a README (``## Author`` / ``## Автор``): every line of it.
README = re.compile(r"^README(\.[a-z]{2})?\.md$")
AUTHOR_HEADING = re.compile(r"^##\s+(Author|Authors|Автор|Авторы)\s*$")


@dataclass
class Finding:
    check: str
    message: str
    path: str | None = None
    line: int | None = None
    rule: int | None = None

    def as_json(self) -> dict[str, object]:
        return {"check": self.check, "path": self.path, "line": self.line, "rule": self.rule, "message": self.message}


@dataclass
class Report:
    items: list[Finding] = field(default_factory=list)

    def add(
        self, check: str, message: str, *, path: str | None = None, line: int | None = None, rule: int | None = None
    ) -> None:
        self.items.append(Finding(check, message, path, line, rule))

    @property
    def findings(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for item in self.items:
            grouped.setdefault(item.check, []).append(item.message)
        return grouped

    @property
    def ok(self) -> bool:
        return not self.items


def is_attribution(path: str, line: str) -> bool:
    """An attribution line of the owner: exempt from the stop-list, nothing else is."""
    name = Path(path).name
    return any(file.match(name) and pattern.search(line) for file, pattern in ATTRIBUTION_RULES)


def author_section(path: str, lines: list[str]) -> set[int]:
    """Line numbers of the author section of a README, up to the next heading."""
    if not README.match(Path(path).name):
        return set()
    numbers: set[int] = set()
    inside = False
    for number, line in enumerate(lines, 1):
        if line.startswith("#"):
            inside = bool(AUTHOR_HEADING.match(line))
        elif inside:
            numbers.add(number)
    return numbers


def tracked(repo: Path, ref: str, *, recursive: bool = True) -> list[str]:
    """Tracked paths at the ref (NUL-separated, so non-ASCII names stay unquoted)."""
    args = ["ls-tree", "-z", *(["-r"] if recursive else []), ref]
    paths = []
    for entry in git(repo, *args).split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        # Files only: submodule gitlinks (commit) are other repositories, checked on their own.
        if meta.split()[1] == "blob" or not recursive:
            paths.append(path)
    return paths


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def blob(repo: Path, ref: str, path: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True, check=True).stdout


def text_of(data: bytes) -> str | None:
    if len(data) > MAX_TEXT_BYTES or b"\0" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def load_stoplist(files: list[str]) -> list[re.Pattern[str]]:
    lines: list[str] = []
    env_file = os.environ.get("OSS_CHECK_STOPLIST_FILE")
    for name in [*files, *([env_file] if env_file else [])]:
        lines += Path(name).read_text(encoding="utf-8").splitlines()
    lines += os.environ.get("OSS_CHECK_STOPLIST", "").splitlines()
    patterns = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(re.compile(line, re.IGNORECASE))
    return patterns


def check_gitleaks(repo: Path, ref: str, report: Report) -> None:
    binary = shutil.which("gitleaks")
    if binary is None:
        report.add("gitleaks", "gitleaks is not installed (use --skip-gitleaks only locally)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.json"
        cmd = [
            binary,
            "git",
            str(repo),
            f"--log-opts={ref}",
            "--no-banner",
            "--redact",
            "--exit-code",
            "0",
            "--report-format",
            "json",
            "--report-path",
            str(out),
        ]
        # Config and ignore file of the checked revision, not of the working tree: a
        # clone without checkout has none, and a checkout may be at another commit.
        for name, flag in ((".gitleaks.toml", "--config"), (".gitleaksignore", "--gitleaks-ignore-path")):
            try:
                content = blob(repo, ref, name)
            except subprocess.CalledProcessError:
                continue
            target = Path(tmp) / name
            target.write_bytes(content)
            cmd += [flag, str(target)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not out.exists():
            report.add("gitleaks", f"gitleaks failed: {result.stderr.strip()[-300:]}")
            return
        leaks = json.loads(out.read_text() or "[]")
    for leak in leaks:
        report.add(
            "gitleaks",
            f"{leak.get('RuleID')}: {leak.get('File')}:{leak.get('StartLine')} "
            f"(commit {str(leak.get('Commit'))[:10]}, fingerprint {leak.get('Fingerprint')})",
            path=leak.get("File"),
            line=leak.get("StartLine"),
        )


def repository_language(repo: Path, ref: str, override: str | None) -> str:
    """Primary language of the documents: --lang, else .oss-language at the ref, else en."""
    if override:
        return override
    try:
        words = blob(repo, ref, LANGUAGE_FILE).decode("utf-8", errors="replace").split()
    except subprocess.CalledProcessError:
        return "en"
    language = words[0].lower() if words else "en"
    if language not in LANGUAGES:
        raise ValueError(f"{LANGUAGE_FILE}: unknown language {language!r}, expected one of {LANGUAGES}")
    return language


def is_english_document(path: str, head: list[str], known: set[str], language: str) -> bool:
    """Should this Markdown file be free of Cyrillic?"""
    if not path.endswith(".md"):
        return False
    marked = any(EN_MARKER.match(line) for line in head)
    if language == "ru":
        return path.endswith(".en.md") or marked
    if path.endswith(".ru.md"):
        return False
    return path[: -len(".md")] + ".ru.md" in known or marked


def check_tree(repo: Path, ref: str, stoplist: list[re.Pattern[str]], report: Report, language: str = "en") -> None:
    paths = tracked(repo, ref)
    known = set(paths)
    for path in paths:
        for rule in BUILTIN_PATH_RULES:
            if rule.search(path):
                report.add("stop-list", f"{path}: private path ({rule.pattern})")
        for index, pattern in enumerate(stoplist, 1):
            if pattern.search(path):
                report.add("stop-list", f"{path}: path matches private pattern #{index}", path=path, rule=index)
        content = text_of(blob(repo, ref, path))
        if content is None:
            continue
        lines = content.splitlines()
        author = author_section(path, lines)
        for index, pattern in enumerate(stoplist, 1):
            for number, line in enumerate(lines, 1):
                if pattern.search(line) and not is_attribution(path, line) and number not in author:
                    # The pattern itself is private: report the location and its number only.
                    report.add(
                        "stop-list",
                        f"{path}:{number}: matches private pattern #{index}",
                        path=path,
                        line=number,
                        rule=index,
                    )
        if is_english_document(path, lines[:5], known, language):
            for number, line in enumerate(lines, 1):
                if CYRILLIC.search(line):
                    report.add(
                        "english-docs", f"{path}:{number}: Cyrillic in an English document", path=path, line=number
                    )


def check_licence(repo: Path, ref: str, report: Report) -> None:
    root = set(tracked(repo, ref, recursive=False))
    for name in REQUIRED_FILES:
        if name not in root:
            report.add("licence", f"{name} is missing at the repository root", path=name)
    for path in tracked(repo, ref):
        if Path(path).name != "pyproject.toml":
            continue
        project = tomllib.loads(blob(repo, ref, path).decode()).get("project", {})
        value = project.get("license")
        if isinstance(value, dict):
            value = value.get("text") or value.get("file")
        if value != LICENSE_ID:
            report.add("licence", f"{path}: project.license is {value!r}, expected {LICENSE_ID!r}", path=path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", type=Path)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--stoplist", action="append", default=[], help="file with private patterns")
    parser.add_argument(
        "--lang",
        choices=LANGUAGES,
        default=None,
        help=f"primary language of the documents (default: {LANGUAGE_FILE} at the ref, else en)",
    )
    parser.add_argument("--skip-gitleaks", action="store_true")
    parser.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        git(repo, "rev-parse", "--verify", f"{args.ref}^{{commit}}")
    except RuntimeError as exc:
        print(f"oss-check: {exc}", file=sys.stderr)
        return 2
    stoplist = load_stoplist(args.stoplist)
    try:
        language = repository_language(repo, args.ref, args.lang)
    except ValueError as exc:
        print(f"oss-check: {exc}", file=sys.stderr)
        return 2
    report = Report()
    if not args.skip_gitleaks:
        check_gitleaks(repo, args.ref, report)
    check_tree(repo, args.ref, stoplist, report, language)
    check_licence(repo, args.ref, report)
    if args.json:
        sha = git(repo, "rev-parse", args.ref).strip()
        print(
            json.dumps(
                {
                    "repo": repo.name,
                    "ref": args.ref,
                    "sha": sha,
                    "ok": report.ok,
                    "lang": language,
                    "gitleaks": not args.skip_gitleaks,
                    "stoplistPatterns": len(stoplist),
                    "findings": [item.as_json() for item in report.items],
                },
                ensure_ascii=False,
            )
        )
        return 0 if report.ok else 1
    sha = git(repo, "rev-parse", "--short", args.ref).strip()
    title = f"oss-check {repo.name}@{sha} (language: {language}, stop-list: {len(stoplist)} private patterns"
    title += ", gitleaks skipped)" if args.skip_gitleaks else ")"
    print(title)
    if report.ok:
        print("  OK: publishable")
        return 0
    for check, messages in report.findings.items():
        print(f"  {check}: {len(messages)} finding(s)")
        for message in messages[:50]:
            print(f"    - {message}")
        if len(messages) > 50:
            print(f"    … and {len(messages) - 50} more")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
