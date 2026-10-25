#!/usr/bin/env python3
"""
apply_vdot_paces.py — применить темпы таблицы Дэниэлса к override'ам недели.

Легкие/длинные сессии не идут через каталог шаблонов — их структура задана
в state/overrides.json. Темпы там тоже зашиты строками.

Скрипт проходит по override'ам и проставляет темпы по зонам Дэниэлса для
ТЕКУЩЕГО VDOT атлета (state/daniels_profile.json):

  Z2 work (обычная)  → темп зоны easy
  Z2 work (длинная)  → easy + 7..17 с (длинная медленнее)
  Z1 warmup          → easy + 12..32 с
  Z1 cooldown        → easy + 22..42 с

Запуск: python3 scripts/apply_vdot_paces.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from lib import daniels  # noqa: E402

OVERRIDES = REPO / "state/overrides.json"
PROFILE = REPO / "state/daniels_profile.json"

# Смещения к темпу зоны easy (с/км) по роли в сессии.
# Роль определяется по фазе, но с запасом: разминка/заминка могут быть
# и под другими именами (work в «лёгкой пятёрке»).
OFFSETS = {
    ("Z2", "work", False): 0,       # обычная лёгкая
    ("Z2", "work", True): 7,        # длинная — медленнее
    ("Z1", "warmup", False): 12,
    ("Z1", "warmup", True): 22,     # в длинной разминка ещё медленнее
    ("Z1", "cooldown", False): 22,
    ("Z1", "cooldown", True): 32,
    ("Z1", "work", False): 32,      # Z1-«работа» (лёгкая пятёрка) — ещё медленнее
}


def main() -> int:
    vdot = json.loads(PROFILE.read_text(encoding="utf-8")).get("vdot", 47)
    easy = daniels.zone_pace_sec("easy", vdot)
    if easy is None:
        print("не удалось получить темп зоны easy для VDOT {}".format(vdot))
        return 1

    ov = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    changed = 0
    for o in ov.get("overrides", []):
        for s in (o.get("replace_slots") or []) + (o.get("add_slots") or []):
            is_long = s.get("subkind") in ("long_Z2", "long_z2")
            for st in (s.get("structure") or []):
                zone = st.get("zone")
                phase = st.get("phase")
                off = OFFSETS.get((zone, phase, is_long))
                if off is None:
                    # фаза может называться иначе — ищем по смыслу
                    if phase in ("cooldown", "заминка"):
                        off = OFFSETS.get((zone, "cooldown", is_long))
                    elif phase in ("warmup", "разминка"):
                        off = OFFSETS.get((zone, "warmup", is_long))
                    elif phase == "work":
                        off = OFFSETS.get((zone, "work", is_long))
                if off is None:
                    continue
                new = daniels.fmt_pace(easy + off)
                if st.get("pace_min_per_km") != new:
                    st["pace_min_per_km"] = new
                    changed += 1
                # помечаем, что темп вычислен по VDOT
                st["pace_vdot"] = vdot

    OVERRIDES.write_text(json.dumps(ov, ensure_ascii=False, indent=2), encoding="utf-8")
    print("темпов обновлено: {} (VDOT {})".format(changed, vdot))
    print("зона easy = {}".format(daniels.fmt_time(easy)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
