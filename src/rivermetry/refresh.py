from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

import httpx

from rivermetry.adapters.base import UpstreamDataError
from rivermetry.adapters.usgs import USGSAdapter
from rivermetry.forecasts.nwps import NWPSForecastAdapter
from rivermetry.history.context import daily_context, recent_change
from rivermetry.models import Location, LocationSnapshot, LocationStatus, Observation
from rivermetry.validation.observations import freshness_state
from rivermetry.validation.trend import calculate_gage_trend


def assemble_snapshot(
    location: Location,
    series: dict,
    daily_values: list[float],
    forecast,
    now: datetime,
) -> LocationSnapshot:
    level_series = tuple(series.get("water_level") or ())
    flow_series = tuple(series.get("streamflow") or ())
    water_level = (
        Observation(level_series[-1].value, "ft", level_series[-1].observed_at)
        if level_series
        else None
    )
    streamflow = (
        Observation(flow_series[-1].value, "ft3/s", flow_series[-1].observed_at)
        if flow_series
        else None
    )

    if water_level is None or streamflow is None:
        update_status = "unavailable"
    else:
        oldest_required = min(water_level.observed_at, streamflow.observed_at)
        update_status = freshness_state(oldest_required, now)

    context = daily_context(daily_values)
    context["changes"] = {
        "1h": recent_change(level_series, 1),
        "6h": recent_change(level_series, 6),
        "24h": recent_change(level_series, 24),
    }
    context["streamflow_unit"] = "ft3/s"

    return LocationSnapshot(
        location=location,
        water_level=water_level,
        streamflow=streamflow,
        trend=calculate_gage_trend(level_series),
        level_series=level_series,
        flow_series=flow_series,
        history_context=context,
        forecast=forecast,
        update_status=update_status,
    )


def fetch_location_snapshot(
    client: httpx.Client,
    location: Location,
    api_key: str | None = None,
    now: datetime | None = None,
) -> LocationSnapshot:
    now = now or datetime.now(UTC)
    usgs = USGSAdapter(client, api_key)
    start = now - timedelta(hours=25)
    daily_start = now - timedelta(days=35)
    series = usgs.fetch_series(location.station_id, start.isoformat(), now.isoformat())
    daily_values = usgs.fetch_daily(
        location.station_id,
        daily_start.date().isoformat(),
        now.date().isoformat(),
    )

    forecast = None
    if location.forecast_provider == "noaa_nwps" and location.forecast_location_id:
        try:
            forecast = NWPSForecastAdapter(client).fetch(location.forecast_location_id)
        except UpstreamDataError:
            forecast = None

    return assemble_snapshot(location, series, daily_values, forecast, now)


def refresh_live_snapshots(
    client: httpx.Client,
    locations: tuple[Location, ...] | list[Location],
    api_key: str | None = None,
    max_workers: int = 6,
) -> dict[str, LocationSnapshot]:
    live = [location for location in locations if location.status == LocationStatus.LIVE]
    now = datetime.now(UTC)
    snapshots: dict[str, LocationSnapshot] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_location_snapshot, client, location, api_key, now): location
            for location in live
        }
        for future in as_completed(futures):
            location = futures[future]
            snapshots[location.location_id] = future.result()
    return snapshots
