"""
actual_load.py — фактическая нагрузка по прошедшим неделям сезона.

Источник: Garmin Connect через garmin_tools (latest_pull.py → index.json с
distance/duration/HR по каждой активности). Ничего не хардкодится — данные
тянутся при каждой генерации.

Возвращает dict: {season_week: {run_km, run_min, bike_km, bike_min,
swim_km, swim_min, sessions, total_h, by_kind}}

Запуск:
    python3 -c "from lib import actual_load; print(actual_load.load_actual())"
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GARMIN_TOOLS = Path.home() / "projects/garmin_tools"
VENV_PYTHON = GARMIN_TOOLS / ".venv/bin/python"

SPORT_MAP = {
    "running": "run",
    "lap_swimming": "swim",
    "pool_swimming": "swim",
    "open_water_swimming": "swim",
    "cycling": "bike",
    "road_biking": "bike",
    "mountain_biking": "bike",
    "gravel_cycling": "bike",
    "indoor_cycling": "bike",
    "virtual_ride": "bike",
}


def _season_start() -> str:
    p = REPO / "state/season_plan.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")).get("season_start_date", "2026-10-11")
    return "2026-10-11"


def _pull(sport: str, count: int, out_dir: Path) -> list[dict]:
    """Тянет активности из Garmin. Пустой список при недоступности."""
    if not VENV_PYTHON.exists() or not (GARMIN_TOOLS / "latest_pull.py").exists():
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [str(VENV_PYTHON), str(GARMIN_TOOLS / "latest_pull.py"),
             "--sport", sport, "--count", str(count), "--out", str(out_dir)],
            capture_output=True, text=True, timeout=180, cwd=str(GARMIN_TOOLS),
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    idx = out_dir / "index.json"
    if not idx.exists():
        return []
    try:
        return json.loads(idx.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def load_actual(season_start: str | None = None,
                count_per_sport: int = 120,
                use_cache: bool = True) -> dict:
    """
    Возвращает {season_week: {...}} — факт по всем видам спорта.

    use_cache=True — не дёргает Garmin повторно, если свежий кэш есть
    (state/actual_load_cache.json, TTL 6 ч).
    """
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from lib import season_week

    season_start = season_start or _season_start()
    cache_path = REPO / "state/actual_load_cache.json"

    raw: list[dict] = []
    if use_cache and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            age = (datetime.now(timezone.utc) -
                   datetime.fromisoformat(cached["pulled_at"])).total_seconds()
            if age < 6 * 3600:
                raw = cached.get("activities", [])
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            raw = []

    if not raw:
        tmp = Path("/tmp/coach_actual_pull")
        for sport in ("running", "cycling", "swimming"):
            raw.extend(_pull(sport, count_per_sport, tmp / sport))
        if raw:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({
                "pulled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "activities": raw,
            }, ensure_ascii=False), encoding="utf-8")

    agg: dict[int, dict] = defaultdict(lambda: defaultdict(float))
    kinds: dict[int, dict] = defaultdict(lambda: defaultdict(int))

    for a in raw:
        date_str = a.get("date")
        if not date_str:
            continue
        try:
            d = datetime.fromisoformat(date_str).date()
        except ValueError:
            continue
        w = season_week.date_to_season_week(d, season_start)
        if not w:
            continue
        key = SPORT_MAP.get(a.get("sport_type", ""), "other")
        agg[w][key + "_km"] += (a.get("distance_km") or 0)
        agg[w][key + "_min"] += (a.get("duration_s") or 0) / 60
        kinds[w][key] += 1

    out: dict[int, dict] = {}
    for w, m in agg.items():
        total_min = sum(m.get(k + "_min", 0) for k in ("run", "bike", "swim", "other"))
        out[w] = {
            "run_km": round(m.get("run_km", 0), 1),
            "run_min": round(m.get("run_min", 0)),
            "bike_km": round(m.get("bike_km", 0), 1),
            "bike_min": round(m.get("bike_min", 0)),
            "swim_km": round(m.get("swim_km", 0), 1),
            "swim_min": round(m.get("swim_min", 0)),
            "sessions": sum(kinds[w].values()),
            "by_kind": dict(kinds[w]),
            "total_h": round(total_min / 60, 2),
        }
    return out


if __name__ == "__main__":
    data = load_actual()
    for w in sorted(data):
        d = data[w]
        print("W{:<2} сессий {:>2} | бег {:>5.1f} км / {:>3.0f} мин | "
              "вел {:>5.1f} км / {:>3.0f} мин | плав {:>4.1f} км / {:>3.0f} мин | "
              "всего {:.2f} ч".format(
                  w, d["sessions"], d["run_km"], d["run_min"],
                  d["bike_km"], d["bike_min"], d["swim_km"], d["swim_min"], d["total_h"]))
