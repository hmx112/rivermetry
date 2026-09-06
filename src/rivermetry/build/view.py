from __future__ import annotations

from datetime import datetime

from rivermetry.models import LocationSnapshot, Observation, ObservationSeriesPoint


def display_unit(unit: str | None) -> str:
    value = (unit or "").strip()
    return {
        "ft3/s": "ft³/s",
        "ft^3/s": "ft³/s",
        "cfs": "cfs",
        "kcfs": "kcfs",
    }.get(value, value)


def measurement_text(observation: Observation | None) -> str:
    if observation is None:
        return "Unavailable"
    return f"{observation.value:g} {display_unit(observation.unit)}".strip()


def _time_text(value: datetime | None) -> str:
    if value is None:
        return "Unavailable"
    return value.isoformat()


def chart_context(points: tuple[ObservationSeriesPoint, ...]) -> dict | None:
    if len(points) < 2:
        return None
    ordered = sorted(points, key=lambda point: point.observed_at)
    start = ordered[0].observed_at.timestamp()
    end = ordered[-1].observed_at.timestamp()
    if end <= start:
        return None
    values = [point.value for point in ordered]
    low = min(values)
    high = max(values)
    spread = high - low
    width = 720.0
    height = 180.0
    pad = 12.0
    drawable_w = width - pad * 2
    drawable_h = height - pad * 2
    coords = []
    for point in ordered:
        x = pad + ((point.observed_at.timestamp() - start) / (end - start)) * drawable_w
        if spread == 0:
            y = height / 2
        else:
            y = pad + ((high - point.value) / spread) * drawable_h
        coords.append(f"{x:.1f},{y:.1f}")
    return {
        "points": " ".join(coords),
        "min": low,
        "max": high,
        "current": ordered[-1].value,
    }


def _change_text(value) -> str:
    if value is None:
        return "Unavailable"
    number = float(value)
    return f"{number:+.2f} ft"


def _forecast_context(snapshot: LocationSnapshot) -> dict | None:
    forecast = snapshot.forecast
    if forecast is None or not forecast.values:
        return None
    rows = []
    for item in forecast.values[:8]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "valid_time": item.get("valid_time"),
                "primary": item.get("primary"),
                "primary_unit": display_unit(item.get("primary_unit")),
                "secondary": item.get("secondary"),
                "secondary_unit": display_unit(item.get("secondary_unit")),
            }
        )
    categories = forecast.official_categories[0] if forecast.official_categories else {}
    return {
        "issued_at": forecast.updated_at.isoformat(),
        "rows": rows,
        "categories": categories if isinstance(categories, dict) else {},
    }


def location_view(snapshot: LocationSnapshot | None) -> dict:
    if snapshot is None:
        return {
            "level_text": "Unavailable",
            "flow_text": "Unavailable",
            "observed_text": "Unavailable",
            "static_observed": "",
            "trend_text": "Unknown",
            "notice": None,
            "level_chart": None,
            "flow_chart": None,
            "changes": {},
            "seven_day_average": None,
            "thirty_day_average": None,
            "streamflow_unit": "",
            "forecast": None,
        }

    observed_times = [
        observation.observed_at
        for observation in (snapshot.water_level, snapshot.streamflow)
        if observation is not None
    ]
    newest = max(observed_times) if observed_times else None
    unavailable = snapshot.update_status == "unavailable"
    notice = None
    if snapshot.update_status == "delayed":
        notice = "Data update delayed"
    elif unavailable:
        notice = "Current observation unavailable"

    context = snapshot.history_context or {}
    changes = context.get("changes") if isinstance(context.get("changes"), dict) else {}
    return {
        "level_text": "Unavailable" if unavailable else measurement_text(snapshot.water_level),
        "flow_text": "Unavailable" if unavailable else measurement_text(snapshot.streamflow),
        "observed_text": _time_text(newest),
        "static_observed": newest.isoformat() if newest else "",
        "trend_text": snapshot.trend.value.title(),
        "notice": notice,
        "level_chart": chart_context(snapshot.level_series),
        "flow_chart": chart_context(snapshot.flow_series),
        "changes": {
            "1h": _change_text(changes.get("1h")),
            "6h": _change_text(changes.get("6h")),
            "24h": _change_text(changes.get("24h")),
        },
        "seven_day_average": context.get("seven_day_average"),
        "thirty_day_average": context.get("thirty_day_average"),
        "streamflow_unit": display_unit(context.get("streamflow_unit")),
        "forecast": _forecast_context(snapshot),
    }
