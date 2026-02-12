from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # --- INFRASTRUCTURE ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/nexus_council"
    REDIS_URL: str = "redis://localhost:6379/0"
    TAVILY_API_KEY: str

    # --- AVALAI (Primary Pro) ---
    AVALAI_API_KEY: str
    AVALAI_BASE_URL: str = "https://api.avalai.ir/v1/chat/completions"
    AVALAI_MODEL_PRO: str = "gpt-4o"
    AVALAI_MODEL_STD: str = "gemma-3n-e2b-it"

    # --- OPENROUTER (Secondary/Backup) ---
    OPENROUTER_API_KEY: str
    OPENROUTER_MODEL: str = "mistralai/mistral-small-3.1-24b-instruct:free"

    # --- CLOUDFLARE (Fast Standard) ---
    CF_ACCOUNT_ID: str
    CF_API_TOKEN: str
    CF_MODEL: str = "@cf/meta/llama-3-8b-instruct"

    # --- EMBEDDINGS ---
    EMBEDDING_DIMENSION: int = 768 
    EMBEDDING_MODEL: str = "nomic-embed-text"

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()