"""
tests/test_phase1_smoke.py — smoke tests для всех модулей lib/.

Запуск:  cd /home/tsybriki/coach && python -m pytest tests/ -v
или:    cd /home/tsybriki/coach && python tests/test_phase1_smoke.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Добавляем корень проекта в sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import parse_fit, fit_ingest, fit_retention, garmin_weight  # noqa: E402
from lib import weekly_report, analyze, plan_adjust, plan_generate  # noqa: E402
from lib import goal_allocator, season_replan, volume_check, render_html, ask_model  # noqa: E402
from lib import zwift_search, zwift_sync  # noqa: E402
from lib.metrics import registry  # noqa: E402


def test_registry_lists_all_metrics():
    active = registry.list_active()
    assert "hr_drift" in active
    assert "cadence_30s" in active
    assert "training_effect" in active
    assert "fatigue_score" in active
    print(f"  ✓ registry.active = {active}")


def test_metrics_run_on_stub_fit():
    stub = {
        "fit_id": "test123",
        "date": "2026-10-13",
        "type": "running",
        "cadence_avg": 161,
        "hr_drift_bpm": 4.5,
        "training_effect": {"aerobic_te": 4.0, "label": "TEMPO", "anaerobic_te": 0.5},
    }
    results = registry.all_metrics_for_fit(stub)
    assert results["hr_drift"]["value"] == 4.5
    assert results["cadence_30s"]["value"] == 161
    assert results["training_effect"]["value"] == 4.0
    print("  ✓ metrics run on stub fit")


def test_volume_check():
    phase = {"hours_per_week_target": 8}
    cn = {
        "weekly_windows": {"ПН": [{"duration_min": 90}], "ВТ": [{"duration_min": 30}, {"duration_min": 75}], "СР": [{"duration_min": 120}]},
        "max_total_hours_per_week": 11,
        "min_total_hours_per_week": 2,
    }
    vc = volume_check.check_volume(phase, cn)
    assert "available_h" in vc
    assert vc["target_h"] == 8
    print(f"  ✓ volume_check: {vc}")


def test_goal_allocator():
    cands = goal_allocator.candidates(
        season_plan_path=ROOT / "state/season_plan.json",
        constraints_path=ROOT / "state/constraints.json",
        athlete_path=ROOT / "state/athlete.json",
    )
    assert len(cands) >= 2
    assert cands[0]["id"] in ("A", "B")
    print(f"  ✓ goal_allocator.candidates = {[c['id'] for c in cands]}")


def test_analyze_modes():
    for mode in ("quick", "contextual", "coaching", "lookback"):
        out = analyze.analyze("test123", mode)
        assert out["mode"] == mode
        assert "schema_version" in out
    print("  ✓ analyze supports all 4 modes")


def test_plan_generate_stub():
    plan = plan_generate.generate("2026-W42")
    assert "weekIso" in plan
    assert "slots" in plan
    assert "phase" in plan
    print(f"  ✓ plan_generate stub returns plan-w42 (slots={len(plan['slots'])})")


def test_season_replan_archive():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # Копируем season_plan в tmp
        sp = ROOT / "state/season_plan.json"
        tmp_sp = tmp / "season_plan.json"
        tmp_sp.write_text(sp.read_text(encoding="utf-8"), encoding="utf-8")
        tmp_arc = tmp / "archive"
        tmp_prog = tmp / "progress.json"
        tmp_prog.write_text("{}", encoding="utf-8")

        result = season_replan.replan(
            reason="test_in_phase1",
            new_state={"chosen_allocation": {"snapshot_date": "2026-10-14", "strategy": "test"}},
            season_plan_path=tmp_sp,
            archive_root=tmp_arc,
            progress_path=tmp_prog,
        )
        assert result["replanned"] is True
        assert (tmp_arc / f"{datetime.now(timezone.utc).date().isoformat()}.json").exists()
        # Проверим что архив старый, новый обновлён
        new = json.loads(tmp_sp.read_text(encoding="utf-8"))
        assert new["chosen_allocation"]["strategy"] == "test"
    print("  ✓ season_replan archives + updates")


def test_fit_retention_no_op_when_empty():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        idx = tmp / "index.json"
        idx.write_text('{"fits":[]}', encoding="utf-8")
        cfg = tmp / "retention.json"
        cfg.write_text('{"fit_ttl_days": 14}', encoding="utf-8")
        result = fit_retention.run(fit_store_root=tmp, config_path=cfg, decisions_root=tmp / "decisions")
        assert result["kept"] == 0
        assert result["deleted"] == []
    print("  ✓ fit_retention is no-op on empty store")


def test_fit_ingest_writes_to_store():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # Создаём фиктивный FIT
        fake_fit = tmp / "2026-10-13_running_garmin.fit"
        fake_fit.write_bytes(b"FAKE_FIT_CONTENT")
        # season_plan stub
        sp = tmp / "season_plan.json"
        sp.write_text(json.dumps({
            "control_points": [
                {"id": "cp_test", "date": "2026-10-13", "what": "test"}
            ]
        }), encoding="utf-8")
        prog = tmp / "progress.json"
        prog.write_text("{}", encoding="utf-8")
        fs = tmp / "fit_store"
        fs.mkdir()

        result = fit_ingest.ingest(
            fake_fit,
            fit_store_root=fs,
            progress_path=prog,
            season_plan_path=sp,
        )
        assert result["fit_id"]
        assert result["control_point_matched"] == "cp_test"
        # Проверим progress.json
        prog_data = json.loads(prog.read_text(encoding="utf-8"))
        assert prog_data["control_points"]["cp_test"]["status"] == "completed"
    print("  ✓ fit_ingest writes to store + matches CP")


def test_garmin_weight_manual():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        at = tmp / "athlete.json"
        at.write_text(json.dumps({"weight_history": [], "weight_kg_current": None}), encoding="utf-8")
        result = garmin_weight.manual_weight(at, kg=99.5)
        assert result["logged"] is True
        new = json.loads(at.read_text(encoding="utf-8"))
        assert new["weight_kg_current"] == 99.5
        assert len(new["weight_history"]) == 1
    print("  ✓ garmin_weight.manual_weight")


def test_ask_model_stub():
    out = ask_model.ask("sys", "user", json_schema={"k": "v"})
    assert out["_stub"] is True
    assert out["_phase"] == 1
    print("  ✓ ask_model stub")


def test_ask_model_validates_cited_principle():
    idx = {
        "principles": [
            {"id": "hr_drift_baseline"},
            {"id": "cadence_lengthening"},
        ]
    }
    errs_ok = ask_model.validate_coaching_output(
        {"cited_principle": {"id": "hr_drift_baseline"}}, idx
    )
    assert errs_ok == []
    errs_missing = ask_model.validate_coaching_output({}, idx)
    assert "missing cited_principle" in errs_missing[0]
    errs_wrong = ask_model.validate_coaching_output(
        {"cited_principle": {"id": "nonsense"}}, idx
    )
    assert "not in corpus_index" in errs_wrong[0]
    print("  ✓ ask_model.validate_coaching_output")


def test_render_html_writes_file():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        plan = plan_generate.generate("2026-W42")
        out = render_html.render_plan_wN(plan, tmp / "plan.html")
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "2026-W42" in content
        assert "doctype" in content.lower()
    print("  ✓ render_html.render_plan_wN")


def test_weekly_report_runs():
    report = weekly_report.report(week_iso="2026-W42")
    assert "week_iso" in report
    assert "preamble" in report
    assert "weight_line" in report
    print(f"  ✓ weekly_report runs (weight_line={report['weight_line']!r})")


def test_zwift_parse_free_text():
    """Парсинг голосовых команд в criteria."""
    cases = [
        ("45 мин Z2 велосипед endurance", {"duration_min": 45, "zones": ["Z2"], "discipline": "cycling"}),
        ("60 min threshold intervals",   {"duration_min": 60, "workout_type": "intervals"}),
        ("30 мин recovery бег",          {"duration_min": 30, "workout_type": "recovery", "discipline": "running"}),
    ]
    for text, must_have in cases:
        parsed = zwift_search.parse_free_text(text)
        for k, v in must_have.items():
            assert parsed.get(k) == v, f"parse_free_text('{text}')[{k}]={parsed.get(k)} != {v}"
    print(f"  ✓ zwift_search.parse_free_text ({len(cases)} cases)")


def test_zwift_search_returns_at_most_4():
    """search возвращает ≤ 4 candidates, не 'так и штук'."""
    criteria = {"discipline": "cycling", "duration_min": 45, "duration_tolerance": 10}
    cands = zwift_search.search(criteria)
    assert len(cands) <= 4, f"got {len(cands)} candidates, expected ≤ 4"
    print(f"  ✓ zwift_search.search returned {len(cands)} (≤ 4)")


def main():
    print("\n=== Phase 1 smoke tests ===\n")
    tests = [
        test_registry_lists_all_metrics,
        test_metrics_run_on_stub_fit,
        test_volume_check,
        test_goal_allocator,
        test_analyze_modes,
        test_plan_generate_stub,
        test_season_replan_archive,
        test_fit_retention_no_op_when_empty,
        test_fit_ingest_writes_to_store,
        test_garmin_weight_manual,
        test_ask_model_stub,
        test_ask_model_validates_cited_principle,
        test_render_html_writes_file,
        test_weekly_report_runs,
        test_zwift_parse_free_text,
        test_zwift_search_returns_at_most_4,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
    print(f"\n=== {len(tests) - failed}/{len(tests)} passed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())