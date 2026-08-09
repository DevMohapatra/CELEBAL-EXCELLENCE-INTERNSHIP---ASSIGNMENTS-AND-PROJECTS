
import re


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def faithfulness_score(answer: str, context_items: list[dict]) -> float:
    context_text = " ".join(c["chunk"].text for c in context_items)
    ans_tokens = _tokens(answer)
    ctx_tokens = _tokens(context_text)
    if not ans_tokens:
        return 0.0
    overlap = ans_tokens & ctx_tokens
    return round(len(overlap) / len(ans_tokens), 3)


def context_relevance_score(reranked: list[dict]) -> float:
    if not reranked:
        return 0.0
    scores = [float(r.get("rerank_score", r.get("score", 0.0))) for r in reranked]
    return round(sum(scores) / len(scores), 3)


def answer_correctness_score(answer: str, reference_answer: str) -> float:
    ans_tokens = _tokens(answer)
    ref_tokens = _tokens(reference_answer)
    if not ref_tokens:
        return 0.0
    overlap = ans_tokens & ref_tokens
    return round(len(overlap) / len(ref_tokens), 3)


def evaluate(answer: str, reranked: list[dict], context_items: list[dict], reference_answer: str | None = None) -> dict:
    result = {
        "faithfulness": faithfulness_score(answer, context_items),
        "context_relevance": context_relevance_score(reranked),
    }
    if reference_answer:
        result["answer_correctness"] = answer_correctness_score(answer, reference_answer)
    return result
