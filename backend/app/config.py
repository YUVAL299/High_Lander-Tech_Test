"""Runtime configuration, read from environment variables (prefix ``HL_``)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HL_", env_file=".env", extra="ignore")

    app_name: str = "High Lander"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # Routing (OSRM). The default is the free FOSSGIS walking instance;
    # point it at http://osrm:5000 to use the local container instead.
    osrm_url: str = "https://routing.openstreetmap.de/routed-foot"
    osrm_profile: str = "foot"
    osrm_timeout_s: float = 5.0
    osrm_retries: int = 1

    # Goal placement
    goal_min_distance_m: float = 200.0
    goal_max_distance_m: float = 800.0
    goal_reach_radius_m: float = 20.0

    # Rerouting
    reroute_off_route_m: float = 25.0
    reroute_min_interval_s: float = 3.0

    # Housekeeping
    session_ttl_s: float = 3600.0
    session_sweep_interval_s: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
