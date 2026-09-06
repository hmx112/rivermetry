from rivermetry.enrichment import enrich_candidates, match_nwps, parse_nwps_gauges_report


NWPS_REPORT = (
    '"location name","nws shef id","usgs id","latitude","longitude","state",'
    '"forecast status","in service"\n'
    '"Test River","TEST1","11264500",37.7001,-119.5001,"CA",'
    '"Forecasts are issued routinely year-round.",true\n'
)


class Response:
    def __init__(self, payload=None):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Client:
    def post(self, url, *, params, headers, json, timeout):
        ids = json["args"][0]["args"][1]
        features = []
        for monitoring_id in ids:
            for code, begin in (
                ("00060", "1990-01-01T00:00:00Z"),
                ("00065", "2000-01-01T00:00:00Z"),
            ):
                features.append(
                    {
                        "properties": {
                            "monitoring_location_id": monitoring_id,
                            "parameter_code": code,
                            "begin": begin,
                        }
                    }
                )
        return Response({"features": features})


def candidate(state="California"):
    return {
        "location_id": "x",
        "station_id": "11264500",
        "state_name": state,
        "latitude": 37.7,
        "longitude": -119.5,
        "hard_gate": True,
    }


def test_enrichment_adds_history_and_nwps_forecast():
    gauges = parse_nwps_gauges_report(NWPS_REPORT)
    rows = enrich_candidates(Client(), [candidate()], nwps_gauges=gauges)
    assert len(rows) == 1
    assert rows[0]["history_years"] > 20
    assert rows[0]["nwps_lid"] == "TEST1"
    assert rows[0]["nwps_forecast"] is True


def test_enrichment_excludes_non_us_launch_regions():
    assert enrich_candidates(Client(), [candidate("British Columbia")], nwps_gauges=[]) == []


def test_static_nwps_report_maps_exact_usgs_id_and_forecast_configuration():
    gauges = parse_nwps_gauges_report(NWPS_REPORT)

    assert gauges[0]["usgs_id"] == "11264500"
    assert gauges[0]["lid"] == "TEST1"
    assert gauges[0]["nwps_forecast"] is True


def test_nwps_match_rejects_distant_gauge():
    gauges = [
        {
            "state": {"name": "California"},
            "latitude": 38.0,
            "longitude": -119.5,
            "lid": "FAR",
        }
    ]
    assert match_nwps(candidate(), gauges) is None
