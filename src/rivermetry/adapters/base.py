from typing import Protocol


class UpstreamDataError(RuntimeError):
    pass


class UpstreamSchemaError(RuntimeError):
    pass


class ObservationAdapter(Protocol):
    def fetch_latest(self, station_ids: list[str]): ...
    def fetch_series(self, station_id: str, start_iso: str, end_iso: str): ...
