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
        self.calls.append((url, params.copy()))
        if "monitoring-locations" in url:
            return FakeResponse(
                {
                    "features": [
                        {
                            "id": "USGS-11264500",
                            "geometry": {"type": "Point", "coordinates": [-119.5, 37.7]},
                            "properties": {
                                "agency_code": "USGS",
                                "monitoring_location_number": "11264500",
                                "monitoring_location_name": "MERCED RIVER AT HAPPY ISLES BRIDGE NR YOSEMITE",
                                "site_type_code": "ST",
                                "state_name": "California",
                                "state_code": "06",
                                "time_zone_abbreviation": "PDT",
                                "drainage_area": 181.0,
                            },
                        }
                    ]
                }
            )
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
                            "parameter_code": code,
                            "time": "2026-09-05T10:30:00Z",
                        },
                    }
                ]
            }
        )


def test_discovery_joins_latest_values_to_monitoring_location_metadata():
    client = FakeClient()

    candidates = discover_usgs_candidates(client, limit=10)

    latest_calls = [params for url, params in client.calls if "latest-continuous" in url]
    assert {call.get("parameter_code") for call in latest_calls} == {"00060", "00065"}
    assert any("monitoring-locations" in url for url, _ in client.calls)
    assert [item["station_id"] for item in candidates] == ["11264500"]
    assert candidates[0]["state_name"] == "California"


class PagingFakeClient:
    def __init__(self):
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append((url, params.copy() if params else {}))
        if "monitoring-locations" in url:
            if "offset=1" in url:
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
                        ],
                        "links": [],
                    }
                )
            return FakeResponse(
                {
                    "features": [],
                    "links": [
                        {
                            "rel": "next",
                            "href": "https://api.waterdata.usgs.gov/ogcapi/v0/collections/monitoring-locations/items?offset=1",
                        }
                    ],
                }
            )
        code = params.get("parameter_code")
        return FakeResponse(
            {
                "features": [
                    {
                        "properties": {
                            "monitoring_location_id": "USGS-11264500",
                            "parameter_code": code,
                            "time": "2026-09-05T10:30:00Z",
                        }
                    }
                ],
                "links": [],
            }
        )


def test_discovery_follows_usgs_next_links_for_nationwide_metadata():
    candidates = discover_usgs_candidates(PagingFakeClient(), limit=10)

    assert [item["state_name"] for item in candidates] == ["California"]
