from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/alphahunter"

    SUPABASE_URL: str = ""

    SUPABASE_KEY: str = ""

    GROQ_API_KEY: str = ""

    CLOUDFLARE_API_KEY: str = ""

    class Config:

        env_file = ".env"


settings = Settings()
