"""
render_html.py — plan / diff / report → self-contained HTML.

Phase 1: переиспользует ту же JSON-driven схему что ~/.hermes/coach/arch/render.py.
Разница: этот модуль в репо coach/, рендерит конкретные артефакты (plan-wN.json, weekly_report dict).
Phase 21: двухэкранная mobile-first навигация — picker (список) → card (детальный), back-button, hash routing.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _duration_str(mins: int) -> str:
    if mins >= 60:
        h, m = mins // 60, mins % 60
        return f"{h}ч{m:02d}м" if m else f"{h}ч"
    return f"{mins}мин"


def _slot_icons(kind: str) -> str:
    icons = {
        "run": "🏃",
        "bike": "🚴",
        "swim": "🏊",
        "brick": "🔄",
        "control_point": "🎯",
        "ofp": "💪",
    }
    return icons.get(kind, "•")


def _kind_class(kind: str) -> str:
    return {
        "run": "tag-run",
        "bike": "tag-bike",
        "swim": "tag-swim",
        "brick": "tag-brick",
        "ofp": "tag-ofp",
        "control_point": "tag-cp",
    }.get(kind, "tag-default")


def _slot_idea(s: dict) -> str:
    """Короткая идея тренировки для compact-карточки (1 строка)."""
    name = s.get("name", "")
    if name:
        return name
    focus = s.get("focus", "")
    sub = s.get("subkind", "")
    return f"{focus} · {sub}" if focus else sub


def _inventory_for(s: dict) -> list[dict]:
    """Что взять на тренировку — на основе location и kind."""
    inv = []
    kind = s.get("kind", "")
    loc = s.get("location", "")

    if "home_stationary_bike" in loc:
        inv.append({"icon": "🚴", "name": "Велостанок (Tacx)"})
    elif loc == "stadium":
        inv.append({"icon": "🏟", "name": "Стадион (400м)"})
    elif loc == "pool_or_asphalt":
        if kind == "swim":
            inv.append({"icon": "🏊", "name": "Бассейн"})
        else:
            inv.append({"icon": "🛣", "name": "Асфальт (коммутер)"})
    elif "long_ride" in loc or loc == "long_ride_or_station":
        inv.append({"icon": "🚴", "name": "Вело (улица или станок)"})

    if kind == "ofp":
        inv.append({"icon": "🧘", "name": "Коврик"})
        inv.append({"icon": "🎗", "name": "Резинка (опционально)"})

    sub = s.get("subkind", "")
    if sub in ("key_intervals", "intervals", "race_pace", "tempo"):
        inv.append({"icon": "⌚", "name": "Garmin / часы с HR"})

    if "home_stationary_bike" in loc and s.get("workout_pending"):
        inv.append({"icon": "🚴", "name": "Zwift-приложение"})

    return inv


def _structure_steps_html(structure: list, kind: str) -> str:
    """Рендерит list[step] в HTML."""
    if not structure:
        return "<div class=\"empty\">Нет структуры</div>"

    is_ofp = "ofp" in kind or any("exercise" in st or "set" in st for st in structure)

    if is_ofp:
        rows = []
        for st in structure:
            phase = esc(st.get("phase", ""))
            dur = esc(st.get("duration_min", ""))
            if "exercise" in st:
                ex = esc(st.get("exercise", ""))
                notes = esc(st.get("notes", ""))
                rows.append(
                    f'<li class="step step-ofp">'
                    f'<div class="step-head"><span class="step-phase">{phase}</span>'
                    f'<span class="step-dur">{dur}мин</span></div>'
                    f'<div class="step-name">{ex}</div>'
                    f'<div class="step-notes">{notes}</div>'
                    f'</li>'
                )
            if "set" in st:
                s = st["set"]
                rows.append(
                    f'<li class="step step-set">'
                    f'<div class="step-head"><span class="step-phase">main</span>'
                    f'<span class="step-dur">{dur}мин</span></div>'
                    f'<div class="step-name">{esc(s["name"])}</div>'
                    f'<ol class="ex-list">'
                )
                for ex in s["exercises"]:
                    rows.append(
                        f'<li class="ex-item">'
                        f'<b>{esc(ex["name"])}</b> · {esc(ex["reps"])}'
                        f'{(" · отдых " + esc(ex["rest"])) if ex.get("rest") else ""}'
                        f'</li>'
                    )
                rows.append('</ol></li>')
        return f'<ol class="structure-list">{"".join(rows)}</ol>'

    # Run / bike / swim — HR-zone based
    rows = []
    for st in structure:
        phase = esc(st.get("phase", ""))
        dur = esc(st.get("duration_min", ""))
        zone = esc(st.get("zone") or "")
        pace = esc(st.get("pace_min_per_km") or "")
        notes = esc(st.get("notes", ""))

        if st.get("phase") == "set" and st.get("set_repeats"):
            reps = st.get("reps", "?")
            sub_rows = []
            for sub in st["set_repeats"]:
                sub_dur = esc(sub.get("duration_min", ""))
                sub_zone = esc(sub.get("zone") or "")
                sub_pace = esc(sub.get("pace_min_per_km") or "")
                sub_phase = esc(sub.get("phase", ""))
                sub_notes = esc(sub.get("notes", ""))
                pace_html = f' <span class="step-pace">@ {sub_pace}/км</span>' if sub_pace else ''
                zone_html = f'<span class="step-zone">{sub_zone}</span>' if sub_zone else ''
                sub_rows.append(
                    f'<li class="step-sub">'
                    f'<div class="step-head">{zone_html}<span class="step-phase">{sub_phase}</span> '
                    f'<span class="step-dur">{sub_dur}мин</span>{pace_html}</div>'
                    f'<div class="step-notes">{sub_notes}</div>'
                    f'</li>'
                )
            sub_html = "".join(sub_rows)
            notes_html = f'<div class="step-notes">{notes}</div>' if notes else ''
            rows.append(
                f'<li class="step step-set">'
                f'<div class="step-head"><span class="step-phase">set</span>'
                f'<span class="step-dur">{dur}мин</span>'
                f'<span class="step-reps">× {reps}</span></div>'
                f'<ol class="step-sublist">{sub_html}</ol>'
                f'{notes_html}'
                f'</li>'
            )
        else:
            pace_html = f' <span class="step-pace">@ {pace}/км</span>' if pace else ''
            zone_html = f'<span class="step-zone">{zone}</span>' if zone else ''
            notes_html = f'<div class="step-notes">{notes}</div>' if notes else ''
            rows.append(
                f'<li class="step">'
                f'<div class="step-head">{zone_html}<span class="step-phase">{phase}</span> '
                f'<span class="step-dur">{dur}мин</span>{pace_html}</div>'
                f'{notes_html}'
                f'</li>'
            )

    return f'<ol class="structure-list">{"".join(rows)}</ol>'


def render_plan_wN(plan: dict[str, Any], out_path: str | Path) -> Path:
    """Рендер plan-wN.json → HTML с двумя экранами (picker + cardWrap) и JS-навигацией.

    v27: обогащён buildPicker (totals/phase/hr-zones бейджики) + renderCard (focus/subkind).
    Навигация = точная копия w1-mobile.html.
    """
    out_path = Path(out_path)
    slots = plan.get("slots", [])
    rules = plan.get("rules", {})

    # HR zones: достаём из rules.hr_zones.zones (dict)
    hrz_dict = rules.get("hr_zones", {}).get("zones", {}) if isinstance(rules.get("hr_zones"), dict) else {}
    hrz_str = ", ".join(f"{k} {v}" for k, v in hrz_dict.items()) if hrz_dict else ""

    # Totals (planned/target/delta)
    totals = plan.get("totals", {})
    planned = totals.get("planned_hours", 0)
    target = totals.get("target_hours", 0)
    delta = totals.get("delta_hours", 0)

    # Phase
    phase = plan.get("phase") or {}

    plan_data = {
        "title": plan.get("title", "Тренировки"),
        "weekIso": f"W{plan.get('season_week', '?')}",
        "subtitle": f"iso {plan.get('iso_week', '—')} · сезон с {plan.get('season_start_date', '?')}",
        "totals": {
            "planned": planned,
            "target": target,
            "delta": delta,
        },
        "phase": {
            "id": phase.get("id", "—"),
            "start": phase.get("start", ""),
            "end": phase.get("end", ""),
            "hours_per_week_target": phase.get("hours_per_week_target", 0),
            "goal_id": phase.get("goal_id", ""),
        },
        "rules": {
            "hr_zones": hrz_str,
            "hr_zones_dict": hrz_dict,
        },
        "control_points_in_range": plan.get("control_points_in_range", []),
        "slots": [
            {
                "id": s.get("id"),
                "day": s.get("day"),
                "time": s.get("time"),
                "name": s.get("name"),
                "short": s.get("name", ""),
                "duration_min": s.get("duration_min"),
                "kind": s.get("kind"),
                "subkind": s.get("subkind"),
                "focus": s.get("focus"),
                "location": s.get("location"),
                "workout_pending": s.get("workout_pending", False),
                "structure": s.get("structure", []),
                "inventory": _inventory_for(s),
            }
            for s in slots
        ],
    }
    plan_data_json = json.dumps(plan_data, ensure_ascii=False)

    body = """<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,viewport-fit=cover">
<title>__TITLE__</title>
<style>
:root{
  --bg:#0f1115;--panel:#161a22;--panel2:#1d222c;--border:#2a3140;
  --text:#e6e9ef;--muted:#9aa3b2;
  --accent:#7aa2ff;--accent2:#5cd6c0;--warn:#ff9b6a;--good:#7ee787;--cp:#d8a0ff;
  --run:#7ec8e3;--bike:#f08a5a;--swim:#5cd6c0;--ofp:#d8a0ff;--brick:#f0c674;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif;
  -webkit-text-size-adjust:100%;line-height:1.4}
body{padding:14px 12px 80px;max-width:780px;margin:0 auto}
h1{font-size:20px;margin:0 0 4px}
h2{font-size:15px;margin:0 0 8px;color:var(--accent)}
h3{font-size:13px;margin:0 0 6px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted)}
.sub{color:var(--muted);font-size:12.5px;margin-bottom:12px}

/* v26: ТОЧНАЯ копия архитектуры из w1-mobile.html (который работал) */
.picker{display:flex;flex-direction:column;gap:10px}
.hidden{display:none !important}
.visible{display:flex !important;flex-direction:column;gap:10px}

.slot{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:14px 16px;text-align:left;cursor:pointer;font:inherit;color:inherit;
  min-height:74px;box-shadow:0 1px 2px rgba(0,0,0,.3);display:flex;
  flex-direction:column;justify-content:center;transition:transform .1s}
.slot:active{transform:scale(0.98);background:var(--panel2)}
.slot .day{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.slot .name{font-size:14px;font-weight:600;margin-top:4px}
.slot .desc{font-size:12px;color:var(--muted);margin-top:2px}
.slot .slot-head{display:flex;align-items:center;gap:8px}
.slot .slot-kind-icon{font-size:16px;width:20px;text-align:center;flex-shrink:0}
.slot .slot-dur{margin-left:auto;font-size:10.5px;color:var(--muted);background:var(--panel2);padding:2px 8px;border-radius:6px;border:1px solid var(--border);font-family:ui-monospace,SFMono-Regular,monospace}
.slot .slot-focus{font-size:11px;color:var(--accent2);margin-top:3px;font-weight:500}

.slots-header{font-size:14px;margin:14px 0 4px;color:var(--accent);text-transform:none;letter-spacing:0}
.slots-sub{font-size:11.5px;color:var(--muted);margin-bottom:6px}

.totals-card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:12px 14px;margin-bottom:8px}
.totals-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:8px}
.total-cell{background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:6px;text-align:center}
.total-cell .v{font-size:16px;font-weight:600;color:var(--accent2);font-family:ui-monospace,SFMono-Regular,monospace}
.total-cell .l{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-top:1px}
.delta-positive .v{color:var(--good)}
.delta-negative .v{color:var(--warn)}
.zones-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:4px;font-size:10.5px}
.zone{background:var(--panel2);padding:4px 8px;border-radius:6px;border:1px solid var(--border);color:var(--muted)}
.zone b{color:var(--accent);font-family:ui-monospace,SFMono-Regular,monospace;font-size:10.5px;margin-right:3px}

.phase-card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:10px 14px;margin-bottom:8px}
.phase-card h3{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin:0 0 3px}
.phase-card p{font-size:11.5px;color:var(--text);margin:0;line-height:1.4}

.cp-card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:10px 14px;margin-bottom:8px}
.cp-card h3{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin:0 0 3px}
.cp-card p{font-size:11.5px;color:var(--text);margin:0;line-height:1.4}

.actual-badge{display:inline-block;background:rgba(126,231,135,.1);border:1px solid rgba(126,231,135,.3);color:var(--good);padding:3px 10px;border-radius:8px;font-size:11px;font-weight:600;margin-top:6px;letter-spacing:.3px}
.slot-done-mark{color:var(--good);font-weight:700;margin-left:4px}
.slot-completed{border-color:rgba(126,231,135,.3) !important;background:rgba(126,231,135,.04) !important}

.summary-card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:10px 14px;margin-bottom:10px}
.summary-card h3{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin:0 0 6px}
.summary-list{margin:0;padding-left:18px;font-size:11.5px;line-height:1.5;color:var(--text)}
.summary-list li{margin-bottom:2px}
.summary-totals{margin-top:8px;padding-top:8px;border-top:1px solid var(--border);font-size:12px;color:var(--accent2);font-weight:600;text-align:center;font-family:ui-monospace,SFMono-Regular,monospace}

.plan-title{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:12px 16px;margin-bottom:4px}
.plan-title h1{font-size:18px;margin:0}
.plan-title .week{font-size:12px;color:var(--muted);margin-top:2px}
.plan-rules{font-size:11px;color:var(--muted);margin-top:6px;line-height:1.4}

.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:14px;margin-bottom:12px}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.card-headline{display:flex;align-items:center;gap:8px;flex:1;min-width:0}
.card-kind-icon{font-size:22px;flex-shrink:0}
.card-name{font-size:16px;font-weight:600;line-height:1.2}
.card-subtitle{font-size:11.5px;color:var(--muted);margin:0 0 8px}
.card-tag{font-size:10.5px;padding:3px 9px;border-radius:8px;background:var(--panel2);color:var(--muted);text-transform:lowercase;letter-spacing:.3px;font-weight:600;flex-shrink:0;margin-left:8px}
.card-tag.kind-run{color:var(--run);background:rgba(126,200,227,.08);border:1px solid rgba(126,200,227,.3)}
.card-tag.kind-bike{color:var(--bike);background:rgba(240,138,90,.08);border:1px solid rgba(240,138,90,.3)}
.card-tag.kind-swim{color:var(--swim);background:rgba(92,214,192,.08);border:1px solid rgba(92,214,192,.3)}
.card-tag.kind-ofp{color:var(--ofp);background:rgba(216,160,255,.08);border:1px solid rgba(216,160,255,.3)}

.exercise{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)}
.exercise:last-child{border-bottom:none}
.ex-icon{width:36px;height:36px;flex-shrink:0;font-size:22px;display:flex;align-items:center;justify-content:center}
.ex-text{flex:1}
.ex-name{font-size:14px;font-weight:600}
.ex-name .eq{font-size:10px;color:var(--warn);background:rgba(255,155,106,.08);padding:1px 5px;border-radius:4px;margin-left:4px}
.ex-why{font-size:12px;color:var(--muted);margin-top:2px}

.inventory{background:rgba(255,155,106,.05);border:1px dashed var(--warn);border-radius:8px;padding:10px 12px;margin-bottom:12px;font-size:13px}
.inv-title{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--warn);font-weight:600;margin-bottom:6px}

.card-meta-row{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 12px}
.card-meta-item{background:var(--panel2);padding:3px 8px;border-radius:6px;border:1px solid var(--border);font-size:10.5px;color:var(--muted);font-family:ui-monospace,SFMono-Regular,monospace}
.focus-pill{font-family:inherit;font-weight:600}
.focus-pill.focus-Z1{color:var(--accent2);background:rgba(92,214,192,.08);border-color:rgba(92,214,192,.3)}
.focus-pill.focus-Z2{color:var(--accent2);background:rgba(92,214,192,.08);border-color:rgba(92,214,192,.3)}
.focus-pill.focus-Z2_low{color:var(--accent2);background:rgba(92,214,192,.08);border-color:rgba(92,214,192,.3)}
.focus-pill.focus-Z3{color:var(--warn);background:rgba(255,155,106,.08);border-color:rgba(255,155,106,.3)}
.focus-pill.focus-Z4{color:var(--warn);background:rgba(255,155,106,.08);border-color:rgba(255,155,106,.3)}
.focus-pill.focus-Z5{color:var(--cp);background:rgba(216,160,255,.08);border-color:rgba(216,160,255,.3)}
.focus-pill.focus-Z6{color:var(--cp);background:rgba(216,160,255,.08);border-color:rgba(216,160,255,.3)}
.zwift-pending{color:var(--warn) !important;border-color:rgba(255,155,106,.4) !important;background:rgba(255,155,106,.08) !important;font-family:inherit !important}

.actual-block{background:rgba(126,231,135,.06);border:1px solid rgba(126,231,135,.3);border-radius:8px;padding:10px 12px;margin:0 0 12px;font-size:13px}
.actual-title{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--good);font-weight:600;margin-bottom:5px}
.actual-line{color:var(--text);font-size:13px;line-height:1.4}
.actual-line b{color:var(--good);font-weight:600}
.actual-notes{margin-top:5px;font-size:12px;color:var(--muted);font-style:italic;line-height:1.4}
.inv-item{display:flex;gap:8px;align-items:center;padding:2px 0}
.inv-icon{color:var(--warn);font-size:14px;width:18px;text-align:center}

.topbar{display:flex;align-items:center;margin-bottom:12px}
.topbar button{background:var(--panel);border:1px solid var(--border);padding:8px 12px;border-radius:8px;cursor:pointer;font:inherit;color:inherit;min-height:36px;display:flex;align-items:center;gap:6px}
.topbar button:active{transform:scale(0.97)}

/* Structure (workout steps) */
.structure-list{margin:0;padding-left:0;list-style:none}
.step{padding:8px 10px;margin-bottom:5px;background:var(--panel2);border-radius:6px;border-left:2px solid var(--accent2)}
.step-set{background:rgba(122,162,255,.08);border-left-color:var(--accent)}
.step-ofp{background:rgba(216,160,255,.08);border-left-color:var(--cp)}
.step-head{display:flex;align-items:center;gap:6px;margin-bottom:2px;flex-wrap:wrap}
.step-phase{color:var(--accent2);font-weight:600;font-size:10.5px;text-transform:uppercase;letter-spacing:.5px}
.step-dur{color:var(--text);font-weight:600;font-size:13px;font-family:ui-monospace,SFMono-Regular,monospace}
.step-zone{background:var(--bg);padding:1px 6px;border-radius:4px;font-size:10.5px;color:var(--accent2);font-family:ui-monospace,SFMono-Regular,monospace}
.step-pace{color:var(--muted);font-size:11px;font-family:ui-monospace,SFMono-Regular,monospace}
.step-reps{color:var(--accent);font-weight:600;font-size:11px;margin-left:4px}
.step-name{font-size:13px;margin-top:2px}
.step-notes{margin-top:3px;font-size:11.5px;color:var(--muted);font-style:italic;line-height:1.4}
.step-sublist{margin:6px 0 4px 12px;padding-left:0;list-style:none;font-size:12px}
.step-sub{padding:4px 6px;margin-bottom:2px;background:var(--bg);border-radius:4px;border-left:2px solid var(--good)}
.ex-list{margin:8px 0 0;padding-left:0;list-style:none;font-size:12.5px;display:flex;flex-direction:column;gap:4px}
.ex-item{display:flex;gap:10px;align-items:flex-start;padding:8px 10px;background:var(--panel);border:1px solid var(--border);border-radius:8px;margin-bottom:0}
.ex-num{flex-shrink:0;width:22px;height:22px;background:var(--accent);color:var(--bg);font-weight:700;font-size:12px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:ui-monospace,SFMono-Regular,monospace}
.ex-content{flex:1;min-width:0}
.ex-name-row{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:2px}
.ex-name{color:var(--accent);font-size:13px;font-weight:600}
.ex-side{color:var(--accent2);font-size:11px;font-weight:600;background:rgba(92,214,192,.08);padding:1px 6px;border-radius:4px;font-family:ui-monospace,SFMono-Regular,monospace}
.ex-band{font-size:13px}
.ex-focus-pill{font-size:10px;color:var(--muted);background:var(--panel2);padding:1px 6px;border-radius:4px;font-weight:500;letter-spacing:.2px}
.ex-reps{font-size:11.5px;color:var(--text);font-family:ui-monospace,SFMono-Regular,monospace;margin-bottom:2px;font-weight:600}
.ex-why{font-size:11.5px;color:var(--muted);line-height:1.4;font-style:italic}

footer{margin-top:18px;text-align:center;font-size:11px;color:var(--muted)}
.empty{color:var(--muted);font-style:italic;padding:14px;text-align:center}
</style></head><body>

<script type="application/json" id="plan-data">__PLAN_DATA__</script>

<div id="picker" class="picker visible"></div>

<div id="cardWrap" class="hidden">
  <div class="topbar">
    <button id="backBtn">← к выбору</button>
  </div>
  <div id="cardHost"></div>
</div>

<script>
// v26: точная копия логики навигации из w1-mobile.html (которая работала у Кирилла).
// Тёмная цветовая гамма, structure/inventory из coach-данных вместо OFP-библиотеки.

const KIND_ICON = { run: '🏃', bike: '🚴', swim: '🏊', ofp: '💪', brick: '🔄', control_point: '🎯' };
let PLAN = null;
let ACTIVE_WEEK_KEY = null;

function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function loadPlan() {
  const el = document.getElementById('plan-data');
  if (!el) return null;
  try { return JSON.parse(el.textContent); }
  catch(e) { console.error('plan-data parse error', e); return null; }
}

function renderStructure(structure, kind) {
  if (!structure || !structure.length) return '<div class="empty">Нет структуры</div>';
  const isOfp = kind === 'ofp' || structure.some(st => 'exercise' in st || 'set' in st);
  if (isOfp) return renderOfpStructure(structure);
  return renderHrStructure(structure);
}

function renderOfpStructure(structure) {
  const rows = structure.map(st => {
    if (st.exercise) {
      return '<li class="step step-ofp">'
        + '<div class="step-head"><span class="step-phase">' + escapeHtml(st.phase||'') + '</span>'
        + '<span class="step-dur">' + escapeHtml(String(st.duration_min||'')) + 'мин</span></div>'
        + '<div class="step-name">' + escapeHtml(st.exercise) + '</div>'
        + (st.notes ? '<div class="step-notes">' + escapeHtml(st.notes) + '</div>' : '')
        + '</li>';
    }
    if (st.set) {
      // Set header (название сета + формат)
      let html = '<li class="step step-set">'
        + '<div class="step-head"><span class="step-phase">main</span>'
        + '<span class="step-dur">' + escapeHtml(String(st.duration_min||'')) + 'мин</span></div>'
        + '<div class="step-name">' + escapeHtml(st.set.name) + '</div>'
        + (st.set.format ? '<div class="step-notes">' + escapeHtml(st.set.format) + '</div>' : '')
        + '<ol class="ex-list">';
      // Каждое упражнение — структурированная карточка
      for (let i = 0; i < (st.set.exercises || []).length; i++) {
        const ex = st.set.exercises[i];
        const num = i + 1;
        const sideTag = ex.side ? ' <span class="ex-side">· ' + escapeHtml(ex.side) + '</span>' : '';
        const bandTag = ex.band ? ' <span class="ex-band">🎗</span>' : '';
        const focusTag = ex.focus ? ' <span class="ex-focus-pill">' + escapeHtml(ex.focus) + '</span>' : '';
        html += '<li class="ex-item">'
          + '<div class="ex-num">' + num + '</div>'
          + '<div class="ex-content">'
          + '<div class="ex-name-row">'
          + '<b class="ex-name">' + escapeHtml(ex.name) + '</b>' + sideTag + bandTag + focusTag
          + '</div>'
          + '<div class="ex-reps">× ' + escapeHtml(ex.reps) + '</div>'
          + (ex.notes ? '<div class="ex-why">' + escapeHtml(ex.notes) + '</div>' : '')
          + '</div>'
          + '</li>';
      }
      return html + '</ol></li>';
    }
    return '';
  }).join('');
  return '<ol class="structure-list">' + rows + '</ol>';
}

function renderHrStructure(structure) {
  // v36: basis-aware rendering.
  //   - basis="time" (default): показываем duration_min + hr_target если есть.
  //   - basis="distance": показываем distance_m, НЕ показываем duration_min, pace_min_per_km как «X:XX/км».
  //   - notes в sub-шагах НИКОГДА не показываются.
  //   - top-level set header: просто "set · × 6" (без объёма, без total time/distance).
  //     Модель может класть st.set_label (например "интервалы") — тогда выводится оно.
  const rows = structure.map(st => {
    if (st.phase === 'set' && st.set_repeats) {
      // Sub-шаги внутри set
      const subHtml = st.set_repeats.map(s => {
        const subBasis = s.basis || 'time';
        // distance-value: либо distance_m, либо duration_min
        let valueHtml = '';
        if (subBasis === 'distance' && s.distance_m) {
          valueHtml = '<span class="step-dur">' + escapeHtml(String(s.distance_m)) + 'м</span>';
        } else if (s.duration_min) {
          valueHtml = '<span class="step-dur">' + escapeHtml(String(s.duration_min)) + 'мин</span>';
        }
        const zone = s.zone ? '<span class="step-zone">' + escapeHtml(s.zone) + '</span>' : '';
        const hr = s.hr_target ? ' <span class="step-pace">HR ' + escapeHtml(String(s.hr_target)) + '</span>' : '';
        const pace = s.pace_min_per_km ? ' <span class="step-pace">@ ' + escapeHtml(s.pace_min_per_km) + '/км</span>' : '';
        return '<li class="step-sub">'
          + '<div class="step-head">' + zone + '<span class="step-phase">' + escapeHtml(s.phase||'') + '</span>'
          + ' ' + valueHtml + hr + pace + '</div>'
          // notes в sub-шагах не показываем
          + '</li>';
      }).join('');
      // Top-level set header — ТОЛЬКО label + reps (без объёма)
      const setLabel = st.label || 'set';
      return '<li class="step step-set">'
        + '<div class="step-head"><span class="step-phase">' + escapeHtml(setLabel) + '</span>'
        + '<span class="step-reps">× ' + escapeHtml(String(st.reps||'?')) + '</span></div>'
        + '<ol class="step-sublist">' + subHtml + '</ol>'
        // top-level notes тоже не показываем в v36
        + '</li>';
    }
    // Top-level одиночный шаг (warmup, cooldown, work, main, etc.)
    const topBasis = st.basis || 'time';
    let topValue = '';
    if (topBasis === 'distance' && st.distance_m) {
      topValue = '<span class="step-dur">' + escapeHtml(String(st.distance_m)) + 'м</span>';
    } else if (st.duration_min) {
      topValue = '<span class="step-dur">' + escapeHtml(String(st.duration_min)) + 'мин</span>';
    }
    const zone = st.zone ? '<span class="step-zone">' + escapeHtml(st.zone) + '</span>' : '';
    const hr = st.hr_target ? ' <span class="step-pace">HR ' + escapeHtml(String(st.hr_target)) + '</span>' : '';
    const pace = st.pace_min_per_km ? ' <span class="step-pace">@ ' + escapeHtml(st.pace_min_per_km) + '/км</span>' : '';
    return '<li class="step">'
      + '<div class="step-head">' + zone + '<span class="step-phase">' + escapeHtml(st.phase||'') + '</span>'
      + ' ' + topValue + hr + pace + '</div>'
      // v36: top-level notes тоже не показываем (Кирилл: 'подпись внизу уродская')
      + '</li>';
  }).join('');
  return '<ol class="structure-list">' + rows + '</ol>';
}

function renderInventory(inv) {
  if (!inv || !inv.length) return '';
  const items = inv.map(i => '<div class="inv-item"><span class="inv-icon">' + escapeHtml(i.icon||'•') + '</span><span>' + escapeHtml(i.name) + '</span></div>').join('');
  return '<div class="inventory"><div class="inv-title">📦 Что нужно</div>' + items + '</div>';
}

function renderCard(slot) {
  const inventory = slot.inventory || [];
  const invHtml = renderInventory(inventory);
  const kind = slot.kind || '';
  const kindIcon = KIND_ICON[kind] || '🎯';
  const tag = (slot.structure && slot.structure.length) || '?';

  // Meta items (v18-style: focus бейджики, subkind, location, workout_pending)
  let metaHtml = '';
  if (slot.location) metaHtml += '<span class="card-meta-item">📍 ' + escapeHtml(slot.location) + '</span>';
  if (slot.focus) metaHtml += '<span class="card-meta-item focus-pill focus-' + escapeHtml(slot.focus) + '">🎯 ' + escapeHtml(slot.focus) + '</span>';
  if (slot.subkind) metaHtml += '<span class="card-meta-item">' + escapeHtml(slot.subkind) + '</span>';
  if (slot.workout_pending) metaHtml += '<span class="card-meta-item zwift-pending">⏳ Zwift pending</span>';

  const stepsHtml = renderStructure(slot.structure, kind);

  // v29: actual-блок (если есть в slot.actual) — показывается зелёным
  let actualHtml = '';
  if (slot.actual && (slot.actual.distance_km || slot.actual.time_sec || slot.actual.notes)) {
    const a = slot.actual;
    const actualItems = [];
    if (a.distance_km) actualItems.push('<b>' + a.distance_km + 'К</b>');
    if (a.time_sec) {
      const mins = Math.floor(a.time_sec / 60);
      const secs = a.time_sec % 60;
      actualItems.push('<b>' + mins + ':' + String(secs).padStart(2, '0') + '</b>');
    }
    if (a.avg_pace) actualItems.push('темп <b>' + escapeHtml(a.avg_pace) + '</b>/км');
    if (a.avg_hr) actualItems.push('HR avg <b>' + a.avg_hr + '</b>');
    if (a.rpe) actualItems.push('RPE <b>' + a.rpe + '/10</b>');
    actualHtml = '<div class="actual-block">'
      + '<div class="actual-title">✅ Факт</div>'
      + '<div class="actual-line">' + actualItems.join(' · ') + '</div>'
      + (a.notes ? '<div class="actual-notes">' + escapeHtml(a.notes) + '</div>' : '')
      + '</div>';
  }

  return '<div class="card">'
    + '<div class="card-header">'
    + '<div class="card-headline">'
    + '<span class="card-kind-icon">' + kindIcon + '</span>'
    + '<span class="card-name">' + escapeHtml(slot.name) + '</span>'
    + '</div>'
    + '<div class="card-tag kind-' + escapeHtml(kind) + '">' + escapeHtml(tag) + ' шагов</div>'
    + '</div>'
    + '<div class="card-subtitle">' + escapeHtml(slot.day) + ' · ' + escapeHtml(slot.time) + ' · '
    + escapeHtml(String(slot.duration_min)) + ' мин</div>'
    + (metaHtml ? '<div class="card-meta-row">' + metaHtml + '</div>' : '')
    + actualHtml
    + invHtml
    + '<h3>Структура тренировки</h3>'
    + stepsHtml
    + '</div>';
}

function buildPicker(plan) {
  ACTIVE_WEEK_KEY = plan.weekIso || plan.season_week || null;
  const isActual = !!plan.is_actual_log;
  let html = '<div class="plan-title">';
  html += '<h1>' + escapeHtml(plan.title || 'Тренировки') + '</h1>';
  if (plan.weekIso) html += '<div class="week">' + escapeHtml(plan.weekIso) + '</div>';
  if (plan.subtitle) html += '<div class="week">' + escapeHtml(plan.subtitle) + '</div>';
  if (isActual) html += '<div class="actual-badge">✅ Фактический лог</div>';
  html += '</div>';

  // Totals (v33: всегда planned / target / delta).
  // planned = сумма duration_min всех слотов (включая actual и planned).
  // target = phase.hours_per_week_target (долгосрочный план).
  // delta = planned - target: зелёный если ≥ 0, красный если < 0.
  const slotsTotal = (plan.slots || []).reduce((sum, s) => sum + (s.duration_min || 0), 0);
  const plannedHours = Math.round(slotsTotal / 60 * 10) / 10;
  const targetHours = (plan.phase && plan.phase.hours_per_week_target) || 0;
  const deltaHours = Math.round((plannedHours - targetHours) * 10) / 10;
  const deltaSign = (deltaHours >= 0 ? '+' : '');
  const deltaClass = (deltaHours >= 0 ? 'delta-positive' : 'delta-negative');
  html += '<div class="totals-card">';
  html += '<div class="totals-grid">';
  html += '<div class="total-cell"><div class="v">' + plannedHours + 'ч</div><div class="l">planned</div></div>';
  html += '<div class="total-cell"><div class="v">' + targetHours + 'ч</div><div class="l">expected</div></div>';
  html += '<div class="total-cell ' + deltaClass + '"><div class="v">' + deltaSign + deltaHours + 'ч</div><div class="l">delta</div></div>';
  html += '</div>';
  // HR zones
  const hrzDict = (plan.rules && plan.rules.hr_zones_dict) ||
                  (plan.rules && plan.rules.hr_zones && plan.rules.hr_zones.zones) || null;
  if (hrzDict) {
    html += '<div class="zones-grid">';
    for (const k of Object.keys(hrzDict)) {
      html += '<div class="zone"><b>' + escapeHtml(k) + '</b> ' + escapeHtml(String(hrzDict[k])) + '</div>';
    }
    html += '</div>';
  }
  html += '</div>';

  // Phase
  if (plan.phase && plan.phase.id && plan.phase.id !== '—') {
    html += '<div class="phase-card">';
    html += '<h3>Фаза · ' + escapeHtml(plan.phase.id) + '</h3>';
    html += '<p>' + escapeHtml(plan.phase.start) + ' → ' + escapeHtml(plan.phase.end)
         + ' · target ' + plan.phase.hours_per_week_target + 'ч/нед'
         + (plan.phase.goal_id ? ' · goal ' + escapeHtml(plan.phase.goal_id) : '')
         + '</p>';
    html += '</div>';
  }

  // Summary (v29: actual log summary)
  if (isActual && plan.summary && plan.summary.actual) {
    html += '<div class="summary-card">';
    html += '<h3>Сводка недели</h3>';
    html += '<ul class="summary-list">';
    for (const line of plan.summary.actual) {
      html += '<li>' + escapeHtml(line) + '</li>';
    }
    html += '</ul>';
    if (plan.summary.totals) {
      html += '<div class="summary-totals">' + escapeHtml(plan.summary.totals) + '</div>';
    }
    html += '</div>';
  }

  // Section title
  html += '<h2 class="slots-header">Тренировки · ' + (plan.slots || []).length + ' шт</h2>';
  html += '<div class="slots-sub">тап → детали</div>';

  // Слоты (с иконкой вида спорта)
  for (const s of (plan.slots || [])) {
    const kindIcon = KIND_ICON[s.kind] || '🎯';
    const doneMark = (s.actual && (s.actual.distance_km || s.actual.time_sec)) ? ' <span class="slot-done-mark">✓</span>' : '';
    html += '<button class="slot ' + (s.actual ? 'slot-completed' : '') + '" data-slot="' + escapeHtml(s.id) + '">';
    html += '<div class="slot-head">';
    html += '<span class="slot-kind-icon">' + kindIcon + '</span>';
    html += '<span class="day">' + escapeHtml(s.day) + ' · ' + escapeHtml(s.time) + '</span>';
    html += '<span class="slot-dur">' + s.duration_min + ' мин' + doneMark + '</span>';
    html += '</div>';
    html += '<div class="name">' + escapeHtml(s.name) + '</div>';
    if (s.focus) html += '<div class="slot-focus">🎯 ' + escapeHtml(s.focus) + '</div>';
    html += '</button>';
  }

  document.getElementById('picker').innerHTML = html;
  // Re-bind clicks
  document.querySelectorAll('.slot').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      showSlot(el.dataset.slot);
    });
  });
}

function showPicker() {
  document.getElementById('picker').classList.remove('hidden');
  document.getElementById('picker').classList.add('visible');
  document.getElementById('cardWrap').classList.add('hidden');
  document.getElementById('cardWrap').classList.remove('visible');
  if (window.location.hash) {
    try { history.replaceState(history.state, '', ' '); } catch(e) {}
  }
  window.scrollTo(0, 0);
}

function showSlot(slot) {
  document.getElementById('picker').classList.add('hidden');
  document.getElementById('picker').classList.remove('visible');
  document.getElementById('cardWrap').classList.remove('hidden');
  document.getElementById('cardWrap').classList.add('visible');

  const slotDef = (PLAN.slots || []).find(s => s.id === slot);
  if (!slotDef) {
    document.getElementById('cardHost').innerHTML = '<div class="card">Слот не найден: ' + escapeHtml(slot) + '</div>';
  } else {
    document.getElementById('cardHost').innerHTML = renderCard(slotDef);
  }
  try {
    if (history.state && history.state.page === 'card') {
      history.replaceState({page: 'card', slot: slot}, '', '#' + slot);
    } else {
      history.pushState({page: 'card', slot: slot}, '', '#' + slot);
    }
  } catch(e) { history.replaceState(null, '', '#' + slot); }
  window.scrollTo(0, 0);
}

window.addEventListener('popstate', (e) => {
  const state = e.state;
  if (!state || state.page !== 'card') showPicker();
});

document.getElementById('backBtn').addEventListener('click', () => {
  if (history.state && history.state.page === 'card') history.back();
  else showPicker();
});

// Init
function init() {
  PLAN = loadPlan();
  if (!PLAN) {
    document.getElementById('picker').innerHTML = '<div class="card">Не удалось загрузить план.</div>';
    return;
  }
  buildPicker(PLAN);
  // Если есть hash — открыть ту карточку
  const initialHash = window.location.hash.replace('#', '');
  const validIds = new Set((PLAN.slots || []).map(s => s.id));
  if (initialHash && validIds.has(initialHash)) {
    history.replaceState({page: 'init'}, '', ' ');
    showSlot(initialHash);
  } else {
    history.replaceState({page: 'init'}, '', ' ');
  }
}

init();
</script>
</body></html>"""

    # Заполнение плейсхолдеров
    body_filled = body.replace("__TITLE__", esc(plan.get("title", "plan")))
    body_filled = body_filled.replace("__PLAN_DATA__", plan_data_json)

    out_path.write_text(body_filled, encoding="utf-8")
    return out_path


def render_weekly_report(report: dict[str, Any], out_path: str | Path) -> Path:
    out_path = Path(out_path)
    pre = report.get("preamble", {})
    pre_html = json.dumps(pre, ensure_ascii=False, indent=2)
    body = f"""
<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Weekly report W{esc(report.get('season_week', report.get('week_iso','')))}</title>
<style>
:root{{--bg:#0f1115;--panel:#161a22;--accent:#7aa2ff;--text:#e6e9ef;--muted:#9aa3b2}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,Roboto,sans-serif;padding:18px 14px}}
.wrap{{max-width:760px;margin:0 auto}}
h1{{font-size:18px;margin:0 0 8px}}
pre{{background:var(--panel);padding:12px;border-radius:8px;overflow-x:auto;font-size:11.5px}}
.card{{background:var(--panel);border-radius:12px;padding:14px;margin-bottom:12px}}
.muted{{color:var(--muted);font-size:12px}}
</style></head><body><div class="wrap">
<h1>Weekly report · W{esc(report.get('season_week', report.get('week_iso','')))}</h1>
<div class="muted">Phase 1 stub — реальные метрики появятся с FIT'ами</div>
<div class="card"><h2 style="color:var(--accent);margin:0 0 8px">Pre-amble</h2>
<pre>{esc(pre_html)}</pre></div>
<div class="card"><h2 style="color:var(--accent);margin:0 0 8px">Вес</h2>
<p>{esc(report.get('weight_line') or '—')}</p></div>
</div></body></html>"""
    out_path.write_text(body, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Fit-review renderer (brief + details)
# ---------------------------------------------------------------------------
#
# Render review JSON → self-contained HTML. Always-visible section = brief
# (3 sentences) + key-metrics grid. Detail sections = collapsible with click.
#
# review dict shape:
# {
#   "title":       "2026-10-14 — Berlin Running (long_Z2)",
#   "date":        "2026-10-14",
#   "sport":       "running",
#   "summary_line": "85:18 moving / 15.16 km / 5:37/км / HR 138",
#   "brief":       ["...", "...", "..."],   # 3 sentences, ALWAYS visible
#   "metrics":     { "moving_min": "85:18", "distance_km": "15.16", ... },  # grid
#   "sections": [
#       {"id": "hr_zones", "title": "HR-зоны", "kind": "hr_zones", "data": {...}},
#       {"id": "splits",   "title": "Per-km splits", "kind": "table", "data": [...]},
#       {"id": "stryd",    "title": "Stryd Running Dynamics", "kind": "kv_grid", "data": {...}},
#       {"id": "pauses",   "title": "Паузы", "kind": "table", "data": [...]},
#       {"id": "recos",    "title": "Что делать", "kind": "recommendations", "data": [...]}
#   ]
# }
#
# Section kinds:
#   hr_zones:           data = {"zones": [{"name":"Z1","sec":134,"pct":2.6}, ...],
#                              "hr_max": 182}
#   table:              data = {"columns": [{"key":"km","label":"km"}, ...],
#                              "rows": [{"km":1, "pace":..., ...}, ...]}
#   kv_grid:            data = {"items": [{"label":"VO","value":"10.8 см","sub":"avg"},
#                                          {"label":"...","value":"..."}, ...]}
#   recommendations:    data = [{"text":"...", "principle":"..."}, ...]
#   text:               data = "free-form markdown-ish text"
# ---------------------------------------------------------------------------

HR_ZONE_COLORS = {
    "Z1":  "#5cd6c0",
    "Z1.5": "#4ec0a8",
    "Z2":  "#7ec8e3",
    "Z3":  "#ff9b6a",
    "Z4":  "#f08a5a",
    "Z5":  "#d8a0ff",
    "Z6":  "#c97aff",
}

# Default HR zones for Кирилл (per state/athlete.json profile, HRmax=182).
# Format: {hr_low, hr_high} — inclusive bounds. Used as a fallback when a
# review-JSON does not specify `hr_range` per zone.
HR_ZONE_BOUNDS = {
    "Z1":   {"low": 100, "high": 117},
    "Z1.5": {"low": 118, "high": 124},
    "Z2":   {"low": 125, "high": 135},
    "Z3":   {"low": 136, "high": 145},
    "Z4":   {"low": 146, "high": 159},
    "Z5":   {"low": 160, "high": 174},
    "Z6":   {"low": 175, "high": 182},
}


def _zone_hr_range(zone: dict) -> str:
    """Format HR bounds for a zone. Prefer explicit zone['hr_range']/['hr_low']/['hr_high'];
    fall back to HR_ZONE_BOUNDS table lookup by zone name.
    """
    rng = zone.get("hr_range")
    if rng:
        return str(rng)
    low = zone.get("hr_low")
    high = zone.get("hr_high")
    if low is not None and high is not None:
        return f"{low}-{high}"
    name = zone.get("name", "")
    fb = HR_ZONE_BOUNDS.get(name)
    if fb:
        return f"{fb['low']}-{fb['high']}"
    return ""


def _render_metrics_grid(metrics: dict[str, Any]) -> str:
    """2-3 column grid of label/value pairs. Robust to str|int|float."""
    if not metrics:
        return ""
    cells = []
    for k, v in metrics.items():
        label = str(k).replace("_", " ").strip()
        # Title-case short labels (>=3 слов), sentence-case for longer descriptions
        words = label.split()
        label_pretty = " ".join(w if w.isupper() or len(w) > 4 else w.capitalize()
                                for w in words) if len(words) <= 4 else label.capitalize()
        cells.append(
            f'<div class="metric-cell">'
            f'<div class="metric-label">{esc(label_pretty)}</div>'
            f'<div class="metric-value">{esc(str(v))}</div>'
            f'</div>'
        )
    return f'<div class="metrics-grid">{"".join(cells)}</div>'


def _render_hr_zones_section(data: dict[str, Any]) -> str:
    zones = data.get("zones", [])
    hr_max = data.get("hr_max")
    if not zones:
        return '<div class="empty">Нет данных</div>'
    rows = []
    max_pct = max((z.get("pct", 0) for z in zones), default=1) or 1
    for z in zones:
        name = z.get("name", "")
        sec = z.get("sec", 0)
        pct = z.get("pct", 0)
        m, s = divmod(int(sec), 60)
        dur_str = f'{m}м{s:02d}с' if m else f'{s}с'
        bar_width = (pct / max(max_pct, 30)) * 100  # at least 30% scaling so small zones are visible
        color = HR_ZONE_COLORS.get(name, "#9aa3b2")
        hr_range = _zone_hr_range(z)
        name_label = f"{esc(name)} <span class='hr-zone-range'>·&nbsp;{esc(hr_range)}</span>" if hr_range else esc(name)
        rows.append(
            f'<div class="hr-zone-row">'
            f'<span class="hr-zone-name" style="--c:{color}">{name_label}</span>'
            f'<div class="hr-zone-bar-wrap">'
            f'<div class="hr-zone-bar" style="width:{bar_width:.1f}%; background:{color}"></div>'
            f'</div>'
            f'<span class="hr-zone-pct">{pct:.1f}%</span>'
            f'<span class="hr-zone-dur muted">{esc(dur_str)}</span>'
            f'</div>'
        )
    sub = f'<div class="muted small">HRmax = {hr_max}</div>' if hr_max else ''
    return f'<div class="hr-zones">{"".join(rows)}</div>{sub}'


def _render_table_section(data: dict[str, Any]) -> str:
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    if not columns or not rows:
        return '<div class="empty">Нет данных</div>'
    head = "".join(f'<th>{esc(c.get("label", c.get("key","")))}</th>' for c in columns)
    body_rows = []
    for r in rows:
        cells = []
        for c in columns:
            key = c.get("key", "")
            v = r.get(key, "")
            fmt = c.get("fmt")
            if fmt and v not in (None, ""):
                try:
                    v = fmt.format(v)
                except (ValueError, KeyError):
                    pass
            # Highlight cells that match the column's tone (good/warn/cp)
            tone = ""
            if c.get("tone") == "warn" and isinstance(v, (int, float)) and v > 0:
                tone = ' class="cell-warn"'
            cells.append(f'<td{tone}>{esc(str(v))}</td>')
        body_rows.append(f'<tr>{"".join(cells)}</tr>')
    return (
        f'<table class="data-table"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table>'
    )


def _render_kv_grid_section(data: dict[str, Any]) -> str:
    items = data.get("items", [])
    if not items:
        return '<div class="empty">Нет данных</div>'
    cells = []
    for it in items:
        label = it.get("label", "")
        value = it.get("value", "")
        sub = it.get("sub", "")
        tone = it.get("tone", "")  # good | warn | cp
        cells.append(
            f'<div class="kv-cell">'
            f'<div class="kv-label">{esc(label)}</div>'
            f'<div class="kv-value {tone}">{esc(str(value))}</div>'
            + (f'<div class="kv-sub muted">{esc(sub)}</div>' if sub else '')
            + f'</div>'
        )
    return f'<div class="kv-grid">{"".join(cells)}</div>'


def _render_recommendations_section(data: list | dict) -> str:
    items = data if isinstance(data, list) else data.get("items", [])
    if not items:
        return '<div class="empty">Нет рекомендаций</div>'
    rows = []
    for i, r in enumerate(items, 1):
        text = r.get("text", "") if isinstance(r, dict) else str(r)
        principle = r.get("principle", "") if isinstance(r, dict) else ""
        priority = r.get("priority", "soon") if isinstance(r, dict) else "soon"
        prio_color = {"now": "#ff9b6a", "soon": "#7aa2ff", "later": "#9aa3b2"}.get(priority, "#7aa2ff")
        rows.append(
            f'<div class="rec-item">'
            f'<div class="rec-num" style="background:{prio_color}">{i}</div>'
            f'<div class="rec-body">'
            f'<div class="rec-text">{esc(text)}</div>'
            + (f'<div class="rec-principle muted">📐 {esc(principle)}</div>' if principle else '')
            + '</div></div>'
        )
    return f'<div class="rec-list">{"".join(rows)}</div>'


def _render_section(section: dict[str, Any]) -> str:
    sid = section.get("id", "")
    title = section.get("title", "")
    kind = section.get("kind", "text")
    data = section.get("data", "")
    summary = section.get("summary", "")

    if kind == "hr_zones":
        body = _render_hr_zones_section(data if isinstance(data, dict) else {})
    elif kind == "table":
        body = _render_table_section(data if isinstance(data, dict) else {})
    elif kind == "kv_grid":
        body = _render_kv_grid_section(data if isinstance(data, dict) else {})
    elif kind == "recommendations":
        body = _render_recommendations_section(data)
    elif kind == "multi_trend":
        body = _render_multi_trend_section(data if isinstance(data, dict) else {})
    elif kind == "text":
        body = f'<div class="text-block">{esc(data) if isinstance(data, str) else data}</div>'
    else:
        body = f'<div class="empty">unsupported kind: {esc(kind)}</div>'

    summary_html = f'<div class="section-summary muted">{esc(summary)}</div>' if summary else ''
    return (
        f'<div class="section" data-section-id="{esc(sid)}">'
        f'<div class="section-head" onclick="toggleSection(this)">'
        f'<span class="section-title">{esc(title)}</span>'
        f'<span class="section-toggle">▾</span>'
        f'</div>'
        f'{summary_html}'
        f'<div class="section-body">{body}</div>'
        f'</div>'
    )


def _render_multi_trend_section(data: dict[str, Any]) -> str:
    """SVG line chart with multiple series from per-second records.

    data = {
        "samples": [{t_sec, dist_m, hr, cadence_stryd, cadence_watch, power}, ...],
        "series": [{"key": "<key in samples>", "label": "Pace", "color": "...", "compute": "pace"|"raw"}]
    }

    Pace is computed lazily from (delta_dist / delta_t) per sample pair — Garmin
    records absolute distance, not pace directly. All other series are read as-is.

    All series are normalised 0..1 by their own min/max (independent y-axes)
    so they overlay in one chart without scale-war.
    """
    samples = data.get("samples", [])
    series = data.get("series", [])
    if not samples or not series:
        return '<div class="empty">Нет данных для графика</div>'

    # Pre-compute pace per sample (delta_dist / delta_t)
    pace_arr = [None] * len(samples)
    prev = None
    for i, s in enumerate(samples):
        d = s.get("dist_m")
        t = s.get("t_sec")
        if d is None or t is None:
            prev = None
            continue
        if prev is not None and prev["t"] is not None and (t - prev["t"]) > 0:
            dd = d - prev["d"]
            dt = t - prev["t"]
            if dd > 0 and dt > 0 and dt < 5:  # skip pause-resume jumps
                pace_arr[i] = dd / dt  # m/s; renderer will convert to min/km
        prev = {"d": d, "t": t}

    # Sample-key -> actual value accessor
    def sample_val(s, key, i):
        if key == "pace_ms":
            return pace_arr[i]
        return s.get(key)

    chart_w, chart_h = 600, 220
    pad_l, pad_r, pad_t, pad_b = 50, 16, 16, 30
    plot_w = chart_w - pad_l - pad_r
    plot_h = chart_h - pad_t - pad_b
    times = [s.get("t_sec") for s in samples if s.get("t_sec") is not None]
    if not times:
        return '<div class="empty">Нет данных для графика</div>'
    x_min, x_max = min(times), max(times)
    if x_max == x_min:
        return '<div class="empty">Слишком короткое окно</div>'

    def x_pos(t):
        return pad_l + (t - x_min) / (x_max - x_min) * plot_w

    def y_pos(n):
        return pad_t + (1.0 - n) * plot_h

    svg_parts = [f'<svg class="trend-svg" viewBox="0 0 {chart_w} {chart_h}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">']

    # Background grid
    for i in range(5):
        y = pad_t + i * plot_h / 4
        svg_parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" stroke="#2a3140" stroke-width="0.5" />')

    # X-axis ticks: every ~10 min
    total_s = x_max - x_min
    tick_step = 600 if total_s < 3600 else 1800
    t = (x_min // tick_step + 1) * tick_step
    while t <= x_max:
        x = x_pos(t)
        svg_parts.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t+plot_h}" stroke="#2a3140" stroke-width="0.3" stroke-dasharray="2,2" />')
        svg_parts.append(f'<text x="{x:.1f}" y="{pad_t+plot_h+12}" fill="#9aa3b2" font-size="9" text-anchor="middle">{int(t//60)}m</text>')
        t += tick_step
    svg_parts.append(f'<text x="{pad_l-4}" y="{pad_t+8}" fill="#9aa3b2" font-size="9" text-anchor="end">high</text>')
    svg_parts.append(f'<text x="{pad_l-4}" y="{pad_t+plot_h/2+4}" fill="#9aa3b2" font-size="9" text-anchor="end">avg</text>')
    svg_parts.append(f'<text x="{pad_l-4}" y="{pad_t+plot_h}" fill="#9aa3b2" font-size="9" text-anchor="end">low</text>')

    # Series
    for s in series:
        key = s.get("key")
        label = s.get("label", key)
        color = s.get("color", "#7aa2ff")
        invert = s.get("invert", False)
        if key == "pace_min_per_km":
            raw_vals = [v for v in pace_arr if v is not None and v > 0]
            if not raw_vals:
                continue
            vmin_p = min(raw_vals)
            vmax_p = max(raw_vals)
            if vmax_p == vmin_p:
                vmax_p = vmin_p + 0.1
            pts = []
            for i, s_row in enumerate(samples):
                p_ms = pace_arr[i]
                t = s_row.get("t_sec")
                if p_ms is None or t is None:
                    continue
                x = x_pos(t)
                # Normalise: faster = higher, so invert = True (slower → top)
                n = (p_ms - vmin_p) / (vmax_p - vmin_p)
                if invert:
                    n = 1 - n
                y = y_pos(n)
                pts.append(f"{x:.1f},{y:.1f}")
            if len(pts) >= 2:
                svg_parts.append(
                    f'<polyline points="{" ".join(pts)}" stroke="{color}" '
                    f'stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round" />'
                )
                last_x, last_y = pts[-1].split(",")
                svg_parts.append(
                    f'<text x="{float(last_x)+4:.1f}" y="{float(last_y)+3:.1f}" fill="{color}" font-size="9">{esc(label)}</text>'
                )
        else:
            raw_vals = [s_row.get(key) for s_row in samples if s_row.get(key) is not None]
            if not raw_vals:
                continue
            vmin, vmax = min(raw_vals), max(raw_vals)
            if vmax == vmin:
                vmax = vmin + 1
            pts = []
            for s_row in samples:
                v = s_row.get(key)
                t = s_row.get("t_sec")
                if v is None or t is None:
                    continue
                x = x_pos(t)
                n = (v - vmin) / (vmax - vmin)
                if invert:
                    n = 1 - n
                y = y_pos(n)
                pts.append(f"{x:.1f},{y:.1f}")
            if len(pts) >= 2:
                svg_parts.append(
                    f'<polyline points="{" ".join(pts)}" stroke="{color}" '
                    f'stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round" />'
                )
                last_x, last_y = pts[-1].split(",")
                svg_parts.append(
                    f'<text x="{float(last_x)+4:.1f}" y="{float(last_y)+3:.1f}" fill="{color}" font-size="9">{esc(label)}</text>'
                )

    # Pause bands (grey)
    for ps in data.get("pauses", []) or []:
        if ps["dur_s"] < 5:
            continue
        x1 = x_pos(ps["t_start"])
        x2 = x_pos(ps["t_end"])
        svg_parts.append(
            f'<rect x="{x1:.1f}" y="{pad_t}" width="{max(0.5, x2-x1):.1f}" '
            f'height="{plot_h}" fill="#9aa3b2" fill-opacity="0.2" />'
        )

    svg_parts.append('</svg>')
    legend_items = " ".join(
        f'<span class="trend-legend-item"><i style="background:{esc(s.get("color","#7aa2ff"))}"></i>{esc(s.get("label", s.get("key","")))}</span>'
        for s in series
    )
    return (
        f'<div class="trend-chart">{"".join(svg_parts)}'
        f'<div class="trend-legend">{legend_items}</div>'
        f'<div class="muted small" style="margin-top:6px;text-align:center">'
        f'нормализовано 0..1 на каждую серию отдельно (raw units не сопоставимы)</div>'
        f'</div>'
    )


def render_review(review: dict[str, Any], out_path: str | Path) -> Path:
    """Render a fit-review JSON → self-contained HTML.

    JSON shape: see docstring above. Always-visible: title + summary_line +
    brief (3 sentences) + metrics grid. Detail sections default to collapsed;
    tap opens them.
    """
    out_path = Path(out_path)

    title = review.get("title", "Fit review")
    summary_line = review.get("summary_line", "")
    brief = review.get("brief", [])
    metrics = review.get("metrics", {})
    sections = review.get("sections", [])
    sport = review.get("sport", "")
    date = review.get("date", "")

    brief_html = "".join(f'<li class="brief-item">{esc(s)}</li>' for s in brief if s)
    metrics_html = _render_metrics_grid(metrics)

    sections_html = "".join(_render_section(s) for s in sections)

    sport_icon = {"running": "🏃", "cycling": "🚴", "swimming": "🏊"}.get(sport, "📊")

    body = f"""<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,viewport-fit=cover">
<title>{esc(title)}</title>
<style>
:root{{
  --bg:#0f1115;--panel:#161a22;--panel2:#1d222c;--border:#2a3140;
  --text:#e6e9ef;--muted:#9aa3b2;
  --accent:#7aa2ff;--accent2:#5cd6c0;--warn:#ff9b6a;--good:#7ee787;--cp:#d8a0ff;
}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif;
  -webkit-text-size-adjust:100%;line-height:1.4}}
body{{padding:14px 12px 80px;max-width:780px;margin:0 auto}}
h1{{font-size:20px;margin:0}}
h2{{font-size:15px;margin:0 0 8px;color:var(--accent)}}
h3{{font-size:13px;margin:0 0 6px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted)}}
.muted{{color:var(--muted)}}.small{{font-size:11.5px}}

.title-card{{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:14px 16px;margin-bottom:8px}}
.title-row{{display:flex;align-items:center;gap:10px;margin-bottom:6px}}
.sport-icon{{font-size:24px}}
.title-meta{{font-size:11.5px;color:var(--muted);font-family:ui-monospace,SFMono-Regular,monospace}}
.summary-line{{font-size:13px;color:var(--accent2);font-weight:600;margin-top:4px}}

.brief-card{{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:12px 16px;margin-bottom:8px}}
.brief-title{{font-size:11px;text-transform:uppercase;letter-spacing:.5px;
  color:var(--accent);margin-bottom:6px;font-weight:600}}
.brief-list{{margin:0;padding-left:22px;font-size:13.5px;line-height:1.5;color:var(--text)}}
.brief-list li{{margin-bottom:4px}}
.brief-list li:last-child{{margin-bottom:0}}

.metrics-card{{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:12px 14px;margin-bottom:10px}}
.metrics-title{{font-size:11px;text-transform:uppercase;letter-spacing:.5px;
  color:var(--muted);margin-bottom:6px;font-weight:600}}
.metrics-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:6px}}
.metric-cell{{background:var(--panel2);border:1px solid var(--border);border-radius:8px;
  padding:8px;text-align:center}}
.metric-label{{font-size:9.5px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.4px;margin-bottom:3px}}
.metric-value{{font-size:15px;font-weight:600;color:var(--accent2);
  font-family:ui-monospace,SFMono-Regular,monospace}}

.section{{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  margin-bottom:8px;overflow:hidden}}
.section-head{{display:flex;align-items:center;justify-content:space-between;
  padding:12px 14px;cursor:pointer;user-select:none;gap:8px}}
.section-head:active{{background:var(--panel2)}}
.section-title{{font-size:13px;font-weight:600;color:var(--text);flex:1}}
.section-toggle{{font-size:14px;color:var(--muted);transition:transform .15s;
  display:inline-block}}
.section-summary{{padding:0 14px 10px;font-size:11.5px;font-style:italic}}
.section-body{{padding:0 14px 14px;font-size:12.5px;display:none}}
.section.open .section-body{{display:block}}
.section.open .section-toggle{{transform:rotate(180deg)}}

/* HR zones */
.hr-zones{{display:flex;flex-direction:column;gap:6px}}
.hr-zone-row{{display:grid;grid-template-columns:88px 1fr 50px 60px;
  gap:8px;align-items:center;font-size:11.5px}}
.hr-zone-name{{font-family:ui-monospace,SFMono-Regular,monospace;font-weight:600;
  color:var(--c,var(--text))}}
.hr-zone-range{{color:var(--muted);font-weight:500;font-size:10.5px;margin-left:2px}}
.hr-zone-bar-wrap{{background:var(--panel2);border:1px solid var(--border);
  border-radius:4px;height:14px;overflow:hidden}}
.hr-zone-bar{{height:100%;border-radius:4px;min-width:4px}}
.hr-zone-pct{{font-family:ui-monospace,SFMono-Regular,monospace;
  font-weight:600;text-align:right}}
.hr-zone-dur{{font-family:ui-monospace,SFMono-Regular,monospace;text-align:right;
  font-size:10.5px}}

/* Tables */
.data-table{{width:100%;border-collapse:collapse;font-size:11.5px;
  font-family:ui-monospace,SFMono-Regular,monospace}}
.data-table th{{text-align:left;padding:5px 8px;color:var(--muted);
  font-size:10px;text-transform:uppercase;letter-spacing:.4px;font-weight:600;
  border-bottom:1px solid var(--border)}}
.data-table td{{padding:5px 8px;color:var(--text);border-bottom:1px solid rgba(255,255,255,.05)}}
.data-table tr:last-child td{{border-bottom:none}}
.cell-warn{{color:var(--warn)!important;font-weight:600}}
.cell-good{{color:var(--good)!important;font-weight:600}}

/* Multi-series trend chart */
.trend-chart{{margin:6px 0 2px}}
.trend-svg{{width:100%;height:220px;background:var(--panel2);border:1px solid var(--border);border-radius:8px}}
.trend-legend{{display:flex;justify-content:center;flex-wrap:wrap;gap:10px;padding:8px 4px 0;font-size:11px}}
.trend-legend-item{{display:inline-flex;align-items:center;gap:5px}}
.trend-legend-item i{{display:inline-block;width:10px;height:3px;border-radius:2px}}

/* KV grid */
.kv-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:6px}}
.kv-cell{{background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:8px}}
.kv-label{{font-size:10px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.4px;margin-bottom:3px;font-weight:600}}
.kv-value{{font-size:16px;font-weight:600;color:var(--text);
  font-family:ui-monospace,SFMono-Regular,monospace}}
.kv-value.good{{color:var(--good)}}
.kv-value.warn{{color:var(--warn)}}
.kv-value.cp{{color:var(--cp)}}
.kv-sub{{font-size:10.5px;margin-top:2px;font-style:italic}}

/* Recommendations */
.rec-list{{display:flex;flex-direction:column;gap:6px}}
.rec-item{{display:flex;gap:10px;align-items:flex-start;padding:10px;
  background:var(--panel2);border:1px solid var(--border);border-radius:8px}}
.rec-num{{flex-shrink:0;width:24px;height:24px;border-radius:50%;
  color:var(--bg);font-weight:700;font-size:13px;
  display:flex;align-items:center;justify-content:center;
  font-family:ui-monospace,SFMono-Regular,monospace}}
.rec-body{{flex:1;min-width:0}}
.rec-text{{font-size:13px;line-height:1.4;color:var(--text)}}
.rec-principle{{font-size:11.5px;margin-top:4px;font-style:italic}}

/* Text block */
.text-block{{font-size:13px;line-height:1.5;color:var(--text);white-space:pre-wrap}}

.empty{{color:var(--muted);font-style:italic;padding:14px;text-align:center}}

footer{{margin-top:18px;text-align:center;font-size:11px;color:var(--muted)}}
</style></head><body>

<div class="title-card">
  <div class="title-row">
    <span class="sport-icon">{esc(sport_icon)}</span>
    <div>
      <h1>{esc(title)}</h1>
      <div class="title-meta">{esc(date)}{' · ' + esc(sport) if sport else ''}</div>
    </div>
  </div>
  {f'<div class="summary-line">{esc(summary_line)}</div>' if summary_line else ''}
</div>

{f'''<div class="brief-card">
  <div class="brief-title">💡 Бриф · 3 предложения</div>
  <ol class="brief-list">{brief_html}</ol>
</div>''' if brief_html else ''}

{f'<div class="metrics-card"><div class="metrics-title">📊 Ключевые метрики</div>{metrics_html}</div>' if metrics_html else ''}

{sections_html}

<footer>rendered via lib/render_html.render_review · schema-rev review-v1</footer>

<script>
function toggleSection(head) {{
  head.parentElement.classList.toggle('open');
}}
// Auto-open recommendations
document.addEventListener('DOMContentLoaded', () => {{
  document.querySelectorAll('.section').forEach(s => {{
    if (s.dataset.sectionId === 'recos') s.classList.add('open');
  }});
}});
</script>
</body></html>
"""
    out_path.write_text(body, encoding="utf-8")
    return out_path