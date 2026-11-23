"""Eski brend nomlari («Getory», «HitMeow») hech qayerda qolmaganini tekshiradi: kod, matnlar, sozlamalar, fayl nomlari.

Ishga tushirish:  python tests/test_branding.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERN = re.compile(r"get[\s_-]?ory|hit[\s_-]?meow", re.I)
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv"}


def main() -> None:
    bad: list[str] = []
    for path in ROOT.rglob("*"):
        if path.is_dir() or SKIP_DIRS & set(path.relative_to(ROOT).parts) or path.resolve() == Path(__file__).resolve():
            continue
        if PATTERN.search(path.name):
            bad.append(f"fayl nomi: {path.relative_to(ROOT)}")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line):
                bad.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:80]}")
    print(("✅ " if not bad else "❌ ") + "eski brend nomlari («Getory», «HitMeow») hech qayerda qolmagan")
    for b in bad:
        print("   ", b)
    if bad:
        sys.exit(1)


main()
