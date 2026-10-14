"""
ask_model.py — единственная обёртка над LLM. JSON-schema валидатор + обязательное cited_principle.

Phase 1: заглушка. Phase 2: реальный вызов API (например MiniMax-M3 через hermes),
          JSON-schema валидация, audit в decisions/.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def ask(system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None = None,
        corpus_root: str | Path = "lib/coaching_corpus",
        decisions_root: str | Path = "decisions") -> dict[str, Any]:
    """
    Phase 1: возвращает stub-ответ с пометкой.

    Контракт Phase 2:
      - вызывает LLM с system + user
      - парсит ответ как JSON
      - если json_schema задана — валидирует (jsonschema или ручная проверка)
      - если kind ∈ {coaching, lookback} → требует cited_principle.id ∈ corpus_index
      - пишет audit в decisions/<date>-<slot>.json
    """
    now = datetime.now(timezone.utc)
    return {
        "_stub": True,
        "_phase": 1,
        "would_call_model": True,
        "system_prompt_preview": system_prompt[:120],
        "user_prompt_preview": user_prompt[:120],
        "json_schema_keys": list((json_schema or {}).keys()),
        "timestamp": now.isoformat(timespec="seconds"),
    }


def validate_coaching_output(output: dict, corpus_index: dict) -> list[str]:
    """
    Проверяет, что cited_principle.id существует в corpus_index.
    Возвращает список ошибок (пустой если всё ок).
    """
    errors = []
    cp = output.get("cited_principle")
    if not cp:
        errors.append("missing cited_principle (required for coaching/lookback)")
        return errors
    cp_id = cp.get("id")
    if not cp_id:
        errors.append("cited_principle.id is empty")
        return errors
    valid_ids = {p["id"] for p in corpus_index.get("principles", [])}
    if cp_id not in valid_ids:
        errors.append(f"cited_principle.id='{cp_id}' not in corpus_index ({sorted(valid_ids)})")
    return errors