from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AgentMason"
    environment: str = "development"
    database_url: str = "sqlite:///./agentmason.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # RAG Configuration
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 800
    chunk_overlap: int = 120
    rag_top_k: int = 5
    max_upload_size_mb: int = 25
    vector_store: str = "pgvector"
    local_storage_path: str = "./storage"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
