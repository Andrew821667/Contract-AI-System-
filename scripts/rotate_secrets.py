#!/usr/bin/env python3
"""
Secret Rotation Helper (C1/C2)

Generates new cryptographic secrets and prints the .env lines to set.
Run this script, then update your .env file with the output.

Usage:
    python3 scripts/rotate_secrets.py
    python3 scripts/rotate_secrets.py --apply   # writes to .env directly
"""
import secrets
import argparse
import os
import re
from pathlib import Path


def generate_secret_key(length: int = 64) -> str:
    return secrets.token_urlsafe(length)


def generate_signing_key(length: int = 32) -> str:
    return secrets.token_hex(length)


def main():
    parser = argparse.ArgumentParser(description="Rotate application secrets")
    parser.add_argument("--apply", action="store_true",
                        help="Apply changes directly to .env file")
    args = parser.parse_args()

    new_secrets = {
        "SECRET_KEY": generate_secret_key(64),
        "DOCUMENT_SIGNING_KEY": generate_signing_key(32),
    }

    print("=" * 60)
    print("  Secret Rotation — новые значения")
    print("=" * 60)
    print()
    for key, value in new_secrets.items():
        print(f"{key}={value}")
    print()

    if args.apply:
        env_path = Path(__file__).parent.parent / ".env"
        if not env_path.exists():
            # Create .env from the generated secrets
            with open(env_path, "a") as f:
                for key, value in new_secrets.items():
                    f.write(f"{key}={value}\n")
            print(f"Добавлено в {env_path}")
        else:
            content = env_path.read_text()
            for key, value in new_secrets.items():
                pattern = rf"^{re.escape(key)}=.*$"
                if re.search(pattern, content, re.MULTILINE):
                    content = re.sub(pattern, f"{key}={value}", content, flags=re.MULTILINE)
                else:
                    content += f"\n{key}={value}\n"
            env_path.write_text(content)
            print(f"Обновлено в {env_path}")
    else:
        print("Добавьте эти значения в .env файл.")
        print("Или запустите с --apply для автоматического обновления.")
    print()
    print("⚠️  После ротации SECRET_KEY все текущие JWT-сессии станут невалидными.")
    print("⚠️  После ротации DOCUMENT_SIGNING_KEY верификация старых подписей сломается.")
    print("    Планируйте ротацию в окне обслуживания.")


if __name__ == "__main__":
    main()
