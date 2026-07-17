#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Гейт против НОВЫХ «слепых» except (L13 аудита).

Зачем diff-scoped: в src/ уже ~53 голых `except`/`except Exception`, часть из
них легитимна (best-effort cleanup при shutdown, необязательный кэш). Массовая
переписка = churn с риском регресса, а «починим когда-нибудь» = не чинится
никогда. Поэтому проверяем ТОЛЬКО добавленные строки в диффе: легаси не мешает,
новый код не протаскивает молчаливое проглатывание ошибок.

flake8 тут не помощник: его E722 ловит лишь `except:`, а подавляющее
большинство случаев — `except Exception:` (в ruff это BLE001, но тащить второй
линтер ради одного правила избыточно).

Что считается нарушением: добавленная строка вида `except:` или
`except Exception[ as e]:` — КРОМЕ случаев, когда:
  * на строке есть `# noqa: BLE001` (осознанное исключение с объяснением рядом);
  * в теле обработчика есть re-raise (`raise`) или логирование
    (`logger.` / `logging.`) — то есть ошибка не проглатывается молча.

Запуск:
    python scripts/check_blind_except.py [--base origin/main]
Выход: 0 — чисто; 1 — найдены новые слепые except.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

BLIND_RE = re.compile(r"^\+\s*except\s*(Exception\s*(as\s+\w+\s*)?)?:\s*(#.*)?$")
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")
# «Ошибка не проглочена»: в теле есть re-raise или логирование.
HANDLED_RE = re.compile(r"\braise\b|logger\.|logging\.")


def changed_python_lines(base: str) -> list[tuple[str, int, str, list[str]]]:
    """[(file, lineno, added_line, following_added_lines)] по добавленным строкам .py."""
    diff = subprocess.run(
        ["git", "diff", "--unified=3", f"{base}...HEAD", "--", "*.py"],
        capture_output=True, text=True, check=False,
    ).stdout
    out: list[tuple[str, int, str, list[str]]] = []
    cur_file = ""
    lineno = 0
    lines = diff.splitlines()
    for i, line in enumerate(lines):
        m_file = FILE_RE.match(line)
        if m_file:
            cur_file = m_file.group(1)
            continue
        m_hunk = HUNK_RE.match(line)
        if m_hunk:
            lineno = int(m_hunk.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            # контекст обработчика: несколько последующих строк диффа
            body = [l[1:] for l in lines[i + 1: i + 7] if l[:1] in "+ "]
            out.append((cur_file, lineno, line, body))
            lineno += 1
        elif line.startswith(" "):
            lineno += 1
        # строки с '-' не увеличивают номер в новой версии
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main", help="база для диффа")
    args = ap.parse_args()

    violations: list[str] = []
    for path, lineno, line, body in changed_python_lines(args.base):
        if not BLIND_RE.match(line):
            continue
        if "noqa: BLE001" in line:
            continue
        if any(HANDLED_RE.search(b) for b in body):
            continue  # ошибка логируется или пробрасывается — не «слепой»
        violations.append(f"  {path}:{lineno}: {line[1:].strip()}")

    if violations:
        print("❌ Новые «слепые» except (ошибка проглатывается молча):\n")
        print("\n".join(violations))
        print(
            "\nЧто сделать (любое из):\n"
            "  • ловить конкретное исключение: `except ValueError:`\n"
            "  • залогировать: `logger.warning(...)` в теле\n"
            "  • пробросить дальше: `raise`\n"
            "  • если проглатывание осознанно — `except Exception:  # noqa: BLE001`\n"
            "    и комментарий рядом, ПОЧЕМУ ошибка тут не важна.\n"
            "\nПроверка diff-scoped: легаси-код не трогаем, гейт только для нового."
        )
        return 1

    print("✅ Новых «слепых» except не добавлено")
    return 0


if __name__ == "__main__":
    sys.exit(main())
