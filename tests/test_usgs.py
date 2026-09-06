from rivermetry.adapters.usgs import (
    normalize_daily_records,
    normalize_latest_records,
    normalize_series_records,
)


def test_latest_and_missing_are_normalized():
    payload = {
        "features": [
            {
                "properties": {
                    "monitoring_location_id": "USGS-1",
                    "parameter_code": "00065",
                    "value": "4.2",
                    "unit_of_measure": "ft",
                    "time": "2026-09-05T00:00:00Z",
                    "approval_status": "Provisional",
                }
            }
        ]
    }
    result = normalize_latest_records(payload)
    assert result["1"]["water_level"].value == 4.2
    assert result["1"]["streamflow"] is None


def test_series_sorting():
    payload = {
        "features": [
            {"properties": {"parameter_code": "00065", "value": "4.2", "time": "2026-09-05T01:00:00Z"}},
            {"properties": {"parameter_code": "00065", "value": "4.1", "time": "2026-09-05T00:00:00Z"}},
        ]
    }
    result = normalize_series_records(payload)
    assert result["water_level"][0].value == 4.1


def test_daily_mean_streamflow_is_chronological_and_ignores_other_statistics():
    payload = {
        "features": [
            {
                "properties": {
                    "parameter_code": "00060",
                    "statistic_id": "00003",
                    "value": "120",
                    "time": "2026-09-05T00:00:00Z",
                }
            },
            {
                "properties": {
                    "parameter_code": "00060",
                    "statistic_id": "00001",
                    "value": "999",
                    "time": "2026-09-05T00:00:00Z",
                }
            },
            {
                "properties": {
                    "parameter_code": "00060",
                    "statistic_id": "00003",
                    "value": "100",
                    "time": "2026-09-04T00:00:00Z",
                }
            },
        ]
    }

    assert normalize_daily_records(payload) == [100.0, 120.0]
