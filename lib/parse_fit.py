"""
parse_fit.py — FIT → dict по стабильной схеме.

Phase 2: тонкая обёртка над ~/projects/garmin_tools/fit_inspect.py.
Не дублирует логику, а вызывает реальный парсер через subprocess
(garmin_tools имеет свой .venv с Python 3.14, общий с ~/coach).

Если ~/projects/garmin_tools/ недоступен — fallback на локальный stub.

CRITICAL: this parser computes **moving time** (sum of per-second records where
distance progressed) as the canonical duration — `session.total_elapsed_s`
includes OFP stops / traffic-light waits / water breaks and would inflate a
"лёгкая" пробежка into Z3. `total_timer_s` is a middle ground but still
includes some autopause/auto-lap time. Moving time = only seconds where the
runner was actually moving forward.

Output convention:
  `elapsed_min` / `timer_min` / `moving_min`      — three duration measures
  `pause_total_s` / `pause_segments[]`            — pause structure
  `duration_min`, `avg_pace_min_per_km`, `splits`,
  `hr_drift_bpm`, `min_hr`                        — all on the moving partition.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

GARMIN_TOOLS = Path(os.environ.get("GARMIN_TOOLS_PATH", str(Path.home() / "projects" / "garmin_tools")))
GARMIN_TOOLS_VENV_PYTHON = GARMIN_TOOLS / ".venv" / "bin" / "python"


STABLE_SCHEMA_KEYS = [
    "fit_id", "date", "type", "source",
    # Movement-corrected (canonical):
    "distance_km", "duration_min", "avg_pace_min_per_km", "avg_hr", "max_hr", "min_hr",
    "cadence_avg", "cadence_avg_watch", "cadence_avg_stryd",
    "cadence_disagreement_abs_mean_spm",
    "stryd_running_dynamics",
    "stride_cm", "steps",
    "elevation_gain_m", "elevation_loss_m", "temperature_avg_c", "calories",
    "training_effect", "splits", "recovery_hr_drop", "hr_drift_bpm",
    # Raw time helpers (for audit / drift analysis):
    "elapsed_min", "timer_min", "moving_min",
    "pause_total_s", "pause_segments",
    "file_hash",
]


PAUSE_GAP_SECS = 2  # min t_sec gap that counts as a pause (default)


def _garmin_tools_available() -> bool:
    return (GARMIN_TOOLS / "fit_inspect.py").exists() and GARMIN_TOOLS_VENV_PYTHON.exists()


def _garmin_call(fit_path: Path, include_streams: bool = False, timeout: int = 120) -> Optional[dict]:
    """Run fit_inspect.py json; optionally include streams."""
    if not _garmin_tools_available():
        return None
    args = [str(GARMIN_TOOLS_VENV_PYTHON), str(GARMIN_TOOLS / "fit_inspect.py"),
            "json"]
    if include_streams:
        args.append("--include-streams")
    args.append(str(fit_path))
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                                cwd=str(GARMIN_TOOLS))
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


# ---------------------------------------------------------------------------
# Pause / moving-time detection
# ---------------------------------------------------------------------------

def _detect_pauses(streams: list[dict], gap_thr: int = PAUSE_GAP_SECS) -> list[dict]:
    """Return pause segments: [{t_start, t_end, dur_s, dist_m}, ...].

    A pause is a gap ≥ gap_thr seconds between two adjacent records (the runner
    was stationary / OFP / waiting / water). The `t_start`/`t_end` are the
    surrounding record times — the gap window itself is [t_start, t_end].
    """
    pauses = []
    prev_t: Optional[int] = None
    for s in streams:
        t = s.get("t_sec")
        if t is None:
            continue
        if prev_t is not None and (t - prev_t) >= gap_thr:
            pauses.append({
                "t_start": int(prev_t),
                "t_end": int(t),
                "dur_s": int(t - prev_t),
                "dist_m": s.get("dist_m"),
            })
        prev_t = t
    return pauses


def _moving_records(streams: list[dict], gap_thr: int = PAUSE_GAP_SECS) -> list[dict]:
    """Drop the LAST record of each moving-run so the pause window itself doesn't
    pollute the moving set with the runner's last stride-after-stop.

    Concretely: index i is dropped if (streams[i+1].t_sec − streams[i].t_sec) ≥ gap_thr.
    All other records (including the first record after a gap) stay — they are
    genuine running strides.
    """
    if not streams:
        return []
    drop = set()
    for i in range(len(streams) - 1):
        t_prev = streams[i].get("t_sec")
        t_cur = streams[i + 1].get("t_sec")
        if t_prev is None or t_cur is None:
            continue
        if (t_cur - t_prev) >= gap_thr:
            drop.add(i)
    return [s for i, s in enumerate(streams) if i not in drop]


def _hr_min(values: list[Optional[int]]) -> int:
    return int(min(v for v in values if v is not None)) if values else 0


def _hr_max(values: list[Optional[int]]) -> int:
    return int(max(v for v in values if v is not None)) if values else 0


def _hr_avg(values: list[Optional[int]]) -> float:
    xs = [v for v in values if v is not None]
    return sum(xs) / len(xs) if xs else 0.0


def _summarize_moving(moving: list[dict]) -> dict:
    """Compute pace, HR, cadence, distance, hr_drift from a moving-only subset.

    Cadence: returns BOTH `cadence_avg` (from watch, primary) and `cadence_stryd_avg`
    when a Stryd footpod is present. Stryd is generally the cleaner source on
    outdoor runs because the watch's wrist accelerometer over-counts during arm
    swing. Cross-source mean absolute difference is reported as
    `cadence_disagreement_abs_mean_spm` — values > 2 spm on a long stretch mean
    one source is wrong (usually watch on treadmill or in heavy-arm-motion hike).

    Stryd Running Dynamics (when present): vertical oscillation, stance time,
    step length, form/air power. Power is in watts, length in cm/mm.
    """
    if not moving:
        return {}
    hrs = [r.get("hr") for r in moving]
    cads_watch = [r.get("cadence_watch") for r in moving]
    cads_stryd = [r.get("cadence_stryd") for r in moving]
    dists = [r.get("dist_m") for r in moving]

    # Running Dynamics default source-of-truth: Stryd footpod.
    # Rationale (per Кирилл, 2026-10-15): "Берём stryd. Garmin rd требует
    # нагрудного ремня. Я не всегда его беру." → Stryd-цифры есть в каждой
    # пробежке с footpod'ом; Garmin RD опциональна и часто отсутствует.
    # Stryd VO/Ground Time НЕ интерпретируются через Garmin-нормы — это IMU
    # в ботинке (см. skill coach-fit-review § Каденс и Running Dynamics).
    #
    # Garmin RD остаётся в схеме как fallback `_garmin_*` для случаев когда
    # Stryd отсутствует (pool swims / indoor cycling / забытый footpod).
    def _pick(*keys):
        for k in keys:
            xs = [r.get(k) for r in moving if r.get(k) is not None]
            if xs:
                return xs, k
        return [], None

    # Stryd preferred, Garmin RD fallback
    vo_stryd_raw, vo_src = _pick("stryd_vo_cm", "garmin_vo_cm")
    ground_stryd_ms, stance_src = _pick("stryd_ground_time_ms", "garmin_stance_ms")
    step_garmin_mm, step_src = _pick("garmin_step_mm", "stryd_step_mm")  # Stryd не пишет step_length в этом FIT
    stance_pct_raw, _ = _pick("garmin_stance_pct")
    form_w_raw, _ = _pick("stryd_form_power_w")
    air_w_raw, _ = _pick("stryd_air_power_w")
    power_w_raw, _ = _pick("stryd_power_w")
    impact_lr_raw, _ = _pick("stryd_impact_loading_rate")
    leg_spring_raw, _ = _pick("stryd_leg_spring_stiffness")
    # Garmin RD values are exposed separately for cross-source comparison
    vo_garmin, _ = _pick("garmin_vo_cm")
    stance_garmin_ms, _ = _pick("garmin_stance_ms")

    # Moving time = number of "moving seconds" = sum across consecutive records of
    # the smaller-of(gap, 1). A gap > 1 means the runner was paused in between —
    # we credit 1 second for the LAST second of motion before the gap, but skip
    # the gap window itself.
    #
    # Empirical: with ~1Hz records this should produce values close to
    # (session.total_elapsed_s − sum(pause.dur_s)). For the 2026-10-14 run that
    # gives 6140 − 1024 = 5116s — which matches Garmin's `total_timer_s` (5115.66).
    moving_s = 0
    for i in range(1, len(moving)):
        t_prev = moving[i - 1].get("t_sec")
        t_cur = moving[i].get("t_sec")
        if t_prev is None or t_cur is None:
            continue
        delta = int(t_cur - t_prev)
        if delta <= 0:
            continue
        # credit exactly 1 second per record boundary — no double-counting for
        # pause windows which appear as large deltas
        moving_s += 1
        # NOTE: when the gap is large (say 561s for a 9-min pause), the records
        # at the boundary (t_prev, t_cur) are 561s apart but the runner only
        # spent 1 second transitioning between them — so this +1 is correct and
        # we DO NOT credit the 560s in between (those seconds are the pause).

    d_first = next((d for d in dists if d is not None), None)
    d_last = next((d for d in reversed(dists) if d is not None), None)
    distance_m = (d_last - d_first) if (d_first is not None and d_last is not None) else 0.0

    avg_hr = _hr_avg(hrs)
    max_hr = _hr_max(hrs)
    min_hr = _hr_min(hrs)

    # Cadence from watch (always present on Garmin running activities)
    cad_watch_avg = _hr_avg(cads_watch)
    cad_stryd_avg = _hr_avg(cads_stryd) if any(c is not None for c in cads_stryd) else 0.0
    cadence_disagreement = 0.0
    if cad_stryd_avg > 0:
        pairs = [(w, s) for w, s in zip(cads_watch, cads_stryd) if w is not None and s is not None]
        if pairs:
            cadence_disagreement = round(
                sum(abs(s - w) for w, s in pairs) / len(pairs), 2
            )

    # Stryd running dynamics (None when footpod absent)
    def _safe_stat(key, vals, agg):
        xs = [v for v in vals if v is not None]
        if not xs:
            return 0.0 if agg != "count" else 0
        if agg == "avg":
            return round(sum(xs) / len(xs), 1)
        if agg == "min":
            return round(min(xs), 1)
        if agg == "max":
            return round(max(xs), 1)
        return 0

    # Resolution: Stryd (preferred, per Кирилл decision 2026-10-15) > Garmin RD (fallback
    # when Stryd отсутствует — pool swims / indoor / забытый footpod).
    vo_vals = vo_stryd_raw or vo_garmin
    vo_source_label = "stryd" if vo_stryd_raw else ("garmin_rd" if vo_garmin else None)
    stance_vals_ms = ground_stryd_ms or stance_garmin_ms
    stance_source_label = "stryd" if ground_stryd_ms else ("garmin_rd" if stance_garmin_ms else None)
    step_vals_mm = step_garmin_mm
    step_source_label = "garmin_rd" if step_garmin_mm else None
    stance_pct_vals = stance_pct_raw
    form_vals = form_w_raw
    air_vals = air_w_raw
    power_vals = power_w_raw
    impact_lr_vals = impact_lr_raw
    leg_spring_vals = leg_spring_raw

    vo_avg = _safe_stat("vo", vo_vals, "avg")
    stance_avg = _safe_stat("stance_ms", stance_vals_ms, "avg")
    step_avg = _safe_stat("step_mm", step_vals_mm, "avg")
    form_avg = _safe_stat("form_w", form_vals, "avg")
    air_avg = _safe_stat("air_w", air_vals, "avg")
    power_avg = _safe_stat("power_w", power_vals, "avg")
    stance_pct_avg = _safe_stat("stance_pct", stance_pct_vals, "avg")
    impact_lr_avg = _safe_stat("impact_lr", impact_lr_vals, "avg")
    leg_spring_avg = _safe_stat("leg_spring", leg_spring_vals, "avg")
    rd_present = bool(vo_vals or stance_vals_ms or step_vals_mm)

    if distance_m > 0 and moving_s > 0:
        avg_pace_min_per_km = moving_s / (distance_m / 1000.0) / 60.0
    else:
        avg_pace_min_per_km = 0.0

    hr_drift_bpm = 0.0
    if len(moving) > 10:
        mid = len(moving) // 2
        first = [r.get("hr") for r in moving[:mid]]
        second = [r.get("hr") for r in moving[mid:]]
        if first and second:
            hr_drift_bpm = round(_hr_avg(second) - _hr_avg(first), 2)

    out = {
        "moving_s": moving_s,
        "distance_m": distance_m,
        "avg_hr": round(avg_hr, 1),
        "max_hr": int(max_hr),
        "min_hr": int(min_hr),
        "cadence_avg": round(cad_watch_avg, 1),
        "cadence_stryd_avg": round(cad_stryd_avg, 1),
        "cadence_disagreement_abs_mean_spm": cadence_disagreement,
        "avg_pace_min_per_km": round(avg_pace_min_per_km, 2),
        "hr_drift_bpm": hr_drift_bpm,
    }
    if rd_present:
        out["stryd"] = {
            "vertical_oscillation_cm_avg": vo_avg,
            "vertical_oscillation_source": vo_source_label,
            "stance_time_ms_avg": stance_avg,
            "stance_time_source": stance_source_label,
            "step_length_mm_avg": step_avg,
            "step_length_m_avg": round(step_avg / 1000.0, 3) if step_avg else 0,
            "step_length_source": step_src if step_src else None,
            "stance_time_pct_avg": stance_pct_avg,
            "form_power_w_avg": form_avg,
            "air_power_w_avg": air_avg,
            "power_w_avg": power_avg,
            "impact_loading_rate_avg": impact_lr_avg,
            "leg_spring_stiffness_avg": leg_spring_avg,
            "samples": sum(1 for v in vo_vals if v is not None) or
                        sum(1 for v in stance_vals_ms if v is not None),
            # Garmin RD values exposed separately — different sensor physics, do not
            # compare against Stryd values directly. Useful for cross-source sanity.
            "_garmin_vertical_oscillation_cm_avg": _safe_stat("vo_g", vo_garmin, "avg"),
            "_garmin_stance_time_ms_avg": _safe_stat("stance_g", stance_garmin_ms, "avg"),
        }
    return out


def _splits_per_km(moving: list[dict]) -> list[dict]:
    """Per-km splits from moving records. Each split closes at the record that
    crosses dist_m ≥ k·1000.

    For each km we report:
      km, dur_s, dist_m, pace_min_per_km,
      cadence_watch_avg, cadence_stryd_avg,
      hr_avg, hr_max,
      power_avg (Stryd, W),
      stride_avg_m  (derived: distance / cadence, available when cadence present).

    NOTE: Garmin measures splits from the start of the *session* (includes pauses).
    Our splits are from the start of the *moving partition*, so the first split is
    the first 1000 m of running after any pre-run warmup stops. This is correct
    for our purposes (we want running tempo per km, not per-elapsed-km).
    """
    if not moving:
        return []
    splits = []
    km = 1
    last_d: Optional[float] = None
    split_start_t: Optional[int] = None
    split_start_idx: Optional[int] = None

    for i, r in enumerate(moving):
        d = r.get("dist_m")
        if d is None:
            continue
        if last_d is None:
            last_d = d
            split_start_t = r.get("t_sec")
            split_start_idx = i
            continue

        target = km * 1000.0
        if d >= target:
            end_idx = i
            end_t = r.get("t_sec")
            if end_t is not None and split_start_t is not None and split_start_idx is not None and end_t > split_start_t:
                dist_m = d - last_d
                if dist_m > 0:
                    chunk = moving[split_start_idx:end_idx + 1]
                    dur_s = end_t - split_start_t
                    pace = dur_s / (dist_m / 1000.0) / 60.0

                    def _mean(xs):
                        xs = [x for x in xs if x is not None]
                        return sum(xs) / len(xs) if xs else None

                    cad_w = _mean([r.get("cadence_watch") for r in chunk])
                    cad_s = _mean([r.get("cadence_stryd") for r in chunk])
                    hr_vals = [r.get("hr") for r in chunk if r.get("hr") is not None]
                    pwr = _mean([r.get("stryd_power_w") for r in chunk])

                    splits.append({
                        "km": km,
                        "t_start": int(split_start_t),
                        "t_end": int(end_t),
                        "dur_s": int(dur_s),
                        "dist_m": round(dist_m, 1),
                        "pace_min_per_km": round(pace, 2),
                        "cadence_watch_avg": round(cad_w or 0, 1),
                        "cadence_stryd_avg": round(cad_s or 0, 1),
                        "hr_avg": round(_mean(hr_vals) or 0, 0),
                        "hr_max": int(max(hr_vals, default=0)),
                        "power_avg": round(pwr or 0, 0),
                    })
                    km += 1
                    last_d = d
                    split_start_t = end_t
                    split_start_idx = end_idx

    return splits


# ---------------------------------------------------------------------------
# Interval-segment detection — disabled per user instruction.
#
# Garmin Connect does not record intervals for plain running activities (only
# for structured workouts with explicit repeat-groups). Inferred segmentation
# from pace changes produces noisy results on steady aerobic runs and is not
# informative. For now, the per-km splits (`_splits_per_km` already in this
# module) provide the closest analog. When the user wants explicit interval
# breakdowns, they should structure workouts via the Workout Builder (see
# `garmin-workout-builder` skill) so FIT contains lap markers.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Multi-series trend for the combined power/cadence/HR/pace chart.
# ---------------------------------------------------------------------------

def _bucket_records_by_t(moving: list[dict], bucket_s: int = 30) -> list[dict]:
    """Group moving records into time-bucketed summaries.

    Each bucket = {t_start, t_end, dur_s, dist_m, pace_min_per_km,
                   cadence_watch_avg, cadence_stryd_avg,
                   hr_avg, hr_max, power_avg,
                   vo_cm_avg, ground_time_ms_avg}

    Buckets with dur_s < bucket_s / 2 are dropped (insufficient data).
    """
    if not moving:
        return []

    def cadence_of(r):
        c = r.get("cadence_stryd")
        return c if c is not None else r.get("cadence_watch")

    if moving[0].get("t_sec") is None:
        return []
    t0 = moving[0]["t_sec"]
    cur_bucket_t = None
    bucket = None
    buckets_out = []

    def _flush(b):
        if b is None:
            return None
        if not b["distances"]:
            return None
        dur = b["t_end"] - b["t_start"]
        if dur < bucket_s / 2:
            return None
        dist = b["distances"][-1] - b["distances"][0]
        if dist <= 0 or dur <= 0:
            return None
        pace = dur / (dist / 1000.0) / 60.0

        def mean(xs):
            xs = [x for x in xs if x is not None]
            return sum(xs) / len(xs) if xs else None

        def maxv(xs):
            xs = [x for x in xs if x is not None]
            return max(xs) if xs else None

        out = {
            "t_start": int(b["t_start"]),
            "t_end": int(b["t_end"]),
            "dur_s": dur,
            "dist_m": round(dist, 1),
            "pace_min_per_km": round(pace, 2),
            "cadence_avg": round(mean(b["cad"]) or 0, 1),
            "hr_avg": round(mean(b["hrs"]) or 0, 0),
            "hr_max": int(maxv(b["hrs"]) or 0),
            "power_avg": round(mean(b["pwr"]) or 0, 0),
            "vo_cm_avg": round(mean(b["vo"]) or 0, 1),
            "ground_time_ms_avg": round(mean(b["gt"]) or 0, 0),
        }
        return out

    for r in moving:
        t = r.get("t_sec")
        d = r.get("dist_m")
        if t is None or d is None:
            continue
        bucket_idx = (t - t0) // bucket_s
        if cur_bucket_t is None or bucket_idx != cur_bucket_t:
            flushed = _flush(bucket)
            if flushed:
                buckets_out.append(flushed)
            cur_bucket_t = bucket_idx
            bucket = {
                "t_start": t,
                "t_end": t,
                "distances": [d],
                "cad": [], "hrs": [], "pwr": [], "vo": [], "gt": [],
            }
        bucket["t_end"] = t
        bucket["distances"].append(d)
        c = cadence_of(r)
        if c is not None:
            bucket["cad"].append(c)
        if r.get("hr") is not None:
            bucket["hrs"].append(r["hr"])
        if r.get("stryd_power_w") is not None:
            bucket["pwr"].append(r["stryd_power_w"])
        if r.get("stryd_vo_cm") is not None:
            bucket["vo"].append(r["stryd_vo_cm"])
        if r.get("stryd_ground_time_ms") is not None:
            bucket["gt"].append(r["stryd_ground_time_ms"])

    flushed = _flush(bucket)
    if flushed:
        buckets_out.append(flushed)
    return buckets_out


def parse_trend(moving: list[dict], bucket_s: int = 30) -> list[dict]:
    """Public entrypoint: time-bucketed summaries for the multi-series trend chart.

    Default bucket = 30 sec. For ~90 min activities → ~180 buckets. Chart renders
    each metric (pace, cadence, HR, power) on its own y-axis normalised 0..1
    so they overlay in a single chart, not overlapping on raw units.

    Buckets with insufficient data are filtered out automatically.
    """
    return _bucket_records_by_t(moving, bucket_s=bucket_s)


# ---------------------------------------------------------------------------
# Stub (fallback when garmin_tools unavailable)
# ---------------------------------------------------------------------------

def _parse_stub(fit_path: Path) -> dict:
    digest = hashlib.sha256(fit_path.read_bytes()).hexdigest()
    name = fit_path.stem
    date = name[:10] if len(name) >= 10 else "1970-01-01"
    typ = "running"
    if "swim" in name.lower() or "pool" in name.lower():
        typ = "swimming"
    elif "bike" in name.lower() or "cycle" in name.lower():
        typ = "cycling"
    return {
        "fit_id": digest[:12],
        "date": date,
        "type": typ,
        "source": "garmin",
        "distance_km": 0.0,
        "duration_min": 0.0,
        "avg_pace_min_per_km": 0.0,
        "avg_hr": 0,
        "max_hr": 0,
        "min_hr": 0,
        "cadence_avg": 0,
        "stride_cm": 0.0,
        "steps": 0,
        "elevation_gain_m": 0,
        "elevation_loss_m": 0,
        "temperature_avg_c": 0.0,
        "calories": 0,
        "training_effect": {"aerobic_te": 0.0, "anaerobic_te": 0.0, "label": "UNKNOWN"},
        "splits": [],
        "recovery_hr_drop": 0,
        "hr_drift_bpm": 0.0,
        "elapsed_min": 0.0,
        "timer_min": 0.0,
        "moving_min": 0.0,
        "pause_total_s": 0,
        "pause_segments": [],
        "file_hash": digest,
        "_schema_version": "0.3.0",
        "_parser": "stub (garmin_tools unavailable)",
    }


# ---------------------------------------------------------------------------
# Normalize garmin_tools JSON output into stable schema
# ---------------------------------------------------------------------------

def _normalize(garmin_output: dict, streams: Optional[list[dict]] = None) -> dict:
    """garmin_output is fit_inspect.py json (with or without 'streams').

    If `streams` is provided (or present in garmin_output), the canonical
    duration is moving time and per-km splits are computed from moving records.
    Otherwise we fall back to session.total_elapsed_s for splits (legacy mode).
    """
    file_id = garmin_output.get("file_id", {}) or {}
    session = garmin_output.get("session", {}) or {}
    laps = garmin_output.get("laps", []) or []

    start_time = session.get("start_time") or file_id.get("time_created", "") or ""
    date = start_time[:10] if start_time else ""

    total_elapsed_s = float(session.get("total_elapsed_s") or 0)
    total_timer_s = float(session.get("total_timer_s") or total_elapsed_s or 0)
    total_distance_m = float(session.get("total_distance_m") or 0)

    raw_streams = streams if streams is not None else garmin_output.get("streams")

    # --- moving / pause partition (preferred when streams present) ---
    pause_segments: list[dict] = []
    moving_summary: dict = {}
    moving_splits: list[dict] = []
    trend_series: list[dict] = []
    if raw_streams:
        pause_segments = _detect_pauses(raw_streams)
        moving = _moving_records(raw_streams)
        moving_summary = _summarize_moving(moving)
        moving_splits = _splits_per_km(moving)
        trend_series = _bucket_records_by_t(moving, bucket_s=30)

    if moving_summary:
        duration_min = round(moving_summary["moving_s"] / 60.0, 2)
        avg_pace = moving_summary["avg_pace_min_per_km"]
        distance_km = round(moving_summary["distance_m"] / 1000.0, 3)
        splits = moving_splits
        avg_hr = moving_summary["avg_hr"]
        max_hr_v = moving_summary["max_hr"]
        min_hr_v = moving_summary["min_hr"]
        cadence_v = moving_summary["cadence_avg"]
        hr_drift = moving_summary["hr_drift_bpm"]
    else:
        # Legacy fallback (no streams) — beware: includes pauses!
        distance_km = round(total_distance_m / 1000.0, 3)
        duration_min = round(total_elapsed_s / 60.0, 2)
        avg_pace = round(duration_min / distance_km, 2) if distance_km else 0.0
        splits = []
        for lap in laps:
            lap_dist_km = (lap.get("distance_m") or 0) / 1000.0
            lap_dur_min = (lap.get("duration_s") or 0) / 60.0
            if lap_dist_km > 0:
                splits.append({
                    "km": round(lap_dist_km, 3),
                    "pace_min_per_km": round(lap_dur_min / lap_dist_km, 2),
                    "hr_avg": round(lap.get("avg_hr") or 0, 1),
                    "cadence": round(lap.get("avg_cadence") or 0, 1),
                })
        avg_hr = round(session.get("avg_hr") or 0, 1)
        max_hr_v = int(session.get("max_hr") or 0)
        min_hr_v = 0
        cadence_v = round(session.get("avg_cadence") or 0, 1)
        # HR drift from laps (legacy): difference between last and first lap avg_hr.
        hr_drift = 0.0
        if len(laps) >= 2:
            first_hr = laps[0].get("avg_hr") or 0
            last_hr = laps[-1].get("avg_hr") or 0
            hr_drift = round(last_hr - first_hr, 2)

    # File hash: prefer streams-aware hash so re-parsing with new schema invalidates
    # downstream caches (downstream caches should already key on schema version
    # but this is defensive).
    digest_input = json.dumps(
        {**garmin_output, "_schema": "0.3.0", "_moving_partition": bool(raw_streams)},
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(digest_input.encode()).hexdigest()

    return {
        "fit_id": digest[:12],
        "date": date,
        "type": session.get("sport", "running"),
        "source": "garmin",
        "distance_km": distance_km,
        "duration_min": duration_min,
        "avg_pace_min_per_km": round(avg_pace, 2),
        "avg_hr": avg_hr,
        "max_hr": max_hr_v,
        "min_hr": min_hr_v,
        # Cadence: watch-derived primary, Stryd-derived secondary when footpod is present
        "cadence_avg": cadence_v,                                       # watch (back-compat)
        "cadence_avg_watch": round(moving_summary.get("cadence_avg", cadence_v), 1),
        "cadence_avg_stryd": round(moving_summary.get("cadence_stryd_avg", 0.0), 1),
        "cadence_disagreement_abs_mean_spm": moving_summary.get("cadence_disagreement_abs_mean_spm", 0.0),
        # Stryd Running Dynamics (when footpod present):
        "stryd_running_dynamics": moving_summary.get("stryd") or {},
        "stride_cm": 0.0,
        "steps": 0,
        "elevation_gain_m": round(session.get("total_ascent") or 0, 1),
        "elevation_loss_m": round(session.get("total_descent") or 0, 1),
        "temperature_avg_c": 0.0,
        "calories": round(session.get("total_calories") or 0, 1),
        "training_effect": {"aerobic_te": 0.0, "anaerobic_te": 0.0, "label": "UNKNOWN"},
        "splits": splits,
        "recovery_hr_drop": 0,
        "hr_drift_bpm": hr_drift,
        # Multi-series trend (30s buckets) for the combined power/cadence/HR/pace chart
        "trend": trend_series,
        "trend_buckets_s": 30,
        "elapsed_min": round(total_elapsed_s / 60.0, 2) if total_elapsed_s else 0.0,
        "timer_min": round(total_timer_s / 60.0, 2) if total_timer_s else 0.0,
        "moving_min": duration_min,
        "pause_total_s": sum(int(p["dur_s"]) for p in pause_segments),
        "pause_segments": pause_segments,
        "file_hash": digest,
        "_schema_version": "0.6.0",
        "_parser": "garmin_tools/fit_inspect.py",
        "_source_path": garmin_output.get("file", {}).get("path", ""),
    }


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def parse_fit(fit_path: str | Path, *, with_streams: bool = True) -> dict:
    """Parse a FIT file.

    with_streams=True (default): invoke `--include-streams` so the canonical
    duration, pace, splits, and HR drift come from the moving-time partition.
    with_streams=False: legacy fast path — uses session-level elapsed/timer and
    lap-based splits (NOT recommended when pauses exist).
    """
    fit_path = Path(fit_path)
    if not fit_path.exists():
        raise FileNotFoundError(f"FIT not found: {fit_path}")

    if with_streams:
        garmin_output = _garmin_call(fit_path, include_streams=True, timeout=120)
    else:
        garmin_output = _garmin_call(fit_path, include_streams=False, timeout=60)

    if garmin_output is None:
        return _parse_stub(fit_path)
    return _normalize(garmin_output)
