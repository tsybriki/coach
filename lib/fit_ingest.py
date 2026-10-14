"""
fit_ingest.py — загрузка FIT в fit_store/ + index.json + (если CP-дата) actual_metrics в season_progress.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .parse_fit import parse_fit


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ingest(fit_path: str | Path, fit_store_root: str | Path = "state/fit_store",
           progress_path: str | Path = "state/season_progress.json",
           season_plan_path: str | Path = "state/season_plan.json") -> dict:
    """
    Копирует FIT в fit_store/YYYY-MM/YYYY-MM-DD_<type>_<source>.fit,
    обновляет index.json.
    Если дата FIT совпала с control_point — пишет actual_metrics в season_progress.
    Возвращает dict с результатом.
    """
    fit_path = Path(fit_path)
    fit_store_root = Path(fit_store_root)
    progress_path = Path(progress_path)
    season_plan_path = Path(season_plan_path)

    parsed = parse_fit(fit_path)
    date = parsed["date"]
    year_month = date[:7]
    typ = parsed["type"]
    source = parsed["source"]
    fit_id = parsed["fit_id"]

    # Куда кладём
    target_dir = fit_store_root / year_month
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{date}_{typ}_{source}.fit"
    shutil.copy(fit_path, target_file)

    # TTL
    expires_at = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    expires_at = expires_at.replace() if False else expires_at
    from datetime import timedelta
    expires_at = datetime.fromisoformat(date + "T00:00:00+00:00") + timedelta(days=14)

    # Обновить index
    index_path = fit_store_root / "index.json"
    if index_path.exists():
        idx = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        idx = {"fits": []}
    idx["fits"] = [f for f in idx.get("fits", []) if f["id"] != fit_id]
    idx["fits"].append({
        "id": fit_id,
        "path": str(target_file.relative_to(fit_store_root.parent)),
        "date": date,
        "type": typ,
        "source": source,
        "created_at": _now_iso(),
        "expires_at": expires_at.isoformat(timespec="seconds"),
        "control_point_id": None,
    })
    index_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

    # Match с control_point
    cp_match = None
    if season_plan_path.exists():
        sp = json.loads(season_plan_path.read_text(encoding="utf-8"))
        for cp in sp.get("control_points", []):
            if cp.get("date") == date:
                cp_match = cp
                break

    if cp_match:
        idx["fits"][-1]["control_point_id"] = cp_match["id"]
        index_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

        if progress_path.exists():
            prog = json.loads(progress_path.read_text(encoding="utf-8"))
        else:
            prog = {"weeks": {}, "control_points": {}, "deviations": []}
        cp_prog = prog.setdefault("control_points", {}).setdefault(cp_match["id"], {
            "status": "completed",
            "date": date,
        })
        cp_prog.update({
            "status": "completed",
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