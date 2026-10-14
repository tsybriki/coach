"""
lib.metrics — одна метрика = один файл. registry.py + @register.
Метрика = чистая функция (FIT-dict) → dict. Никакого I/O.
"""
# Подгружаем все метрики, чтобы @register сработал
from . import hr_drift  # noqa: F401
from . import cadence_30s  # noqa: F401
from . import pace_variability  # noqa: F401
from . import training_effect  # noqa: F401
from . import fatigue_score  # noqa: F401
from . import transition_efficiency  # noqa: F401
from . import race_pace_under_fatigue  # noqa: F401
from . import registry  # noqa: F401