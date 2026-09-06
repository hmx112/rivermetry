from rivermetry.adapters.usgs import (
    USGSAdapter,
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


def test_series_ignores_null_quality_gaps_instead_of_failing_station():
    payload = {
        "features": [
            {"properties": {"parameter_code": "00065", "value": None, "time": "2026-09-05T00:30:00Z"}},
            {"properties": {"parameter_code": "00065", "value": "4.2", "time": "2026-09-05T01:00:00Z"}},
        ]
    }

    result = normalize_series_records(payload)

    assert [point.value for point in result["water_level"]] == [4.2]


def test_daily_mean_accepts_date_only_time_and_returns_newest_first():
    payload = {
        "features": [
            {
                "properties": {
                    "parameter_code": "00060",
                    "statistic_id": "00003",
                    "value": "120",
                    "time": "2026-09-05",
                }
            },
            {
                "properties": {
                    "parameter_code": "00060",
                    "statistic_id": "00001",
                    "value": "999",
                    "time": "2026-09-05",
                }
            },
            {
                "properties": {
                    "parameter_code": "00060",
                    "statistic_id": "00003",
                    "value": "100",
                    "time": "2026-09-04",
                }
            },
        ]
    }

    assert normalize_daily_records(payload) == [120.0, 100.0]


class BulkResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200
        self.headers = {}

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class BulkClient:
    def __init__(self):
        self.calls = []

    def post(self, url, *, params, headers, json, timeout):
        self.calls.append((url, params.copy(), headers.copy(), json))
        station_ids = [value.removeprefix("USGS-") for value in json["args"][1]]
        features = []
        if "/continuous/" in url:
            parameter = params["parameter_code"]
            for station_id in station_ids:
                features.append(
                    {
                        "properties": {
                            "monitoring_location_id": f"USGS-{station_id}",
                            "parameter_code": parameter,
                            "value": "4.2" if parameter == "00065" else "300",
                            "time": "2026-09-05T01:00:00Z",
                        }
                    }
                )
        else:
            for station_id in station_ids:
                features.append(
                    {
                        "properties": {
                            "monitoring_location_id": f"USGS-{station_id}",
                            "parameter_code": "00060",
                            "statistic_id": "00003",
                            "value": "120",
                            "time": "2026-09-05",
                        }
                    }
                )
        return BulkResponse({"features": features})


def test_bulk_series_and_daily_use_bounded_cql_station_batches():
    client = BulkClient()
    adapter = USGSAdapter(client)

    series = adapter.fetch_series_bulk(["1", "2"], "2026-09-04T00:00:00Z", "2026-09-05T00:00:00Z")
    daily = adapter.fetch_daily_bulk(["1", "2"], "2026-08-01", "2026-09-05")

    assert series["1"]["water_level"][0].value == 4.2
    assert series["2"]["streamflow"][0].value == 300
    assert daily == {"1": [120.0], "2": [120.0]}
    assert len(client.calls) == 3
    for _, _, headers, body in client.calls:
        assert headers["Content-Type"] == "application/query-cql-json"
        assert body == {
            "op": "in",
            "args": [{"property": "monitoring_location_id"}, ["USGS-1", "USGS-2"]],
        }
