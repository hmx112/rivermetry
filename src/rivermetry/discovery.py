from __future__ import annotations

import re
from collections import defaultdict, deque
from datetime import UTC, datetime

import httpx

from rivermetry.adapters.base import UpstreamDataError, UpstreamSchemaError
from rivermetry.selection import demand_score as launch_demand_score

COLLECTIONS_BASE = "https://api.waterdata.usgs.gov/ogcapi/v1/collections"
LATEST_URL = f"{COLLECTIONS_BASE}/latest-continuous/items"
MONITORING_URL = f"{COLLECTIONS_BASE}/monitoring-locations/items"


def _slug(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:72] or "river-station"


def _timezone(abbr: str | None) -> str:
    return {
        "PST": "America/Los_Angeles",
        "PDT": "America/Los_Angeles",
        "MST": "America/Denver",
        "MDT": "America/Denver",
        "CST": "America/Chicago",
        "CDT": "America/Chicago",
        "EST": "America/New_York",
        "EDT": "America/New_York",
        "AKST": "America/Anchorage",
        "AKDT": "America/Anchorage",
        "HST": "Pacific/Honolulu",
    }.get((abbr or "").upper(), "UTC")


def _region_slug(name: str | None, code: str | None) -> str:
    return _slug(name or f"state-{code or 'unknown'}")


def _fetch_features(
    client: httpx.Client,
    url: str,
    params: dict[str, str],
    api_key: str | None,
) -> list[dict]:
    request_params = {"f": "json", "limit": "50000", **params}
    if api_key:
        request_params["api_key"] = api_key
    features: list[dict] = []
    next_url: str | None = url
    next_params: dict[str, str] = request_params
    pages = 0
    while next_url:
        pages += 1
        if pages > 20:
            raise UpstreamSchemaError("USGS discovery pagination exceeded safety limit")
        try:
            response = client.get(
                next_url,
                params=next_params,
                headers={"User-Agent": "Rivermetry/0.1 (+https://rivermetry.example)"},
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamDataError("USGS discovery request failed") from exc
        page_features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(page_features, list):
            raise UpstreamSchemaError("USGS discovery returned no features")
        features.extend(page_features)
        links = payload.get("links") if isinstance(payload, dict) else None
        next_link = next(
            (link for link in links or [] if link.get("rel") == "next" and link.get("href")),
            None,
        )
        next_url = str(next_link["href"]) if next_link else None
        next_params = {"api_key": api_key} if api_key else {}
    return features


def _targeted_metadata_ids(stations: dict[str, dict], limit: int) -> list[str]:
    max_metadata = max(limit * 8, 800)
    buckets: dict[tuple[int, int], deque[tuple[float, str]]] = defaultdict(deque)
    eligible: dict[tuple[int, int], list[tuple[float, str]]] = defaultdict(list)
    for monitoring_id, station in stations.items():
        if station["parameters"] != {"00060", "00065"} or not station["ages"]:
            continue
        age_minutes = max(station["ages"])
        if age_minutes > 90:
            continue
        coordinates = station.get("coordinates") or [None, None]
        if len(coordinates) < 2 or coordinates[0] is None or coordinates[1] is None:
            continue
        longitude, latitude = coordinates[0], coordinates[1]
        grid = (int((float(latitude) + 90) // 5), int((float(longitude) + 180) // 5))
        eligible[grid].append((age_minutes, monitoring_id))
    for grid, values in eligible.items():
        buckets[grid] = deque(sorted(values, key=lambda item: (item[0], item[1])))
    selected: list[str] = []
    grid_keys = sorted(buckets)
    while len(selected) < max_metadata and grid_keys:
        next_keys = []
        for key in grid_keys:
            if buckets[key] and len(selected) < max_metadata:
                selected.append(buckets[key].popleft()[1])
            if buckets[key]:
                next_keys.append(key)
        grid_keys = next_keys
    return selected


def _fetch_targeted_metadata(
    client: httpx.Client, monitoring_ids: list[str], api_key: str | None
) -> dict[str, dict]:
    metadata: dict[str, dict] = {}
    for offset in range(0, len(monitoring_ids), 100):
        batch = monitoring_ids[offset : offset + 100]
        params = {"f": "json", "limit": "100"}
        if api_key:
            params["api_key"] = api_key
        headers = {
            "User-Agent": "Rivermetry/0.1 (+https://rivermetry.example)",
            "Content-Type": "application/query-cql-json",
        }
        body = {"op": "in", "args": [{"property": "id"}, batch]}
        try:
            response = client.post(
                MONITORING_URL,
                params=params,
                headers=headers,
                json=body,
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamDataError("USGS targeted metadata request failed") from exc
        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise UpstreamSchemaError("USGS targeted metadata returned no features")
        for feature in features:
            props = feature.get("properties") or {}
            station_number = str(props.get("monitoring_location_number") or "")
            station_id = str(feature.get("id") or "")
            if not station_id and station_number:
                station_id = f"USGS-{station_number}"
            if station_id:
                metadata[station_id] = feature
    return metadata


def discover_usgs_candidates(
    client: httpx.Client, limit: int = 450, api_key: str | None = None
) -> list[dict]:
    latest_features = []
    for parameter_code in ("00060", "00065"):
        latest_features.extend(
            _fetch_features(
                client,
                LATEST_URL,
                {
                    "parameter_code": parameter_code,
                    "agency_code": "USGS",
                    "site_type_code": "ST",
                },
                api_key,
            )
        )

    stations: dict[str, dict] = defaultdict(
        lambda: {"parameters": set(), "ages": [], "coordinates": None}
    )
    now = datetime.now(UTC)
    for feature in latest_features:
        props = feature.get("properties") or {}
        parameter = props.get("parameter_code")
        if parameter not in {"00060", "00065"}:
            continue
        monitoring_id = str(props.get("monitoring_location_id") or "")
        if not monitoring_id:
            continue
        try:
            observed = datetime.fromisoformat(str(props.get("time") or ""))
            age_minutes = max(0, (now - observed).total_seconds() / 60)
        except ValueError:
            continue
        item = stations[monitoring_id]
        item["parameters"].add(parameter)
        item["ages"].append(age_minutes)
        coordinates = (feature.get("geometry") or {}).get("coordinates")
        if coordinates and len(coordinates) >= 2:
            item["coordinates"] = coordinates

    metadata_ids = _targeted_metadata_ids(stations, limit)
    metadata = _fetch_targeted_metadata(client, metadata_ids, api_key)

    qualified = []
    for monitoring_id in metadata_ids:
        station = stations[monitoring_id]
        feature = metadata.get(monitoring_id)
        if not feature:
            continue
        props = feature.get("properties") or {}
        coordinates = (feature.get("geometry") or {}).get("coordinates") or station.get(
            "coordinates"
        )
        if (
            not coordinates
            or len(coordinates) < 2
            or coordinates[0] is None
            or coordinates[1] is None
        ):
            continue
        station_id = str(
            props.get("monitoring_location_number") or monitoring_id.removeprefix("USGS-")
        )
        name = str(props.get("monitoring_location_name") or station_id)
        state_name = str(props.get("state_name") or "Unknown")
        state_code = str(props.get("state_code") or "")
        region = _region_slug(state_name, state_code)
        age_minutes = max(station["ages"])
        data_quality = 35 if age_minutes <= 30 else 25
        drainage_area = props.get("drainage_area")
        history_score = 8 if drainage_area else 5
        candidate = {
            "location_id": f"us-{region}-{station_id}",
            "status": "candidate",
            "country_code": "us",
            "region_code": region,
            "slug": _slug(name),
            "river_name": name.split(" AT ")[0].split(" NR ")[0].title(),
            "station_name": name.title(),
            "observation_provider": "usgs",
            "station_id": station_id,
            "latitude": coordinates[1],
            "longitude": coordinates[0],
            "timezone": _timezone(props.get("time_zone_abbreviation")),
            "state_name": state_name,
            "drainage_area": drainage_area,
            "hard_gate": True,
            "data_quality_score": data_quality,
            "history_score": history_score,
            "geographic_score": 10,
            "nearby_score": 3,
            "nwps_match": False,
        }
        candidate["demand_score"] = launch_demand_score(candidate)
        qualified.append(candidate)
    qualified.sort(
        key=lambda item: (
            -item["data_quality_score"],
            -item["demand_score"],
            -float(item.get("drainage_area") or 0),
            item["station_id"],
        )
    )

    by_state: dict[str, deque] = defaultdict(deque)
    for item in qualified:
        by_state[item["region_code"]].append(item)
    selected: list[dict] = []
    state_keys = sorted(by_state)
    while len(selected) < limit and state_keys:
        next_keys = []
        for key in state_keys:
            if by_state[key] and len(selected) < limit:
                selected.append(by_state[key].popleft())
            if by_state[key]:
                next_keys.append(key)
        state_keys = next_keys
    return selected
