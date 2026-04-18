"""Application configuration from environment variables."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Backend settings loaded from environment."""

    # Database
    database_url: str = "postgresql+asyncpg://tracker:tracker@localhost:5432/tracker"

    # MQTT
    mqtt_host: str = "mqtt.chickendinner.vip"
    mqtt_port: int = 8883
    mqtt_username: str = "trackerbackend"
    mqtt_password: str = ""
    # Dev only: subscribe to MQTT "#" to verify broker traffic (noisy; turn off after testing)
    mqtt_subscribe_catchall: bool = False

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Position retention (hours to keep historical positions)
    position_retention_hours: int = 24

    # Dev only: exposes /debug/mqtt (no auth). Default true for now — set false before production.
    enable_mqtt_debug_page: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
