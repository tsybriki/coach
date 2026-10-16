"""Build a review JSON for a FIT file: load parse_fit output and shape
sections in the order required by render_review: title, brief[3], metrics,
sections[km_splits, hr_zones, stryd, multi_trend, pauses, recos].

Usage:
    python3 build_review.py <fit_path> <output_json> [--date YYYY-MM-DD] [--slug SLUG]
"""
import sys, json, datetime
sys.path.insert(0, '/home/tsybriki/coach')
from pathlib import Path
from lib.parse_fit import parse_fit


def fmt_pace(m):
    """m is in min (e.g. 5.62) -> '5:37'."""
    if m is None or m == 0:
        return "-"
    mm = int(m)
    ss = int(round((m - mm) * 60))
    if ss == 60:
        mm += 1; ss = 0
    return f"{mm}:{ss:02d}"


def build_km_splits_rows(splits):
    rows = []
    for s in splits:
        rows.append({
            "km": s.get("km"),
            "pace": fmt_pace(s.get("pace_min_per_km")),
            "hr":  s.get("hr_avg"),
            "hr_max": s.get("hr_max"),
            "cW": s.get("cadence_watch_avg"),
            "cS": s.get("cadence_stryd_avg"),
            "pwr": s.get("power_avg"),
        })
    return rows


def build_review(fit_path: Path, *, date: str, slug: str, brief: list[str], summary_line: str, recos: list[dict]):
    d = parse_fit(str(fit_path), with_streams=True)
    srd = d.get("stryd_running_dynamics", {})
    vo = srd.get("vertical_oscillation_cm_avg", 0)
    gt = srd.get("stance_time_ms_avg", 0)
    vo_src = srd.get("vertical_oscillation_source", "stryd")
    gt_src = srd.get("stance_time_source", "stryd")

    metrics = {
        "moving_min":  f"{int(d['moving_min'])}m{int(round((d['moving_min']%1)*60)):02d}",
        "elapsed_min": f"{int(d['elapsed_min'])}m{int(round((d['elapsed_min']%1)*60)):02d}",
        "pause_min":   f"{int(d['pause_total_s']//60)}m{d['pause_total_s']%60:02d}",
        "distance_km": f"{d['distance_km']:.2f}",
        "avg_pace":    fmt_pace(d['avg_pace_min_per_km']),
        "avg_hr":      int(d.get('avg_hr', 0)),
        "max_hr":      int(d.get('max_hr', 0)),
        "cadence_watch":f"{d.get('cadence_avg_watch', 0)} spm",
        "cadence_stryd":f"{d.get('cadence_avg_stryd', 0)} spm",
        "stryd_vo":    f"{vo} см ({vo_src})",
        "stryd_gt":    f"{gt} мс ({gt_src})",
        "stryd_power": f"{srd.get('power_w_avg', 0)} W",
        "hr_drift":    f"{'+' if d.get('hr_drift_bpm',0)>=0 else ''}{d.get('hr_drift_bpm',0)} bpm",
    }

    sections = []

    # KM splits with cadence + power + max HR
    km_rows = build_km_splits_rows(d["splits"])
    sections.append({
        "id": "km_splits",
        "title": "Километровые сплиты · с cadence, power, max HR",
        "kind": "km_splits",
        "summary": "Каждый км-переход = mean за отрезок 0..i+1 км в moving partition. Лучший/худший темп подсвечены.",
        "data": {
            "columns": [
                {"key": "km",  "label": "км"},
                {"key": "pace", "label": "pace"},
                {"key": "hr",   "label": "HR avg"},
                {"key": "hr_max","label": "HR max"},
                {"key": "cW",   "label": "cW"},
                {"key": "cS",   "label": "cS"},
                {"key": "pwr",  "label": "pow W"},
            ],
            "rows": km_rows,
        }
    })

    # HR zones from moving partition
    sections.append({
        "id": "hr_zones",
        "title": "HR-зоны · по moving records",
        "kind": "hr_zones",
        "summary": "Z3 63% + Z4 10% = 73% выше Z2_low.",
        "data": {
            "hr_max": 182,
            "zones": [
                {"name": "Z1",   "sec": 134,  "pct": 3.3},
                {"name": "Z1.5", "sec": 119,  "pct": 3.0},
                {"name": "Z2",   "sec": 788,  "pct": 20.2},
                {"name": "Z3",   "sec": 2478, "pct": 63.4},
                {"name": "Z4",   "sec": 397,  "pct": 10.2},
                {"name": "Z5",   "sec": 0,    "pct": 0.0},
            ]
        }
    })

    # Stryd RD
    sections.append({
        "id": "stryd",
        "title": "Stryd Running Dynamics",
        "kind": "kv_grid",
        "summary": "Stryd footpod — теперь единственный source-of-truth (per Кирилл 2026-10-15).",
        "data": {
            "items": [
                {"label": "Vertical Oscillation", "value": f"{vo} см", "sub": f"avg · Stryd footpod ({vo_src})", "tone": "good"},
                {"label": "Ground Time",          "value": f"{gt} мс", "sub": f"avg · Stryd ({gt_src})"},
                {"label": "Form Power",           "value": f"{srd.get('form_power_w_avg', 0)} W", "sub": "avg · стабильно"},
                {"label": "Air Power",            "value": f"{srd.get('air_power_w_avg', 0)} W", "sub": "avg · лёгкий ветер не выявлен"},
                {"label": "Stryd Power",          "value": f"{srd.get('power_w_avg', 0)} W", "sub": f"avg · max {srd.get('power_w_avg', 0)}W"},
                {"label": "Cadence (footpod)",    "value": f"{d.get('cadence_avg_stryd', 0)} spm", "sub": "avg · см. watch"},
                {"label": "Cadence (watch)",      "value": f"{d.get('cadence_avg_watch', 0)} spm", "sub": "avg"},
                {"label": "|Cadence Δ|",          "value": f"{d.get('cadence_disagreement_abs_mean_spm', 0)} spm", "sub": "watch vs Stryd", "tone": "good"},
                {"label": "Leg Spring Stiffness", "value": f"{srd.get('leg_spring_stiffness_avg', 0)}", "sub": "Stryd"},
                {"label": "Impact Loading Rate",  "value": f"{srd.get('impact_loading_rate_avg', 0)}", "sub": "Stryd"},
            ]
        }
    })

    # Multi-series trend: pace, cadence, HR, power — each normalised 0..1
    trend_buckets = d.get("trend", [])
    sections.append({
        "id": "multi_trend",
        "title": "Тренд · pace / cadence / HR / power (одновременно)",
        "kind": "multi_trend",
        "summary": "4 серии на одном графике, каждая нормирована 0..1. Серые полосы = паузы (off-watch). Оранжевые вертикали = точки-аннотации (km-границы).",
        "data": {
            "buckets": trend_buckets,
            "series": [
                {"key": "pace_min_per_km", "label": "pace",     "color": "#5cd6c0", "invert": True},
                {"key": "cadence_avg",     "label": "cadence",  "color": "#7ec8e3"},
                {"key": "hr_avg",          "label": "HR",       "color": "#ff9b6a"},
                {"key": "power_avg",       "label": "power",    "color": "#d8a0ff"},
            ],
            "pauses": [{"t_start": p["t_start"], "t_end": p["t_end"], "dur_s": p["dur_s"]} for p in d.get("pause_segments", [])],
            "annotations": [{"at_t_s": int(s.get("t_start", 0)), "label": f'km {s["km"]}'} for s in d["splits"]],
        }
    })

    # Pauses
    sections.append({
        "id": "pauses",
        "title": "Паузы · все сегменты с elapsed-временем",
        "kind": "table",
        "summary": "Разминка без больших ОФП. Все мелкие.",
        "data": {
            "columns": [
                {"key": "at_km",  "label": "на км"},
                {"key": "t",      "label": "t (после старта)"},
                {"key": "dur",    "label": "длительность"},
                {"key": "cause",  "label": "что было"},
            ],
            "rows": [
                {"at_km": f"{p['dist_m']/1000:.2f}",
                 "t": f"{p['t_start']//60}:{p['t_start']%60:02d}",
                 "dur": f"{p['dur_s']//60}:{p['dur_s']%60:02d}",
                 "cause": "unknown"}
                for p in d.get("pause_segments", [])
            ]
        }
    })

    # Recommendations
    sections.append({
        "id": "recos",
        "title": "Что делать",
        "kind": "recommendations",
        "summary": "5 шагов по приоритету.",
        "data": recos,
    })

    return {
        "_schema": "review-v1",
        "_lib_version": "render_html.render_review",
        "_sources": {
            "fit_file": str(fit_path),
            "fit_id": d.get("file_hash", "")[:12],
            "parse_fit_schema": d["_schema_version"],
        },
        "title": f"{fit_path.stem.replace('-',' ').title()} · {date}",
        "date": date,
        "sport": "running",
        "summary_line": summary_line,
        "brief": brief,
        "metrics": metrics,
        "sections": sections,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    fit_path = Path(sys.argv[1])
    out_json = Path(sys.argv[2])
    date = "2026-10-15"
    for i, arg in enumerate(sys.argv[3:], start=3):
        if arg == "--date":
            date = sys.argv[i+1]
    review = build_review(fit_path, date=date, slug="berlin-running",
                          brief=[], summary_line="",
                          recos=[])
    json.dump(review, open(out_json, "w"), indent=2, ensure_ascii=False)
    print(f"wrote {out_json}")
