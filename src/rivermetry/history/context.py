from statistics import fmean

from rivermetry.models import ObservationSeriesPoint


def recent_change(points: tuple[ObservationSeriesPoint, ...], hours: int) -> float | None:
    if len(points) < 2:
        return None
    ordered = sorted(points, key=lambda point: point.observed_at)
    newest = ordered[-1]
    target_seconds = hours * 3600
    candidates = [
        point
        for point in ordered[:-1]
        if 0.7 * target_seconds
        <= (newest.observed_at - point.observed_at).total_seconds()
        <= 1.3 * target_seconds
    ]
    if not candidates:
        return None
    prior = min(
        candidates,
        key=lambda point: abs(
            (newest.observed_at - point.observed_at).total_seconds() - target_seconds
        ),
    )
    return round(newest.value - prior.value, 3)


def daily_context(values: list[float]) -> dict[str, float | int | None]:
    cleaned = [float(value) for value in values]
    seven = cleaned[-7:] if len(cleaned) >= 7 else []
    thirty = cleaned[-30:] if len(cleaned) >= 30 else []
    return {
        "seven_day_average": round(fmean(seven), 3) if seven else None,
        "seven_day_sample_count": len(seven),
        "thirty_day_average": round(fmean(thirty), 3) if thirty else None,
        "thirty_day_sample_count": len(thirty),
    }
