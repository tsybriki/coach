"""Regenerate reviews for 14 and 15 Oct with the new schema (km_splits +
multi_trend sections).
"""
import sys, json
sys.path.insert(0, '/home/tsybriki/coach')
from pathlib import Path
sys.path.insert(0, '/home/tsybriki/coach/tests')
from build_review import build_review

# 14 окт
fit14 = Path('/home/tsybriki/projects/garmin_tools/raw/running/fit/24724230740.fit')
review14 = build_review(
    fit14, date='2026-10-14', slug='berlin-running',
    brief=[
        "85:18 moving (с 17:03 пауз — главная 9:21 ОФП), основная работа 12 км в 5:25-5:35. Каденс 82 spm, Z2 22% / Z3 63% / Z4 9% — выше Z2.",
        "Stryd RD показал VO 6.5 см, Ground Time 290 мс — норма для любителя. Техника стабильная, длинная пробежка была не структурной интервалкой.",
        "Действие: метроном 170 bpm с первого км (каденс 85+), темп 5:50 целенаправленно для поиска настоящей Z2.",
    ],
    summary_line='85:18 moving / 15.16 km @ 5:37/км / HR avg 138 · Z3 63% / Z4 9% · Stryd VO 6.5 см / GT 290 мс',
    recos=[
        {"priority": "now", "text": "Завтра метроном 170 bpm с первого км, цель 85 spm каждую минуту.", "principle": "Каденс-дрель на старте, не на финише."},
        {"priority": "now", "text": "5:50 целенаправленно вместо 5:30. 73% объёма выше Z2.", "principle": "Z2 — диапазон по HR ≤ 138, не по ощущению."},
        {"priority": "soon", "text": "Air power 2.3W — ветра не было. На 5:30 стабильно паузу в часы между labs не делать.", "principle": "Воздух ничтожный — увеличение 3-4W не от техники."},
        {"priority": "later", "text": "Garmin RD (10.7 см) ≠ Stryd VO (6.5 см). Source-of-truth = Stryd. Не путай.", "principle": "Разные sensor fusion, цифры не сопоставимы."},
        {"priority": "later", "text": "Если найдёшь Z2 границу на 5:50 — это базовая отметка W3+. Трендируй.", "principle": "Z2 — фундамент для марафонского сезона."},
    ]
)
out14 = Path('/home/tsybriki/coach/state/reviews/2026-10-14-berlin-running.json')
json.dump(review14, open(out14, 'w'), indent=2, ensure_ascii=False)
print(f'wrote {out14}')

# 15 окт
fit15 = Path('/home/tsybriki/projects/garmin_tools/raw/today/fit/24734796814.fit')
review15 = build_review(
    fit15, date='2026-10-15', slug='berlin-running',
    brief=[
        "65:09 в движении (3:46 мелких пауз, без ОФП), 11.50 км с negative split'ом (km 1: 6:53 → km 9: 5:32). Лучшая структура после 14 окт.",
        "Stryd VO 6.3 см, Ground Time 293 мс — стабильная техника. Каденс 85-86 на финише (Watch/Stryd согласованы, |Δ|=0.5).",
        "Z3 63% + Z4 10% = 73% выше Z2 — та же проблема с темпом. Действие: завтра 5:50 целенаправленно на З2 и метроном с первого км.",
    ],
    summary_line='65:09 moving / 11.50 km @ 5:40/км / HR avg 138 · negative split · cad 85-86 к финишу · Stryd VO 6.3 см / GT 293 мс',
    recos=[
        {"priority": "now", "text": "Метроном 170 bpm с первого км, цель 85 spm каждую минуту.", "principle": "Каденс-дрель на старте, не на финише."},
        {"priority": "now", "text": "Беги 5:50 целенаправленно. 73% объёма выше Z2 — это не Z2.", "principle": "Z2 — диапазон по HR ≤ 138, не по ощущению."},
        {"priority": "soon", "text": "Air power 3.4W (было 2.3). На следующей — если > 10W, это важный сигнал.", "principle": "Air power > 15-20W = встречный ветер или terrain с боковым."},
        {"priority": "later", "text": "Garmin RD (отсутствует в этом FIT) ≠ Stryd. Source-of-truth = Stryd.", "principle": "Гармин RD требует нагрудного ремня; Stryd всегда есть в ботинке."},
        {"priority": "later", "text": "Если найдёшь Z2 границу на 5:50 — это базовая отметка W3+. Трендируй.", "principle": "Z2 — фундамент для полу-марафонского сезона (W28 race)."},
    ]
)
out15 = Path('/home/tsybriki/coach/state/reviews/2026-10-15-berlin-running.json')
json.dump(review15, open(out15, 'w'), indent=2, ensure_ascii=False)
print(f'wrote {out15}')
