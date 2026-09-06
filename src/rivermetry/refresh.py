from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

import httpx

from rivermetry.adapters.base import UpstreamDataError, UpstreamSchemaError
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
    """Fetch one location directly; retained for focused diagnostics/tests.

    Production refreshes use ``refresh_live_snapshots`` so USGS observations are
    fetched in bounded multi-station batches instead of one request per station.
    """
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

    forecast = _fetch_optional_forecast(client, location)
    return assemble_snapshot(location, series, daily_values, forecast, now)


def _fetch_optional_forecast(client: httpx.Client, location: Location):
    if location.forecast_provider != "noaa_nwps" or not location.forecast_location_id:
        return None
    try:
        return NWPSForecastAdapter(client).fetch(location.forecast_location_id)
    except (UpstreamDataError, UpstreamSchemaError):
        return None


def refresh_live_snapshots(
    client: httpx.Client,
    locations: tuple[Location, ...] | list[Location],
    api_key: str | None = None,
    max_workers: int = 6,
) -> dict[str, LocationSnapshot]:
    live = [location for location in locations if location.status == LocationStatus.LIVE]
    if not live:
        return {}

    now = datetime.now(UTC)
    start = now - timedelta(hours=25)
    daily_start = now - timedelta(days=35)
    station_ids = [location.station_id for location in live]

    # USGS is intentionally fetched in bounded CQL2 batches. For 150 launch
    # gauges this is roughly 9 upstream requests instead of ~300 per-station
    # requests, which avoids rate-limit spikes and keeps the scheduled refresh
    # within the free public-data operating model.
    usgs = USGSAdapter(client, api_key)
    series_by_station = usgs.fetch_series_bulk(
        station_ids,
        start.isoformat(),
        now.isoformat(),
    )
    daily_by_station = usgs.fetch_daily_bulk(
        station_ids,
        daily_start.date().isoformat(),
        now.date().isoformat(),
    )

    forecasts: dict[str, object] = {}
    forecast_locations = [
        location
        for location in live
        if location.forecast_provider == "noaa_nwps" and location.forecast_location_id
    ]
    if forecast_locations:
        with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 6))) as executor:
            futures = {
                executor.submit(_fetch_optional_forecast, client, location): location
                for location in forecast_locations
            }
            for future in as_completed(futures):
                location = futures[future]
                forecasts[location.location_id] = future.result()

    snapshots: dict[str, LocationSnapshot] = {}
    empty_series = {"water_level": (), "streamflow": ()}
    for location in live:
        snapshots[location.location_id] = assemble_snapshot(
            location,
            series_by_station.get(location.station_id, empty_series),
            daily_by_station.get(location.station_id, []),
            forecasts.get(location.location_id),
            now,
        )
    return snapshots
