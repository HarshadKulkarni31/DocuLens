import os
import logging
from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer
from ..config import settings

logger = logging.getLogger(__name__)

# Prevent tokenizer fork deadlocks in multi-threaded/async environments
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


class EmbeddingService:
    _instance = None
    _model = None

    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        if EmbeddingService._model is None:
            # First attempt to load from local cache without network call
            try:
                EmbeddingService._model = SentenceTransformer(
                    self.model_name,
                    local_files_only=True,
                )
            except Exception:
                # Fall back to downloading or standard load
                EmbeddingService._model = SentenceTransformer(self.model_name)
        self.model = EmbeddingService._model

    def encode(self, texts: Union[str, List[str]]) -> np.ndarray:
        """
        Encodes text or list of texts into L2-normalized float32 embeddings.
        Normalizing vectors allows using Inner Product (IP) index as Cosine Similarity.
        """
        if isinstance(texts, str):
            texts = [texts]

        if not texts or all(not (t and t.strip()) for t in texts):
            return np.empty((0, self.get_dimension()), dtype=np.float32)

        # Filter or encode
        embeddings = self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.astype(np.float32)

    def get_dimension(self) -> int:
        if hasattr(self.model, "get_embedding_dimension"):
            return self.model.get_embedding_dimension()
        return self.model.get_sentence_embedding_dimension()
