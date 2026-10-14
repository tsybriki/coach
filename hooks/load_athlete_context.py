"""
hooks/load_athlete_context.py — Hermes hook.

Перед каждым запросом подгружает athlete.json + season_plan.json + constraints.json +
last override + last decisions и инжектит в system-prompt как неизменяемое контекстное окно.

Установка в Hermes: ~/.hermes/hooks/load_athlete_context.py (симлинк или копия).
"""
from __future__ import annotations

import json
from pathlib import Path

from hermes_tools import hook  # noqa: F401 — реальный импорт в Phase 2

# Phase 1: пустой stub. Phase 2: реализует чтение + инжект.

COACH_ROOT = Path(__file__).resolve().parent.parent  # /home/tsybriki/coach


def build_context_block() -> str:
    """Собирает блок контекста для system-prompt."""
    files = {
        "athlete": COACH_ROOT / "state/athlete.json",
        "season_plan": COACH_ROOT / "state/season_plan.json",
        "constraints": COACH_ROOT / "state/constraints.json",
        "overrides": COACH_ROOT / "state/overrides.json",
        "season_progress": COACH_ROOT / "state/season_progress.json",
    }
    parts = ["=== COACH CONTEXT (Phase 1 stub) ==="]
    for name, path in files.items():
        if path.exists():
            parts.append(f"--- {name} ({path}) ---")
            parts.append(path.read_text(encoding="utf-8"))
        else:
            parts.append(f"--- {name}: MISSING ---")
    return "\n".join(parts)


if __name__ == "__main__":
    print(build_context_block()[:500])