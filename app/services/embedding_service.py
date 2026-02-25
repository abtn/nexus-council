import asyncio # 1. Import asyncio
from sentence_transformers import SentenceTransformer
from app.core.config import get_settings
import logging
from functools import lru_cache

settings = get_settings()
logger = logging.getLogger(__name__)

@lru_cache()
def get_embedding_model():
    """Loads the model once per process."""
    logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}...")
    return SentenceTransformer(settings.EMBEDDING_MODEL)

class EmbeddingService:
    def __init__(self):
        self.model = get_embedding_model()

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        
        # 2. Run the blocking model.encode in a separate thread to unblock the event loop
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(None, self.model.encode, texts)
        
        return [emb.tolist() for emb in embeddings]

    async def embed_query(self, text: str) -> list[float]:
        # 3. Update to await the async method
        return (await self.embed_texts([text]))[0]