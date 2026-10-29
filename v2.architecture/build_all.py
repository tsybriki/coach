#!/usr/bin/env python3
"""
build_all.py — пересобрать все артефакты дизайна Coach App.

Запуск:
    python3 v2.architecture/build_all.py

Делает:
  1. logical.json      → LOGICAL.md       (build_logical_md.py)
  2. design/*.md       → DESIGN.md        (build_design_md.py)
  3. logical.json      → LOGICAL.html     (render_logical.py)
  4. design/*.md       → DESIGN.html      (render_design.py)
  5. синхронизация MD в ~/projects/coach-app/ рядом с местом реализации
  6. проверка утечек знания о физическом хранилище (check_storage_leaks.py)

Порядок важен: MD собираются первыми, HTML — из тех же источников, копии — последними,
чтобы разъезда не было.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.expanduser("~/projects/coach-app")

STEPS = [
    ("MD логического уровня", "build_logical_md.py"),
    ("MD дизайна", "build_design_md.py"),
    ("HTML логического уровня", "render_logical.py"),
    ("HTML дизайна", "render_design.py"),
]


def run(script: str) -> bool:
    r = subprocess.run([sys.executable, os.path.join(HERE, script)],
                       capture_output=True, text=True)
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if out:
        print(out)
    if r.returncode != 0:
        print(f"  ОШИБКА в {script}:\n{err}")
        return False
    return True


def sync() -> bool:
    """Скопировать MD-артефакты рядом с реализацией."""
    if not os.path.isdir(TARGET):
        print(f"  пропуск: {TARGET} не существует")
        return True
    dst_design = os.path.join(TARGET, "design")
    os.makedirs(dst_design, exist_ok=True)
    for fn in sorted(os.listdir(os.path.join(HERE, "design"))):
        if fn.endswith(".md"):
            shutil.copy2(os.path.join(HERE, "design", fn), os.path.join(dst_design, fn))
    for fn in ("LOGICAL.md", "DESIGN.md"):
        src = os.path.join(HERE, fn)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(TARGET, fn))
    print(f"  синхронизировано в {TARGET}")
    return True


def main() -> int:
    print("== сборка артефактов ==")
    for label, script in STEPS:
        print(f"-- {label}")
        if not run(script):
            return 1

    print("-- синхронизация в projects/coach-app")
    if not sync():
        return 1

    print("-- проверка утечек")
    r = subprocess.run([sys.executable, os.path.join(HERE, "check_storage_leaks.py")],
                       capture_output=True, text=True)
    print((r.stdout or "").strip())
    if r.returncode != 0:
        print((r.stderr or "").strip())
        return 1

    print("\nготово")
    return 0


if __name__ == "__main__":
    sys.exit(main())
