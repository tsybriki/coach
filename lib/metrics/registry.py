"""
registry.py — реестр метрик. @register('hr_drift') декоратор.

При добавлении новой метрики: копируешь _template.py, реализуешь compute(),
регистрируешь через @register('my_metric'). Всё, она в игре.
"""
from __future__ import annotations

from typing import Callable, Any


_REGISTRY: dict[str, Callable[[dict], dict]] = {}


def register(metric_id: str):
    """Декоратор: @register('hr_drift')"""
    def deco(fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
        if metric_id in _REGISTRY:
            raise ValueError(f"metric '{metric_id}' already registered")
        _REGISTRY[metric_id] = fn
        return fn
    return deco


def list_active() -> list[str]:
    return sorted(_REGISTRY.keys())


def call(metric_id: str, fit: dict) -> dict[str, Any]:
    """Вызвать метрику. Если метрики нет — KeyError."""
    if metric_id not in _REGISTRY:
        raise KeyError(f"metric '{metric_id}' not registered; active: {list_active()}")
    return _REGISTRY[metric_id](fit)


def all_metrics_for_fit(fit: dict) -> dict[str, dict]:
    """Все метрики для одного FIT. Возвращает {metric_id: result}."""
    return {mid: fn(fit) for mid, fn in _REGISTRY.items()}