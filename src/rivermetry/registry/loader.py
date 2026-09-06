from __future__ import annotations

import json
from pathlib import Path

from rivermetry.models import Location, LocationStatus


def location_from_dict(item: dict) -> Location:
    return Location(
        location_id=item["location_id"],
        status=LocationStatus(item["status"]),
        country_code=item["country_code"],
        region_code=item["region_code"],
        slug=item["slug"],
        river_name=item["river_name"],
        station_name=item["station_name"],
        observation_provider=item["observation_provider"],
        station_id=item["station_id"],
        latitude=float(item["latitude"]),
        longitude=float(item["longitude"]),
        timezone=item.get("timezone", "UTC"),
        forecast_provider=item.get("forecast_provider"),
        forecast_location_id=item.get("forecast_location_id"),
        state_name=item.get("state_name"),
        drainage_area=item.get("drainage_area"),
        launch_validated_at=item.get("launch_validated_at"),
    )


def load_locations(path: str | Path = "data/locations.json") -> tuple[Location, ...]:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, list):
        raise ValueError("locations registry must be a JSON array")
    locations = tuple(location_from_dict(item) for item in raw)
    ids = [loc.location_id for loc in locations]
    paths = [loc.public_path for loc in locations]
    stations = [loc.station_id for loc in locations if loc.status == LocationStatus.LIVE]
    if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
        raise ValueError("duplicate location id or public path")
    if len(stations) != len(set(stations)):
        raise ValueError("duplicate live USGS station")
    return locations
