"""
zwift_search.py — поиск Zwift-тренировок по критериям.

Phase 2: скрапинг whatsonzwift.com/workouts/ + базовый ranking.
Phase 3: индексированная база + кэш.

Возвращает candidates[] — 2-4 варианта (НЕ 'так и штук').
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any


CRITERIA_SCHEMA = {
    "discipline": str,        # 'cycling' | 'running' | 'swim'
    "duration_min": int,       # целевая длительность
    "duration_tolerance": int, # допуск в минутах (default 10)
    "zones": list,             # ['Z1','Z2','Z3','Z4','Z5'] — какие зоны покрывает workout
    "workout_type": str,       # 'steady' | 'intervals' | 'tempo' | 'recovery' | 'race' | 'mixed'
    "tags": list,             # ['endurance','hills','flat','vo2','threshold'] — произвольные
    "free_text": str,         # "45 min Z2" — будет разпарсен если кризику от Кирилла
}


def parse_free_text(text: str) -> dict[str, Any]:
    """
    '45 min Z2 cycling endurance' → {duration_min:45, zones:['Z2'], discipline:'cycling', tags:['endurance']}.
    Phase 2: простая regex-логика. Phase 3: NLP.
    """
    out = {}
    text_l = text.lower()

    # duration
    m = re.search(r"(\d+)\s*(?:мин|min|м)", text_l)
    if m:
        out["duration_min"] = int(m.group(1))

    # zones
    zones_found = re.findall(r"\bz([1-6])\b", text_l)
    if zones_found:
        out["zones"] = [f"Z{z}" for z in zones_found]

    # discipline
    if "вел" in text_l or "bike" in text_l or "cycling" in text_l:
        out["discipline"] = "cycling"
    elif "бег" in text_l or "run" in text_l:
        out["discipline"] = "running"
    elif "плав" in text_l or "swim" in text_l:
        out["discipline"] = "swim"

    # workout type
    type_map = {
        "steady": ["steady", "ровно", "равномерно"],
        "intervals": ["interval", "интервал"],
        "tempo": ["tempo", "темповая", "темпо"],
        "recovery": ["recovery", "восстанов"],
        "race": ["race", "гонк"],
    }
    for t, keys in type_map.items():
        if any(k in text_l for k in keys):
            out["workout_type"] = t
            break

    # tags
    tag_map = {
        "endurance": ["endurance", "выносл", "объём"],
        "hills": ["hill", "холм", "горк"],
        "flat": ["flat", "ровн"],
        "threshold": ["threshold", "порог"],
        "vo2": ["vo2", "кислород"],
    }
    tags = []
    for tag, keys in tag_map.items():
        if any(k in text_l for k in keys):
            tags.append(tag)
    if tags:
        out["tags"] = tags

    return out


def _rank(workout: dict, criteria: dict) -> float:
    """Чем выше score, тем лучше workout соответствует критериям."""
    score = 0.0
    target = criteria.get("duration_min", 0)
    actual = workout.get("duration_min", 0)
    if target and actual:
        # штраф за отклонение от длительности
        diff = abs(actual - target)
        score -= diff * 2
    if criteria.get("workout_type") == workout.get("workout_type"):
        score += 20
    if criteria.get("zones"):
        overlap = set(criteria["zones"]) & set(workout.get("zones", []))
        score += len(overlap) * 10
    if criteria.get("tags"):
        overlap = set(criteria["tags"]) & set(workout.get("tags", []))
        score += len(overlap) * 5
    return score


def search(criteria: dict[str, Any], max_results: int = 4) -> list[dict[str, Any]]:
    """
    Phase 2: парсит https://whatsonzwift.com/workouts/ и фильтрует по criteria.
    max_results=4 по умолчанию (не 'так и штук' — 2-4 варианта).

    Phase 3: заменить на индексированную базу с кэшем.
    """
    duration = criteria.get("duration_min", 0)
    tolerance = criteria.get("duration_tolerance", 10)
    discipline = criteria.get("discipline", "")

    # Phase 2: парсим страницу workouts
    url = "https://whatsonzwift.com/workouts/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "coach/0.3 (tsybriki)"})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, TimeoutError) as e:
        return [{
            "_error": f"scrape_failed: {e}",
            "url": url,
            "_phase": "2 stub",
        }]

    # Извлекаем workouts из HTML — простой regex (Phase 3: BeautifulSoup)
    pattern = re.compile(
        r'<a[^>]+href="(/workouts/[^"]+)"[^>]*>([^<]+)</a>',
        re.IGNORECASE
    )
    raw = pattern.findall(html)

    # Phase 2 stub: фильтруем по discipline + duration keywords в title
    filtered = []
    for href, title in raw[:50]:  # первые 50 — sample
        title_l = title.lower()
        if discipline == "cycling" and not any(k in title_l for k in ["bike", "вел", "cycle", "ride"]):
            continue
        if discipline == "running" and not any(k in title_l for k in ["run", "бег"]):
            continue
        # duration в title: "45 min" / "45min" / "1h 15m"
        m = re.search(r"(\d+)\s*(?:min|мин|м)", title_l)
        title_duration = int(m.group(1)) if m else 0
        if duration and abs(title_duration - duration) > tolerance:
            continue

        workout = {
            "id": href,
            "title": title.strip(),
            "url": "https://whatsonzwift.com" + href,
            "duration_min": title_duration or duration,
            "zones": [],  # Phase 3: парсить описание
            "workout_type": None,
            "tags": [],
            "_source": "whats_on_zwift",
            "_phase": "2 stub — фильтр только по discipline + duration",
        }
        filtered.append(workout)

    # Ранжирование
    for w in filtered:
        w["_rank_score"] = _rank(w, criteria)

    # Top max_results
    filtered.sort(key=lambda w: w["_rank_score"], reverse=True)
    return filtered[:max_results]


if __name__ == "__main__":
    # Демонстрация парсинга free_text
    examples = ["45 мин Z2 велосипед endurance", "60 min threshold intervals", "30 мин recovery бег"]
    for ex in examples:
        parsed = parse_free_text(ex)
        print(f"  '{ex}' → {json.dumps(parsed, ensure_ascii=False)}")
    print()
    # Демо search (если есть интернет)
    cands = search(parse_free_text("45 мин Z2 cycling"))
    print(f"  search returned {len(cands)} candidates")
    for c in cands[:3]:
        print(f"    {c.get('title', c.get('_error', '?'))}")