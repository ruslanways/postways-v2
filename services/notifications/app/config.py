"""Configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Notification service settings."""

    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_topic: str = "post-events"
    kafka_consumer_group: str = "notifications-service"

    model_config = {"env_prefix": "NOTIFICATIONS_"}


settings = Settings()
