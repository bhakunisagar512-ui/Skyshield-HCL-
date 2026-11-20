from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://skyshield:skyshield@localhost:5433/skyshield"

    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    cors_origins: str = "http://localhost:5173"

    # AI: llm_provider = mock | anthropic | openai ; embedding_provider = hash | openai
    llm_provider: str = "mock"
    llm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    embedding_provider: str = "hash"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    rag_top_k: int = 6

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
