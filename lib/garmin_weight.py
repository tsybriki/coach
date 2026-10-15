"""
garmin_weight.py — синк веса из Garmin (плюс Renpho→Garmin через garmin_tools).

Phase 2: тонкая обёртка над ~/projects/garmin_tools/.
  - sync_from_garmin() — читает последний вес напрямую из garmin_tools (там уже есть синк Renpho).
    Если хочется чистый Garmin (без Renpho) — garmin_tools/main_garmin_only.py.
  - manual_weight() — локальная запись (без внешних вызовов).
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

GARMIN_TOOLS = Path(os.environ.get("GARMIN_TOOLS_PATH", str(Path.home() / "projects" / "garmin_tools")))
GARMIN_TOOLS_VENV_PYTHON = GARMIN_TOOLS / ".venv" / "bin" / "python"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_garmin_tools_script(script_name: str, *args: str) -> dict | None:
    """Универсальный вызов скрипта из garmin_tools с JSON stdout."""
    script = GARMIN_TOOLS / script_name
    if not (script.exists() and GARMIN_TOOLS_VENV_PYTHON.exists()):
        return None
    try:
        result = subprocess.run(
            [str(GARMIN_TOOLS_VENV_PYTHON), str(script), *args, "--json"],
            capture_output=True, text=True, timeout=120,
            cwd=str(GARMIN_TOOLS),
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def sync_from_garmin(athlete_path: str | Path = "state/athlete.json") -> dict:
    """
    Phase 2: дёргает garmin_tools (там Renpho→Garmin sync).
    Возвращает {synced, kg, date, reason}.
    """
    # Сначала запускаем main.py (Renpho sync в Garmin Connect)
    sync_result = _run_garmin_tools_script("main.py")

    # Затем читаем последний вес из Garmin через running_pull.py или прямой read
    # (Phase 2: упрощение — читаем из state/athlete.json напрямую если есть
    #  отдельный sync_state. Phase 3: реализовать читалку из Garmin Connect API)
    out = {"synced": False, "kg": None, "date": None, "reason": "phase 2.3 stub"}

    if sync_result and sync_result.get("ok"):
        out["synced"] = True
        out["kg"] = sync_result.get("weight_kg")
        out["date"] = sync_result.get("date")
        out["reason"] = "via garmin_tools/main.py"

        if out["kg"] and athlete_path and Path(athlete_path).exists():
            athlete = json.loads(Path(athlete_path).read_text(encoding="utf-8"))
            athlete.setdefault("weight_history", [])
            athlete["weight_history"].append({
                "date": out["date"], "kg": out["kg"], "source": "renpho_via_garmin",
            })
            athlete["weight_history"].sort(key=lambda x: x["date"])
            athlete["weight_kg_current"] = out["kg"]
            Path(athlete_path).write_text(
                json.dumps(athlete, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    return out


def manual_weight(athlete_path: str | Path, kg: float, date: str | None = None) -> dict:
    """Записать вес вручную (команда 'я взвесился — X кг'). Без внешних вызовов."""
    athlete_path = Path(athlete_path)
    if not athlete_path.exists():
        raise FileNotFoundError(athlete_path)
    a = json.loads(athlete_path.read_text(encoding="utf-8"))
    if date is None:
        date = datetime.now(timezone.utc).date().isoformat()
    a.setdefault("weight_history", [])
    a["weight_history"].append({"date": date, "kg": kg, "source": "manual"})
    a["weight_history"].sort(key=lambda x: x["date"])
    a["weight_kg_current"] = kg
    athlete_path.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"logged": True, "kg": kg, "date": date}
