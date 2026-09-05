from datetime import datetime, timedelta, timezone

from rivermetry.config import CURRENT_CACHE_SECONDS, TREND_DEADBAND_FT
from rivermetry.models import Location, LocationStatus, ObservationSeriesPoint, TrendDirection
from rivermetry.validation.observations import freshness_state
from rivermetry.validation.trend import calculate_gage_trend

NOW=datetime(2026,9,5,2,0,tzinfo=timezone.utc)

def test_global_url():
    loc=Location('x',LocationStatus.LIVE,'us','california','merced-river','Merced River','Merced River','usgs','11264500',37.7,-119.5,'America/Los_Angeles')
    assert loc.public_path=='/us/california/merced-river/'

def test_release_constants():
    assert CURRENT_CACHE_SECONDS==900
    assert TREND_DEADBAND_FT==0.03

def test_freshness():
    assert freshness_state(NOW-timedelta(minutes=30),NOW)=='fresh'
    assert freshness_state(NOW-timedelta(minutes=60),NOW)=='delayed'
    assert freshness_state(NOW-timedelta(minutes=91),NOW)=='unavailable'

def test_trend():
    pts=(ObservationSeriesPoint(4.0,NOW-timedelta(minutes=60)),ObservationSeriesPoint(4.04,NOW))
    assert calculate_gage_trend(pts)==TrendDirection.RISING
