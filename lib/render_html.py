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

    v26: точная копия архитектуры из w1-mobile.html (который работал у Кирилла).
    Тёмная цветовая гамма, structure/inventory из coach-данных.
    """
    out_path = Path(out_path)
    slots = plan.get("slots", [])
    rules = plan.get("rules", {})

    # Сериализуем планные данные в формате который ожидает JS в renderCard():
    # {id, day, time, name, short, kind, subkind, focus, location, duration_min,
    #  structure: [...], inventory: [...]}
    # Дополнительно для picker: title, weekIso, subtitle, rules.hr_zones
    hrz = rules.get("hr_zones")
    if isinstance(hrz, dict):
        hrz_str = ", ".join(f"{k}={v.get('bpm', v)}" if isinstance(v, dict) else f"{k}={v}" for k, v in hrz.get("zones", {}).items())
    elif isinstance(hrz, str):
        hrz_str = hrz
    else:
        hrz_str = ""

    plan_data = {
        "title": plan.get("title", "Тренировки"),
        "weekIso": f"W{plan.get('season_week', '?')}",
        "subtitle": f"iso {plan.get('iso_week', '—')} · сезон с {plan.get('season_start_date', '?')}",
        "rules": {
            "hr_zones": hrz_str,
        },
        "slots": [
            {
                "id": s.get("id"),
                "day": s.get("day"),
                "time": s.get("time"),
                "name": s.get("name"),
                "short": s.get("name", ""),  # в w1-mobile.html `short` — это краткое описание (например "Easy 5К low-Z2")
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

.plan-title{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:12px 16px;margin-bottom:4px}
.plan-title h1{font-size:18px;margin:0}
.plan-title .week{font-size:12px;color:var(--muted);margin-top:2px}
.plan-rules{font-size:11px;color:var(--muted);margin-top:6px;line-height:1.4}

.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:14px;margin-bottom:12px}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.card-subtitle{font-size:11px;color:var(--muted);margin-top:2px}
.card-tag{font-size:10.5px;padding:3px 9px;border-radius:8px;background:var(--panel2);color:var(--muted);text-transform:lowercase;letter-spacing:.3px;font-weight:600}
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
.ex-list{margin-top:6px;padding-left:14px;font-size:12.5px}
.ex-item{padding:2px 0}
.ex-item b{color:var(--accent)}

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

function renderHrStructure(structure) {
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
  return '<div class="inventory"><div class="inv-title">📦 Что нужно</div>' + items + '</div>';
}

function renderCard(slot) {
  const inventory = slot.inventory || [];
  const invHtml = renderInventory(inventory);
  const kind = slot.kind || '';
  const kindIcon = KIND_ICON[kind] || '🎯';
  const tag = (slot.structure && slot.structure.length) || '?';

  // Meta items
  let metaHtml = '';
  if (slot.location) metaHtml += '<span class="card-meta-item">📍 ' + escapeHtml(slot.location) + '</span>  ';
  if (slot.focus) metaHtml += '<span class="card-meta-item">🎯 ' + escapeHtml(slot.focus) + '</span>  ';
  if (slot.subkind) metaHtml += '<span class="card-meta-item">' + escapeHtml(slot.subkind) + '</span>  ';
  if (slot.workout_pending) metaHtml += '<span class="card-meta-item" style="color:var(--warn);border-color:rgba(255,155,106,.4);background:rgba(255,155,106,.08)">Zwift pending</span>';

  const stepsHtml = renderStructure(slot.structure, kind);

  return '<div class="card">'
    + '<div class="card-header">'
    + '<div>'
    + '<div style="font-size:20px;margin-right:8px;display:inline-block;vertical-align:middle">' + kindIcon + '</div>'
    + '<h2 style="display:inline-block;vertical-align:middle;margin:0">' + escapeHtml(slot.name) + '</h2>'
    + '<div class="card-subtitle">' + escapeHtml(slot.day) + ' · ' + escapeHtml(slot.time) + ' · '
    + escapeHtml(String(slot.duration_min)) + ' мин</div>'
    + '</div>'
    + '<div class="card-tag kind-' + escapeHtml(kind) + '">' + escapeHtml(tag) + ' шагов</div>'
    + '</div>'
    + (metaHtml ? '<div style="font-size:11.5px;color:var(--muted);margin:6px 0;display:flex;gap:6px;flex-wrap:wrap">' + metaHtml + '</div>' : '')
    + invHtml
    + '<h3>Структура тренировки</h3>'
    + stepsHtml
    + '</div>';
}

function buildPicker(plan) {
  ACTIVE_WEEK_KEY = plan.weekIso || plan.season_week || null;
  let html = '<div class="plan-title">';
  html += '<h1>' + escapeHtml(plan.title || 'Тренировки') + '</h1>';
  if (plan.weekIso) html += '<div class="week">' + escapeHtml(plan.weekIso) + '</div>';
  if (plan.subtitle) html += '<div class="week">' + escapeHtml(plan.subtitle) + '</div>';
  if (plan.rules && plan.rules.hr_zones) {
    const hrz = (typeof plan.rules.hr_zones === 'string') ? plan.rules.hr_zones : JSON.stringify(plan.rules.hr_zones);
    html += '<div class="plan-rules">HR: ' + escapeHtml(hrz) + '</div>';
  }
  html += '</div>';

  // Слоты
  for (const s of (plan.slots || [])) {
    html += '<button class="slot" data-slot="' + escapeHtml(s.id) + '">';
    html += '<div class="day">' + escapeHtml(s.day) + ' · ' + escapeHtml(s.time) + '</div>';
    html += '<div class="name">' + escapeHtml(s.name) + '</div>';
    if (s.short) html += '<div class="desc">' + escapeHtml(s.short) + '</div>';
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