from datetime import UTC, datetime, timedelta

from rivermetry.models import Location, LocationStatus, ObservationSeriesPoint, TrendDirection
from rivermetry.refresh import assemble_snapshot


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
        "water_level": (ObservationSeriesPoint(4.2, old - timedelta(hours=1)), ObservationSeriesPoint(4.3, old)),
        "streamflow": (ObservationSeriesPoint(300, old - timedelta(hours=1)), ObservationSeriesPoint(310, old)),
    }

    snapshot = assemble_snapshot(location(), series, [100.0] * 30, forecast=None, now=now)

    assert snapshot.update_status == "unavailable"
