"""
season_week.py — утилиты конвертации season_week ↔ date ↔ iso_week.

Единый счётчик W1..W~49. W1 = season_start_date (2026-10-11, Sun). Week runs Sun→Sat..
season_week НЕ зависит от ISO недели — это ordinal с начала сезона.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta


def _parse(d: str | date) -> date:
    if isinstance(d, date):
        return d
    return datetime.strptime(d, "%Y-%m-%d").date()


def season_week_to_dates(season_week: int, season_start: str | date = "2026-10-11") -> tuple[date, date]:
    """W1 = [start, start+6]. W2 = [start+7, start+13]."""
    start = _parse(season_start)
    week_start = start + timedelta(days=7 * (season_week - 1))
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def date_to_season_week(d: str | date, season_start: str | date = "2026-10-11") -> int:
    """Обратная конвертация. До старта → 0. После — какой W (1-based)."""
    target = _parse(d)
    start = _parse(season_start)
    if target < start:
        return 0
    delta_days = (target - start).days
    return (delta_days // 7) + 1


def season_week_to_iso(season_week: int, season_start: str | date = "2026-10-11") -> str:
    """W1 → '2026-W42' (берёт ПОНЕДЕЛЬНИК недели, чтобы season_week не зависел от Sun-старта).

    Нюанс: если season_start = Sun, week_start (Sun) принадлежит предыдущей ISO-неделе.
    Берём week_start + 1 day (Mon), чтобы получить правильную ISO-неделю season_week.
    """
    week_start, _ = season_week_to_dates(season_week, season_start)
    monday = week_start + timedelta(days=1)
    iso_year, iso_week, _ = monday.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def iso_to_season_week(iso: str, season_start: str | date = "2026-10-11") -> int:
    """'2026-W42' → W1 (берём ПОНЕДЕЛЬНИК iso-недели)."""
    year, w = iso.split("-W")
    # Понедельник iso-недели
    monday = datetime.strptime(f"{year}-W{int(w)}-1", "%G-W%V-%u").date()
    return date_to_season_week(monday, season_start)


def phase_for_season_week(season_week: int, phases: list[dict],
                          season_start: str | date = "2026-10-11") -> dict | None:
    """Возвращает phase в которой находится season_week."""
    for ph in phases:
        s = date_to_season_week(ph["start"], season_start)
        e = date_to_season_week(ph.get("end", ph["start"]), season_start)
        if s <= season_week <= e:
            return {**ph, "_season_week_start": s, "_season_week_end": e}
    return None


def control_points_for_season_week(season_week: int, control_points: list[dict],
                                    season_start: str | date = "2026-10-11") -> list[dict]:
    """Возвращает CP которые попадают в season_week."""
    out = []
    for cp in control_points:
        if date_to_season_week(cp["date"], season_start) == season_week:
            out.append(cp)
    return out


def total_season_weeks(season_end: str | date, season_start: str | date = "2026-10-11") -> int:
    """Общее число недель в сезоне."""
    end = _parse(season_end)
    start = _parse(season_start)
    return ((end - start).days // 7) + 1


if __name__ == "__main__":
    print("W1:", season_week_to_dates(1))
    print("W12:", season_week_to_dates(12))
    print("W26:", season_week_to_dates(26))   # хочу race_run на W27
    print("W27:", season_week_to_dates(27))   # 12-18 апр 2027 = race_run
    print("W28:", season_week_to_dates(28))   # transition
    print()
    print("iso W42 → season_week:", iso_to_season_week("2026-W42"))  # должно быть 1
    print("date 2026-10-15 →", date_to_season_week("2026-10-15"))    # 1
    print("date 2027-04-18 (10К race) →", date_to_season_week("2027-04-18"))  # 27
    print("date 2027-09-12 (tri race) →", date_to_season_week("2027-09-12"))  # ???
    print()
    print("W1 iso:", season_week_to_iso(1))
    print("W27 iso:", season_week_to_iso(27))   # race_run
    print()
    print("total season weeks:", total_season_weeks("2027-09-12"))  # 46
