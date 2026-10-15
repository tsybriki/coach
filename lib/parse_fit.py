"""
parse_fit.py — FIT → dict по стабильной схеме.

Phase 2: тонкая обёртка над ~/projects/garmin_tools/fit_inspect.py.
Не дублирует логику, а вызывает реальный парсер через subprocess
(garmin_tools имеет свой .venv с Python 3.14, общий с ~/coach).

Если ~/projects/garmin_tools/ недоступен — fallback на локальный stub.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

# Путь к garmin_tools — overridable через ENV
GARMIN_TOOLS = Path(os.environ.get("GARMIN_TOOLS_PATH", str(Path.home() / "projects" / "garmin_tools")))
GARMIN_TOOLS_VENV_PYTHON = GARMIN_TOOLS / ".venv" / "bin" / "python"


STABLE_SCHEMA_KEYS = [
    "fit_id", "date", "type", "source", "distance_km", "duration_min",
    "avg_pace_min_per_km", "avg_hr", "max_hr", "min_hr", "cadence_avg",
    "stride_cm", "steps", "elevation_gain_m", "elevation_loss_m",
    "temperature_avg_c", "calories", "training_effect", "splits",
    "recovery_hr_drop", "hr_drift_bpm", "file_hash",
]


def _garmin_tools_available() -> bool:
    return (GARMIN_TOOLS / "fit_inspect.py").exists() and GARMIN_TOOLS_VENV_PYTHON.exists()


def _parse_via_garmin_tools(fit_path: Path) -> dict | None:
    """Вызывает fit_inspect.py с subcommand 'json', парсит JSON stdout."""
    if not _garmin_tools_available():
        return None
    try:
        result = subprocess.run(
            [str(GARMIN_TOOLS_VENV_PYTHON), str(GARMIN_TOOLS / "fit_inspect.py"),
             "json", str(fit_path)],
            capture_output=True, text=True, timeout=60,
            cwd=str(GARMIN_TOOLS),
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def _parse_stub(fit_path: Path) -> dict:
    """Fallback: минимальный dict на основе имени файла."""
    digest = hashlib.sha256(fit_path.read_bytes()).hexdigest()
    name = fit_path.stem
    date = name[:10] if len(name) >= 10 else "1970-01-01"
    typ = "running"
    if "swim" in name.lower() or "pool" in name.lower():
        typ = "swimming"
    elif "bike" in name.lower() or "cycle" in name.lower():
        typ = "cycling"
    return {
        "fit_id": digest[:12],
        "date": date,
        "type": typ,
        "source": "garmin",
        "distance_km": 0.0,
        "duration_min": 0.0,
        "avg_pace_min_per_km": 0.0,
        "avg_hr": 0,
        "max_hr": 0,
        "min_hr": 0,
        "cadence_avg": 0,
        "stride_cm": 0.0,
        "steps": 0,
        "elevation_gain_m": 0,
        "elevation_loss_m": 0,
        "temperature_avg_c": 0.0,
        "calories": 0,
        "training_effect": {"aerobic_te": 0.0, "anaerobic_te": 0.0, "label": "UNKNOWN"},
        "splits": [],
        "recovery_hr_drop": 0,
        "hr_drift_bpm": 0.0,
        "file_hash": digest,
        "_schema_version": "0.2.0",
        "_parser": "stub (garmin_tools unavailable)",
    }


def _normalize(garmin_output: dict) -> dict:
    """Нормализует вывод fit_inspect.py → стабильная схема ~/coach/lib/parse_fit.py.

    fit_inspect.json structure:
      file_id.time_created -> 'YYYY-MM-DD HH:MM:SS'
      session.{start_time, total_elapsed_s, total_distance_m, avg_hr, max_hr,
                avg_cadence, total_calories, total_ascent, total_descent, sport}
      laps[] — per-lap breakdown (avg_cadence, avg_hr, distance_m, duration_s)
    """
    file_id = garmin_output.get("file_id", {})
    session = garmin_output.get("session", {})
    laps = garmin_output.get("laps", [])

    start_time = session.get("start_time") or file_id.get("time_created", "")
    date = start_time[:10] if start_time else ""

    total_elapsed_s = session.get("total_elapsed_s", 0)
    total_distance_m = session.get("total_distance_m", 0)
    distance_km = round(total_distance_m / 1000.0, 3) if total_distance_m else 0.0
    duration_min = round(total_elapsed_s / 60.0, 2) if total_elapsed_s else 0.0
    avg_pace = (duration_min / distance_km) if distance_km else 0.0

    # Splits: per-lap данные
    splits = []
    for lap in laps:
        lap_dist_km = (lap.get("distance_m") or 0) / 1000.0
        lap_dur_min = (lap.get("duration_s") or 0) / 60.0
        splits.append({
            "km": round(lap_dist_km, 3),
            "pace_min_per_km": round(lap_dur_min / lap_dist_km, 2) if lap_dist_km else 0,
            "hr_avg": round(lap.get("avg_hr") or 0, 1),
            "cadence": round(lap.get("avg_cadence") or 0, 1),
        })

    # HR drift: разница avg_hr между первым и последним lap (на длинной)
    hr_drift_bpm = 0.0
    if len(laps) >= 2:
        first_hr = laps[0].get("avg_hr") or 0
        last_hr = laps[-1].get("avg_hr") or 0
        hr_drift_bpm = round(last_hr - first_hr, 2)

    digest = hashlib.sha256(
        json.dumps(garmin_output, sort_keys=True).encode()
    ).hexdigest()

    return {
        "fit_id": digest[:12],
        "date": date,
        "type": session.get("sport", "running"),
        "source": "garmin",
        "distance_km": distance_km,
        "duration_min": duration_min,
        "avg_pace_min_per_km": round(avg_pace, 2),
        "avg_hr": round(session.get("avg_hr") or 0, 1),
        "max_hr": round(session.get("max_hr") or 0, 1),
        "min_hr": 0,  # fit_inspect не отдаёт min_hr
        "cadence_avg": round(session.get("avg_cadence") or 0, 1),
        "stride_cm": 0.0,  # fit_inspect не отдаёт stride
        "steps": 0,  # fit_inspect не отдаёт steps
        "elevation_gain_m": round(session.get("total_ascent") or 0, 1),
        "elevation_loss_m": round(session.get("total_descent") or 0, 1),
        "temperature_avg_c": 0.0,
        "calories": round(session.get("total_calories") or 0, 1),
        "training_effect": {"aerobic_te": 0.0, "anaerobic_te": 0.0, "label": "UNKNOWN"},
        "splits": splits,
        "recovery_hr_drop": 0,  # fit_inspect не отдаёт recovery drop
        "hr_drift_bpm": hr_drift_bpm,
        "file_hash": digest,
        "_schema_version": "0.2.0",
        "_parser": "garmin_tools/fit_inspect.py",
        "_source_path": garmin_output.get("file", {}).get("path", ""),
    }


def parse_fit(fit_path: str | Path) -> dict:
    """Parse a FIT file. Phase 2: через garmin_tools если доступен, иначе stub."""
    fit_path = Path(fit_path)
    if not fit_path.exists():
        raise FileNotFoundError(f"FIT not found: {fit_path}")

    garmin_output = _parse_via_garmin_tools(fit_path)
    if garmin_output is not None:
        return _normalize(garmin_output)
    return _parse_stub(fit_path)
