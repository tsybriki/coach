"""Build a review JSON for a FIT file: load parse_fit output and shape
sections in the order required by render_review: title, brief[3], metrics,
sections[hr_zones, stryd, multi_trend, pauses, recos].

GARMIN-INTRINSIC DATA ONLY. No per-km splits (Garmin doesn't write intervals for
plain running sessions; auto-segmentation adds noise rather than signal). When
Garmin presents an interval in a future structured workout via lap markers,
the rendering will include it via the trend chart's pause bands — those are
the only flags Garmin writes.

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


def build_review(fit_path: Path, *, date: str, slug: str, brief: list[str], summary_line: str, recos: list[dict]):
    d = parse_fit(str(fit_path), with_streams=True)
    profile = d.get("hr_zones_profile", {}) or {}
    prof_zones = profile.get("zones", {}) if isinstance(profile, dict) else {}
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

    # HR zones from moving partition — computed by parse_fit using the
    # athlete.json profile (so Z2L / Z2 / etc. show with the user's
    # actual threshold values, not renderer-side defaults).
    hr_zone_stats = d.get("hr_zone_stats", [])
    if hr_zone_stats:
        hr_max_from_profile = profile.get("hr_max") or d.get("max_hr") or 182
        total_sec = sum(z.get("sec", 0) for z in hr_zone_stats)
        z3_pct = next((z["pct"] for z in hr_zone_stats if z.get("name") == "Z3"), 0)
        z4_pct = next((z["pct"] for z in hr_zone_stats if z.get("name") == "Z4"), 0)
        z2_low_pct = next((z["pct"] for z in hr_zone_stats if z.get("name") == "Z2L"), 0)
        z2_pct = next((z["pct"] for z in hr_zone_stats if z.get("name") == "Z2"), 0)
        summary_text = (
            f"Z3 {z3_pct:.0f}% + Z4 {z4_pct:.0f}% = {z3_pct+z4_pct:.0f}% выше Z2L. "
            f"HR-границы — из athlete profile (HRmax={hr_max_from_profile})."
        )
        sections.append({
            "id": "hr_zones",
            "title": "HR-зоны · по moving records",
            "kind": "hr_zones",
            "summary": summary_text,
            "data": {
                "hr_max": hr_max_from_profile,
                "hr_zones_profile": profile,
                "zones": hr_zone_stats,
            },
        })

    # Athlete HR-zone profile (full per-zone bands from athlete.json)
    if prof_zones:
        items = []
        for name, z in prof_zones.items():
            if not isinstance(z, dict):
                continue
            rng = z.get("raw") or f'{z.get("low","?")}-{z.get("high","?")}'
            sub = f'method: {profile.get("method","")}' if name == "Z1" else None
            items.append({
                "label": name,
                "value": rng,
                "sub": sub,
            })
        # Bottom-of-list summary
        items.append({
            "label": "HRmax",
            "value": str(profile.get("hr_max") or "—"),
            "sub": f'method: {profile.get("method","")}',
        })
        items.append({
            "label": "RHR",
            "value": str(profile.get("rhr") or "—"),
            "sub": "resting HR",
        })
        notes = profile.get("notes", "")
        if notes:
            items.append({
                "label": "notes",
                "value": notes,
                "sub": "athlete.json",
            })
        sections.append({
            "id": "hr_profile",
            "title": "Athlete HR-профиль · из athlete.json",
            "kind": "kv_grid",
            "summary": "Границы зон, HRmax, RHR, метод расчёта — все из constraints.hr_zones athlete.json.",
            "data": {"items": items},
        })

    # Stryd Running Dynamics
    sections.append({
        "id": "stryd",
        "title": "Stryd Running Dynamics",
        "kind": "kv_grid",
        "summary": "Stryd footpod — единственный source-of-truth (per Кирилл 2026-10-15).",
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

    # Multi-series trend — per-second samples (no bucketing, no km-segmentation)
    trend_samples = d.get("trend", [])
    sections.append({
        "id": "multi_trend",
        "title": "Тренд · pace / cadence / HR / power (одновременно)",
        "kind": "multi_trend",
        "summary": "4 серии на одном графике, каждая нормирована 0..1. Серые полосы = паузы (Garmin autopause). Без синтетических km-маркеров.",
        "data": {
            "samples": trend_samples,
            "series": [
                {"key": "pace_min_per_km", "label": "pace",     "color": "#5cd6c0", "invert": True},
                {"key": "cadence_stryd",  "label": "cadence",  "color": "#7ec8e3"},
                {"key": "hr",             "label": "HR",       "color": "#ff9b6a"},
                {"key": "power",          "label": "power",    "color": "#d8a0ff"},
            ],
            "pauses": [{"t_start": p["t_start"], "t_end": p["t_end"], "dur_s": p["dur_s"]} for p in d.get("pause_segments", [])],
        }
    })

    # Pauses (Garmin autopause / water / etc.)
    sections.append({
        "id": "pauses",
        "title": "Паузы · Garmin autopause с elapsed-временем",
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

    # Recommendations (free-form)
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

