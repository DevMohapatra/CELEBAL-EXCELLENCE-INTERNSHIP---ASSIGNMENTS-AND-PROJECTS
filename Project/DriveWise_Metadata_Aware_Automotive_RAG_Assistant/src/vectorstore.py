
import numpy as np
import faiss
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

from ingest import Chunk


class Embedder:

    def __init__(self, n_components: int = 128):
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.fitted = False

    def fit(self, texts: list[str]):
        tfidf = self.vectorizer.fit_transform(texts)
        self.fitted = True
        return self._normalize(tfidf.toarray()).astype("float32")

    def transform(self, texts: list[str]):
        if not self.fitted:
            raise RuntimeError("Embedder not fitted yet.")
        tfidf = self.vectorizer.transform(texts)
        return self._normalize(tfidf.toarray()).astype("float32")

    @staticmethod
    def _normalize(vecs: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1e-8
        return vecs / norms


class DriveWiseVectorStore:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.embedder = Embedder()
        texts = [c.search_text for c in chunks]
        vectors = self.embedder.fit(texts)
        self.dim = vectors.shape[1]
        self.index = faiss.IndexFlatIP(self.dim)  # cosine sim via normalized inner product
        self.index.add(vectors)

    def _metadata_filter(self, brand: str | None, model: str | None) -> list[int]:
        """Return indices of chunks matching the brand/model filter."""
        idxs = []
        for i, c in enumerate(self.chunks):
            if brand and c.metadata["brand"].lower() != brand.lower():
                continue
            if model and c.metadata["model"].lower() != model.lower():
                continue
            idxs.append(i)
        return idxs

    def search(self, query: str, brand: str | None = None, model: str | None = None, top_k: int = 5):
        
        candidate_idxs = self._metadata_filter(brand, model)
        if not candidate_idxs:
            return []

        query_vec = self.embedder.transform([query])

        # Build a temporary sub-index over the filtered candidates only,
        # so metadata filtering happens BEFORE similarity search (not after).
        sub_vectors = np.stack([self._vector_for(i) for i in candidate_idxs])
        sub_index = faiss.IndexFlatIP(self.dim)
        sub_index.add(sub_vectors)

        k = min(top_k, len(candidate_idxs))
        scores, sub_positions = sub_index.search(query_vec, k)

        results = []
        for score, sub_pos in zip(scores[0], sub_positions[0]):
            if sub_pos == -1:
                continue
            real_idx = candidate_idxs[sub_pos]
            results.append({"chunk": self.chunks[real_idx], "score": float(score)})
        return results

    def _vector_for(self, idx: int) -> np.ndarray:
        # Recompute embedding lazily via cached matrix for simplicity.
        if not hasattr(self, "_all_vectors"):
            self._all_vectors = self.embedder.transform([c.search_text for c in self.chunks])
        return self._all_vectors[idx]
