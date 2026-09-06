import pytest

from rivermetry.promotion import promote_launch_preview


def preview_item(index: int, forecast: bool = True) -> dict:
    return {
        "location_id": f"us-california-{index:08d}",
        "status": "preview",
        "country_code": "us",
        "region_code": "california",
        "slug": f"river-at-sample-{index}",
        "river_name": "Sample River",
        "station_name": f"Sample River At Gauge {index}",
        "observation_provider": "usgs",
        "station_id": f"{index:08d}",
        "latitude": 37.0 + index / 10000,
        "longitude": -120.0,
        "timezone": "America/Los_Angeles",
        "state_name": "California",
        "drainage_area": 1000.0,
        "nwps_lid": f"L{index:04d}" if forecast else None,
        "nwps_forecast": forecast,
        "score": 99,
        "history_years": 40,
        "demand_score": 25,
    }


def test_promotion_creates_exact_live_registry_and_strips_selection_fields():
    preview = [preview_item(index) for index in range(150)]

    registry = promote_launch_preview(preview, "2026-09-06T01:55:45Z")

    assert len(registry) == 150
    assert {item["status"] for item in registry} == {"live"}
    assert {item["launch_validated_at"] for item in registry} == {"2026-09-06T01:55:45Z"}
    assert registry[0]["forecast_provider"] == "noaa_nwps"
    assert registry[0]["forecast_location_id"] == "L0000"
    assert "score" not in registry[0]
    assert "history_years" not in registry[0]
    assert "nwps_lid" not in registry[0]


def test_promotion_omits_forecast_binding_when_official_forecast_is_not_configured():
    preview = [preview_item(index) for index in range(150)]
    preview[0] = preview_item(0, forecast=False)

    registry = promote_launch_preview(preview, "2026-09-06T01:55:45Z")

    assert registry[0]["forecast_provider"] is None
    assert registry[0]["forecast_location_id"] is None


def test_promotion_rejects_wrong_count_and_duplicate_station_or_path():
    with pytest.raises(ValueError, match="exactly 150"):
        promote_launch_preview([preview_item(1)], "2026-09-06T01:55:45Z")

    duplicate_station = [preview_item(index) for index in range(150)]
    duplicate_station[1]["station_id"] = duplicate_station[0]["station_id"]
    with pytest.raises(ValueError, match="duplicate"):
        promote_launch_preview(duplicate_station, "2026-09-06T01:55:45Z")

    duplicate_path = [preview_item(index) for index in range(150)]
    duplicate_path[1]["slug"] = duplicate_path[0]["slug"]
    with pytest.raises(ValueError, match="duplicate"):
        promote_launch_preview(duplicate_path, "2026-09-06T01:55:45Z")
