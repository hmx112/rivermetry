from __future__ import annotations

import re
from collections import defaultdict, deque
from datetime import UTC, datetime

import httpx

from rivermetry.adapters.base import UpstreamDataError, UpstreamSchemaError

COLLECTIONS_BASE = "https://api.waterdata.usgs.gov/ogcapi/v0/collections"
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
    try:
        response = client.get(
            url,
            params=request_params,
            headers={"User-Agent": "Rivermetry/0.1 (+https://rivermetry.example)"},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise UpstreamDataError("USGS discovery request failed") from exc
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        raise UpstreamSchemaError("USGS discovery returned no features")
    return features


def discover_usgs_candidates(
    client: httpx.Client, limit: int = 450, api_key: str | None = None
) -> list[dict]:
    monitoring_features = _fetch_features(
        client,
        MONITORING_URL,
        {"agency_code": "USGS", "site_type_code": "ST"},
        api_key,
    )
    metadata: dict[str, dict] = {}
    for feature in monitoring_features:
        props = feature.get("properties") or {}
        station_number = str(props.get("monitoring_location_number") or "")
        station_id = str(feature.get("id") or "")
        if not station_id and station_number:
            station_id = f"USGS-{station_number}"
        if station_id:
            metadata[station_id] = feature

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

    stations: dict[str, dict] = defaultdict(lambda: {"parameters": set(), "ages": []})
    now = datetime.now(UTC)
    for feature in latest_features:
        props = feature.get("properties") or {}
        parameter = props.get("parameter_code")
        if parameter not in {"00060", "00065"}:
            continue
        monitoring_id = str(props.get("monitoring_location_id") or "")
        if monitoring_id not in metadata:
            continue
        try:
            observed = datetime.fromisoformat(str(props.get("time") or ""))
            age_minutes = max(0, (now - observed).total_seconds() / 60)
        except ValueError:
            continue
        item = stations[monitoring_id]
        item["parameters"].add(parameter)
        item["ages"].append(age_minutes)

    qualified = []
    for monitoring_id, station in stations.items():
        if station["parameters"] != {"00060", "00065"}:
            continue
        feature = metadata[monitoring_id]
        props = feature.get("properties") or {}
        coordinates = (feature.get("geometry") or {}).get("coordinates", [None, None])
        if len(coordinates) < 2 or coordinates[0] is None or coordinates[1] is None:
            continue
        station_id = str(
            props.get("monitoring_location_number") or monitoring_id.removeprefix("USGS-")
        )
        name = str(props.get("monitoring_location_name") or station_id)
        state_name = str(props.get("state_name") or "Unknown")
        state_code = str(props.get("state_code") or "")
        region = _region_slug(state_name, state_code)
        age_minutes = max(station["ages"])
        data_quality = 35 if age_minutes <= 30 else 25 if age_minutes <= 90 else 10
        drainage_area = props.get("drainage_area")
        history_score = 8 if drainage_area else 5
        demand_score = 8
        if any(token in name.upper() for token in (" RIVER ", " CREEK ", " FORK ", " AT ", " NR ")):
            demand_score += 4
        qualified.append(
            {
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
                "hard_gate": age_minutes <= 90,
                "data_quality_score": data_quality,
                "demand_score": demand_score,
                "history_score": history_score,
                "geographic_score": 10,
                "nearby_score": 3,
                "nwps_match": False,
            }
        )
    qualified.sort(
        key=lambda item: (
            -item["data_quality_score"],
            -item["demand_score"],
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
