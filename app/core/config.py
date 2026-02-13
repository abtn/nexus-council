from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    # --- INFRASTRUCTURE ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/nexus_council"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # --- API KEYS ---
    TAVILY_API_KEY: str
    AVALAI_API_KEY: str
    OPENROUTER_API_KEY: str
    CF_ACCOUNT_ID: str
    CF_API_TOKEN: str

    # --- AVALAI CONFIG ---
    # Added the missing Base URL
    AVALAI_BASE_URL: str = "https://api.avalai.ir/v1"

    # --- ROLE-BASED MODEL MAPPING ---
    MODEL_ARCHITECT: str = "avalai/grok-3-mini-fast-beta"
    MODEL_HUNTER_QUERY: str = "avalai/grok-3-mini-fast-beta"
    MODEL_ANALYST: str = "avalai/grok-3-mini-fast-beta"
    MODEL_MODERATOR: str = "avalai/grok-3-mini-fast-beta"

    # --- EMBEDDINGS ---
    EMBEDDING_DIMENSION: int = 768 
    # Added the missing Embedding Model
    EMBEDDING_MODEL: str = "nomic-embed-text"

    # Pydantic V2 Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()