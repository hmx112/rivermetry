from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

import httpx

from rivermetry.selection import US_LAUNCH_REGIONS

USGS_HISTORY_URL = "https://api.waterdata.usgs.gov/ogcapi/v1/collections/time-series-metadata/items"
NWPS_GAUGES_REPORT_URL = (
    "https://water.noaa.gov/resources/downloads/reports/nwps_all_gauges_report.csv"
)


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


def _float_or_none(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def fetch_nwps_gauges(client: httpx.Client) -> list[dict]:
    response = client.get(
        NWPS_GAUGES_REPORT_URL,
        headers={"User-Agent": "Rivermetry/0.1 (+https://rivermetry.example)"},
        timeout=60,
    )
    response.raise_for_status()
    reader = csv.DictReader(io.StringIO(response.text.lstrip("\ufeff")))
    gauges = []
    for row in reader:
        lid = str(row.get("nws shef id") or "").strip()
        if not lid:
            continue
        in_service = str(row.get("in service") or "").strip().lower()
        if in_service not in {"true", "1", "yes"}:
            continue
        forecast_status = str(row.get("forecast status") or "").strip()
        gauges.append(
            {
                "lid": lid,
                "name": str(row.get("location name") or "").strip(),
                "usgs_id": str(row.get("usgs id") or "").strip(),
                "state": {"abbreviation": str(row.get("state") or "").strip()},
                "latitude": _float_or_none(row.get("latitude")),
                "longitude": _float_or_none(row.get("longitude")),
                "nwps_forecast": forecast_status.lower().startswith("forecasts are issued"),
                "forecast_status": forecast_status,
            }
        )
    return gauges


def _distance_sq(candidate: dict, gauge: dict) -> float:
    return (float(candidate["latitude"]) - float(gauge["latitude"])) ** 2 + (
        float(candidate["longitude"]) - float(gauge["longitude"])
    ) ** 2


def match_nwps(candidate: dict, gauges: list[dict], max_degrees: float = 0.03) -> dict | None:
    station_id = str(candidate.get("station_id") or "")
    exact = [gauge for gauge in gauges if station_id and str(gauge.get("usgs_id") or "") == station_id]
    if exact:
        exact.sort(
            key=lambda gauge: (
                not bool(gauge.get("nwps_forecast")),
                _distance_sq(candidate, gauge)
                if gauge.get("latitude") is not None and gauge.get("longitude") is not None
                else float("inf"),
                str(gauge.get("lid") or ""),
            )
        )
        return exact[0]

    state = candidate.get("state_name")
    matches = []
    for gauge in gauges:
        if gauge.get("usgs_id"):
            continue
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
            row["nwps_forecast"] = bool(gauge.get("nwps_forecast"))
            row["nwps_forecast_status"] = gauge.get("forecast_status")
        else:
            row["nwps_lid"] = None
            row["nwps_match"] = False
            row["nwps_forecast"] = False
            row["nwps_forecast_status"] = None
        enriched.append(row)
    return enriched
