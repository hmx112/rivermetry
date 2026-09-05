from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class LocationStatus(StrEnum):
    CANDIDATE = "candidate"
    PREVIEW = "preview"
    LIVE = "live"
    PAUSED = "paused"


class TrendDirection(StrEnum):
    RISING = "rising"
    FALLING = "falling"
    STEADY = "steady"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Observation:
    value: float
    unit: str
    observed_at: datetime
    quality_status: str | None = None


@dataclass(frozen=True)
class ObservationSeriesPoint:
    value: float
    observed_at: datetime


@dataclass(frozen=True)
class ForecastSnapshot:
    provider: str
    location_id: str
    updated_at: datetime
    values: tuple[dict, ...] = ()
    official_categories: tuple[dict, ...] = ()


@dataclass(frozen=True)
class Location:
    location_id: str
    status: LocationStatus
    country_code: str
    region_code: str
    slug: str
    river_name: str
    station_name: str
    observation_provider: str
    station_id: str
    latitude: float
    longitude: float
    timezone: str
    forecast_provider: str | None = None
    forecast_location_id: str | None = None
    state_name: str | None = None
    drainage_area: float | None = None
    launch_validated_at: str | None = None

    @property
    def public_path(self) -> str:
        return f"/{self.country_code}/{self.region_code}/{self.slug}/"


@dataclass(frozen=True)
class LocationSnapshot:
    location: Location
    water_level: Observation | None
    streamflow: Observation | None
    trend: TrendDirection
    level_series: tuple[ObservationSeriesPoint, ...] = field(default_factory=tuple)
    flow_series: tuple[ObservationSeriesPoint, ...] = field(default_factory=tuple)
    history_context: dict = field(default_factory=dict)
    forecast: ForecastSnapshot | None = None
    update_status: str = "fresh"
