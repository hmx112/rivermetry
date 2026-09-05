from __future__ import annotations

from datetime import UTC, datetime

import httpx

from rivermetry.selection import US_LAUNCH_REGIONS

USGS_HISTORY_URL = "https://api.waterdata.usgs.gov/ogcapi/v1/collections/time-series-metadata/items"
NWPS_GAUGES_URL = "https://api.water.noaa.gov/nwps/v1/gauges"


def _years_since(value: str | None, now: datetime) -> float:
    if not value:
        return 0.0
    try:
        start = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    return max(0.0, (now - start).total_seconds() / (365.2425 * 86400))


def fetch_history_years(
    client: httpx.Client, station_ids: list[str], api_key: str | None = None
) -> dict[str, float]:
    now = datetime.now(UTC)
    begins: dict[str, dict[str, list[str]]] = {}
    for offset in range(0, len(station_ids), 100):
        batch = [f"USGS-{station_id}" for station_id in station_ids[offset : offset + 100]]
        body = {
            "op": "and",
            "args": [
                {"op": "in", "args": [{"property": "monitoring_location_id"}, batch]},
                {"op": "in", "args": [{"property": "parameter_code"}, ["00060", "00065"]]},
            ],
        }
        params = {"f": "json", "limit": "5000"}
        if api_key:
            params["api_key"] = api_key
        response = client.post(
            USGS_HISTORY_URL,
            params=params,
            headers={
                "User-Agent": "Rivermetry/0.1 (+https://rivermetry.example)",
                "Content-Type": "application/query-cql-json",
            },
            json=body,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise ValueError("USGS history metadata returned no features")
        for feature in features:
            props = feature.get("properties") or {}
            monitoring_id = str(props.get("monitoring_location_id") or "")
            parameter = str(props.get("parameter_code") or "")
            begin = props.get("begin")
            if monitoring_id and parameter in {"00060", "00065"} and begin:
                begins.setdefault(monitoring_id, {}).setdefault(parameter, []).append(str(begin))

    output = {}
    for station_id in station_ids:
        monitoring_id = f"USGS-{station_id}"
        by_parameter = begins.get(monitoring_id, {})
        years = []
        for parameter in ("00060", "00065"):
            values = by_parameter.get(parameter) or []
            if values:
                years.append(_years_since(min(values), now))
        output[station_id] = min(years) if len(years) == 2 else 0.0
    return output


def fetch_nwps_gauges(client: httpx.Client) -> list[dict]:
    response = client.get(
        NWPS_GAUGES_URL,
        headers={"User-Agent": "Rivermetry/0.1 (+https://rivermetry.example)"},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    gauges = payload.get("gauges") if isinstance(payload, dict) else None
    if not isinstance(gauges, list):
        raise ValueError("NWPS gauge list returned unexpected JSON")
    return gauges


def _distance_sq(candidate: dict, gauge: dict) -> float:
    return (float(candidate["latitude"]) - float(gauge["latitude"])) ** 2 + (
        float(candidate["longitude"]) - float(gauge["longitude"])
    ) ** 2


def match_nwps(candidate: dict, gauges: list[dict], max_degrees: float = 0.03) -> dict | None:
    state = candidate.get("state_name")
    matches = []
    for gauge in gauges:
        gauge_state = (gauge.get("state") or {}).get("name")
        if state and gauge_state and state != gauge_state:
            continue
        if gauge.get("latitude") is None or gauge.get("longitude") is None:
            continue
        distance = _distance_sq(candidate, gauge)
        if distance <= max_degrees**2:
            matches.append((distance, gauge))
    if not matches:
        return None
    matches.sort(key=lambda pair: pair[0])
    return matches[0][1]


def enrich_candidates(
    client: httpx.Client, candidates: list[dict], api_key: str | None = None
) -> list[dict]:
    launch_candidates = [
        item for item in candidates if item.get("state_name") in US_LAUNCH_REGIONS
    ]
    history = fetch_history_years(
        client, [str(item["station_id"]) for item in launch_candidates], api_key
    )
    gauges = fetch_nwps_gauges(client)
    enriched = []
    for item in launch_candidates:
        row = dict(item)
        row["history_years"] = round(history.get(str(item["station_id"]), 0.0), 2)
        gauge = match_nwps(row, gauges)
        if gauge:
            row["nwps_lid"] = gauge.get("lid")
            row["nwps_match"] = True
            row["nwps_forecast"] = bool((gauge.get("pedts") or {}).get("forecast"))
        else:
            row["nwps_lid"] = None
            row["nwps_match"] = False
            row["nwps_forecast"] = False
        enriched.append(row)
    return enriched
