from dataclasses import replace
from datetime import UTC, datetime, timedelta

from rivermetry.adapters.usgs import USGSAdapter
from rivermetry.models import Location, LocationStatus, ObservationSeriesPoint, TrendDirection
from rivermetry.refresh import assemble_snapshot, refresh_live_snapshots


def location():
    return Location(
        location_id="us-ca-test",
        status=LocationStatus.LIVE,
        country_code="us",
        region_code="california",
        slug="test-river",
        river_name="Test River",
        station_name="Test River at Town",
        observation_provider="usgs",
        station_id="12345678",
        latitude=37.7,
        longitude=-119.5,
        timezone="America/Los_Angeles",
        forecast_provider="noaa_nwps",
        forecast_location_id="TEST1",
    )


def test_assemble_snapshot_uses_series_as_static_fallback_and_builds_context():
    now = datetime(2026, 9, 6, 4, 0, tzinfo=UTC)
    level = tuple(
        ObservationSeriesPoint(4.0 + index * 0.1, now - timedelta(hours=24 - index))
        for index in range(25)
    )
    flow = tuple(
        ObservationSeriesPoint(300 + index * 5, now - timedelta(hours=24 - index))
        for index in range(25)
    )

    snapshot = assemble_snapshot(
        location(),
        {"water_level": level, "streamflow": flow},
        [float(value) for value in range(100, 130)],
        forecast=None,
        now=now,
    )

    assert snapshot.water_level.value == 6.4
    assert snapshot.water_level.unit == "ft"
    assert snapshot.streamflow.value == 420
    assert snapshot.streamflow.unit == "ft3/s"
    assert snapshot.trend == TrendDirection.RISING
    assert snapshot.update_status == "fresh"
    assert snapshot.history_context["changes"]["24h"] == 2.4
    assert snapshot.history_context["seven_day_average"] == 126.0
    assert snapshot.history_context["thirty_day_average"] == 114.5


def test_assemble_snapshot_marks_old_series_unavailable():
    now = datetime(2026, 9, 6, 4, 0, tzinfo=UTC)
    old = now - timedelta(hours=2)
    series = {
        "water_level": (
            ObservationSeriesPoint(4.2, old - timedelta(hours=1)),
            ObservationSeriesPoint(4.3, old),
        ),
        "streamflow": (
            ObservationSeriesPoint(300, old - timedelta(hours=1)),
            ObservationSeriesPoint(310, old),
        ),
    }

    snapshot = assemble_snapshot(location(), series, [100.0] * 30, forecast=None, now=now)

    assert snapshot.update_status == "unavailable"


def test_refresh_uses_bulk_usgs_queries_for_all_live_locations(monkeypatch):
    first = replace(
        location(),
        forecast_provider=None,
        forecast_location_id=None,
    )
    second = replace(
        first,
        location_id="us-ca-test-2",
        slug="test-river-2",
        station_id="87654321",
    )
    now = datetime.now(UTC)

    def points(level_value, flow_value):
        return {
            "water_level": (
                ObservationSeriesPoint(level_value - 0.1, now - timedelta(hours=1)),
                ObservationSeriesPoint(level_value, now),
            ),
            "streamflow": (
                ObservationSeriesPoint(flow_value - 10, now - timedelta(hours=1)),
                ObservationSeriesPoint(flow_value, now),
            ),
        }

    calls = {"series": 0, "daily": 0}

    def bulk_series(self, station_ids, start_iso, end_iso, batch_size=50):
        calls["series"] += 1
        assert station_ids == ["12345678", "87654321"]
        return {
            "12345678": points(4.2, 300),
            "87654321": points(5.1, 420),
        }

    def bulk_daily(self, station_ids, start_iso, end_iso, batch_size=50):
        calls["daily"] += 1
        assert station_ids == ["12345678", "87654321"]
        return {station_id: [100.0] * 30 for station_id in station_ids}

    def forbidden(*args, **kwargs):
        raise AssertionError("per-station USGS refresh path was called")

    monkeypatch.setattr(USGSAdapter, "fetch_series_bulk", bulk_series)
    monkeypatch.setattr(USGSAdapter, "fetch_daily_bulk", bulk_daily)
    monkeypatch.setattr(USGSAdapter, "fetch_series", forbidden)
    monkeypatch.setattr(USGSAdapter, "fetch_daily", forbidden)

    snapshots = refresh_live_snapshots(object(), [first, second], max_workers=2)

    assert set(snapshots) == {"us-ca-test", "us-ca-test-2"}
    assert snapshots["us-ca-test"].water_level.value == 4.2
    assert snapshots["us-ca-test-2"].streamflow.value == 420
    assert calls == {"series": 1, "daily": 1}
