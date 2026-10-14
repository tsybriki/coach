"""
garmin_weight.py — раз в день (cron eae7b0d88b4a): читает последний вес из Garmin.
Если новее последней записи в athlete.weight_history → append (source='garmin').

Phase 1: заглушка (возвращает no-op). Phase 2: реальная интеграция через garth.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sync_from_garmin(athlete_path: str | Path = "state/athlete.json") -> dict:
    """
    Phase 1: no-op. Возвращает {'synced': False, 'reason': 'phase-1 stub'}.

    Phase 2 будет:
      - читать последний вес из Garmin (garth)
      - если date > athlete.weight_history[-1].date → append с source='garmin'
    """
    return {"synced": False, "reason": "phase-1 stub"}


def manual_weight(athlete_path: str | Path, kg: float, date: str | None = None) -> dict:
    """Записать вес вручную (команда Кирилла 'я взвесился — X кг')."""
    athlete_path = Path(athlete_path)
    if not athlete_path.exists():
        raise FileNotFoundError(athlete_path)
    a = json.loads(athlete_path.read_text(encoding="utf-8"))
    if date is None:
        date = datetime.now(timezone.utc).date().isoformat()
    a.setdefault("weight_history", [])
    a["weight_history"].append({"date": date, "kg": kg, "source": "manual"})
    a["weight_kg_current"] = kg
    a["weight_history"].sort(key=lambda x: x["date"])
    athlete_path.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"logged": True, "kg": kg, "date": date}