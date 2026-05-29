from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    secret_key: str = "dev-secret-change-in-production"
    linkedin_cookie_secret: str = ""
    database_url: str = "sqlite:///./data/linkedin_manager.db"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"
    environment: str = "development"

    # JWT
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Safety limits
    max_connections_per_day: int = 15
    max_posts_per_day: int = 3
    min_action_interval_seconds: int = 45

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
