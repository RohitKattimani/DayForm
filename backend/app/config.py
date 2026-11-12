from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Dayform Store API"
    environment: str = "development"
    database_url: str = ""

    kafka_bootstrap_servers: str = ""
    kafka_username: str = ""
    kafka_password: str = ""
    kafka_sasl_mechanism: str = "SCRAM-SHA-256"
    kafka_ca_path: str = ""
    kafka_topic: str = "store.events"
    kafka_group_id: str = "dayform-inventory-sync-v1"

    opensearch_url: str = ""
    opensearch_index: str = "dayform-products-v1"

    auto_create_tables: bool = True
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    log_level: str = "INFO"

    @property
    def kafka_configured(self) -> bool:
        return bool(self.kafka_bootstrap_servers and self.kafka_username and self.kafka_password)

    @property
    def opensearch_configured(self) -> bool:
        return bool(self.opensearch_url)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
