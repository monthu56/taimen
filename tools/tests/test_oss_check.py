"""oss-check: attribution lines, private stop-list, document language, machine output.

python3 -m pytest -q tools/tests
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import oss_check  # noqa: E402

OWNER = "Jane Maintainer"
STOPLIST = "Jane Maintainer\nsecret-client\n"
APACHE = "Licensed under the Apache License, Version 2.0.\n"


def make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "component"
    repo.mkdir()
    base = {
        "LICENSE": APACHE + f"   Copyright 2026 {OWNER} and contributors\n",
        "NOTICE": f"Component\nCopyright 2026 {OWNER} and contributors\n",
        "THIRD_PARTY.md": "none\n",
        "TRADEMARK.md": f'"Name" is a trademark of {OWNER} ("the owner").\n',
        "pyproject.toml": f'[project]\nname = "c"\nlicense = {{ text = "Apache-2.0" }}\n'
        f'authors = [{{ name = "{OWNER}" }}]\n',
    }
    for path, text in {**base, **files}.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    for args in (
        ["init", "-q", "-b", "main"],
        ["add", "-A"],
        ["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "c"],
    ):
        subprocess.run(["git", "-C", str(repo), *args], check=True)
    return repo


def run(repo: Path, tmp_path: Path, *extra: str) -> tuple[int, str]:
    stoplist = tmp_path / "stoplist.txt"
    stoplist.write_text(STOPLIST, encoding="utf-8")
    code = oss_check.main([str(repo), "--skip-gitleaks", "--stoplist", str(stoplist), *extra])
    return code, ""


def test_attribution_lines_are_publishable(tmp_path, capsys):
    repo = make_repo(
        tmp_path,
        {
            "cla/CLA-individual.md": f"Taimen, whose copyright is held by {OWNER} (the owner).\n",
            "README.md": f"# C\n\n## Author\n\n{OWNER} — architecture and code.\n\n## Licence\n\nApache-2.0\n",
        },
    )
    code, _ = run(repo, tmp_path)
    assert code == 0, capsys.readouterr().out


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("docs/guide.md", f"Ask {OWNER} to publish the demo.\n"),
        ("NOTICE", f"Component\nCopyright 2026 {OWNER}\nMaintained by {OWNER}\n"),  # not a copyright line
        ("TRADEMARK.md", f"Contact {OWNER} for permission.\n"),
        ("pyproject.toml", f'[project]\nname = "c"\nlicense = {{ text = "Apache-2.0" }}\ndescription = "by {OWNER}"\n'),
        ("tests/test_x.py", 'CLIENT = "secret-client"\n'),
        ("README.md", f"# C\n\n## Author\n\nme\n\n## Support\n\nWrite to {OWNER}.\n"),  # after the section
        ("cla/CLA-individual.md", f"Send the form to {OWNER}.\n"),
    ],
)
def test_the_stop_list_still_catches_everything_else(tmp_path, capsys, path, text):
    repo = make_repo(tmp_path, {path: text})
    code, _ = run(repo, tmp_path)
    out = capsys.readouterr().out
    assert code == 1
    assert f"{path}:" in out and "private pattern #" in out


def test_json_names_locations_and_rules_but_never_the_match(tmp_path, capsys):
    repo = make_repo(tmp_path, {"docs/guide.md": "Deployed for secret-client.\n", "README.md": "*English.*\nПривет\n"})
    code, _ = run(repo, tmp_path, "--json")
    out = capsys.readouterr().out
    report = json.loads(out)
    assert code == 1 and report["ok"] is False and report["gitleaks"] is False
    stop = next(f for f in report["findings"] if f["check"] == "stop-list")
    assert {k: stop[k] for k in ("path", "line", "rule")} == {"path": "docs/guide.md", "line": 1, "rule": 2}
    assert any(f["check"] == "english-docs" and f["line"] == 2 for f in report["findings"])
    assert "secret-client" not in out and OWNER not in out


def english_findings(tmp_path: Path, capsys, files: dict[str, str], *extra: str) -> tuple[str, set]:
    repo = make_repo(tmp_path, files)
    run(repo, tmp_path, "--json", *extra)
    report = json.loads(capsys.readouterr().out)
    return report["lang"], {f["path"] for f in report["findings"] if f["check"] == "english-docs"}


RUSSIAN = "Привет\n"


def test_default_language_is_english_and_ru_siblings_mark_english_documents(tmp_path, capsys):
    lang, paths = english_findings(
        tmp_path,
        capsys,
        {
            "README.md": RUSSIAN,
            "README.ru.md": RUSSIAN,
            "docs/notes.md": RUSSIAN,
        },
    )
    assert lang == "en" and paths == {"README.md"}


def test_english_readme_with_a_russian_twin_is_publishable(tmp_path, capsys):
    lang, paths = english_findings(
        tmp_path,
        capsys,
        {
            ".oss-language": "en\n",
            "README.md": "# C\n\n*Russian version: [README.ru.md](README.ru.md)*\n",
            "README.ru.md": "# C\n\n*English version: [README.md](README.md)*\n" + RUSSIAN,
            "CONTRIBUTING.md": "# Contributing\n",
        },
    )
    assert lang == "en" and paths == set()


def test_russian_repository_checks_only_en_companions(tmp_path, capsys):
    lang, paths = english_findings(
        tmp_path,
        capsys,
        {
            ".oss-language": "ru\n",
            "README.md": RUSSIAN,
            "README.en.md": RUSSIAN,
            "CONTRIBUTING.md": RUSSIAN,
            "docs/intro.md": "*English.*\n" + RUSSIAN,
        },
    )
    assert lang == "ru" and paths == {"README.en.md", "docs/intro.md"}


def test_lang_flag_overrides_the_language_file(tmp_path, capsys):
    lang, paths = english_findings(
        tmp_path,
        capsys,
        {
            ".oss-language": "ru\n",
            "README.md": RUSSIAN,
            "README.ru.md": RUSSIAN,
        },
        "--lang",
        "en",
    )
    assert lang == "en" and paths == {"README.md"}


def test_unknown_language_is_a_usage_error(tmp_path, capsys):
    repo = make_repo(tmp_path, {".oss-language": "de\n"})
    code, _ = run(repo, tmp_path)
    assert code == 2 and ".oss-language" in capsys.readouterr().err


def test_missing_licence_kit_is_a_finding(tmp_path, capsys):
    repo = make_repo(tmp_path, {})
    subprocess.run(["git", "-C", str(repo), "rm", "-q", "NOTICE"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "rm"],
        check=True,
    )
    code, _ = run(repo, tmp_path, "--json")
    report = json.loads(capsys.readouterr().out)
    assert code == 1 and report["findings"] == [
        {
            "check": "licence",
            "path": "NOTICE",
            "line": None,
            "rule": None,
            "message": "NOTICE is missing at the repository root",
        }
    ]


GITLEAKS_ALLOWLIST = """[extend]
useDefault = true
[[allowlists]]
paths = ['''^tests/test_redaction\\.py$''']
"""


def run_full(repo: Path, tmp_path: Path) -> int:
    stoplist = tmp_path / "stoplist.txt"
    stoplist.write_text(STOPLIST, encoding="utf-8")
    return oss_check.main([str(repo), "--stoplist", str(stoplist)])


@pytest.mark.skipif(shutil.which("gitleaks") is None, reason="gitleaks is not installed")
def test_gitleaks_uses_the_allowlist_of_the_checked_revision(tmp_path, capsys):
    fixture = 'SAMPLE = "AKIA' + "Z7VRSQ5TJN2XGLHP" + '"\n'  # AWS-shaped test input, not a secret
    repo = make_repo(tmp_path, {"tests/test_redaction.py": fixture})
    assert run_full(repo, tmp_path) == 1
    assert "aws-access-token" in capsys.readouterr().out

    (repo / ".gitleaks.toml").write_text(GITLEAKS_ALLOWLIST, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "commit",
            "-q",
            "-m",
            "allowlist",
        ],
        check=True,
    )
    # the working tree loses the file: only the revision may be the source of the config
    (repo / ".gitleaks.toml").unlink()
    assert run_full(repo, tmp_path) == 0, capsys.readouterr().out
