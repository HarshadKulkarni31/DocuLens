import os
import sys
import logging
from typing import List, Tuple, Optional
import numpy as np
from .chunking_service import Chunk
from .embedding_service import EmbeddingService
from ..config import settings

logger = logging.getLogger(__name__)

# Determine vector search backend:
# On Windows Python 3.14, faiss-cpu C-extension has known STATUS_INVALID_HANDLE issues.
# NumPy dot product on normalized vectors provides identical cosine similarity results.
# In Docker / Linux deployments, FAISS is used natively.
env_faiss = os.getenv("USE_FAISS", "auto").lower()
if env_faiss == "auto":
    HAS_FAISS = sys.platform != "win32"
else:
    HAS_FAISS = env_faiss in ("true", "1", "yes")

if HAS_FAISS:
    try:
        import faiss
    except Exception as e:
        HAS_FAISS = False
        logger.warning(f"FAISS unavailable ({e}). Using high-performance NumPy cosine similarity.")


class DocumentIndex:
    def __init__(
        self,
        document_id: str,
        chunks: List[Chunk],
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self.document_id = document_id
        self.chunks = chunks  # Vector index position maps 1:1 to chunk index
        self.embedding_service = embedding_service or EmbeddingService()
        self.dimension = self.embedding_service.get_dimension()
        self.use_faiss = HAS_FAISS
        self.index = None
        self.embeddings_matrix = None

        self._build_index()

    def _build_index(self):
        if not self.chunks:
            return

        texts = [chunk.text for chunk in self.chunks]
        embeddings = self.embedding_service.encode(texts)
        if embeddings.shape[0] == 0:
            return

        self.embeddings_matrix = embeddings

        if self.use_faiss:
            try:
                import faiss
                # Flat Inner Product on normalized vectors equals cosine similarity
                index = faiss.IndexFlatIP(self.dimension)
                index.add(embeddings)
                self.index = index
            except Exception as e:
                logger.warning(f"FAISS indexing error ({e}). Falling back to NumPy cosine similarity.")
                self.use_faiss = False

    def search(self, query: str, top_k: int = None) -> List[Tuple[Chunk, float]]:
        """
        Retrieves the top_k most similar chunks for a given query string.
        Returns a list of (Chunk, similarity_score) tuples.
        Safely guards against empty queries, missing index, or zero-chunk documents.
        """
        top_k = top_k or settings.TOP_K
        if not query or not query.strip():
            return []

        if not self.chunks or self.embeddings_matrix is None or len(self.chunks) == 0:
            return []

        top_k = min(top_k, len(self.chunks))
        query_vector = self.embedding_service.encode(query.strip())
        if query_vector.shape[0] == 0:
            return []

        if self.use_faiss and self.index is not None:
            # FAISS search
            scores, indices = self.index.search(query_vector, top_k)
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if 0 <= idx < len(self.chunks):
                    results.append((self.chunks[idx], float(score)))
            return results
        else:
            # High-performance NumPy cosine similarity: dot product of normalized vectors
            scores = np.dot(self.embeddings_matrix, query_vector[0])
            top_indices = np.argsort(scores)[::-1][:top_k]
            results = []
            for idx in top_indices:
                results.append((self.chunks[idx], float(scores[idx])))
            return results
