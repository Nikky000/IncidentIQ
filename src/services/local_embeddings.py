"""
Simple Local Embedding Service using sentence-transformers

This provides FREE local embeddings for testing without API keys.
"""

import numpy as np
from typing import Optional

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class LocalEmbeddingService:
    """
    Free local embeddings using sentence-transformers.

    No API key required - runs entirely on your machine.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize local embedding model.

        Args:
            model_name: Model to use (default: all-MiniLM-L6-v2)
                      - Fast, good quality, 384 dimensions
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )

        self.model = SentenceTransformer(model_name)
        self.dimensions = self.model.get_sentence_embedding_dimension()

    def embed(self, text: str, use_cache: bool = True) -> list[float]:
        """
        Generate embedding for text.

        Args:
            text: Input text
            use_cache: Ignored (local model, no caching needed)

        Returns:
            List of embedding dimensions
        """
        # Generate embedding
        embedding = self.model.encode(text, convert_to_numpy=True)

        # Convert to list and return
        return embedding.tolist()

    async def aembed(self, text: str, use_cache: bool = True) -> list[float]:
        """Async version of embed"""
        # sentence-transformers is synchronous, but that's fine for local use
        return self.embed(text, use_cache)

    async def embed_batch(self, texts: list[str], use_cache: bool = True) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of input texts
            use_cache: Ignored (local model, no caching needed)

        Returns:
            List of embedding vectors
        """
        # Generate embeddings in batch
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()


# Singleton
_local_embedding_instance: Optional[LocalEmbeddingService] = None


def get_local_embedding_service() -> LocalEmbeddingService:
    """Get or create local embedding service singleton"""
    global _local_embedding_instance

    if _local_embedding_instance is None:
        _local_embedding_instance = LocalEmbeddingService()

    return _local_embedding_instance


if __name__ == "__main__":
    # Quick test
    service = get_local_embedding_service()

    texts = [
        "database connection timeout",
        "postgres pool exhausted",
        "redis memory error",
    ]

    print("Testing local embeddings...")
    for text in texts:
        emb = service.embed(text)
        print(f"  {text}: {len(emb)} dimensions")

    # Test similarity
    from sklearn.metrics.pairwise import cosine_similarity

    embeddings = [service.embed(t) for t in texts]

    print("\nSimilarity matrix:")
    for i, text1 in enumerate(texts):
        for j, text2 in enumerate(texts):
            if i < j:
                sim = cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]
                print(f"  '{text1}' vs '{text2}': {sim:.2f}")
