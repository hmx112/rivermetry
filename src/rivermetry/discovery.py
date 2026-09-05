from __future__ import annotations

import re
from collections import defaultdict, deque
from datetime import UTC, datetime

import httpx

from rivermetry.adapters.base import UpstreamDataError, UpstreamSchemaError

LATEST_URL = "https://api.waterdata.usgs.gov/ogcapi/v0/collections/latest-continuous/items"


def _slug(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:72] or "river-station"


def _timezone(abbr: str | None) -> str:
    return {
        "PST": "America/Los_Angeles", "PDT": "America/Los_Angeles",
        "MST": "America/Denver", "MDT": "America/Denver",
        "CST": "America/Chicago", "CDT": "America/Chicago",
        "EST": "America/New_York", "EDT": "America/New_York",
        "AKST": "America/Anchorage", "AKDT": "America/Anchorage",
        "HST": "Pacific/Honolulu",
    }.get((abbr or "").upper(), "UTC")


def _region_slug(name: str | None, code: str | None) -> str:
    return _slug(name or f"state-{code or 'unknown'}")


def discover_usgs_candidates(
    client: httpx.Client, limit: int = 450, api_key: str | None = None
) -> list[dict]:
    def fetch_parameter(parameter_code: str) -> list[dict]:
        params = {
            "f": "json",
            "limit": "50000",
            "parameter_code": parameter_code,
            "agency_code": "USGS",
        }
        if api_key:
            params["api_key"] = api_key
        try:
            response = client.get(
                LATEST_URL,
                params=params,
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

    features = fetch_parameter("00060") + fetch_parameter("00065")
    stations: dict[str, dict] = defaultdict(lambda: {"parameters": set()})
    now = datetime.now(UTC)
    for feature in features:
        p = feature.get("properties") or {}
        parameter = p.get("parameter_code")
        if parameter not in {"00060", "00065"}:
            continue
        if str(p.get("site_type_code") or "").upper() not in {"ST", "ST-CA", "ST-DCH"}:
            continue
        sid = str(p.get("monitoring_location_number") or "")
        if not sid:
            raw = str(p.get("monitoring_location_id") or "")
            sid = raw.removeprefix("USGS-")
        if not sid:
            continue
        try:
            observed = datetime.fromisoformat(str(p.get("time") or ""))
            age_minutes = max(0, (now - observed).total_seconds() / 60)
        except ValueError:
            continue
        item = stations[sid]
        item["parameters"].add(parameter)
        item.update(
            {
                "station_id": sid,
                "station_name": str(p.get("monitoring_location_name") or sid),
                "state_name": str(p.get("state_name") or "Unknown"),
                "state_code": str(p.get("state_code") or ""),
                "latitude": (feature.get("geometry") or {}).get("coordinates", [None, None])[1],
                "longitude": (feature.get("geometry") or {}).get("coordinates", [None, None])[0],
                "timezone": _timezone(p.get("time_zone_abbreviation")),
                "drainage_area": p.get("drainage_area"),
                "age_minutes": min(item.get("age_minutes", age_minutes), age_minutes),
            }
        )

    qualified = []
    for station in stations.values():
        if station["parameters"] != {"00060", "00065"}:
            continue
        if station.get("latitude") is None or station.get("longitude") is None:
            continue
        name = station["station_name"]
        region = _region_slug(station.get("state_name"), station.get("state_code"))
        data_quality = (
            35 if station["age_minutes"] <= 30 else 25 if station["age_minutes"] <= 90 else 10
        )
        history_score = 8 if station.get("drainage_area") else 5
        demand_score = 8
        if any(token in name.upper() for token in (" RIVER ", " CREEK ", " FORK ", " AT ", " NR ")):
            demand_score += 4
        qualified.append(
            {
                "location_id": f"us-{region}-{station['station_id']}",
                "status": "candidate",
                "country_code": "us",
                "region_code": region,
                "slug": _slug(name),
                "river_name": name.split(" AT ")[0].split(" NR ")[0].title(),
                "station_name": name.title(),
                "observation_provider": "usgs",
                "station_id": station["station_id"],
                "latitude": station["latitude"],
                "longitude": station["longitude"],
                "timezone": station["timezone"],
                "state_name": station["state_name"],
                "drainage_area": station.get("drainage_area"),
                "hard_gate": station["age_minutes"] <= 90,
                "data_quality_score": data_quality,
                "demand_score": demand_score,
                "history_score": history_score,
                "geographic_score": 10,
                "nearby_score": 3,
                "nwps_match": False,
            }
        )
    qualified.sort(
        key=lambda x: (-x["data_quality_score"], -x["demand_score"], x["station_id"])
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
