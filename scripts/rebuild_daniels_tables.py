"""Пересборка разобранных таблиц Дэниэлса из сырых файлов.

Сырьё — источник правды: reference/daniels/raw_*.txt (как прислано).
Разобранный daniels_tables.json — производный артефакт, он пересобирается
из сырья, а не правится руками.

Запуск: python3 scripts/rebuild_daniels_tables.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import daniels  # noqa: E402

JSON_PATH = ROOT / "reference" / "daniels" / "daniels_tables.json"


def main() -> int:
    tables = daniels._parse_all()
    JSON_PATH.write_text(
        json.dumps(tables, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"записано: {JSON_PATH}")
    print(f"  темпов: {len(tables['training_paces'])} строк")
    print(f"  гонок:  {len(tables['race_times'])} строк")
    return 0


if __name__ == "__main__":
    sys.exit(main())
