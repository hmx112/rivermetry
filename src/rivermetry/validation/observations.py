from datetime import datetime
import math
from typing import Literal

from rivermetry.models import Observation


class ObservationValidationError(ValueError):
    pass


def validate_observation(obs: Observation, now: datetime) -> Observation:
    if not math.isfinite(obs.value):
        raise ObservationValidationError("observation value is non-finite")
    if not obs.unit.strip():
        raise ObservationValidationError("observation unit is empty")
    if obs.observed_at.tzinfo is None or now.tzinfo is None:
        raise ObservationValidationError("observation timestamps must be timezone-aware")
    if (obs.observed_at - now).total_seconds() > 600:
        raise ObservationValidationError("observation timestamp is too far in the future")
    return obs


def freshness_state(observed_at: datetime, now: datetime) -> Literal["fresh", "delayed", "unavailable"]:
    age = (now - observed_at).total_seconds()
    if age <= 1800:
        return "fresh"
    if age <= 5400:
        return "delayed"
    return "unavailable"
