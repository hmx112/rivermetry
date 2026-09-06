from rivermetry.config import TREND_DEADBAND_FT, TREND_WINDOW_MINUTES
from rivermetry.models import ObservationSeriesPoint, TrendDirection


def calculate_gage_trend(
    points: tuple[ObservationSeriesPoint, ...],
    window_minutes: int = TREND_WINDOW_MINUTES,
    deadband_ft: float = TREND_DEADBAND_FT,
) -> TrendDirection:
    if len(points) < 2:
        return TrendDirection.UNKNOWN
    ordered = sorted(points, key=lambda point: point.observed_at)
    newest = ordered[-1]
    candidates = []
    for point in ordered[:-1]:
        age = (newest.observed_at - point.observed_at).total_seconds() / 60
        if 45 <= age <= 75:
            candidates.append((abs(age - window_minutes), point))
    if not candidates:
        return TrendDirection.UNKNOWN
    prior = min(candidates, key=lambda item: item[0])[1]
    delta = newest.value - prior.value
    if abs(delta) <= deadband_ft:
        return TrendDirection.STEADY
    return TrendDirection.RISING if delta > 0 else TrendDirection.FALLING
