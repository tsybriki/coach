#!/usr/bin/env python3
"""
render_subsystems.py — рендер архитектуры подсистем из subsystems.json.

Запуск:
    python3 v2.architecture/render_subsystems.py

На входе:  subsystems.json (source of truth)
На выходе: SUBSYSTEMS.html (self-contained, читается с телефона офлайн)
"""
from __future__ import annotations

import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "subsystems.json")
OUT = os.path.join(HERE, "SUBSYSTEMS.html")

# палитра — из DOMAIN-SPEC.html (домен Coach App)
PALETTE = {
    "bg": "#fdf6ed",
    "card": "#fffefb",
    "ink": "#1a1a1a",
    "muted": "#6a6056",
    "faint": "#9a9085",
    "border": "#e6dac4",
    "code": "#f4ede0",
    "planner": "#c2410c",
    "input": "#6a6056",
    "state": "#0284c7",
    "fact": "#0b7d71",
    "delivery": "#a17405",
    "narrator": "#7c3aed",
    "entry": "#d4a017",
}

TONE_FILL = {
    "planner": "rgba(194,65,12,0.06)",
    "input": "rgba(106,96,86,0.06)",
    "state": "rgba(2,132,199,0.06)",
    "fact": "rgba(20,184,166,0.08)",
    "delivery": "rgba(212,160,23,0.08)",
    "narrator": "rgba(124,58,237,0.06)",
    "entry": "rgba(212,160,17,0.10)",
}


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def svg_diagram(d: dict) -> str:
    parts = [f'<svg viewBox="{esc(d["viewBox"])}" role="img" aria-label="Схема подсистем">']

    # 1. стрелки — под блоками (z-order)
    for a in d.get("arrows", []):
        plain = a.get("plain")
        dash = "" if plain else ' stroke-dasharray="5,3"'
        arrow = "" if plain else ' marker-end="url(#ar)"'
        parts.append(
            f'<path d="{esc(a["path"])}" fill="none" stroke="{PALETTE["muted"]}" '
            f'stroke-width="1.2"{dash}{arrow}/>'
        )
        bx, by = a["badge"]
        parts.append(
            f'<circle cx="{bx}" cy="{by}" r="7.5" fill="{PALETTE["card"]}" '
            f'stroke="{PALETTE["muted"]}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{bx}" y="{by + 2.8}" font-size="8" font-weight="700" '
            f'fill="{PALETTE["muted"]}" text-anchor="middle">{esc(a["n"])}</text>'
        )

    # 2. блоки
    for b in d.get("boxes", []):
        tone = b.get("tone", "input")
        color = PALETTE.get(tone, PALETTE["muted"])
        fill = TONE_FILL.get(tone, "rgba(106,96,86,0.05)")
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        container = b.get("container")
        dash = ' stroke-dasharray="8,5"' if container else ""
        parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" '
            f'stroke="{color}" stroke-width="{1.5 if container else 1.2}"{dash}/>'
        )
        ty = y + 15
        parts.append(
            f'<text x="{x + 10}" y="{ty}" font-size="10.5" font-weight="700" '
            f'fill="{color}">{esc(b["title"])}</text>'
        )
        for ln in b.get("lines", []):
            ty += 12
            parts.append(
                f'<text x="{x + 10}" y="{ty}" font-size="8.3" fill="{PALETTE["muted"]}">'
                f'{esc(ln)}</text>'
            )
        if b.get("foot"):
            ty += 12
            parts.append(
                f'<text x="{x + 10}" y="{ty}" font-size="7.6" fill="{PALETTE["faint"]}" '
                f'font-style="italic">{esc(b["foot"])}</text>'
            )

    parts.append(
        '<defs><marker id="ar" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">'
        f'<polygon points="0 0, 9 3.5, 0 7" fill="{PALETTE["muted"]}"/></marker></defs>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def render(d: dict) -> str:
    m = d["meta"]
    out: list[str] = []
    A = out.append

    A("<!DOCTYPE html>")
    A('<html lang="ru"><head><meta charset="UTF-8">')
    A('<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">')
    A(f'<title>{esc(d["title"])}</title>')
    A("<style>")
    A(f"""
  :root {{
    --bg:{PALETTE['bg']}; --card-bg:{PALETTE['card']}; --ink:{PALETTE['ink']};
    --muted:{PALETTE['muted']}; --faint:{PALETTE['faint']}; --border:{PALETTE['border']};
    --code-bg:{PALETTE['code']}; --planner:{PALETTE['planner']}; --state:{PALETTE['state']};
    --fact:{PALETTE['fact']}; --delivery:{PALETTE['delivery']}; --narrator:{PALETTE['narrator']};
    --entry:{PALETTE['entry']}; --input:{PALETTE['input']};
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  html {{ -webkit-text-size-adjust:100%; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    background:var(--bg); color:var(--ink); line-height:1.5; font-size:16px; padding-bottom:48px; }}
  code {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}

  header {{ padding:16px 14px 12px; border-bottom:1px solid var(--border); background:var(--card-bg); }}
  header h1 {{ font-size:19px; font-weight:700; }}
  header .sub {{ font-size:12.5px; color:var(--muted); margin-top:4px; }}
  header .meta {{ font-size:11px; color:var(--faint); margin-top:6px; line-height:1.6; }}

  nav {{ position:sticky; top:0; z-index:10; background:rgba(253,246,237,.96); backdrop-filter:blur(8px);
    border-bottom:1px solid var(--border); overflow-x:auto; white-space:nowrap; padding:7px 12px; scrollbar-width:none; }}
  nav::-webkit-scrollbar {{ display:none; }}
  nav a {{ display:inline-block; font-size:12px; color:var(--muted); text-decoration:none;
    padding:4px 9px; margin-right:4px; border:1px solid var(--border); border-radius:999px; background:var(--card-bg); }}

  main {{ padding:0 12px; max-width:780px; margin:0 auto; }}
  section {{ margin-top:26px; }}
  .h2 {{ font-size:16px; font-weight:700; padding-bottom:6px; border-bottom:2px solid var(--ink); margin-bottom:10px; }}
  h3 {{ font-size:14px; font-weight:700; margin:16px 0 6px; }}
  p {{ font-size:14.5px; margin-bottom:8px; }}
  .lead {{ font-size:14px; color:var(--muted); }}
  .muted {{ color:var(--muted); }}

  .dia {{ background:var(--card-bg); border:1px solid var(--border); border-radius:10px; padding:8px; overflow-x:auto; }}
  .dia svg {{ width:100%; min-width:340px; display:block; }}
  .cap {{ font-size:12px; color:var(--muted); margin-top:7px; }}

  .legend {{ display:flex; flex-wrap:wrap; gap:6px 14px; margin-top:9px; }}
  .legend span {{ display:inline-flex; align-items:center; gap:5px; font-size:11.5px; color:var(--muted); }}
  .legend i {{ width:11px; height:11px; border-radius:3px; border:1.5px solid; display:inline-block; }}

  .tw {{ overflow-x:auto; -webkit-overflow-scrolling:touch; margin:6px 0 12px; position:relative; }}
  table {{ border-collapse:collapse; width:100%; min-width:440px; font-size:12.5px; }}
  th,td {{ text-align:left; padding:6px 7px; border-bottom:1px solid var(--border); vertical-align:top; }}
  th {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted);
    font-weight:700; background:var(--code-bg); }}
  td.n {{ white-space:nowrap; color:var(--faint); font-weight:700; }}

  .ent {{ border:1px solid var(--border); border-radius:8px; background:var(--card-bg);
    margin-bottom:8px; overflow:hidden; }}
  .ent .eh {{ background:var(--ink); color:#fff; padding:5px 10px; font-size:13px; font-weight:700;
    display:flex; justify-content:space-between; gap:8px; align-items:center; }}
  .ent .eh .st {{ font-size:10px; font-weight:700; padding:1px 8px; border-radius:999px;
    background:rgba(255,255,255,.2); white-space:nowrap; }}
  .ent .bd {{ padding:9px 11px; font-size:12.5px; }}
  .ent .bd p {{ font-size:12.5px; margin-bottom:5px; }}
  .ent .bd .lab {{ color:var(--faint); font-size:10px; text-transform:uppercase; letter-spacing:.04em; }}
  .ent .bd b {{ font-weight:700; }}

  .planner {{ border:2px solid var(--planner); border-radius:10px; background:rgba(194,65,12,.04);
    padding:10px 11px; margin-bottom:10px; }}
  .planner > .ph {{ font-size:14px; font-weight:700; color:var(--planner); margin-bottom:3px; }}
  .planner > .ps {{ font-size:12.5px; color:var(--muted); margin-bottom:10px; }}
  .ent3 {{ border:1px solid var(--entry); border-radius:8px; background:var(--card-bg);
    padding:9px 10px; margin-bottom:8px; }}
  .ent3 .t {{ font-size:12.5px; font-weight:700; color:var(--entry); margin-bottom:4px; }}
  .ent3 ol {{ margin:0; padding-left:20px; font-size:12.5px; }}
  .ent3 ol li {{ margin-bottom:3px; }}
  .ent3 .kv {{ font-size:12px; margin-top:6px; }}
  .ent3 .kv div {{ margin-bottom:3px; }}
  .ent3 .kv b {{ color:var(--muted); font-weight:700; }}

  .fork {{ border:1px solid var(--border); border-radius:8px; background:var(--card-bg);
    padding:9px 11px; margin-bottom:8px; }}
  .fork .fq {{ font-size:13px; font-weight:700; margin-bottom:6px; }}
  .fork .opt {{ font-size:12.5px; margin-bottom:4px; }}
  .fork .opt b {{ font-weight:700; }}
  .fork .ch {{ font-size:12px; color:var(--muted); margin-top:6px; }}

  .note {{ background:var(--code-bg); border:1px solid var(--border); border-radius:8px;
    padding:9px 11px; font-size:12.5px; margin-bottom:8px; }}

  .link {{ border:1px solid var(--border); border-radius:8px; background:var(--card-bg);
    padding:8px 10px; margin-bottom:6px; }}
  .link .ln {{ display:flex; align-items:baseline; gap:6px; font-size:12.5px; font-weight:700; }}
  .link .ln .nb {{ display:inline-block; min-width:17px; height:17px; line-height:17px; text-align:center;
    border-radius:50%; background:var(--code-bg); border:1px solid var(--border); color:var(--muted);
    font-size:10px; font-weight:700; flex:0 0 auto; }}
  .link .ln .ar {{ color:var(--faint); font-weight:400; }}
  .link .ln .to {{ color:var(--state); }}
  .link .lw {{ font-size:12.5px; color:var(--ink); margin-top:3px; padding-left:23px; }}
  .link .lwh {{ font-size:11.5px; color:var(--faint); margin-top:1px; padding-left:23px; }}

  hr {{ border:none; border-top:1px solid var(--border); margin:22px 0 0; }}
  .end {{ text-align:center; font-size:11.5px; color:var(--faint); padding:20px 0 8px; }}

  @media (max-width:560px) {{
    main {{ padding:0 10px; }}
    header h1 {{ font-size:17px; }}
    p {{ font-size:14px; }}
    table {{ min-width:400px; font-size:12px; }}
    .tw::after {{ content:'→ свайп'; position:absolute; right:2px; bottom:2px; font-size:9px;
      color:var(--faint); background:var(--card-bg); padding:0 4px; pointer-events:none; }}
  }}
""")
    A("</style></head><body>")

    # ---- header
    A("<header>")
    A(f'<h1>{esc(d["title"])}</h1>')
    A(f'<div class="sub">{esc(d["subtitle"])}</div>')
    A(f'<div class="meta">v{esc(d["version"])} · подсистем: {m["subsystems"]} · '
      f'взаимодействий: {m["interactions"]} · развилок: {m["forks"]}</div>')
    A(f'<div class="meta">{esc(m["base"])}</div>')
    A("</header>")

    # ---- nav
    A("<nav>")
    A('<a href="#d">1 · Схема</a>')
    A('<a href="#p">2 · Планировщик</a>')
    A('<a href="#s">3 · Подсистемы</a>')
    A('<a href="#i">4 · Взаимодействия</a>')
    A('<a href="#f">5 · Развилки</a>')
    A("</nav>")

    A("<main>")

    # ---- 1 диаграмма
    A('<section id="d">')
    A('<div class="h2">1 · Схема подсистем</div>')
    A(f'<p class="lead">{esc(d["lead"])}</p>')
    A('<div class="dia">')
    A(svg_diagram(d["diagram"]))
    A("</div>")
    A('<div class="legend">')
    for lg in d["diagram"]["legend"]:
        tone = lg["tone"]
        color = PALETTE.get(tone, PALETTE["muted"])
        A(f'<span><i style="border-color:{color};background:{TONE_FILL.get(tone,"#fff")}"></i>'
          f'{esc(lg["text"])}</span>')
    A("</div>")
    A(f'<p class="cap">{esc(d["diagram"]["caption"])}</p>')
    A("</section>")

    # ---- 2 планировщик
    A('<section id="p">')
    A('<div class="h2">2 · Планировщик</div>')
    A(f'<p class="lead">{esc(d["planner"]["lead"])}</p>')
    for e in d["planner"]["entries"]:
        A('<div class="ent3">')
        A(f'<div class="t">{esc(e["name"])}</div>')
        A('<ol>')
        for s in e["steps"]:
            A(f'<li>{esc(s)}</li>')
        A("</ol>")
        A('<div class="kv">')
        A(f'<div><b>вход</b> {esc(e["input"])}</div>')
        A(f'<div><b>цифры</b> {esc(e["numbers"])}</div>')
        if e.get("have"):
            A(f'<div><b>есть</b> {esc(e["have"])}</div>')
        if e.get("missing"):
            A(f'<div><b>нет</b> {esc(e["missing"])}</div>')
        A("</div>")
        A("</div>")
    A("</section>")

    # ---- 3 подсистемы
    A('<section id="s">')
    A('<div class="h2">3 · Подсистемы</div>')
    for s in d["subsystems"]:
        tone_color = PALETTE.get(
            {"есть": "fact", "частично": "entry", "нет": "faint"}.get(s["status"], "input"),
            PALETTE["muted"],
        )
        A('<div class="ent">')
        A('<div class="eh">')
        A(f'<span>{esc(s["name"])}</span>')
        A(f'<span class="st" style="background:{tone_color};color:#fff">{esc(s["status"])}</span>')
        A("</div>")
        A('<div class="bd">')
        A(f'<p>{esc(s["role"])}</p>')
        A(f'<div><span class="lab">владеет</span><br>{esc(s["owns"])}</div>')
        A(f'<div style="margin-top:6px"><span class="lab">вход</span><br>{esc(s["in"])}</div>')
        if s.get("detail"):
            A(f'<p class="muted" style="margin-top:6px">{esc(s["detail"])}</p>')
        A("</div>")
        A("</div>")
    A("</section>")

    # ---- 4 взаимодействия
    A('<section id="i">')
    A('<div class="h2">4 · Взаимодействия</div>')
    for it in d["interactions"]:
        A('<div class="link">')
        A(f'<div class="ln"><span class="nb">{it["n"]}</span>'
          f'<span class="fr">{esc(it["from"])}</span>'
          f'<span class="ar">→</span>'
          f'<span class="to">{esc(it["to"])}</span></div>')
        A(f'<div class="lw">{esc(it["what"])}</div>')
        A(f'<div class="lwh">{esc(it["when"])}</div>')
        A("</div>")
    A("</section>")

    # ---- 5 развилки
    A('<section id="f">')
    A('<div class="h2">5 · Развилки</div>')
    for f in d["forks"]:
        A('<div class="fork">')
        A(f'<div class="fq">{f["n"]}. {esc(f["question"])}</div>')
        A(f'<div class="opt"><b>A</b> — {esc(f["a"])}</div>')
        A(f'<div class="opt"><b>B</b> — {esc(f["b"])}</div>')
        A(f'<div class="ch">что меняет: {esc(f["changes"])}</div>')
        A("</div>")
    A("</section>")

    # ---- notes
    A('<section id="n">')
    A('<div class="h2">Замечания по текущему состоянию</div>')
    for n in d.get("notes", []):
        A(f'<div class="note">{esc(n)}</div>')
    A("</section>")

    A("<hr>")
    A(f'<p class="end">Coach App · подсистемы v{esc(d["version"])}</p>')
    A("</main></body></html>")

    return "\n".join(out)


def main() -> int:
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)
    html_text = render(data)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html_text)
    print(f"written: {OUT} ({os.path.getsize(OUT)} bytes)")
    print(f"subsystems={len(data['subsystems'])} interactions={len(data['interactions'])} "
          f"forks={len(data['forks'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
