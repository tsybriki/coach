"""
fit_ingest.py — загрузка FIT в state/fit_store/ + index.json + (если CP-дата) actual_metrics в season_progress.

Phase 2: тонкая обёртка. Не дублирует pull из Garmin Connect (это ~/projects/garmin_tools/latest_pull.py).
fit_ingest.py работает на уже-имеющихся FIT:
  - либо уже скачанных из Garmin (лежат в ~/projects/garmin_tools/raw/<sport>/fit/)
  - либо переданных напрямую (fit_path=...)

Если FIT нет локально, fit_ingest.py дёргает garmin_tools/latest_pull.py как subprocess.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .parse_fit import parse_fit, GARMIN_TOOLS, GARMIN_TOOLS_VENV_PYTHON
from .season_week import cp_date


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _try_pull_from_garmin(days: int = 7, sport: str = "running") -> int:
    """Безопасный вызов garmin_tools/latest_pull.py. Возвращает кол-во скачанных FIT."""
    script = GARMIN_TOOLS / "latest_pull.py"
    if not (script.exists() and GARMIN_TOOLS_VENV_PYTHON.exists()):
        return 0
    try:
        result = subprocess.run(
            [str(GARMIN_TOOLS_VENV_PYTHON), str(script),
             "--sport", sport, "--days", str(days)],
            capture_output=True, text=True, timeout=120,
            cwd=str(GARMIN_TOOLS),
        )
        if result.returncode == 0:
            # читаем raw/<sport>/fit/index.json чтобы посчитать скачанные
            idx = GARMIN_TOOLS / "raw" / sport / "fit" / "index.json"
            if idx.exists():
                return len(json.loads(idx.read_text(encoding="utf-8")).get("files", []))
        return 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0


def ingest(fit_path: str | Path | None = None,
           fit_store_root: str | Path = "state/fit_store",
           progress_path: str | Path = "state/season_progress.json",
           season_plan_path: str | Path = "state/season_plan.json",
           auto_pull_days: int = 7) -> dict:
    """
    Если fit_path задан — копирует этот FIT в fit_store/.
    Если fit_path=None — пытается pull из Garmin через garmin_tools (auto_pull_days дней).

    Возвращает {fit_id, stored_at, control_point_matched, expires_at, pulled_count?}.
    """
    fit_store_root = Path(fit_store_root)
    progress_path = Path(progress_path)
    season_plan_path = Path(season_plan_path)

    pulled_count = 0
    if fit_path is None:
        # Auto-pull через garmin_tools/latest_pull.py
        for sport in ("running", "cycling", "swimming"):
            n = _try_pull_from_garmin(days=auto_pull_days, sport=sport)
            pulled_count += n
        # Теперь берём все FIT из garmin_tools/raw/ и копируем в fit_store/
        ingested = []
        for sport in ("running", "cycling", "swimming"):
            src_dir = GARMIN_TOOLS / "raw" / sport / "fit"
            if not src_dir.exists():
                continue
            for f in src_dir.glob("*.fit"):
                r = _ingest_single(f, fit_store_root, progress_path, season_plan_path)
                if r:
                    ingested.append(r)
        return {"mode": "auto_pull", "pulled_from_garmin": pulled_count, "ingested": ingested}

    return _ingest_single(Path(fit_path), fit_store_root, progress_path, season_plan_path) or {}


def _ingest_single(fit_path: Path,
                   fit_store_root: Path,
                   progress_path: Path,
                   season_plan_path: Path) -> dict | None:
    """Копирует один FIT в fit_store/, обновляет index, матчит CP."""
    parsed = parse_fit(fit_path)
    date = parsed["date"]
    year_month = date[:7]
    typ = parsed["type"]
    source = parsed["source"]
    fit_id = parsed["fit_id"]

    target_dir = fit_store_root / year_month
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{date}_{typ}_{source}.fit"
    if not target_file.exists():
        shutil.copy(fit_path, target_file)

    expires_at = datetime.fromisoformat(date + "T00:00:00+00:00") + timedelta(days=14)

    # Index
    index_path = fit_store_root / "index.json"
    if index_path.exists():
        idx = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        idx = {"fits": []}
    idx["fits"] = [f for f in idx.get("fits", []) if f["id"] != fit_id]
    index_entry = {
        "id": fit_id,
        "path": str(target_file.relative_to(fit_store_root.parent)),
        "date": date,
        "type": typ,
        "source": source,
        "created_at": _now_iso(),
        "expires_at": expires_at.isoformat(timespec="seconds"),
        "control_point_id": None,
    }
    idx["fits"].append(index_entry)

    # CP match: по неделе и дню (конкретной даты у CP в макро больше нет).
    cp_match = None
    if season_plan_path.exists():
        sp = json.loads(season_plan_path.read_text(encoding="utf-8"))
        for cp in sp.get("control_points", []):
            if cp.get("date") == date:
                cp_match = cp
                break
            sw = cp.get("season_week")
            wd = cp.get("weekday")
            if sw is None or not wd:
                continue
            try:
                cp_d = cp_date(cp, sp.get("season_start_date", "2026-10-11"))
            except Exception:
                cp_d = None
            if cp_d is not None and cp_d.isoformat() == date:
                cp_match = cp
                break
    if cp_match:
        index_entry["control_point_id"] = cp_match["id"]

    index_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

    # Progress
    if cp_match and progress_path.exists():
        prog = json.loads(progress_path.read_text(encoding="utf-8"))
        cp_prog = prog.setdefault("control_points", {}).setdefault(cp_match["id"], {})
        cp_prog.update({
            "status": "completed",
            "date": date,
            "actual_metrics": {
                "distance_km": parsed["distance_km"],
                "duration_min": parsed["duration_min"],
                "avg_hr": parsed["avg_hr"],
                "hr_drift_bpm": parsed["hr_drift_bpm"],
                "cadence_avg": parsed["cadence_avg"],
                "training_effect_label": parsed["training_effect"]["label"],
                "aerobic_te": parsed["training_effect"]["aerobic_te"],
            },
            "logged_at": _now_iso(),
        })
        progress_path.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "fit_id": fit_id,
        "stored_at": str(target_file),
        "control_point_matched": cp_match["id"] if cp_match else None,
        "expires_at": expires_at.isoformat(timespec="seconds"),
    }
