"""
parse_fit.py — FIT → dict по стабильной схеме.

Используется как источник сырья для метрик и weekly_report.
В Phase 1 — заглушка на основе garth/fitparse при наличии, иначе на mock.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


STABLE_SCHEMA = {
    "fit_id": str,
    "date": str,                # YYYY-MM-DD
    "type": str,                # 'running' | 'cycling' | 'swimming' | 'other'
    "source": str,              # 'garmin' | 'manual'
    "distance_km": float,
    "duration_min": float,
    "avg_pace_min_per_km": float,
    "avg_hr": int,
    "max_hr": int,
    "min_hr": int,
    "cadence_avg": int,
    "stride_cm": float,
    "steps": int,
    "elevation_gain_m": int,
    "elevation_loss_m": int,
    "temperature_avg_c": float,
    "calories": int,
    "training_effect": {
        "aerobic_te": float,
        "anaerobic_te": float,
        "label": str,           # 'RECOVERY' | 'TEMPO' | 'THRESHOLD' | 'VO2MAX' | 'ANAEROBIC'
    },
    "splits": list,             # [{km, pace_min_per_km, hr_avg, cadence}]
    "recovery_hr_drop": int,    # drop за 60с после остановки
    "hr_drift_bpm": float,      # последний сплит - первый (на длинной)
    "file_hash": str,           # sha256(fit_path)
}


def parse_fit(fit_path: str | Path) -> dict:
    """Parse a FIT file. Phase 1: парсит если есть fitparse/garth, иначе возвращает mock."""
    fit_path = Path(fit_path)
    if not fit_path.exists():
        raise FileNotFoundError(f"FIT not found: {fit_path}")

    digest = hashlib.sha256(fit_path.read_bytes()).hexdigest()

    # Phase 1: настоящий парсер ниже — заглушка
    # try:
    #     from fitparse import FitFile
    #     ...
    # except ImportError:
    #     pass

    # Заглушка: возвращает минимальный dict на основе имени файла
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
        "_schema_version": "0.1.0",
    }


def parse_fit_stubdumps(stubdump: dict) -> dict:
    """Если FIT уже распарсен (например из Garmin stubdump) — нормализует в стабильную схему."""
    return {
        "fit_id": stubdump.get("id", ""),
        "date": stubdump.get("date", ""),
        "type": stubdump.get("type", "running"),
        "source": stubdump.get("source", "manual"),
        **{k: v for k, v in stubdump.items() if k in STABLE_SCHEMA},
        "file_hash": stubdump.get("file_hash", hashlib.sha256(json.dumps(stubdump, sort_keys=True).encode()).hexdigest()),
    }