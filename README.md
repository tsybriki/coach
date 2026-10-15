# coach

Coaching machinery for Kirill. Архитектура и реализация.

- Полная архитектура: `ARCHITECTURE.html` (открывается в браузере / Telegram preview).
- JSON-исходник: `architecture.json`.
- Phase 1 issue: https://github.com/tsybriki/coach/issues/1
- Phase 2 issue: https://github.com/tsybriki/coach/issues/2

## Структура

```
coach/
├── lib/                        — Python toolkit (тонкие обёртки)
│   ├── metrics/                — метрики через registry + @register
│   └── coaching_corpus/        — принципы с source
├── state/                      — JSON правды (athlete, season_plan, constraints, ...)
├── skills/                     — SKILL.md по схеме coach-<area>-<verb>
├── hooks/                        — Hermes hooks
├── tests/                      — smoke tests (Phase 1: 14/14 passing)
├── requirements.txt            — -e ~/projects/garmin_tools
├── README.md
└── ARCHITECTURE.html + architecture.json
```

## Garmin integration (без дублирования)

`~/projects/garmin_tools/` — это **external dependency**, не часть `~/coach/`.
Там живут реальные интеграции:
- `fit_inspect.py` — реальный FIT-парсер
- `latest_pull.py` / `running_pull.py` — pull из Garmin Connect
- `latest_analyse.py` — per-FIT глубокий разбор (HR drift, сплиты, Riegel)
- `zwift_sync.py` — WhatsOnZwift → Garmin Connect workout
- `main.py` / `main_garmin_only.py` — Renpho sync

`~/coach/lib/` — **тонкие обёртки**:
- `parse_fit.py` → вызывает `garmin_tools/fit_inspect.py` через subprocess
- `fit_ingest.py` → может дёрнуть `garmin_tools/latest_pull.py` для auto-pull
- `lib/metrics/*.py` → пытаются использовать `garmin_tools/latest_analyse.py`
- `garmin_weight.py` → использует `garmin_tools/main.py` для Renpho→Garmin

Подключение: `requirements.txt` содержит `-e /home/tsybriki/projects/garmin_tools`.
Это editable install — правки в garmin_tools сразу видны в coach.

Python: garmin_tools использует свой `.venv` с Python 3.14 (`>=3.12` для garminconnect>=0.3.3).
`~/coach` зовёт `~/projects/garmin_tools/.venv/bin/python` напрямую через subprocess,
поэтому версия Python coach не критична.

**Не дублируй:**
- Не копируй скрипты из `~/projects/garmin_tools/` в `~/coach/lib/`.
- Не переписывай FIT-парсер или Garmin Connect клиент в coach.
- Не трогай `secrets/` в garmin_tools — он НЕ в git и НЕ должен быть в coach.

**Исключение:** `garmin-workout-builder` skill (zwift_sync.py) — оставлен со старым именем.
Это не coach-* потому что его имя отражает источник (Garmin workout), а не задачу.

## Разработка

```bash
cd ~/coach
# Правки
$EDITOR lib/plan_generate.py
# Тесты
python tests/test_phase1_smoke.py
# Git
git add -A && git commit -m "..." && git push
```

Симлинки в `~/.hermes/skills/coach-*` указывают на `~/coach/skills/`.
Один source of truth.

## Версии

- `architecture.json` имеет поле `"version"`. Bump при изменении.
- Phase 1 → v13 (shipped)
- Phase 2 → v14 (current)
- Семантическое: patch = bugfix, minor = backward-compat, major = breaking.