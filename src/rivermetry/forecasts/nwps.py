from __future__ import annotations

from datetime import UTC, datetime
import math

import httpx

from rivermetry.adapters.base import UpstreamDataError, UpstreamSchemaError
from rivermetry.models import ForecastSnapshot

BASE = "https://api.water.noaa.gov/nwps/v1"


def _timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UpstreamSchemaError("NWPS forecast timestamp is malformed") from exc
    if parsed.tzinfo is None:
        raise UpstreamSchemaError("NWPS forecast timestamp is not timezone-aware")
    return parsed


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _threshold(value) -> float | None:
    number = _number(value)
    if number is None or number <= -9000:
        return None
    return number


def normalize_forecast(
    metadata: dict, stageflow: dict, location_id: str
) -> ForecastSnapshot | None:
    forecast = stageflow.get("forecast") if isinstance(stageflow, dict) else None
    if not isinstance(forecast, dict):
        return None
    data = forecast.get("data")
    if not isinstance(data, list) or not data:
        return None

    primary_unit = str(forecast.get("primaryUnits") or "")
    secondary_unit = str(forecast.get("secondaryUnits") or "")
    values = []
    for item in data:
        if not isinstance(item, dict) or not item.get("validTime"):
            continue
        primary = _number(item.get("primary"))
        secondary = _number(item.get("secondary"))
        if primary is None and secondary is None:
            continue
        values.append(
            {
                "valid_time": str(item["validTime"]),
                "primary": primary,
                "primary_unit": primary_unit,
                "secondary": secondary,
                "secondary_unit": secondary_unit,
            }
        )
    if not values:
        return None

    flood = metadata.get("flood") if isinstance(metadata, dict) else None
    categories_payload = flood.get("categories") if isinstance(flood, dict) else None
    categories = {
        "stage_unit": str(flood.get("stageUnits") or "") if isinstance(flood, dict) else "",
        "flow_unit": str(flood.get("flowUnits") or "") if isinstance(flood, dict) else "",
    }
    for name in ("action", "minor", "moderate", "major"):
        raw = categories_payload.get(name) if isinstance(categories_payload, dict) else None
        categories[name] = {
            "stage": _threshold(raw.get("stage")) if isinstance(raw, dict) else None,
            "flow": _threshold(raw.get("flow")) if isinstance(raw, dict) else None,
        }

    return ForecastSnapshot(
        provider="noaa_nwps",
        location_id=location_id,
        updated_at=_timestamp(forecast.get("issuedTime")),
        values=tuple(values),
        official_categories=(categories,),
    )


class NWPSForecastAdapter:
    def __init__(self, client: httpx.Client):
        self.client = client

    def fetch(self, location_id: str) -> ForecastSnapshot | None:
        try:
            metadata = self.client.get(
                f"{BASE}/gauges/{location_id}",
                headers={"User-Agent": "Rivermetry/0.1 (+https://rivermetry.example)"},
                timeout=30,
            )
            metadata.raise_for_status()
            stageflow = self.client.get(
                f"{BASE}/gauges/{location_id}/stageflow",
                headers={"User-Agent": "Rivermetry/0.1 (+https://rivermetry.example)"},
                timeout=30,
            )
            stageflow.raise_for_status()
            meta_json = metadata.json()
            flow_json = stageflow.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamDataError("NWPS request failed") from exc
        if not isinstance(meta_json, dict) or not isinstance(flow_json, dict):
            raise UpstreamSchemaError("NWPS returned unexpected JSON")
        return normalize_forecast(meta_json, flow_json, location_id)
