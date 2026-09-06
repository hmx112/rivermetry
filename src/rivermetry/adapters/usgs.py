from __future__ import annotations

from datetime import datetime
import math
from typing import Any

import httpx

from rivermetry.adapters.base import UpstreamDataError, UpstreamSchemaError
from rivermetry.models import Observation, ObservationSeriesPoint

BASE = "https://api.waterdata.usgs.gov/ogcapi/v1/collections"
PARAMETERS = {"00065": "water_level", "00060": "streamflow"}


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise UpstreamSchemaError("USGS timestamp is not timezone-aware")
    return parsed


def _features(payload: dict[str, Any]) -> list[dict[str, Any]]:
    features = payload.get("features")
    if not isinstance(features, list):
        raise UpstreamSchemaError("USGS response has no feature list")
    return features


def normalize_latest_records(payload: dict[str, Any]) -> dict[str, dict[str, Observation | None]]:
    result: dict[str, dict[str, Observation | None]] = {}
    for feature in _features(payload):
        props = feature.get("properties") or {}
        parameter = props.get("parameter_code")
        if parameter not in PARAMETERS:
            continue
        station = str(props.get("monitoring_location_id") or "").removeprefix("USGS-")
        if not station:
            raise UpstreamSchemaError("USGS record missing monitoring_location_id")
        try:
            value = float(props["value"])
            observed_at = _dt(props["time"])
        except (KeyError, TypeError, ValueError) as exc:
            raise UpstreamSchemaError("USGS latest record is malformed") from exc
        if not math.isfinite(value):
            raise UpstreamSchemaError("USGS latest value is non-finite")
        item = result.setdefault(station, {"water_level": None, "streamflow": None})
        item[PARAMETERS[parameter]] = Observation(
            value=value,
            unit=str(props.get("unit_of_measure") or ""),
            observed_at=observed_at,
            quality_status=str(props.get("approval_status") or "") or None,
        )
    return result


def normalize_series_records(payload: dict[str, Any]) -> dict[str, tuple[ObservationSeriesPoint, ...]]:
    buckets: dict[str, dict[datetime, ObservationSeriesPoint]] = {
        "water_level": {},
        "streamflow": {},
    }
    for feature in _features(payload):
        props = feature.get("properties") or {}
        parameter = props.get("parameter_code")
        if parameter not in PARAMETERS:
            continue
        try:
            value = float(props["value"])
            observed_at = _dt(props["time"])
        except (KeyError, TypeError, ValueError) as exc:
            raise UpstreamSchemaError("USGS series record is malformed") from exc
        if not math.isfinite(value):
            continue
        buckets[PARAMETERS[parameter]][observed_at] = ObservationSeriesPoint(value, observed_at)
    return {
        key: tuple(sorted(points.values(), key=lambda point: point.observed_at))
        for key, points in buckets.items()
    }


def normalize_daily_records(payload: dict[str, Any]) -> list[float]:
    values: dict[str, float] = {}
    for feature in _features(payload):
        props = feature.get("properties") or {}
        if props.get("parameter_code") != "00060" or props.get("statistic_id") != "00003":
            continue
        try:
            value = float(props["value"])
            observed_day = str(props["time"])
        except (KeyError, TypeError, ValueError):
            continue
        if observed_day and math.isfinite(value):
            values[observed_day] = value
    return [values[key] for key in sorted(values, reverse=True)]


class USGSAdapter:
    def __init__(self, client: httpx.Client, api_key: str | None = None):
        self.client = client
        self.api_key = api_key

    def _params(self, extra: dict[str, str]) -> dict[str, str]:
        params = {"f": "json", **extra}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _get(self, collection: str, params: dict[str, str]) -> dict:
        try:
            response = self.client.get(
                f"{BASE}/{collection}/items",
                params=self._params(params),
                headers={"User-Agent": "Rivermetry/0.1 (+https://rivermetry.example)"},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamDataError(f"USGS {collection} request failed") from exc
        if not isinstance(payload, dict):
            raise UpstreamSchemaError("USGS returned non-object JSON")
        return payload

    def fetch_latest(self, station_ids: list[str]):
        result: dict[str, dict[str, Observation | None]] = {}
        for station in station_ids:
            payload = self._get(
                "latest-continuous",
                {"monitoring_location_id": f"USGS-{station}", "limit": "20"},
            )
            result.update(normalize_latest_records(payload))
        return result

    def fetch_series(self, station_id: str, start_iso: str, end_iso: str):
        payload = self._get(
            "continuous",
            {
                "monitoring_location_id": f"USGS-{station_id}",
                "datetime": f"{start_iso}/{end_iso}",
                "limit": "10000",
            },
        )
        return normalize_series_records(payload)

    def fetch_daily(self, station_id: str, start_iso: str, end_iso: str) -> list[float]:
        payload = self._get(
            "daily",
            {
                "monitoring_location_id": f"USGS-{station_id}",
                "parameter_code": "00060",
                "statistic_id": "00003",
                "datetime": f"{start_iso}/{end_iso}",
                "limit": "1000",
            },
        )
        return normalize_daily_records(payload)
