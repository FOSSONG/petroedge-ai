from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PetroEdge AI"
    environment: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    jwt_secret: str = "change-this-secret-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    database_url: str = "postgresql+psycopg://petroedge:petroedge@localhost:5432/petroedge"
    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap_servers: str = "localhost:29092"
    mlflow_tracking_uri: str = "http://localhost:5000"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @cached_property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

