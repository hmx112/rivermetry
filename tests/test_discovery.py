from rivermetry.discovery import discover_usgs_candidates


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self):
        self.get_calls = []
        self.post_calls = []

    def get(self, url, *, params, headers, timeout):
        self.get_calls.append((url, params.copy()))
        code = params.get("parameter_code")
        if code not in {"00060", "00065"}:
            return FakeResponse({"features": [], "links": []})
        return FakeResponse(
            {
                "features": [
                    {
                        "geometry": {"type": "Point", "coordinates": [-119.5, 37.7]},
                        "properties": {
                            "monitoring_location_id": "USGS-11264500",
                            "parameter_code": code,
                            "time": "2099-09-05T10:30:00+00:00",
                        },
                    }
                ],
                "links": [],
            }
        )

    def post(self, url, *, params, headers, json, timeout):
        self.post_calls.append((url, params.copy(), headers.copy(), json))
        return FakeResponse(
            {
                "features": [
                    {
                        "id": "USGS-11264500",
                        "geometry": {"type": "Point", "coordinates": [-119.5, 37.7]},
                        "properties": {
                            "monitoring_location_number": "11264500",
                            "monitoring_location_name": "MERCED RIVER AT HAPPY ISLES BRIDGE NR YOSEMITE",
                            "state_name": "California",
                            "state_code": "06",
                            "time_zone_abbreviation": "PDT",
                            "drainage_area": 181.0,
                        },
                    }
                ]
            }
        )


def test_discovery_joins_latest_values_to_targeted_monitoring_metadata():
    client = FakeClient()

    candidates = discover_usgs_candidates(client, limit=10)

    latest_calls = [params for url, params in client.get_calls if "latest-continuous" in url]
    assert {call.get("parameter_code") for call in latest_calls} == {"00060", "00065"}
    assert len(client.post_calls) == 1
    _, params, headers, body = client.post_calls[0]
    assert params == {"f": "json", "limit": "100"}
    assert headers["Content-Type"] == "application/query-cql-json"
    assert body == {"op": "in", "args": [{"property": "id"}, ["USGS-11264500"]]}
    assert [item["station_id"] for item in candidates] == ["11264500"]
    assert candidates[0]["state_name"] == "California"


class TwoStationClient(FakeClient):
    def get(self, url, *, params, headers, timeout):
        self.get_calls.append((url, params.copy()))
        code = params.get("parameter_code")
        return FakeResponse(
            {
                "features": [
                    {
                        "geometry": {"type": "Point", "coordinates": [-119.5, 37.7]},
                        "properties": {
                            "monitoring_location_id": "USGS-11264500",
                            "parameter_code": code,
                            "time": "2099-09-05T10:30:00+00:00",
                        },
                    },
                    {
                        "geometry": {"type": "Point", "coordinates": [-80.0, 35.0]},
                        "properties": {
                            "monitoring_location_id": "USGS-99999999",
                            "parameter_code": code,
                            "time": "2099-09-05T10:30:00+00:00",
                        },
                    },
                ],
                "links": [],
            }
        )

    def post(self, url, *, params, headers, json, timeout):
        self.post_calls.append((url, params.copy(), headers.copy(), json))
        ids = set(json["args"][1])
        assert ids == {"USGS-11264500", "USGS-99999999"}
        return FakeResponse(
            {
                "features": [
                    {
                        "id": "USGS-11264500",
                        "geometry": {"type": "Point", "coordinates": [-119.5, 37.7]},
                        "properties": {
                            "monitoring_location_number": "11264500",
                            "monitoring_location_name": "MERCED RIVER AT HAPPY ISLES BRIDGE NR YOSEMITE",
                            "state_name": "California",
                            "state_code": "06",
                            "time_zone_abbreviation": "PDT",
                            "drainage_area": 181.0,
                        },
                    },
                    {
                        "id": "USGS-99999999",
                        "geometry": {"type": "Point", "coordinates": [-80.0, 35.0]},
                        "properties": {
                            "monitoring_location_number": "99999999",
                            "monitoring_location_name": "TEST RIVER AT SAMPLE",
                            "state_name": "North Carolina",
                            "state_code": "37",
                            "time_zone_abbreviation": "EDT",
                            "drainage_area": 50.0,
                        },
                    },
                ]
            }
        )


def test_discovery_uses_cql_in_instead_of_unbounded_metadata_scan():
    client = TwoStationClient()

    candidates = discover_usgs_candidates(client, limit=10)

    assert {item["station_id"] for item in candidates} == {"11264500", "99999999"}
    assert len(client.post_calls) == 1
    _, _, _, body = client.post_calls[0]
    assert body["op"] == "in"
    assert body["args"][0] == {"property": "id"}
