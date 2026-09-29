#!/usr/bin/env python3
"""Заполнить пустые секреты в .env случайными значениями (make secrets).

Меняются только переменные из списка SECRET_KEYS, у которых значение пустое;
всё остальное в файле остаётся как есть. Повторный запуск ничего не перезапишет.
Ключ, которого в файле нет (появился в .env.example позже), дописывается.
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

SECRET_KEYS = {
    "CP_POSTGRES_PASSWORD",
    "IAM_POSTGRES_PASSWORD",
    "MEMORY_POSTGRES_PASSWORD",
    "NOTIFY_POSTGRES_PASSWORD",
    "KEYCLOAK_DB_PASSWORD",
    "CP_BOOTSTRAP_TOKEN",
    "IAM_BOOTSTRAP_TOKEN",
    "MEMORY_API_KEY",
    "KEYCLOAK_ADMIN_PASSWORD",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "CP_S3_ACCESS_KEY_ID",
    "CP_S3_SECRET_ACCESS_KEY",
}


def token_for(key: str) -> str:
    # Идентификатор ключа S3 короче: MinIO ограничивает его длину.
    return secrets.token_hex(12 if key.endswith("S3_ACCESS_KEY_ID") else 24)


def main(path: str) -> int:
    env = Path(path)
    lines = env.read_text().splitlines()
    filled: list[str] = []
    for i, line in enumerate(lines):
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in SECRET_KEYS and value.strip() == "":
            lines[i] = f"{key}={token_for(key)}"
            filled.append(key)
    present = {line.split("=", 1)[0].strip() for line in lines if "=" in line and not line.lstrip().startswith("#")}
    for key in sorted(SECRET_KEYS - present):
        lines.append(f"{key}={token_for(key)}")
        filled.append(key)
    env.write_text("\n".join(lines) + "\n")
    env.chmod(0o600)
    print("заполнены секреты:", ", ".join(filled) if filled else "нечего заполнять")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ".env"))
