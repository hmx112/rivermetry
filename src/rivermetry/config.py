from dataclasses import dataclass
import os

CURRENT_CACHE_SECONDS = 900
STATIC_REFRESH_SECONDS = 7200
STALE_CURRENT_SECONDS = 5400
TREND_WINDOW_MINUTES = 60
TREND_DEADBAND_FT = 0.03


@dataclass(frozen=True)
class Settings:
    site_name: str
    base_url: str
    worker_base_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        base_url = os.environ.get("BASE_URL", "https://rivermetry.example").rstrip("/")
        worker_base_url = os.environ.get(
            "WORKER_BASE_URL", "https://current.rivermetry.example"
        ).rstrip("/")
        if not base_url.startswith("https://"):
            raise ValueError("BASE_URL must use https")
        if not worker_base_url.startswith("https://"):
            raise ValueError("WORKER_BASE_URL must use https")
        return cls(
            site_name=os.environ.get("SITE_NAME", "Rivermetry"),
            base_url=base_url,
            worker_base_url=worker_base_url,
        )
