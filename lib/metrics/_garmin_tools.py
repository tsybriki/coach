"""
_garmin_tools.py — общая утилита для метрик.
Метрика может вызвать latest_analyse.py если FIT на диске,
либо использовать готовый fit_dict (стабильная схема parse_fit.py).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

GARMIN_TOOLS = Path(os.environ.get("GARMIN_TOOLS_PATH", str(Path.home() / "projects" / "garmin_tools")))
GARMIN_TOOLS_VENV_PYTHON = GARMIN_TOOLS / ".venv" / "bin" / "python"


def analyse_fit_local(fit_path: str | Path) -> dict | None:
    """Вызывает garmin_tools/latest_analyse.py для FIT на диске."""
    script = GARMIN_TOOLS / "latest_analyse.py"
    if not (script.exists() and GARMIN_TOOLS_VENV_PYTHON.exists()):
        return None
    try:
        result = subprocess.run(
            [str(GARMIN_TOOLS_VENV_PYTHON), str(script), "--json", str(fit_path)],
            capture_output=True, text=True, timeout=120,
            cwd=str(GARMIN_TOOLS),
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def garmin_tools_available() -> bool:
    return (GARMIN_TOOLS / "latest_analyse.py").exists() and GARMIN_TOOLS_VENV_PYTHON.exists()
