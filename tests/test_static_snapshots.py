import json
from datetime import UTC, datetime, timedelta

from rivermetry.build.site import build_site
from rivermetry.models import (
    ForecastSnapshot,
    LocationSnapshot,
    Observation,
    ObservationSeriesPoint,
    TrendDirection,
)


def test_location_page_keeps_validated_static_snapshot_and_context(tmp_path, monkeypatch):
    registry = tmp_path / "locations.json"
    registry.write_text(
        json.dumps(
            [
                {
                    "location_id": "us-ca-test",
                    "status": "live",
                    "country_code": "us",
                    "region_code": "california",
                    "slug": "test-river-town",
                    "river_name": "Test River",
                    "station_name": "Test River at Town",
                    "observation_provider": "usgs",
                    "station_id": "12345678",
                    "latitude": 37.7,
                    "longitude": -119.5,
                    "timezone": "America/Los_Angeles",
                    "forecast_provider": "noaa_nwps",
                    "forecast_location_id": "TEST1",
                    "state_name": "California",
                    "launch_validated_at": "2026-09-06T00:00:00Z",
                }
            ]
        )
    )
    monkeypatch.setenv("BASE_URL", "https://rivermetry.example")
    monkeypatch.setenv("WORKER_BASE_URL", "https://current.rivermetry.example")

    now = datetime(2026, 9, 6, 4, 0, tzinfo=UTC)
    level_series = tuple(
        ObservationSeriesPoint(4.0 + index * 0.1, now - timedelta(hours=3 - index))
        for index in range(4)
    )
    flow_series = tuple(
        ObservationSeriesPoint(340 + index * 14, now - timedelta(hours=3 - index))
        for index in range(4)
    )
    forecast = ForecastSnapshot(
        provider="noaa_nwps",
        location_id="TEST1",
        updated_at=now,
        values=(
            {
                "valid_time": "2026-09-06T06:00:00Z",
                "primary": 8.2,
                "primary_unit": "ft",
                "secondary": 9.1,
                "secondary_unit": "kcfs",
            },
        ),
        official_categories=(
            {
                "stage_unit": "ft",
                "flow_unit": "cfs",
                "minor": {"stage": 10.0, "flow": 10000.0},
            },
        ),
    )

    snapshots = {
        "us-ca-test": LocationSnapshot(
            location=None,
            water_level=Observation(4.3, "ft", now, "Provisional"),
            streamflow=Observation(382, "ft3/s", now, "Provisional"),
            trend=TrendDirection.RISING,
            level_series=level_series,
            flow_series=flow_series,
            history_context={
                "changes": {"1h": 0.1, "6h": 0.3, "24h": -0.2},
                "seven_day_average": 350.0,
                "thirty_day_average": 330.0,
                "streamflow_unit": "ft3/s",
            },
            forecast=forecast,
            update_status="delayed",
        )
    }

    build_site(tmp_path / "dist", False, registry, snapshots=snapshots)
    page = (tmp_path / "dist/us/california/test-river-town/index.html").read_text()

    assert "4.3 ft" in page
    assert "382 ft³/s" in page
    assert "Data update delayed" in page
    assert "Rising" in page
    assert "24-hour river level" in page
    assert "<svg" in page
    assert "7-day average streamflow" in page
    assert "350" in page
    assert "Official NWS Forecast" in page
    assert "8.2 ft" in page
    assert "Minor flood stage" in page
    assert "10.0 ft" in page
    assert 'data-static-observed="2026-09-06T04:00:00+00:00"' in page
