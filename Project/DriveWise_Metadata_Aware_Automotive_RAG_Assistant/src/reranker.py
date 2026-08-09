
from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def rerank(query: str, retrieved: list[dict], vector_weight: float = 0.5) -> list[dict]:
    
    if not retrieved:
        return []

    corpus = [_tokenize(r["chunk"].search_text) for r in retrieved]
    bm25 = BM25Okapi(corpus)
    bm25_scores = bm25.get_scores(_tokenize(query))

    # normalize both score sets to [0, 1] so they can be blended fairly
    def normalize(scores):
        lo, hi = min(scores), max(scores)
        if hi - lo < 1e-9:
            return [1.0 for _ in scores]
        return [(s - lo) / (hi - lo) for s in scores]

    vector_scores = normalize([r["score"] for r in retrieved])
    bm25_scores_n = normalize(list(bm25_scores))

    for r, v, b in zip(retrieved, vector_scores, bm25_scores_n):
        r["rerank_score"] = vector_weight * v + (1 - vector_weight) * b

    return sorted(retrieved, key=lambda r: r["rerank_score"], reverse=True)
