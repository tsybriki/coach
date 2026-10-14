"""
season_replan.py — season_plan + progress + форма + причина → новый season_plan.
Phase 1: скелет.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def replan(reason: str,
           new_state: dict[str, Any] | None = None,
           season_plan_path: str | Path = "state/season_plan.json",
           archive_root: str | Path = "state/season_plan.archive",
           progress_path: str | Path = "state/season_progress.json",
           athlete_path: str | Path = "state/athlete.json",
           constraints_path: str | Path = "state/constraints.json") -> dict[str, Any]:
    """
    Phase 1: архивирует старый season_plan, обновляет по new_state.
    Real sanity-check (weeks_to_race, гонки на месте, total_volume рост ≤10%/нед,
    CP не уезжают за горизонт) — Phase 2.
    """
    season_plan_path = Path(season_plan_path)
    archive_root = Path(archive_root)
    archive_root.mkdir(parents=True, exist_ok=True)

    old = json.loads(season_plan_path.read_text(encoding="utf-8"))
    archive_path = archive_root / f"{datetime.now(timezone.utc).date().isoformat()}.json"
    shutil.copy(season_plan_path, archive_path)

    new = {**old, **(new_state or {})}
    new["last_replan"] = {"reason": reason, "at": _now_iso()}
    season_plan_path.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "replanned": True,
        "reason": reason,
        "archived_to": str(archive_path),
        "diff_summary": list((new_state or {}).keys()),
        "_phase": "1 stub — реальный diff в Phase 2",
    }