"""
plan_runtime.py — runtime entry point для plan-wN операций.

Одна функция generate_plan_with_html() = plan_generate.generate() + render_html.render_plan_wN().
Каждая coach-plan-* skill вызывает её. Гарантирует:
  - plan-wN.json обновляется
  - wN-plan.html генерируется в state/
  - путь к HTML возвращается в ответе

Где живёт HTML:
  - state/plan-wN.html — канонический артефакт (рядом с JSON)
  - overrides → state/wN-plan.html
  - Phase 3: render_html улучшен, плюс optional --open / --send-telegram флаги

Это FIX: после v18 HTML был опциональным. После v19 — обязательная часть выхода
для ЛЮБОГО изменения plan-wN (новая генерация, override, replan).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import plan_generate, render_html


def generate_plan_with_html(season_week: int | str,
                             season_plan_path: str | Path = "state/season_plan.json",
                             athlete_path: str | Path = "state/athlete.json",
                             constraints_path: str | Path = "state/constraints.json",
                             overrides_path: str | Path = "state/overrides.json",
                             out_dir: str | Path = "state",
                             write_json: bool = True,
                             write_html: bool = True) -> dict[str, Any]:
    """
    Канонический entry point для любой coach-plan-* skill.

    Возвращает {plan, html_path, json_path}. HTML генерируется всегда (если write_html=True).
    """
    plan = plan_generate.generate(
        season_week,
        season_plan_path=season_plan_path,
        athlete_path=athlete_path,
        constraints_path=constraints_path,
        overrides_path=overrides_path,
    )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sw = plan.get("season_week", "?")
    json_path = out_dir / f"plan-w{sw}.json"
    html_path = out_dir / f"plan-w{sw}.html"

    if write_json:
        json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    if write_html:
        render_html.render_plan_wN(plan, html_path)

    return {
        "plan": plan,
        "json_path": str(json_path),
        "html_path": str(html_path),
        "season_week": sw,
        "slots_count": len(plan.get("slots", [])),
        "bike_pending": sum(1 for s in plan.get("slots", []) if s.get("workout_pending")),
        "totals": plan.get("totals", {}),
    }


def generate_preview_with_html(season_week: int | str,
                                out_dir: str | Path = "state",
                                plan_json: str | Path | None = None) -> dict[str, Any]:
    """
    Компактное read-only превью недели → HTML.

    Отличие от generate_plan_with_html: не перегенерирует план, а читает
    готовый state/plan-wN.json и строит плоский список «день → тренировка».
    Использует scripts/week_preview.py как рендерер.
    """
    import sys as _sys
    from pathlib import Path as _Path

    if plan_json is None:
        plan_json = _Path(out_dir) / f"plan-w{season_week}.json"
    plan_json = _Path(plan_json)
    if not plan_json.exists():
        raise FileNotFoundError(f"нет плана: {plan_json} (сначала generate_plan_with_html)")

    plan = json.loads(plan_json.read_text(encoding="utf-8"))

    scripts_dir = _Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in _sys.path:
        _sys.path.insert(0, str(scripts_dir))
    import week_preview  # noqa: E402

    data = week_preview.build(plan)
    out_path = _Path(out_dir) / f"preview-w{season_week}.html"
    week_preview.render(data, out_path)

    return {
        "preview_path": str(out_path),
        "season_week": season_week,
        "slots_count": data["slots_count"],
        "days": len(data["days"]),
        "week_goal": data.get("week_goal"),
    }


def generate_all_weeks(start_w: int = 1, end_w: int = 48,
                        out_dir: str | Path = "state",
                        season_plan_path: str | Path = "state/season_plan.json") -> list[dict]:
    """Массовая генерация plan-wN для диапазона. Используется для build/full-season."""
    out = []
    for sw in range(start_w, end_w + 1):
        result = generate_plan_with_html(sw, out_dir=out_dir,
                                         season_plan_path=season_plan_path)
        out.append({"season_week": sw, "html_path": result["html_path"]})
    return out


if __name__ == "__main__":
    import sys
    sw = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    result = generate_plan_with_html(sw)
    print(f"W{sw} plan:")
    print(f"  json: {result['json_path']}")
    print(f"  html: {result['html_path']}")
    print(f"  slots: {result['slots_count']}")
    print(f"  bike_pending: {result['bike_pending']}")
    print(f"  totals: {result['totals']}")