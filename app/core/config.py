from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    # --- INFRASTRUCTURE ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/nexus_council"
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- API KEYS (Loaded from .env) ---
    TAVILY_API_KEY: str
    AVALAI_API_KEY: str
    OPENROUTER_API_KEY: str
    CF_ACCOUNT_ID: str
    CF_API_TOKEN: str

    # --- API CONFIGS ---
    AVALAI_BASE_URL: str = "https://api.avalai.ir/v1"

    # =========================================================
    #  MODEL REGISTRY (Centralized List of Available Models)
    # =========================================================
    
    # --- AVALAI (Free / Almost Free Tier) ---
    # Google's latest efficient models
    MDL_GEMMA_3_27B: str = "avalai/gemma-3-27b-it"
    MDL_GEMMA_3_12B: str = "avalai/gemma-3-12b-it"
    
    # NVIDIA NIM (Highly optimized, great reasoning)
    MDL_NEMOTRON_70B: str = "avalai/nvidia_nim.llama-3.3-nemotron-super-49b-v1.5"
    MDL_QWEN_THINKING: str = "avalai/nvidia_nim.qwen3-next-80b-a3b-thinking"
    
    # Ultra-Cheap / Fast
    MDL_GPT_NANO: str = "avalai/gpt-5-nano"
    MDL_QWEN_FLASH: str = "avalai/qwen-flash"
    MDL_GEMINI_FLASH: str = "avalai/gemini-2.0-flash-lite"

    # --- CLOUDFLARE (Free) ---
    MDL_CF_LLAMA_3: str = "cloudflare/@cf/meta/llama-3-8b-instruct"

    # --- OPENROUTER (Free Backup) ---
    MDL_OR_MISTRAL: str = "openrouter/mistralai/mistral-small-3.1-24b-instruct:free"

    # =========================================================
    #  ROLE ASSIGNMENTS (The Brains of the Operation)
    # =========================================================

    # 1. ARCHITECT
    # Needs: Strict JSON adherence and logical planning.
    # Selection: Gemini Flash Lite is excellent at JSON structure.
    MODEL_ARCHITECT: str = MDL_GEMINI_FLASH

    # 2. HUNTER
    # Needs: Speed and ability to generate creative search queries.
    # Selection: Gemma 3 12B is very fast and creative.
    MODEL_HUNTER_QUERY: str = MDL_GEMMA_3_12B

    # 3. ANALYST
    # Needs: Reading comprehension and high-quality writing.
    # Selection: Nemotron 70B is a "super" model. It writes better reports than 8B models.
    MODEL_ANALYST: str = MDL_NEMOTRON_70B

    # 4. MODERATOR
    # Needs: Large context window (to read all reports) and synthesis skills.
    # Selection: Gemini Flash Lite has a huge context window and is very stable.
    MODEL_MODERATOR: str = MDL_GEMINI_FLASH

    # =========================================================

    # --- EMBEDDINGS ---
    EMBEDDING_DIMENSION: int = 768
    EMBEDDING_MODEL: str = "nomic-embed-text"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

@lru_cache
def get_settings() -> Settings:
    return Settings() # pyright: ignore[reportCallIssue]