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


def render_plan_wN(plan: dict[str, Any], out_path: str | Path) -> Path:
    """Простой рендер plan-wN.json → wN-mobile.html (Phase 1: предельно простой)."""
    out_path = Path(out_path)
    slots = plan.get("slots", [])
    slots_html = "".join(
        f"<li><b>{esc(s.get('day'))} {esc(s.get('time'))}</b> — {esc(s.get('name'))} <i>({esc(s.get('kind'))})</i></li>"
        for s in slots
    )
    cp = plan.get("control_points_in_range", [])
    cp_html = ", ".join(esc(c) for c in cp) or "—"

    body = f"""
<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(plan.get('title', plan.get('weekIso', 'plan')))}</title>
<style>
:root{{--bg:#0f1115;--panel:#161a22;--accent:#7aa2ff;--text:#e6e9ef;--muted:#9aa3b2}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,Roboto,sans-serif;padding:18px 14px}}
.wrap{{max-width:760px;margin:0 auto}}
h1{{font-size:18px;margin:0 0 12px}}
.card{{background:var(--panel);border-radius:12px;padding:14px;margin-bottom:12px}}
.card h2{{font-size:14px;color:var(--accent);margin:0 0 8px}}
ul{{margin:0;padding-left:18px;font-size:14px;line-height:1.5}}
.meta{{font-size:12px;color:var(--muted);margin-bottom:14px}}
</style></head><body><div class="wrap">
<header><h1>{esc(plan.get('title', ''))}</h1>
<div class="meta">W{esc(plan.get('season_week', '?'))} · {esc(plan.get('weekIso', '—'))} · CP в диапазоне: {cp_html}</div></header>
<div class="card"><h2>Слоты</h2>
<ul>{slots_html or '<li><i>(Phase 1 stub: слоты пока пустые)</i></li>'}</ul></div>
<div class="card"><h2>Фаза</h2>
<p>{esc((plan.get('phase') or {}).get('name', '—'))} · target {esc((plan.get('phase') or {}).get('hours_per_week_target', '—'))}ч/нед</p></div>
<footer style="text-align:center;font-size:11px;color:var(--muted);margin-top:18px">
self-contained · Phase 1 stub
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