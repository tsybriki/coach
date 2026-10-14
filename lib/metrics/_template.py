"""
_template.py — шаблон новой метрики.

Скопируй в новый файл (например, my_metric.py), реализуй compute(),
замени @register('placeholder') на @register('my_metric').
"""
from __future__ import annotations

from typing import Any
from .registry import register


@register("placeholder")
def compute(fit: dict) -> dict[str, Any]:
    """
    Метрика = чистая функция. Вход — FIT-dict (стабильная схема parse_fit.py).
    Выход — dict с результатом.

    Пример структуры:
    {
      "value": 0.0,         # главная цифра
      "unit": "bpm",         # единица
      "target": 0.0,         # цель (если есть)
      "deviation": 0.0,      # отклонение от target
      "confidence": 0.0,     # 0..1 — насколько можно доверять
      "source_splits": [],   # какие сплиты участвовали
      "notes": ""
    }
    """
    return {
        "value": 0.0,
        "unit": "",
        "target": None,
        "deviation": None,
        "confidence": 0.0,
        "notes": "Phase 1 stub — реализуй перед использованием",
    }