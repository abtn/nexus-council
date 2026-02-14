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
    AVALAI_BASE_URL: str = "https://api.avalai.ir/v1"

    # --- ROLE-BASED MODEL MAPPING (DEV MODE: FREE/CHEAP MODELS) ---
    # Architect needs JSON structure, Gemini is good for this.
    MODEL_ARCHITECT: str = "avalai/google/gemini-flash-lite-latest" 
    
    # Hunter/Analyst needs to read text fast. Llama 3.1 8b on Cloudflare is great.
    MODEL_HUNTER_QUERY: str = "avalai/google/gemini-flash-lite-latest"
    MODEL_ANALYST: str = "cloudflare/@cf/meta/llama-3.1-8b-instruct"
    
    # Moderator needs to synthesize. Gemini Flash Lite has a good context window.
    MODEL_MODERATOR: str = "avalai/google/gemini-flash-lite-latest"

    # --- EMBEDDINGS ---
    EMBEDDING_DIMENSION: int = 768
    EMBEDDING_MODEL: str = "nomic-embed-text"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()