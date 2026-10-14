"""
coach.lib — Python toolkit для спортивного слоя Hermes.

Правила:
- Модель вызывается ТОЛЬКО через ask_model.py.
- skill/агент НЕ пишет промпты руками.
- FIT retention — единственная функция, имеющая право удалить FIT-файл.
- plan_generate читает constraints, НЕ правит.
- goal_allocator возвращает candidates[], НЕ выбирает за Кирилла.
"""
__version__ = "0.1.0"