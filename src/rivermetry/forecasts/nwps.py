from __future__ import annotations

from datetime import datetime, timezone

import httpx

from rivermetry.adapters.base import UpstreamDataError, UpstreamSchemaError
from rivermetry.models import ForecastSnapshot

BASE = "https://api.water.noaa.gov/nwps/v1"


class NWPSForecastAdapter:
    def __init__(self, client: httpx.Client):
        self.client = client

    def fetch(self, location_id: str) -> ForecastSnapshot:
        try:
            metadata = self.client.get(f"{BASE}/gauges/{location_id}", timeout=30)
            metadata.raise_for_status()
            stageflow = self.client.get(f"{BASE}/gauges/{location_id}/stageflow", timeout=30)
            stageflow.raise_for_status()
            meta_json = metadata.json()
            flow_json = stageflow.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamDataError("NWPS request failed") from exc
        if not isinstance(meta_json, dict) or not isinstance(flow_json, dict):
            raise UpstreamSchemaError("NWPS returned unexpected JSON")
        forecast = flow_json.get("forecast") or {}
        values = forecast.get("data") or forecast.get("values") or []
        flood = meta_json.get("flood") or meta_json.get("floodCategories") or {}
        return ForecastSnapshot(
            provider="noaa_nwps",
            location_id=location_id,
            updated_at=datetime.now(timezone.utc),
            values=tuple(values if isinstance(values, list) else ()),
            official_categories=(flood,) if isinstance(flood, dict) and flood else (),
        )
