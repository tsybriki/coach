#!/usr/bin/env python3
"""
rebase_templates_to_vdot.py — привязать каталог шаблонов к VDOT.

Зачем: в state/workout_templates.json темпы записаны строкой ('4:25').
Это «зашитое» число — оно не двигается, когда растёт форма. Тренироваться
нужно по ТЕКУЩИМ темпам (таблица Дэниэлса для текущего VDOT), а целевые
темпы сезона — отдельная задача.

Что делает:
  1. Для каждого блока каталога определяет, к какой зоне Дэниэлса он
     относится (easy / marathon / threshold / interval / repetition).
  2. Считает СМЕЩЕНИЕ относительно темпа этой зоны (в с/км).
  3. Заменяет 'pace': '4:25' на:
       'daniels_zone': 'threshold',
       'pace_offset_sec': 1
  4. Шаблон получает 'pace' как ДИАПАЗОН-ОПИСАНИЕ зоны (для показа),
     а конкретный темп считается при планировании недели.

Итог: каталог хранит ЗОНУ и СМЕЩЕНИЕ, темп вычисляется из VDOT атлета.
Рост формы → вся серия автоматически ускоряется.

Запуск: python3 scripts/rebase_templates_to_vdot.py [--dry]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from lib import daniels  # noqa: E402

TPL_PATH = REPO / "state/workout_templates.json"

# Какому блоку какая зона Дэниэлса соответствует.
# Ключ: (template_id, variant_id) → список (место в блоке, зона, смещение_в_с).
# Смещение считается автоматически из текущего 'pace' и темпа зоны при
# REFERENCE_VDOT — так числа не выдумываются, а выводятся из каталога.
REFERENCE_VDOT = 48

# Зона по смыслу работы (вручную, но однозначно):
#   threshold_power/speed → threshold (порог)
#   tempo                  → marathon..threshold (темповая работа)
#   vo2max                 → interval (интервалы)
#   mixed                  → threshold + repetition
#   pyramid                → threshold → interval → repetition (пирамида)
#   fartlek                → easy + interval
#   progression            → easy → threshold
#   time_trial             → по цели CP (темп из контрольной точки)
#   taper_race_pace        → threshold + repetition


def sec_from(pace: str) -> int | None:
    m = re.search(r"(\d+):(\d{2})", str(pace))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def zone_offset(base_sec: int | None, pace: str | None) -> int | None:
    """Смещение темпа блока относительно темпа зоны (с/км)."""
    if base_sec is None or pace is None:
        return None
    p = sec_from(pace)
    return None if p is None else int(p - base_sec)


# Суффикс ключа темпа → суффикс ключа зоны/смещения
_KEY_SUFFIX = {"pace": "", "from_pace": "_from", "to_pace": "_to",
               "easy_pace": "_easy", "hard_pace": "_hard"}


def rebase_block(block: dict, zone: str, base_sec: int | None,
                 offset: int | None, pace_key: str = "pace") -> None:
    """
    Заменяет 'pace' на daniels_zone + pace_offset_sec.

    Для from_pace/to_pace/easy_pace/hard_pace используются отдельные ключи
    (daniels_zone_from и т.д.), чтобы прогрессия и фартлек имели свои зоны.
    """
    if pace_key not in block:
        return
    old = block.get(pace_key)
    if not isinstance(old, str) or not re.search(r"\d+:\d{2}", old):
        return
    suffix = _KEY_SUFFIX.get(pace_key, "")
    # legacy храним один раз на блок
    if pace_key == "pace":
        block["pace_legacy"] = old
    else:
        block.setdefault("pace_legacy_" + pace_key, old)
    block["daniels_zone" + suffix] = zone
    if offset is not None:
        block["pace_offset_sec" + suffix] = offset
    # 'pace' удаляем — он вычисляется при планировании
    block.pop(pace_key, None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    d = json.loads(TPL_PATH.read_text(encoding="utf-8"))
    tpl = d["templates"]
    z = daniels.zone_summary(REFERENCE_VDOT)["zones_sec_per_km"]

    # Зона Дэниэлса определяется по HR-зоне блока — это надёжнее, чем по
    # имени шаблона: в 'mixed' один вариант содержит и порог (Z5), и
    # VO2-повторы (Z6).
    HR_ZONE_TO_DANIELS = {
        "Z1": "easy", "Z2": "easy", "Z3": "easy",
        "Z4": "marathon",          # темповая работа
        "Z5": "threshold",         # порог
        "Z6": "interval",          # VO2 / супер-порог
        "Z7": "repetition",        # анаэробная скорость
    }

    changed = 0
    for tid, tpl_i in tpl.items():
        if not isinstance(tpl_i, dict):
            continue
        for v in tpl_i.get("variants", []) or []:
            for b in v.get("blocks", []) or []:
                btype = b.get("type")
                if btype in ("reps", "continuous"):
                    zone = HR_ZONE_TO_DANIELS.get(b.get("zone"), "threshold")
                    off = zone_offset(z.get(zone), b.get("pace"))
                    rebase_block(b, zone, z.get(zone), off)
                    changed += 1
                elif btype == "reps_progression":
                    # Прогрессия: шаги идут от порога к интервалу/повторам.
                    # Зоны задаются здесь: ["threshold", "interval", "repetition"]
                    plist = b.get("paces") or []
                    zlist = b.get("daniels_zones") or ["threshold", "interval", "repetition"]
                    if plist:
                        new_plist, new_zones, offsets = [], [], []
                        for i, pc in enumerate(plist):
                            zn = zlist[i] if i < len(zlist) else zlist[-1]
                            off = zone_offset(z.get(zn), pc)
                            new_plist.append(pc)
                            new_zones.append(zn)
                            offsets.append(off)
                        b["paces"] = new_plist
                        b["daniels_zones"] = new_zones
                        b["pace_offsets_sec"] = offsets
                        b["pace_legacy"] = " / ".join(plist)
                        b.pop("pace", None)
                        changed += 1
                elif btype == "pyramid":
                    steps = b.get("steps") or []
                    new_steps = []
                    for st in steps:
                        st = dict(st)
                        zone = HR_ZONE_TO_DANIELS.get(st.get("zone"), "threshold")
                        off = zone_offset(z.get(zone), st.get("pace"))
                        rebase_block(st, zone, z.get(zone), off)
                        new_steps.append(st)
                        changed += 1
                    b["steps"] = new_steps
                elif btype == "fartlek":
                    if b.get("easy_pace"):
                        off = zone_offset(z.get("easy"), b["easy_pace"])
                        rebase_block(b, "easy", z.get("easy"), off, "easy_pace")
                        changed += 1
                    if b.get("hard_pace"):
                        zone = HR_ZONE_TO_DANIELS.get(b.get("hard_zone"), "threshold")
                        off = zone_offset(z.get(zone), b["hard_pace"])
                        rebase_block(b, zone, z.get(zone), off, "hard_pace")
                        changed += 1
                elif btype == "progression":
                    # начало — easy, конец — по HR-зоне блока (Z3/Z4)
                    if b.get("from_pace"):
                        off = zone_offset(z.get("easy"), b["from_pace"])
                        rebase_block(b, "easy", z.get("easy"), off, "from_pace")
                        changed += 1
                    if b.get("to_pace"):
                        # конец прогрессии — это пороговый уровень (Z3/Z4 в
                        # блоке, но по смыслу — переход в threshold)
                        zone = "threshold"
                        off = zone_offset(z.get(zone), b["to_pace"])
                        rebase_block(b, zone, z.get(zone), off, "to_pace")
                        changed += 1
                elif btype in ("tt_pace", "tt_max"):
                    # темп задаёт контрольная точка — привязываем к зоне
                    zone = HR_ZONE_TO_DANIELS.get(b.get("zone"), "threshold")
                    off = zone_offset(z.get(zone), b.get("pace"))
                    if off is not None:
                        b["daniels_zone"] = zone
                        b["pace_offset_sec"] = off
                        b["pace_legacy"] = b.get("pace")
                        b.pop("pace", None)
                        changed += 1

    # шаблонный pace → описание зон
    d["_daniels_binding"] = {
        "_note": "Каталог привязан к зонам Дэниэлса. Темп в блоке = "
                 "темп зоны для ТЕКУЩЕГО VDOT атлета + pace_offset_sec. "
                 "zone_summary/zone_pace_sec — в lib/daniels.py.",
        "reference_vdot": REFERENCE_VDOT,
        "zones": {k: daniels.fmt_time(v) for k, v in z.items() if v},
        "rebase_script": "scripts/rebase_templates_to_vdot.py",
    }

    if not args.dry:
        TPL_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print("блоков перепривязано: {} ({} режим)".format(
        changed, "сухой" if args.dry else "запись"))
    print("зоны при VDOT {}: {}".format(
        REFERENCE_VDOT, {k: daniels.fmt_time(v) for k, v in z.items() if v}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
