"""
zwift_sync.py — тонкая обёртка над garmin_tools/zwift_sync.py.

URL → workout JSON → Garmin Connect.
Используется skill coach-plan-zwift после выбора candidate Кириллом.

Phase 2: subprocess в garmin_tools.
Phase 3: прямой import.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .zwift_search import search

GARMIN_TOOLS = Path(os.environ.get("GARMIN_TOOLS_PATH", str(Path.home() / "projects" / "garmin_tools")))
GARMIN_TOOLS_VENV_PYTHON = GARMIN_TOOLS / ".venv" / "bin" / "python"


def sync_to_garmin(whats_on_zwift_url: str,
                   workout_name: str | None = None,
                   athlete_path: str | Path = "state/athlete.json") -> dict:
    """
    Берёт WhatsOnZwift URL, дёргает garmin_tools/zwift_sync.py → Garmin Connect workout.
    Возвращает {workout_id, name, scheduled?}.
    """
    script = GARMIN_TOOLS / "zwift_sync.py"
    if not (script.exists() and GARMIN_TOOLS_VENV_PYTHON.exists()):
        return {"synced": False, "reason": "garmin_tools unavailable", "url": whats_on_zwift_url}

    args = [str(GARMIN_TOOLS_VENV_PYTHON), str(script), "--url", whats_on_zwift_url, "--json"]
    if workout_name:
        args += ["--name", workout_name]

    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=180,
            cwd=str(GARMIN_TOOLS),
        )
        if result.returncode != 0:
            return {"synced": False, "reason": f"exit={result.returncode}", "stderr": result.stderr[:200]}
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        return {"synced": False, "reason": str(e)}


if __name__ == "__main__":
    # Демо: дёрнем первый попавшийся workout
    cands = search({"discipline": "cycling", "duration_min": 45, "duration_tolerance": 10})
    if cands:
        first = cands[0]
        print(f"first candidate: {first['title']}")
        print(f"  url: {first['url']}")
        result = sync_to_garmin(first["url"], workout_name=first["title"][:60])
        print(f"  sync result: {result}")
    else:
        print("no candidates")