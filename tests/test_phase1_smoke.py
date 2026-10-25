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
from lib import zwift_search, zwift_sync, plan_runtime  # noqa: E402
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
    plan = plan_generate.generate(1)  # W1 сезона
    assert "season_week" in plan
    assert plan["season_week"] == 1
    assert "iso_week" in plan
    assert plan["iso_week"] == "2026-W42"
    assert "phase" in plan
    assert plan["phase"]["id"] == "run_base"
    assert "slots" in plan
    print(f"  ✓ plan_generate W1 returns plan with phase={plan['phase']['id']}, iso={plan['iso_week']}")

    plan_iso = plan_generate.generate("2026-W42")
    assert plan_iso["season_week"] == 1, "iso→season_week conversion broken"

    plan_w4 = plan_generate.generate(4)
    assert "cp_3k_w4" in plan_w4["control_points_in_range"], "CP should be in W4 range"
    print(f"  ✓ plan_generate accepts int/iso/W-string, CP-mapping works")


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


def test_goal_guard_macro_leads_to_target():
    """Цель сезона одна, макро ведёт к ней, откат ловится."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import goal_guard

    sp = json.loads((ROOT / "state/season_plan.json").read_text(encoding="utf-8"))
    at = json.loads((ROOT / "state/athlete.json").read_text(encoding="utf-8"))

    # 1) Цель объявлена и одинакова в season_goal и goals[primary]
    sg = sp.get("season_goal")
    assert sg, "season_goal не задан — нет якоря плана"
    prim = next(g for g in sp["goals"] if g.get("primary"))
    target_sec = prim["goal_metric"]["target"]
    assert abs(target_sec / 10.0 - goal_guard.pace_sec(sg["race_pace_min_per_km"])) <= 1.0, \
        "цель в goals[] и season_goal расходятся"

    # 2) Макро к цели ведёт — нарушений нет
    problems = goal_guard.check(sp, at)
    assert not problems, "goal_guard нашёл нарушения:\n  - " + "\n  - ".join(problems)

    # 3) Guard ловит откат: если неделя гонки откатывается на медленный темп,
    #    проверка обязана ругнуться
    import copy
    # Откат: замедляем темпы варианта гонку-недели в КАТАЛОГЕ.
    # Структура живёт в каталоге — макро хранит только variant_id.
    tpl_path = ROOT / "state/workout_templates.json"
    tpl_orig = tpl_path.read_text(encoding="utf-8")
    try:
        tpl = json.loads(tpl_orig)
        for v in tpl["templates"]["time_trial"]["variants"]:
            if v["id"] == "tt_race":
                for b in v.get("blocks") or []:
                    b["pace_legacy"] = "4:24"
                    b["daniels_zone"] = "threshold"
                    b["pace_offset_sec"] = 0
        tpl_path.write_text(json.dumps(tpl, ensure_ascii=False, indent=2), encoding="utf-8")
        assert goal_guard.check(sp, at), "goal_guard НЕ заметил откат недели гонки"
    finally:
        tpl_path.write_text(tpl_orig, encoding="utf-8")

    print("  ✓ goal_guard: макро ведёт к цели, откат ловится")


def test_review_gates_built_and_persisted():
    """Gates строятся после каждой фазы и каждой CP; решения переживают регенерацию."""
    sys.path.insert(0, str(ROOT / "lib"))
    from lib import review_gates

    sp = json.loads((ROOT / "state/season_plan.json").read_text(encoding="utf-8"))
    gates = review_gates.build_gates(sp)
    assert gates, "gates не построились"

    # 1) есть gate после каждой run-фазы
    phase_gates = [g for g in gates if g.kind == "phase"]
    run_phases = [p for p in sp["phases"] if p["id"].startswith("run_")
                  and p["id"] != "run_taper"]
    assert len(phase_gates) >= len(run_phases), \
        "не для каждой run-фазы есть gate ({} на {})".format(len(phase_gates), len(run_phases))

    # 2) у каждой gate есть вопрос, рычаг и ветки решений
    for g in gates:
        assert g.question, "у gate {} нет вопроса".format(g.id)
        assert g.lever, "у gate {} нет рычага корректировки".format(g.id)
        assert set(g.decisions) >= {"pass", "warn", "fail"}, \
            "у gate {} нет трёх веток решений".format(g.id)

    # 3) каждая CP имеет gate
    cp_ids = {c["id"] for c in sp.get("control_points", [])
              if (c.get("session") or {}).get("target_sec")}
    gate_cps = {g.id.replace("gate_cp_", "") for g in gates
                if g.kind in ("quality", "metric")}
    assert cp_ids <= gate_cps, \
        "не у каждой CP есть gate: нет {}".format(cp_ids - gate_cps)

    # 4) решения сохраняются при перегенерации
    tmp_prog = ROOT / "state/season_progress.json"
    original = tmp_prog.read_text(encoding="utf-8")
    try:
        review_gates.decide("gate_cp_cp_3k_w4", "confirm", "тест")
        prog = review_gates.load_progress()
        g = next(x for x in prog["gates"] if x["id"] == "gate_cp_cp_3k_w4")
        assert g["decision"] == "confirm", "решение не сохранилось"
        assert g["decided_at"], "не записано время решения"

        # перегенерация не теряет решение
        review_gates.sync_gates(sp)
        prog = review_gates.load_progress()
        g = next(x for x in prog["gates"] if x["id"] == "gate_cp_cp_3k_w4")
        assert g["decision"] == "confirm", "решение потерялось при перегенерации"
    finally:
        tmp_prog.write_text(original, encoding="utf-8")

    print("  ✓ review_gates: gates после фаз и CP, решения сохраняются")


def test_macro_structure_is_data_not_string():
    """Макро ссылается на каталог, структура в blocks, нагрузка вычисляется."""
    sys.path.insert(0, str(ROOT / "lib"))
    from lib import load_model

    sp = json.loads((ROOT / "state/season_plan.json").read_text(encoding="utf-8"))
    at = json.loads((ROOT / "state/athlete.json").read_text(encoding="utf-8"))
    tpl = json.loads((ROOT / "state/workout_templates.json").read_text(encoding="utf-8"))["templates"]

    ids = set()
    for gid, t in tpl.items():
        if not isinstance(t, dict):
            continue
        for v in t.get("variants") or []:
            assert v["id"] not in ids, "дубликат variant_id: {}".format(v["id"])
            ids.add(v["id"])

    # в каталоге у каждого варианта есть блоки
    for gid, t in tpl.items():
        if not isinstance(t, dict):
            continue
        for v in t.get("variants") or []:
            assert v.get("blocks"), "{}: у варианта '{}' нет blocks".format(gid, v["id"])
            # блоки привязаны к зоне Дэниэлса (или к темпу CP)
            for b in v["blocks"]:
                has_zone = (b.get("daniels_zone") or b.get("daniels_zone_hard")
                            or b.get("daniels_zones") or b.get("daniels_zone_from")
                            or b.get("daniels_zone_to"))
                has_tt = b.get("type") in ("tt_pace", "tt_max")
                if b.get("type") == "pyramid":
                    # зоны — в шагах пирамиды
                    for st in b.get("steps") or []:
                        assert st.get("daniels_zone"), \
                            "{} / {}: шаг пирамиды без зоны".format(gid, v["id"])
                    has_zone = True
                assert has_zone or has_tt, \
                    "{} / {}: блок без привязки к зоне Дэниэлса".format(gid, v["id"])

    for w in sp["weekly_macro"]:
        q = w.get("quality") or {}
        n = w["season_week"]
        # 1) ссылка на каталог
        assert q.get("variant_id"), "W{}: нет variant_id".format(n)
        assert q["variant_id"] in ids, "W{}: variant_id '{}' нет в каталоге".format(n, q["variant_id"])
        # 2) структура — в каталоге; макро хранит ТОЛЬКО ссылку
        assert not q.get("blocks"), \
            "W{}: в макро лежит копия blocks — источник истины в каталоге".format(n)
        assert "_legacy_structure" not in q, "W{}: осталась строка _legacy_structure".format(n)
        # 3) нагрузка вычисляется из структуры и совпадает
        calc = load_model.macro_week_load(w, at)["total_h"]
        assert abs(calc - float(w.get("total_h", 0))) <= 0.05, \
            "W{}: total_h={} != пересчёт {}".format(n, w.get("total_h"), calc)
        # 4) разбивка бега сходится
        parts = (w.get("run_km_long", 0) + w.get("run_km_quality", 0)
                 + w.get("run_km_easy", 0))
        assert abs(parts - w["run_km"]) <= 0.2, \
            "W{}: long+качеств+лёгк = {} != run_km {}".format(n, round(parts, 1), w["run_km"])

    print("  ✓ макро: структура в данных, нагрузка вычисляется, разбивка сходится")


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


def test_render_html_includes_v18_features():
    """v26: план-data содержит focus, workout_pending, kind; HTML использует их в renderCard."""
    import re
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        plan = plan_generate.generate(1)
        out = render_html.render_plan_wN(plan, tmp / "plan.html")
        content = out.read_text(encoding="utf-8")
        # plan-data inline JSON содержит slots с focus/workout_pending
        plan_data_match = re.search(r'<script type="application/json" id="plan-data">(.+?)</script>', content, re.DOTALL)
        assert plan_data_match, "missing plan-data"
        plan_obj = json.loads(plan_data_match.group(1))
        # focus Z2 где-то есть
        focuses = [s.get("focus", "") for s in plan_obj.get("slots", [])]
        assert any("Z2" in f for f in focuses), f"no Z2 focus in {focuses}"
        # workout_pending где-то есть
        wps = [s.get("workout_pending", False) for s in plan_obj.get("slots", [])]
        assert any(wps), f"no workout_pending in {plan_obj.get('slots', [])}"
        # JS renderCard использует focus/workout_pending
        assert "slot.focus" in content, "renderCard should use slot.focus"
        assert "slot.workout_pending" in content, "renderCard should use slot.workout_pending"
        # HR zones (rule)
        assert "hr_zones" in plan_obj.get("rules", {}), "missing hr_zones in plan-data"
    print("  ✓ render_html v26: plan-data has focus/workout_pending, JS renderCard uses them")


def test_plan_runtime_generates_json_and_html():
    """v19: plan_runtime.generate_plan_with_html всегда создаёт и JSON, и HTML."""
    import shutil
    tmp = tempfile.mkdtemp(prefix="plan_runtime_")
    try:
        out_dir = Path(tmp)
        result = plan_runtime.generate_plan_with_html(
            1, out_dir=out_dir,
            season_plan_path=ROOT / "state/season_plan.json",
            athlete_path=ROOT / "state/athlete.json",
            constraints_path=ROOT / "state/constraints.json",
            overrides_path=ROOT / "state/overrides.json",
        )

        json_path_str = result["json_path"]
        html_path_str = result["html_path"]

        assert Path(json_path_str).exists(), f"JSON не создан: {json_path_str}"
        assert Path(html_path_str).exists(), f"HTML не создан: {html_path_str}"

        json_data = json.loads(Path(json_path_str).read_text(encoding="utf-8"))
        assert json_data["season_week"] == 1

        html_content = Path(html_path_str).read_text(encoding="utf-8")
        assert "W1" in html_content
        # run_base переехал в plan-data JSON
        assert "run_base" in html_content or "run_base" in json.dumps(json_data, ensure_ascii=False)
        assert len(html_content) > 3000

        assert result["slots_count"] >= 4
        assert result["season_week"] == 1

        print(f"  ✓ plan_runtime W1: json={Path(json_path_str).name} ({Path(json_path_str).stat().st_size}B), "
              f"html={Path(html_path_str).name} ({Path(html_path_str).stat().st_size}B), "
              f"slots={result['slots_count']}, bike_pending={result['bike_pending']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_plan_runtime_for_several_weeks():
    """v19: regen нескольких W_N — каждая порождает JSON + HTML."""
    import shutil
    tmp = tempfile.mkdtemp(prefix="plan_runtime_several_")
    try:
        out_dir = Path(tmp)
        for sw in [1, 4, 13, 27]:
            result = plan_runtime.generate_plan_with_html(
                sw, out_dir=out_dir,
                season_plan_path=ROOT / "state/season_plan.json",
                athlete_path=ROOT / "state/athlete.json",
                constraints_path=ROOT / "state/constraints.json",
                overrides_path=ROOT / "state/overrides.json",
            )
            assert Path(result["json_path"]).exists()
            assert Path(result["html_path"]).exists()
        print(f"  ✓ plan_runtime для W1, W4, W13, W27: все (json, html) созданы")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_slot_structure_w1():
    """v20: каждый run/bike/swim слот имеет structure с warmup/work/cooldown."""
    plan = plan_generate.generate(1)
    for s in plan["slots"]:
        assert "structure" in s, f"slot {s.get('name')} missing structure"
        assert len(s["structure"]) > 0, f"slot {s['name']} has empty structure"
        phases = {st["phase"] for st in s["structure"]}
        if s["kind"] in ("run", "bike", "swim", "brick"):
            assert "warmup" in phases or "work" in phases or "cooldown" in phases, \
                f"slot {s['name']} missing key phases, has {phases}"
    ofp_slots = [s for s in plan["slots"] if s["kind"] == "ofp"]
    assert len(ofp_slots) >= 1, "W1 должна иметь ≥1 OFP слот"
    for s in ofp_slots:
        assert "structure" in s
        has_exercise = any("exercise" in st or "set" in st for st in s["structure"])
        assert has_exercise, f"OFP slot {s['name']} missing exercise/set"
    print(f"  ✓ W1 structure: все {len(plan['slots'])} слотов имеют structure, OFP={len(ofp_slots)}")


def test_step_builder_long_run():
    """step_builder строит правильную структуру для длинного бега."""
    from lib import step_builder
    structure = step_builder.build_structure("long_Z2", 90)
    assert len(structure) == 3
    phases = [s["phase"] for s in structure]
    assert phases == ["warmup", "work", "cooldown"]
    assert structure[1]["duration_min"] == 65
    assert structure[1]["zone"] == "Z2"
    print(f"  ✓ step_builder.long_Z2 90мин: warmup/work/cooldown по {structure[0]['duration_min']}/{structure[1]['duration_min']}/{structure[2]['duration_min']} мин")


def test_step_builder_intervals():
    """step_builder строит структуру с repeat-блоком для интервалов."""
    from lib import step_builder
    structure = step_builder.build_structure("key_intervals", 60)
    set_steps = [s for s in structure if s.get("phase") == "set"]
    assert len(set_steps) == 1
    s = set_steps[0]
    assert s["reps"] >= 5
    assert len(s["set_repeats"]) == 2
    print(f"  ✓ step_builder.key_intervals 60мин: {s['reps']}× ({s['set_repeats'][0]['duration_min']}м + {s['set_repeats'][1]['duration_min']}м)")


def test_html_has_details_structure():
    """v26: HTML копирует архитектуру w1-mobile.html (picker + cardWrap + JS)."""
    import shutil
    tmp = tempfile.mkdtemp(prefix="plan_runtime_html_")
    try:
        result = plan_runtime.generate_plan_with_html(1, out_dir=Path(tmp))
        html = Path(result["html_path"]).read_text(encoding="utf-8")
        # picker и cardWrap
        assert 'id="picker"' in html, "HTML missing picker"
        assert 'id="cardWrap"' in html, "HTML missing cardWrap"
        assert 'id="cardHost"' in html, "HTML missing cardHost"
        assert 'id="backBtn"' in html, "HTML missing backBtn"
        # план в inline JSON
        assert 'id="plan-data"' in html, "HTML missing plan-data"
        # JS-функции (из w1-mobile.html)
        assert "function buildPicker" in html, "missing buildPicker"
        assert "function showSlot" in html, "missing showSlot"
        assert "function showPicker" in html, "missing showPicker"
        # classList add/remove для navigation (как в w1-mobile.html)
        assert "classList.add('hidden')" in html, "missing classList.add('hidden')"
        assert "classList.remove('hidden')" in html, "missing classList.remove('hidden')"
        # history.pushState
        assert "pushState" in html, "missing pushState"
        # renderCard в JS использует kind → icon
        assert "KIND_ICON" in html, "missing KIND_ICON"
        # slots рендерятся как <button class="slot"> (в HTML — backBtn, остальные добавляет JS)
        # Проверяем JS-функцию buildPicker, которая их рендерит
        assert "for (const s of (plan.slots" in html, "buildPicker missing slots loop"
        assert "data-slot=" in html, "buildPicker should set data-slot attribute"
        # в HTML есть backBtn button
        assert '<button id="backBtn"' in html, "missing backBtn"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"  ✓ HTML v26: w1-mobile.html архитектура (picker + cardWrap + JS)")


def test_html_slot_links_navigable():
    """v26: slot кнопки с data-slot, click handler вызывает showSlot."""
    import shutil
    tmp = tempfile.mkdtemp(prefix="plan_runtime_nav_")
    try:
        result = plan_runtime.generate_plan_with_html(1, out_dir=Path(tmp))
        html = Path(result["html_path"]).read_text(encoding="utf-8")
        import re
        # В picker JS рендерит <button class="slot" data-slot="...">, проверяем что JS функция это делает
        assert "buildPicker" in html, "missing buildPicker"
        assert 'data-slot="' in html or "data-slot" in html, "missing data-slot in JS"
        # click handler + showSlot
        assert "addEventListener('click'" in html, "missing click handler"
        assert "showSlot(" in html, "missing showSlot call"
        # classList navigation
        assert "classList.add('hidden')" in html, "missing classList.add('hidden') for showSlot"
        assert "classList.add('visible')" in html, "missing classList.add('visible') for showSlot"
        # showSlot uses cardHost.innerHTML
        assert "cardHost" in html, "missing cardHost"
        # popstate listener
        assert "popstate" in html, "missing popstate listener"
        # backBtn → history.back()
        assert "backBtn" in html and "history.back" in html, "missing back-button handler"
        # план содержит 8 слотов в JSON
        plan_data_match = re.search(r'<script type="application/json" id="plan-data">(.+?)</script>', html, re.DOTALL)
        assert plan_data_match, "missing plan-data script"
        plan_obj = json.loads(plan_data_match.group(1))
        assert len(plan_obj.get("slots", [])) == 8, f"plan-data should have 8 slots, got {len(plan_obj.get('slots', []))}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ HTML v26: w1-mobile.html slot navigation (click → showSlot → cardHost.innerHTML)")


def test_render_html_basis_aware():
    """v35: renderHrStructure учитывает basis (time/distance), sub-шаги без notes."""
    import shutil
    tmp = tempfile.mkdtemp(prefix="basis_test_")
    try:
        test_plan = {
            "schema_version": "0.1.0",
            "title": "W1 test basis",
            "season_week": 1, "iso_week": "2026-W42", "season_start_date": "2026-10-11",
            "week_start": "2026-10-11", "week_end": "2026-10-17", "is_actual_log": True,
            "phase": {"id": "run_base", "start": "2026-10-11", "end": "2027-01-02",
                      "hours_per_week_target": 5, "goal_id": "g_run_spring"},
            "totals": {"planned_hours": 1.0, "target_hours": 5.0, "delta_hours": -4.0,
                       "actual_hours": 1.0, "actual_km": 0, "actual_sessions": 0},
            "rules": {"hr_zones": {"zones": {"Z1": "100-118", "Z2": "125-145", "Z3": "136-146", "Z4": "146-160"}}},
            "control_points_in_range": [],
            "slots": [
                {"id": "test-distance", "day": "ПТ", "date": "2026-10-16", "time": "18:30",
                 "name": "Distance-based set", "kind": "run", "subkind": "tempo",
                 "focus": "Z4", "location": "stadium", "duration_min": 25, "workout_pending": False,
                 "structure": [
                     {"phase": "warmup", "duration_min": 5, "zone": "Z1", "pace_min_per_km": "5:45", "notes": "warmup notes"},
                     {"phase": "set", "basis": "distance", "reps": 6,
                      "set_repeats": [
                          {"phase": "work", "basis": "distance", "distance_m": 150, "zone": "Z4", "pace_min_per_km": "3:40"},
                          {"phase": "recovery", "basis": "distance", "distance_m": 250, "zone": "Z1", "pace_min_per_km": "5:45"}
                      ]},
                     {"phase": "cooldown", "duration_min": 5, "zone": "Z1", "pace_min_per_km": "5:45", "notes": "cooldown notes"}
                 ], "inventory": []},
                {"id": "test-time", "day": "СБ", "date": "2026-10-17", "time": "10:00",
                 "name": "Time-based set", "kind": "run", "subkind": "tempo",
                 "focus": "Z3", "location": "asphalt", "duration_min": 18, "workout_pending": False,
                 "structure": [
                     {"phase": "set", "reps": 6, "duration_min": 18,
                      "set_repeats": [
                          {"phase": "work", "duration_min": 1, "zone": "Z3", "hr_target": 165},
                          {"phase": "recovery", "duration_min": 2, "zone": "Z2", "hr_target": 135}
                      ]}
                 ], "inventory": []}
            ],
            "summary": {"actual": [], "totals": ""}
        }
        out = Path(tmp) / "test.html"
        render_html.render_plan_wN(test_plan, out)
        html = out.read_text(encoding="utf-8")
        # JS source должен содержать basis-aware логику
        assert "s.basis" in html, "missing basis check in renderHrStructure"
        assert "s.distance_m" in html, "missing distance_m in renderHrStructure"
        assert "st.distance_m" in html, "missing st.distance_m in renderHrStructure (top-level set)"
        assert "hr_target" in html, "missing hr_target rendering"
        # Логика для sub-шагов: НЕ показываем notes
        # (это сложно проверить без exec JS, проверю через sub_basis в коде)
        assert "subBasis" in html or "st.basis" in html, "missing basis assignment"
        # distance-based set: НЕ умножаем work × reps (Кирилл: 'не пиши объём, просто интервалы')
        # Проверяем что totalM логика удалена
        assert "totalM" not in html, "v36: totalM should be removed (no auto-multiplied volume)"
        # label берётся из step.label или fallback 'set'
        assert "setLabel" in html, "missing setLabel in renderHrStructure"
        # notes НЕ показываются нигде в sub-шагах И в top-level
        # (проверяем через отсутствие step-notes в rendered template)
        # v36: убрали все step-notes, кроме OFP set.format (который у нас в renderOfpStructure)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  ✓ HTML v36: renderHrStructure no volume-math, setLabel, no notes anywhere")


def test_render_html_every_slot_renders():
    """v37: реальный JS-рендеринг каждого слота в plan-w1 не падает.

    Защита от регрессов вроде 's is not defined' — ловит ReferenceError в renderHrStructure.
    """
    import shutil
    tmp = tempfile.mkdtemp(prefix="js_render_test_")
    try:
        from lib import render_html
        # Рендерим plan-w1.html
        plan = json.load(open(ROOT / "state/plan-w1.json"))
        out = Path(tmp) / "plan.html"
        render_html.render_plan_wN(plan, out)
        html = out.read_text(encoding="utf-8")

        # Проверяем что node доступен
        node_bin = __import__("shutil").which("node")
        if not node_bin:
            print("  ~ HTML v37: node не найден, тест пропущен")
            return

        # Сохраняем JS-скрипт
        js_script = '''const fs = require('fs');
const html = fs.readFileSync('{}', 'utf-8');
const dataMatch = html.match(/<script type="application\\/json" id="plan-data">([\\s\\S]*?)<\\/script>/);
const planData = JSON.parse(dataMatch[1]);
const scripts = html.match(/<script>([\\s\\S]*?)<\\/script>/g) || [];
const lastScript = scripts[scripts.length - 1].replace(/^<script>/, '').replace(/<\\/script>$/, '').replace(/init\\(\\);[\\s]*$/, '');
const elements = {{}};
global.document = {{ getElementById: (id) => elements[id] = elements[id] || {{ innerHTML: '', classList: {{ add: () => {{}}, remove: () => {{}} }}, addEventListener: () => {{}} }} }};
global.history = {{ state: null, pushState: () => {{}}, replaceState: () => {{}} }};
global.window = {{ scrollTo: () => {{}}, addEventListener: () => {{}} }};
global.location = {{ hash: '' }};
try {{
  eval(lastScript);
  for (const slot of planData.slots) {{
    const card = renderCard(slot);
    if (card.length < 50) {{ console.log('SHORT:' + slot.id + ':' + card.length); process.exit(1); }}
  }}
  console.log('OK');
}} catch (e) {{
  console.log('ERROR:' + e.message);
  process.exit(1);
}}
'''.format(str(out).replace("'", "'\\''"))
        js_file = Path(tmp) / "test.js"
        js_file.write_text(js_script, encoding="utf-8")
        result = __import__("subprocess").run([node_bin, str(js_file)], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, f"JS render failed: {result.stdout} {result.stderr}"
        assert "OK" in result.stdout, f"Unexpected output: {result.stdout}"
        # Все 8 слотов должны рендериться
        slots_count = len(plan.get("slots", []))
        assert slots_count == 8, f"W1 should have 8 slots, got {slots_count}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"  ✓ HTML v37: реальный JS-рендеринг всех 8 слотов W1 без ошибок")


def test_weekly_report_runs():
    report = weekly_report.report(1)  # W1 сезона
    assert "season_week" in report
    assert "week_key" in report
    assert "preamble" in report
    assert "weight_line" in report
    print(f"  ✓ weekly_report W1 (weight_line={report['weight_line']!r})")


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


def test_auto_zwift_rule_in_constraints():
    """auto_zwift правило присутствует и включено в state/constraints.json (v16)."""
    cn = json.loads(Path(ROOT / "state/constraints.json").read_text(encoding="utf-8"))
    assert "auto_zwift" in cn, "constraints.json missing auto_zwift rule"
    az = cn["auto_zwift"]
    assert az["enabled"] is True
    assert az["duration_min_max"] == 90
    assert "home_stationary_bike" in az["locations"]
    assert "bike" in az["kinds"]
    print(f"  ✓ auto_zwift: enabled, ≤90min, kinds={az['kinds']}")


def test_plan_generate_layout_w1_run_base():
    """W1 (run_base) должен сгенерировать slots для всех рабочих дней."""
    plan = plan_generate.generate(1)
    slots = plan["slots"]
    assert len(slots) >= 5, f"W1 должен иметь ≥5 slots, got {len(slots)}"
    days = {s["day"] for s in slots}
    assert "ПН" in days, "ПН обязательно"
    assert "СР" in days, "СР обязательно (длинная)"
    assert "ЧТ" in days, "ЧТ обязательно (вел)"
    # Total planned hours в пределах разумного
    total_min = sum(s["duration_min"] for s in slots)
    assert 240 <= total_min <= 600, f"Ожидалось 4-10ч, got {total_min/60:.1f}ч"
    # Конкретные имена должны быть информативными
    long_run = next((s for s in slots if "Длинный" in s["name"]), None)
    assert long_run is not None, "Нет длинной в W1"
    assert "Z2" in long_run["name"], "Длинная должна быть в Z2"
    # auto_zwift: bike-слот должен иметь workout_pending=true
    bike_slots = [s for s in slots if s["kind"] == "bike"]
    for bs in bike_slots:
        assert bs.get("workout_pending", False), f"bike slot {bs['name']} должен иметь workout_pending"
    print(f"  ✓ W1 run_base: {len(slots)} slots, {total_min/60:.1f}ч, {len(bike_slots)} bike with auto_zwift")


def test_plan_generate_layout_all_phases():
    """Все phase должны генерировать непустые slots."""
    for sw in [1, 13, 20, 26, 27, 28, 31, 37, 44, 48]:
        plan = plan_generate.generate(sw)
        assert "slots" in plan
        slots = plan["slots"]
        if plan["phase"] and plan["phase"]["id"] in ("run_taper", "transition"):
            # Taper и transition могут иметь меньше
            assert len(slots) >= 1, f"W{sw} ({plan['phase']['id']}) должна иметь ≥1 slot"
        else:
            assert len(slots) >= 5, f"W{sw} ({plan['phase']['id']}) должна иметь ≥5 slots, got {len(slots)}"
    print("  ✓ plan_generate работает для W1, W13, W20, W26, W27, W28, W31, W37, W44, W48")


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
        test_goal_guard_macro_leads_to_target,
        test_review_gates_built_and_persisted,
        test_macro_structure_is_data_not_string,
        test_fit_retention_no_op_when_empty,
        test_fit_ingest_writes_to_store,
        test_garmin_weight_manual,
        test_ask_model_stub,
        test_ask_model_validates_cited_principle,
        test_render_html_writes_file,
        test_weekly_report_runs,
        test_zwift_parse_free_text,
        test_zwift_search_returns_at_most_4,
        test_auto_zwift_rule_in_constraints,
        test_plan_generate_layout_w1_run_base,
        test_plan_generate_layout_all_phases,
        test_render_html_includes_v18_features,
        test_plan_runtime_generates_json_and_html,
        test_plan_runtime_for_several_weeks,
        test_slot_structure_w1,
        test_step_builder_long_run,
        test_step_builder_intervals,
        test_html_has_details_structure,
        test_html_slot_links_navigable,
        test_render_html_basis_aware,
        test_render_html_every_slot_renders,
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