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
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append(params.copy())
        code = params.get("parameter_code")
        if code not in {"00060", "00065"}:
            return FakeResponse({"features": []})
        return FakeResponse(
            {
                "features": [
                    {
                        "geometry": {"type": "Point", "coordinates": [-119.5, 37.7]},
                        "properties": {
                            "monitoring_location_id": "USGS-11264500",
                            "monitoring_location_number": "11264500",
                            "monitoring_location_name": "MERCED RIVER AT HAPPY ISLES BRIDGE NR YOSEMITE",
                            "parameter_code": code,
                            "site_type_code": "ST",
                            "state_name": "California",
                            "state_code": "06",
                            "time_zone_abbreviation": "PDT",
                            "time": "2026-09-05T10:30:00Z",
                            "drainage_area": 181.0,
                        },
                    }
                ]
            }
        )


def test_discovery_queries_flow_and_gage_height_separately():
    client = FakeClient()

    candidates = discover_usgs_candidates(client, limit=10)

    assert {call.get("parameter_code") for call in client.calls} == {"00060", "00065"}
    assert [item["station_id"] for item in candidates] == ["11264500"]
