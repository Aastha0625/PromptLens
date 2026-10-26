import logging
import math
from typing import List, Optional

logger = logging.getLogger(__name__)

class Embedder:
    """
    Lazy-loading wrapper around sentence-transformers ('all-MiniLM-L6-v2').
    Loads the model once per process on demand.
    If sentence-transformers is missing or fails, gracefully falls back without crashing.
    """
    _instance: Optional["Embedder"] = None

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._available: Optional[bool] = None

    @classmethod
    def get_instance(cls) -> "Embedder":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_model(self):
        if self._available is not None:
            return

        try:
            # Lazy import to avoid loading heavy torch/sentence-transformers on startup
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._available = True
            logger.info("SentenceTransformer model '%s' loaded successfully.", self.model_name)
        except Exception as e:
            self._available = False
            self._model = None
            logger.warning("Failed to load SentenceTransformer ('%s'): %s. Semantic checks will be skipped.", self.model_name, e)

    def is_available(self) -> bool:
        """Returns True if the embedding model is installed and loaded, False otherwise."""
        if self._available is None:
            self._load_model()
        return bool(self._available)

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a list of texts into vector representations.
        Returns empty list if texts are empty or model is unavailable.
        """
        if not texts:
            return []
        if not self.is_available():
            return []

        # encode returns numpy array or list of floats
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two 1D float vectors."""
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)
