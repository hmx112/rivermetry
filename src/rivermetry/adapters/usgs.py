from __future__ import annotations

from datetime import datetime
import math
import time
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


def _station_id(properties: dict[str, Any]) -> str:
    return str(properties.get("monitoring_location_id") or "").removeprefix("USGS-")


def normalize_latest_records(payload: dict[str, Any]) -> dict[str, dict[str, Observation | None]]:
    result: dict[str, dict[str, Observation | None]] = {}
    for feature in _features(payload):
        props = feature.get("properties") or {}
        parameter = props.get("parameter_code")
        if parameter not in PARAMETERS:
            continue
        station = _station_id(props)
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
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        buckets[PARAMETERS[parameter]][observed_at] = ObservationSeriesPoint(value, observed_at)
    return {
        key: tuple(sorted(points.values(), key=lambda point: point.observed_at))
        for key, points in buckets.items()
    }


def normalize_series_records_by_station(
    payload: dict[str, Any],
) -> dict[str, dict[str, tuple[ObservationSeriesPoint, ...]]]:
    buckets: dict[str, dict[str, dict[datetime, ObservationSeriesPoint]]] = {}
    for feature in _features(payload):
        props = feature.get("properties") or {}
        parameter = props.get("parameter_code")
        station = _station_id(props)
        if parameter not in PARAMETERS or not station:
            continue
        try:
            value = float(props["value"])
            observed_at = _dt(props["time"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        station_bucket = buckets.setdefault(
            station,
            {"water_level": {}, "streamflow": {}},
        )
        station_bucket[PARAMETERS[parameter]][observed_at] = ObservationSeriesPoint(
            value,
            observed_at,
        )
    return {
        station: {
            key: tuple(sorted(points.values(), key=lambda point: point.observed_at))
            for key, points in station_bucket.items()
        }
        for station, station_bucket in buckets.items()
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


def normalize_daily_records_by_station(payload: dict[str, Any]) -> dict[str, list[float]]:
    values: dict[str, dict[str, float]] = {}
    for feature in _features(payload):
        props = feature.get("properties") or {}
        station = _station_id(props)
        if (
            not station
            or props.get("parameter_code") != "00060"
            or props.get("statistic_id") != "00003"
        ):
            continue
        try:
            value = float(props["value"])
            observed_day = str(props["time"])
        except (KeyError, TypeError, ValueError):
            continue
        if observed_day and math.isfinite(value):
            values.setdefault(station, {})[observed_day] = value
    return {
        station: [by_day[key] for key in sorted(by_day, reverse=True)]
        for station, by_day in values.items()
    }


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

    def _post_station_batch(
        self,
        collection: str,
        station_ids: list[str],
        params: dict[str, str],
    ) -> dict:
        body = {
            "op": "in",
            "args": [
                {"property": "monitoring_location_id"},
                [f"USGS-{station_id}" for station_id in station_ids],
            ],
        }
        headers = {
            "User-Agent": "Rivermetry/0.1 (+https://rivermetry.example)",
            "Content-Type": "application/query-cql-json",
        }
        request_params = self._params({"limit": "50000", **params})
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = self.client.post(
                    f"{BASE}/{collection}/items",
                    params=request_params,
                    headers=headers,
                    json=body,
                    timeout=60,
                )
                if getattr(response, "status_code", 200) == 429 and attempt < 3:
                    retry_after = getattr(response, "headers", {}).get("Retry-After", "1")
                    try:
                        delay = float(retry_after)
                    except (TypeError, ValueError):
                        delay = 1.0
                    time.sleep(min(max(delay, 1.0) * (attempt + 1), 8.0))
                    continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise UpstreamSchemaError("USGS returned non-object JSON")
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                break
        raise UpstreamDataError(f"USGS {collection} batch request failed") from last_error

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

    def fetch_series_bulk(
        self,
        station_ids: list[str],
        start_iso: str,
        end_iso: str,
        batch_size: int = 50,
    ) -> dict[str, dict[str, tuple[ObservationSeriesPoint, ...]]]:
        result = {
            station_id: {"water_level": (), "streamflow": ()}
            for station_id in station_ids
        }
        for offset in range(0, len(station_ids), batch_size):
            batch = station_ids[offset : offset + batch_size]
            for parameter_code in ("00065", "00060"):
                payload = self._post_station_batch(
                    "continuous",
                    batch,
                    {
                        "parameter_code": parameter_code,
                        "datetime": f"{start_iso}/{end_iso}",
                    },
                )
                parsed = normalize_series_records_by_station(payload)
                for station_id, series in parsed.items():
                    if station_id not in result:
                        continue
                    for key in ("water_level", "streamflow"):
                        existing = result[station_id][key]
                        incoming = series.get(key, ())
                        merged = {
                            point.observed_at: point
                            for point in (*existing, *incoming)
                        }
                        result[station_id][key] = tuple(
                            sorted(merged.values(), key=lambda point: point.observed_at)
                        )
        return result

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

    def fetch_daily_bulk(
        self,
        station_ids: list[str],
        start_iso: str,
        end_iso: str,
        batch_size: int = 50,
    ) -> dict[str, list[float]]:
        result = {station_id: [] for station_id in station_ids}
        for offset in range(0, len(station_ids), batch_size):
            batch = station_ids[offset : offset + batch_size]
            payload = self._post_station_batch(
                "daily",
                batch,
                {
                    "parameter_code": "00060",
                    "statistic_id": "00003",
                    "datetime": f"{start_iso}/{end_iso}",
                },
            )
            parsed = normalize_daily_records_by_station(payload)
            for station_id, values in parsed.items():
                if station_id in result:
                    result[station_id] = values
        return result
