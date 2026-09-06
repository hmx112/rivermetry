from __future__ import annotations

REGISTRY_FIELDS = (
    "location_id",
    "status",
    "country_code",
    "region_code",
    "slug",
    "river_name",
    "station_name",
    "observation_provider",
    "station_id",
    "latitude",
    "longitude",
    "timezone",
    "forecast_provider",
    "forecast_location_id",
    "state_name",
    "drainage_area",
    "launch_validated_at",
)


def _public_path(item: dict) -> str:
    return f"/{item['country_code']}/{item['region_code']}/{item['slug']}/"


def promote_launch_preview(preview: list[dict], validated_at: str) -> list[dict]:
    if len(preview) != 150:
        raise ValueError(f"launch promotion requires exactly 150 locations; found {len(preview)}")
    if not validated_at or not validated_at.strip():
        raise ValueError("launch promotion requires validation timestamp")

    location_ids: set[str] = set()
    station_ids: set[str] = set()
    public_paths: set[str] = set()
    registry: list[dict] = []

    for item in preview:
        if item.get("status") != "preview":
            raise ValueError("launch promotion only accepts preview locations")
        if item.get("country_code") != "us":
            raise ValueError("launch promotion only accepts US locations")
        if item.get("observation_provider") != "usgs" or not item.get("station_id"):
            raise ValueError("launch promotion requires a USGS station for every location")

        location_id = str(item.get("location_id") or "")
        station_id = str(item.get("station_id") or "")
        public_path = _public_path(item)
        if location_id in location_ids or station_id in station_ids or public_path in public_paths:
            raise ValueError("duplicate location id, station id, or public path")
        location_ids.add(location_id)
        station_ids.add(station_id)
        public_paths.add(public_path)

        official_forecast = bool(item.get("nwps_forecast")) and bool(item.get("nwps_lid"))
        row = {
            "location_id": location_id,
            "status": "live",
            "country_code": "us",
            "region_code": str(item["region_code"]),
            "slug": str(item["slug"]),
            "river_name": str(item["river_name"]),
            "station_name": str(item["station_name"]),
            "observation_provider": "usgs",
            "station_id": station_id,
            "latitude": float(item["latitude"]),
            "longitude": float(item["longitude"]),
            "timezone": str(item.get("timezone") or "UTC"),
            "forecast_provider": "noaa_nwps" if official_forecast else None,
            "forecast_location_id": str(item["nwps_lid"]) if official_forecast else None,
            "state_name": item.get("state_name"),
            "drainage_area": item.get("drainage_area"),
            "launch_validated_at": validated_at.strip(),
        }
        registry.append({field: row[field] for field in REGISTRY_FIELDS})

    return registry
