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

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts: 
            return []
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]