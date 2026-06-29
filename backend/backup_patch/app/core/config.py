from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/alphahunter"

    SUPABASE_URL: Optional[str] = None

    SUPABASE_KEY: Optional[str] = None

    GROQ_API_KEY: Optional[str] = None

    CLOUDFLARE_API_KEY: Optional[str] = None

    QDRANT_HOST: str = "localhost"

    QDRANT_PORT: int = 6333

    REDIS_URL: str = "redis://localhost:6379"

    class Config:

        env_file = ".env"


settings = Settings()
