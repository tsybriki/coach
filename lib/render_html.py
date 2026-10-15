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
    """Рендер plan-wN.json → двухэкранный HTML с навигацией.

    Экран 1 (picker): список слотов как compact-карточки.
    Клик → переход на экран 2 (cardWrap): детальная карточка с back-button.
    """
    out_path = Path(out_path)
    slots = plan.get("slots", [])
    totals = plan.get("totals", {})
    phase = plan.get("phase") or {}
    cp_in_range = plan.get("control_points_in_range", [])

    phase_name = esc(phase.get("id", "—"))
    phase_target = phase.get("hours_per_week_target", 0)
    phase_start = esc(phase.get("start", ""))
    phase_end = esc(phase.get("end", ""))
    phase_goal_id = esc(phase.get("goal_id", ""))

    planned = totals.get("planned_hours", 0)
    target = totals.get("target_hours", 0)
    delta = totals.get("delta_hours", 0)
    delta_sign = "+" if delta >= 0 else ""
    delta_class = "delta-positive" if delta >= 0 else "delta-negative"

    rules = plan.get("rules", {})
    hr_zones = rules.get("hr_zones", {})
    zones = hr_zones.get("zones", {})

    # Сериализуем платные данные для JS
    plan_data_json = json.dumps({
        "slots": [
            {
                "id": s.get("id"),
                "day": s.get("day"),
                "time": s.get("time"),
                "duration_min": s.get("duration_min"),
                "name": s.get("name"),
                "kind": s.get("kind"),
                "subkind": s.get("subkind"),
                "focus": s.get("focus"),
                "location": s.get("location"),
                "workout_pending": s.get("workout_pending", False),
                "workout_ref": s.get("workout_ref"),
                "structure": s.get("structure", []),
                "inventory": _inventory_for(s),
            }
            for s in slots
        ],
    }, ensure_ascii=False)

    # Picker cards
    picker_items = []
    for idx, s in enumerate(slots):
        kind = s.get("kind", "")
        kind_cls = _kind_class(kind)
        icon = _slot_icons(kind)
        day = esc(s.get("day", ""))
        time = esc(s.get("time", ""))
        dur = _duration_str(s.get("duration_min", 0))
        idea = esc(_slot_idea(s))
        picker_items.append(
            f'<button type="button" class="slot-card {kind_cls}" data-slot-idx="{idx}" onclick="showCard({idx});">'
            f'<div class="slot-card-head">'
            f'<span class="slot-icon">{icon}</span>'
            f'<span class="slot-day">{day}</span>'
            f'<span class="slot-time">{time}</span>'
            f'<span class="slot-dur">{dur}</span>'
            f'</div>'
            f'<div class="slot-card-name">{idea}</div>'
            f'</button>'
        )
    picker_html = "".join(picker_items) if picker_items else '<div class="empty">Нет слотов</div>'

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

.picker{display:flex;flex-direction:column;gap:10px}
/* hidden / visible — классы больше не используются, перешли на inline style.display */

/* Picker cards */
.slot-card{
  background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:14px 16px;cursor:pointer;font:inherit;color:inherit;text-align:left;
  min-height:74px;display:flex;flex-direction:column;justify-content:center;
  transition:transform .1s;
}
.slot-card:active{transform:scale(0.98);background:var(--panel2)}
.slot-card-head{display:flex;align-items:center;gap:8px}
.slot-icon{font-size:18px;width:24px;text-align:center}
.slot-day{font-weight:600;color:var(--accent2);min-width:24px;font-size:13px;letter-spacing:.5px}
.slot-time{color:var(--muted);font-size:11.5px;font-family:ui-monospace,SFMono-Regular,monospace}
.slot-dur{margin-left:auto;font-size:11.5px;color:var(--muted);background:var(--panel2);
  padding:2px 8px;border-radius:8px;border:1px solid var(--border)}
.slot-card-name{font-size:14px;font-weight:600;margin-top:5px}
.tag-run{color:var(--run);border:1px solid rgba(126,200,227,.3);background:rgba(126,200,227,.08)}
.tag-bike{color:var(--bike);border:1px solid rgba(240,138,90,.3);background:rgba(240,138,90,.08)}
.tag-swim{color:var(--swim);border:1px solid rgba(92,214,192,.3);background:rgba(92,214,192,.08)}
.tag-ofp{color:var(--ofp);border:1px solid rgba(216,160,255,.3);background:rgba(216,160,255,.08)}
.tag-brick{color:var(--brick);border:1px solid rgba(240,198,116,.3);background:rgba(240,198,116,.08)}
.tag-cp{color:var(--cp);border:1px solid rgba(255,160,122,.3);background:rgba(255,160,122,.08)}

/* Detail view */
.topbar{display:flex;align-items:center;margin-bottom:12px;gap:8px}
.topbar button{
  background:var(--panel);border:1px solid var(--border);padding:8px 14px;
  border-radius:8px;cursor:pointer;font:inherit;color:inherit;min-height:36px;
  display:flex;align-items:center;gap:6px;
}
.topbar button:active{transform:scale(0.97)}
.topbar button .arrow{font-size:14px}

.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:14px;margin-bottom:10px}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.card-tag{font-size:10.5px;padding:3px 9px;border-radius:8px;background:var(--panel2);color:var(--muted);text-transform:lowercase;letter-spacing:.3px;font-weight:600}
.card-tag.tag-run{color:var(--run);border:1px solid rgba(126,200,227,.3);background:rgba(126,200,227,.08)}
.card-tag.tag-bike{color:var(--bike);border:1px solid rgba(240,138,90,.3);background:rgba(240,138,90,.08)}
.card-tag.tag-swim{color:var(--swim);border:1px solid rgba(92,214,192,.3);background:rgba(92,214,192,.08)}
.card-tag.tag-ofp{color:var(--ofp);border:1px solid rgba(216,160,255,.3);background:rgba(216,160,255,.08)}
.card-tag.tag-brick{color:var(--brick);border:1px solid rgba(240,198,116,.3);background:rgba(240,198,116,.08)}
.card-tag.tag-cp{color:var(--cp);border:1px solid rgba(255,160,122,.3);background:rgba(255,160,122,.08)}

.card-headline{font-size:18px;font-weight:600;margin:0 0 4px}
.card-subtitle{font-size:12.5px;color:var(--muted);margin:0 0 8px}
.card-meta{display:flex;gap:6px;font-size:11.5px;color:var(--muted);margin:6px 0;flex-wrap:wrap}
.card-meta-item{background:var(--panel2);padding:3px 8px;border-radius:6px;border:1px solid var(--border)}

/* Inventory */
.inventory{background:rgba(255,155,106,.05);border:1px dashed var(--warn);border-radius:8px;padding:10px 12px;margin-bottom:12px;font-size:13px}
.inv-title{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--warn);font-weight:600;margin-bottom:6px}
.inv-item{display:flex;gap:8px;align-items:center;padding:3px 0}
.inv-icon{font-size:14px;width:18px;text-align:center}

/* Structure */
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
.ex-list{margin-top:6px;padding-left:14px;font-size:12.5px}
.ex-item{padding:2px 0}
.ex-item b{color:var(--accent)}

/* Summary */
.totals{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:8px}
.total-cell{background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:6px;text-align:center}
.total-cell .v{font-size:16px;font-weight:600;color:var(--accent2)}
.total-cell .l{font-size:9.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-top:1px}
.delta-positive .v{color:var(--good)}
.delta-negative .v{color:var(--warn)}
.zones{display:grid;grid-template-columns:repeat(2,1fr);gap:4px;font-size:11.5px;margin-top:6px}
.zone{background:var(--panel2);padding:5px 8px;border-radius:6px;border:1px solid var(--border)}
.zone b{color:var(--accent);font-family:ui-monospace,SFMono-Regular,monospace}

footer{margin-top:18px;text-align:center;font-size:11px;color:var(--muted)}
.empty{color:var(--muted);font-style:italic;padding:14px;text-align:center}
</style></head><body>

<!-- Экран 1: список слотов -->
<div id="picker" class="picker" style="display:flex">
  <div style="margin-bottom:10px">
    <h1 style="margin:0">__PICKER_TITLE__</h1>
    <div class="sub">W__SW__ · iso __ISO__ · сезон стартовал __SEASON_START__</div>
  </div>

  <div class="card" style="background:var(--panel);padding:10px 12px;margin-bottom:10px">
    <h3>Сводка</h3>
    <div class="totals">
      <div class="total-cell"><div class="v">__PLANNED__ч</div><div class="l">planned</div></div>
      <div class="total-cell"><div class="v">__TARGET__ч</div><div class="l">target</div></div>
      <div class="total-cell __DELTA_CLASS__"><div class="v">__DELTA_SIGN____DELTA__ч</div><div class="l">delta</div></div>
    </div>
    <div class="zones">
      __ZONES_HTML__
    </div>
  </div>

  <div class="card" style="background:var(--panel);padding:10px 12px;margin-bottom:10px">
    <h3>Фаза · __PHASE_NAME__</h3>
    <p style="margin:0;font-size:12px;color:var(--muted)">__PHASE_START__ → __PHASE_END__ · target __PHASE_TARGET__ч/нед · goal __PHASE_GOAL__</p>
  </div>

  <h2 style="margin:14px 0 4px">Тренировки · __SLOTS_COUNT__ шт</h2>
  <div style="font-size:12px;color:var(--muted);margin-bottom:4px">тап → детали</div>

  __PICKER_ITEMS__

  <div class="card" style="margin-top:14px">
    <h3>Контрольные точки</h3>
    __CP_HTML__
  </div>

  <footer>self-contained · v21 · plan-w__SW__.html</footer>
</div>

<!-- Экран 2: детальная карточка -->
<div id="cardWrap" style="display:none">
  <div class="topbar">
    <button id="backBtn"><span class="arrow">←</span> назад</button>
  </div>
  <div id="cardHost"></div>
</div>

<script>
const PLAN = __PLAN_DATA__;

function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function tagClass(kind) {
  return {"run":"tag-run","bike":"tag-bike","swim":"tag-swim","ofp":"tag-ofp","brick":"tag-brick","control_point":"tag-cp"}.get(kind,"");
}

function renderSteps(structure, kind) {
  if (!structure || !structure.length) return '<div class="empty">Нет структуры</div>';
  const isOfp = kind === 'ofp' || structure.some(st => 'exercise' in st || 'set' in st);
  if (isOfp) return renderOfpSteps(structure);
  return renderHrSteps(structure);
}

function renderOfpSteps(structure) {
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
      let html = '<li class="step step-set">'
        + '<div class="step-head"><span class="step-phase">main</span>'
        + '<span class="step-dur">' + escapeHtml(String(st.duration_min||'')) + 'мин</span></div>'
        + '<div class="step-name">' + escapeHtml(st.set.name) + '</div>'
        + '<ol class="ex-list">';
      for (const ex of st.set.exercises) {
        html += '<li class="ex-item"><b>' + escapeHtml(ex.name) + '</b> · ' + escapeHtml(ex.reps)
              + (ex.rest ? ' · отдых ' + escapeHtml(ex.rest) : '') + '</li>';
      }
      return html + '</ol></li>';
    }
    return '';
  }).join('');
  return '<ol class="structure-list">' + rows + '</ol>';
}

function renderHrSteps(structure) {
  const rows = structure.map(st => {
    if (st.phase === 'set' && st.set_repeats) {
      let subHtml = st.set_repeats.map(s => {
        let pace = s.pace_min_per_km ? ' <span class="step-pace">@ ' + escapeHtml(s.pace_min_per_km) + '/км</span>' : '';
        let zone = s.zone ? '<span class="step-zone">' + escapeHtml(s.zone) + '</span>' : '';
        return '<li class="step-sub">'
          + '<div class="step-head">' + zone + '<span class="step-phase">' + escapeHtml(s.phase||'') + '</span>'
          + ' <span class="step-dur">' + escapeHtml(String(s.duration_min||'')) + 'мин</span>' + pace + '</div>'
          + (s.notes ? '<div class="step-notes">' + escapeHtml(s.notes) + '</div>' : '')
          + '</li>';
      }).join('');
      return '<li class="step step-set">'
        + '<div class="step-head"><span class="step-phase">set</span>'
        + '<span class="step-dur">' + escapeHtml(String(st.duration_min||'')) + 'мин</span>'
        + '<span class="step-reps">× ' + escapeHtml(String(st.reps||'?')) + '</span></div>'
        + '<ol class="step-sublist">' + subHtml + '</ol>'
        + (st.notes ? '<div class="step-notes">' + escapeHtml(st.notes) + '</div>' : '')
        + '</li>';
    }
    let pace = st.pace_min_per_km ? ' <span class="step-pace">@ ' + escapeHtml(st.pace_min_per_km) + '/км</span>' : '';
    let zone = st.zone ? '<span class="step-zone">' + escapeHtml(st.zone) + '</span>' : '';
    return '<li class="step">'
      + '<div class="step-head">' + zone + '<span class="step-phase">' + escapeHtml(st.phase||'') + '</span>'
      + ' <span class="step-dur">' + escapeHtml(String(st.duration_min||'')) + 'мин</span>' + pace + '</div>'
      + (st.notes ? '<div class="step-notes">' + escapeHtml(st.notes) + '</div>' : '')
      + '</li>';
  }).join('');
  return '<ol class="structure-list">' + rows + '</ol>';
}

function renderInventory(inv) {
  if (!inv || !inv.length) return '';
  const items = inv.map(i => '<div class="inv-item"><span class="inv-icon">' + escapeHtml(i.icon||'•') + '</span><span>' + escapeHtml(i.name) + '</span></div>').join('');
  return '<div class="inventory"><div class="inv-title">Что взять</div>' + items + '</div>';
}

function renderCard(slot) {
  const tc = tagClass(slot.kind);
  const tagLabel = slot.kind || '';
  const inv = slot.inventory || [];
  const invHtml = renderInventory(inv);
  let meta = '';
  if (slot.location) meta += '<span class="card-meta-item">📍 ' + escapeHtml(slot.location) + '</span>';
  if (slot.focus) meta += '<span class="card-meta-item">🎯 ' + escapeHtml(slot.focus) + '</span>';
  if (slot.subkind) meta += '<span class="card-meta-item">' + escapeHtml(slot.subkind) + '</span>';
  if (slot.workout_pending) meta += '<span class="card-meta-item" style="color:var(--warn);border-color:rgba(255,155,106,.4);background:rgba(255,155,106,.08)">Zwift pending</span>';

  const steps = renderSteps(slot.structure, slot.kind);
  return '<div class="card">'
    + '<div class="card-header"><div><div class="card-headline">' + escapeHtml(slot.name) + '</div>'
    + '<div class="card-subtitle">' + escapeHtml(slot.day) + ' ' + escapeHtml(slot.time) + ' · ' + escapeHtml(String(slot.duration_min)) + ' мин</div></div>'
    + '<div class="card-tag ' + tc + '">' + escapeHtml(tagLabel) + '</div></div>'
    + (meta ? '<div class="card-meta">' + meta + '</div>' : '')
    + invHtml
    + '<h3>Структура тренировки</h3>'
    + steps
    + '</div>';
}

function showCard(idx) {
  const slot = PLAN.slots[idx];
  if (!slot) return;
  document.getElementById('cardHost').innerHTML = renderCard(slot);
  document.getElementById('picker').style.display = 'none';
  document.getElementById('cardWrap').style.display = 'block';
  window.scrollTo(0, 0);
  if (history && history.pushState) {
    history.pushState({view:'card', idx}, '', '#slot-' + idx);
  }
}

function showList() {
  document.getElementById('picker').style.display = 'flex';
  document.getElementById('cardWrap').style.display = 'none';
  if (history && history.pushState) {
    history.pushState({view:'list'}, '', '#list');
  }
}

document.getElementById('backBtn').addEventListener('click', () => showList());
window.addEventListener('popstate', () => {
  const h = (location.hash || '').replace('#','');
  if (h.startsWith('slot-')) showCard(parseInt(h.slice(5), 10));
  else showList();
});
// Fallback: если hash установлен при загрузке (открыли по прямой ссылке), показываем карточку
document.addEventListener('DOMContentLoaded', () => {
  const h = (location.hash || '').replace('#','');
  if (h.startsWith('slot-')) showCard(parseInt(h.slice(5), 10));
});
</script>
</body></html>"""

    # Build zones HTML
    zones_html = "".join(
        f'<div class="zone"><b>{k}</b> {esc(v)}</div>' for k, v in zones.items()
    )

    # CP HTML
    if cp_in_range:
        cp_html = f'<p style="margin:0;font-size:13px">В этой неделе: {", ".join(esc(cp) for cp in cp_in_range)}</p>'
    else:
        cp_html = '<p style="margin:0;font-size:13px">Нет контрольных точек в этой неделе.</p>'

    # Заполнение плейсхолдеров
    body_filled = body
    body_filled = body_filled.replace("__TITLE__", esc(plan.get("title", "plan")))
    body_filled = body_filled.replace("__PICKER_TITLE__", esc(plan.get("title", "")))
    body_filled = body_filled.replace("__SW__", esc(str(plan.get("season_week", "?"))))
    body_filled = body_filled.replace("__ISO__", esc(plan.get("iso_week", "—")))
    body_filled = body_filled.replace("__SEASON_START__", esc(plan.get("season_start_date", "")))
    body_filled = body_filled.replace("__PLANNED__", esc(str(planned)))
    body_filled = body_filled.replace("__TARGET__", esc(str(target)))
    body_filled = body_filled.replace("__DELTA_SIGN__", delta_sign)
    body_filled = body_filled.replace("__DELTA__", esc(str(delta)))
    body_filled = body_filled.replace("__DELTA_CLASS__", delta_class)
    body_filled = body_filled.replace("__ZONES_HTML__", zones_html)
    body_filled = body_filled.replace("__PHASE_NAME__", phase_name)
    body_filled = body_filled.replace("__PHASE_START__", phase_start)
    body_filled = body_filled.replace("__PHASE_END__", phase_end)
    body_filled = body_filled.replace("__PHASE_TARGET__", esc(str(phase_target)))
    body_filled = body_filled.replace("__PHASE_GOAL__", phase_goal_id)
    body_filled = body_filled.replace("__SLOTS_COUNT__", esc(str(len(slots))))
    body_filled = body_filled.replace("__PICKER_ITEMS__", picker_html)
    body_filled = body_filled.replace("__CP_HTML__", cp_html)
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