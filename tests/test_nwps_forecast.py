from rivermetry.forecasts.nwps import normalize_forecast


def test_nwps_forecast_normalizes_rows_and_official_categories():
    metadata = {
        "lid": "TEST1",
        "flood": {
            "stageUnits": "ft",
            "flowUnits": "cfs",
            "categories": {
                "major": {"stage": 14.0, "flow": 30000},
                "moderate": {"stage": 12.0, "flow": 20000},
                "minor": {"stage": 10.0, "flow": 10000},
                "action": {"stage": 9.0, "flow": 8000},
            },
        },
    }
    stageflow = {
        "forecast": {
            "issuedTime": "2026-09-06T01:00:00Z",
            "primaryName": "Stage",
            "primaryUnits": "ft",
            "secondaryName": "Flow",
            "secondaryUnits": "kcfs",
            "data": [
                {
                    "validTime": "2026-09-06T03:00:00Z",
                    "generatedTime": "2026-09-06T01:05:00Z",
                    "primary": 8.2,
                    "secondary": 9.1,
                }
            ],
        }
    }

    result = normalize_forecast(metadata, stageflow, "TEST1")

    assert result is not None
    assert result.updated_at.isoformat() == "2026-09-06T01:00:00+00:00"
    assert result.values[0] == {
        "valid_time": "2026-09-06T03:00:00Z",
        "primary": 8.2,
        "primary_unit": "ft",
        "secondary": 9.1,
        "secondary_unit": "kcfs",
    }
    assert result.official_categories[0]["minor"]["stage"] == 10.0
    assert result.official_categories[0]["stage_unit"] == "ft"


def test_nwps_missing_forecast_returns_none():
    assert normalize_forecast({"lid": "NONE1"}, {"forecast": None}, "NONE1") is None


def test_nwps_sentinel_flood_thresholds_are_removed():
    result = normalize_forecast(
        {
            "flood": {
                "stageUnits": "ft",
                "flowUnits": "cfs",
                "categories": {"minor": {"stage": -9999, "flow": -9999}},
            }
        },
        {
            "forecast": {
                "issuedTime": "2026-09-06T01:00:00Z",
                "primaryUnits": "ft",
                "secondaryUnits": "kcfs",
                "data": [{"validTime": "2026-09-06T03:00:00Z", "primary": 8.2, "secondary": 9.1}],
            }
        },
        "TEST1",
    )

    assert result is not None
    assert result.official_categories[0]["minor"] == {"stage": None, "flow": None}
