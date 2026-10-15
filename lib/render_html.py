"""
render_html.py — plan / diff / report → self-contained HTML.

Phase 1: переиспользует ту же JSON-driven схему что ~/.hermes/coach/arch/render.py.
Разница: этот модуль в репо coach/, рендерит конкретные артефакты (plan-wN.json, weekly_report dict).
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _slot_icon(kind: str) -> str:
    icons = {
        "run": "🏃", "bike": "🚴", "swim": "🏊", "brick": "🔄",
        "control_point": "🎯", "ofp": "💪",
    }
    return icons.get(kind, "•")


def _duration_str(mins: int) -> str:
    if mins >= 60:
        h, m = mins // 60, mins % 60
        return f"{h}ч{m:02d}м" if m else f"{h}ч"
    return f"{mins}мин"


def render_plan_wN(plan: dict[str, Any], out_path: str | Path) -> Path:
    """Рендер plan-wN.json → self-contained HTML. v18: workout_pending, totals, focus, location."""
    out_path = Path(out_path)
    slots = plan.get("slots", [])
    totals = plan.get("totals", {})
    phase = plan.get("phase") or {}
    cp_in_range = plan.get("control_points_in_range", [])
    cp_slots = [s for s in slots if s.get("kind") == "control_point"]
    bike_pending = [s for s in slots if s.get("workout_pending")]

    slot_rows = []
    for s in slots:
        icon = _slot_icon(s.get("kind", ""))
        time = s.get("time", "")
        dur = _duration_str(s.get("duration_min", 0))
        name = esc(s.get("name", ""))
        kind = esc(s.get("kind", ""))
        focus = esc(s.get("focus", ""))
        loc = esc(s.get("location", ""))

        badges = []
        if focus:
            badges.append(f'<span class="badge badge-focus">{focus}</span>')
        if loc:
            badges.append(f'<span class="badge badge-loc">{loc}</span>')
        if s.get("workout_pending"):
            badges.append('<span class="badge badge-pending">Zwift pending</span>')
        if s.get("control_point_id"):
            cp_id = esc(s.get("control_point_id", ""))
            badges.append(f'<span class="badge badge-cp">CP · {cp_id}</span>')
        if s.get("workout_ref"):
            wref = esc(s.get("workout_ref", {}).get("url", "")[:40])
            badges.append(f'<span class="badge badge-workout">Zwift · {wref}…</span>')

        slot_rows.append(
            f'<li class="slot-row">'
            f'<div class="slot-head">'
            f'<span class="slot-icon">{icon}</span>'
            f'<span class="slot-day">{esc(s.get("day", ""))}</span>'
            f'<span class="slot-time">{esc(time)}</span>'
            f'<span class="slot-dur">{dur}</span>'
            f'</div>'
            f'<div class="slot-name">{name} <i>({kind})</i></div>'
            f'<div class="slot-badges">{" ".join(badges)}</div>'
            f'</li>'
        )
    slots_html = "".join(slot_rows) if slot_rows else '<li class="slot-empty"><i>Нет слотов</i></li>'

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

    vc = plan.get("volume_check", {})
    vc_suggestion = esc(vc.get("suggestion", "") or "")

    rules = plan.get("rules", {})
    hr_zones = rules.get("hr_zones", {})
    zones = hr_zones.get("zones", {})

    body = f"""<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(plan.get("title", plan.get("weekIso","plan")))}</title>
<style>
:root{{
  --bg:#0f1115;--panel:#161a22;--panel2:#1d222c;--border:#2a3140;
  --text:#e6e9ef;--muted:#9aa3b2;
  --accent:#7aa2ff;--accent2:#5cd6c0;--warn:#ff9b6a;--good:#7ee787;--cp:#d8a0ff;
}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif;
  -webkit-text-size-adjust:100%}}
.wrap{{max-width:760px;margin:0 auto;padding:18px 14px 64px}}
header{{margin-bottom:18px}}
h1{{font-size:20px;line-height:1.25;margin:0 0 6px}}
.meta{{font-size:12px;color:var(--muted);margin-bottom:14px}}
.meta b{{color:var(--text)}}
.card{{background:var(--panel);border:1px solid var(--border);border-radius:12px;
  padding:14px;margin-bottom:12px}}
.card h2{{font-size:13px;color:var(--accent);margin:0 0 10px;text-transform:uppercase;letter-spacing:.5px}}
ul{{margin:0;padding:0;list-style:none;font-size:14px;line-height:1.45}}
.slot-row{{padding:10px 0;border-bottom:1px solid var(--border)}}
.slot-row:last-child{{border-bottom:none}}
.slot-head{{display:flex;align-items:center;gap:10px;margin-bottom:4px}}
.slot-icon{{font-size:16px;width:22px;text-align:center}}
.slot-day{{font-weight:600;color:var(--accent2);min-width:24px}}
.slot-time{{color:var(--muted);font-size:12px;min-width:46px;font-family:ui-monospace,SFMono-Regular,monospace}}
.slot-dur{{margin-left:auto;font-size:12px;color:var(--muted);background:var(--panel2);
  padding:2px 8px;border-radius:8px;border:1px solid var(--border)}}
.slot-name{{font-size:14px}}
.slot-name i{{color:var(--muted);font-size:12px;font-style:normal}}
.slot-badges{{margin-top:4px;display:flex;flex-wrap:wrap;gap:4px}}
.badge{{font-size:10.5px;padding:2px 7px;border-radius:8px;border:1px solid var(--border);
  background:var(--panel2);color:var(--muted);font-family:ui-monospace,SFMono-Regular,monospace}}
.badge-focus{{color:var(--accent2);border-color:rgba(92,214,192,.3)}}
.badge-loc{{color:var(--muted)}}
.badge-pending{{color:var(--warn);border-color:rgba(255,155,106,.4);background:rgba(255,155,106,.08)}}
.badge-cp{{color:var(--cp);border-color:rgba(216,160,255,.4);background:rgba(216,160,255,.08)}}
.badge-workout{{color:var(--good);border-color:rgba(126,231,135,.4);background:rgba(126,231,135,.08)}}
.totals{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}
.total-cell{{background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:8px;text-align:center}}
.total-cell .v{{font-size:18px;font-weight:600;color:var(--accent2)}}
.total-cell .l{{font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-top:2px}}
.delta-positive .v{{color:var(--good)}}
.delta-negative .v{{color:var(--warn)}}
.zones{{display:grid;grid-template-columns:repeat(2,1fr);gap:6px;font-size:12px}}
.zone{{background:var(--panel2);padding:6px 10px;border-radius:6px;border:1px solid var(--border)}}
.zone b{{color:var(--accent);font-family:ui-monospace,SFMono-Regular,monospace}}
.suggestion{{margin-top:8px;padding:8px;background:rgba(255,155,106,.08);border-left:3px solid var(--warn);
  border-radius:6px;font-size:12.5px}}
.suggestion:empty{{display:none}}
footer{{margin-top:18px;text-align:center;font-size:11px;color:var(--muted)}}
</style></head><body><div class="wrap">
<header>
  <h1>{esc(plan.get("title",""))}</h1>
  <div class="meta">
    <b>W{plan.get("season_week","?")}</b> · iso {esc(plan.get("iso_week","—"))} ·
    сезон стартовал {esc(plan.get("season_start_date",""))}
  </div>
</header>

<div class="card">
  <h2>Сводка</h2>
  <div class="totals">
    <div class="total-cell">
      <div class="v">{planned}ч</div>
      <div class="l">planned</div>
    </div>
    <div class="total-cell">
      <div class="v">{target}ч</div>
      <div class="l">target</div>
    </div>
    <div class="total-cell {delta_class}">
      <div class="v">{delta_sign}{delta}ч</div>
      <div class="l">delta</div>
    </div>
  </div>
  <div class="zones" style="margin-top:10px">
    {''.join(f'<div class="zone"><b>{k}</b> {esc(v)}</div>' for k, v in zones.items())}
  </div>
</div>

<div class="card">
  <h2>Фаза · {phase_name}</h2>
  <p style="margin:0;font-size:13px;color:var(--muted)">
    {phase_start} → {phase_end} · target {phase_target}ч/нед · goal {phase_goal_id}
  </p>
  <div class="suggestion">{vc_suggestion}</div>
</div>

<div class="card">
  <h2>Слоты · {len(slots)} шт</h2>
  <ul>{slots_html}</ul>
</div>

<div class="card">
  <h2>Контрольные точки</h2>
  <p style="margin:0;font-size:13px">
    {('В этой неделе: ' + ', '.join(esc(cp) for cp in cp_in_range)) if cp_in_range else 'Нет контрольных точек в этой неделе.'}
  </p>
  {f'<p style="margin:8px 0 0;font-size:12px;color:var(--muted)">CP-слотов: {len(cp_slots)}</p>' if cp_slots else ''}
</div>

{('<div class="card"><h2>Zwift workouts pending</h2><p style="margin:0;font-size:13px">' +
  f'{len(bike_pending)} bike/brick слот-ов ждут workout_ref. Скажи "переподбери workout на слот <id>" или подожди Phase 3 с inline Zwift.' +
  '</p></div>') if bike_pending else ''}

<footer>
  self-contained · v18 · plan-w{plan.get("season_week", "?")}.html
</footer>
</div></body></html>"""
    out_path.write_text(body, encoding="utf-8")
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