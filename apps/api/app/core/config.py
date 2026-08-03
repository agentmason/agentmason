from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AgentMason"
    environment: str = "development"
    database_url: str = "postgresql://agentmason:agentmason@localhost:5432/agentmason"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
