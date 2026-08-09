
import time

from ingest import build_chunks, available_brands_models
from vectorstore import DriveWiseVectorStore
from reranker import rerank
from generator import generate_answer, control_context_window
from evaluator import evaluate
import logger as qlog


class DriveWisePipeline:
    def __init__(self, progress_callback=None):
        self.chunks = build_chunks(progress_callback=progress_callback)
        self.store = DriveWiseVectorStore(self.chunks)
        self.brands_models = available_brands_models()

    def list_options(self):
        return self.brands_models

    def ask(self, brand: str, model: str, query: str, top_k: int = 5, reference_answer: str | None = None) -> dict:
        start = time.time()
        try:
            retrieved = self.store.search(query, brand=brand, model=model, top_k=top_k)
            if not retrieved:
                elapsed_ms = (time.time() - start) * 1000
                qlog.log_query(brand, model, query, elapsed_ms, "failed",
                                error="No matching brand/model or no relevant chunks found.")
                return {
                    "answer": f"No brochure data found for {brand} {model}, or nothing relevant to your question.",
                    "sources": [],
                    "evaluation": {},
                    "response_time_ms": round(elapsed_ms, 1),
                }

            reranked = rerank(query, retrieved)
            context_items = control_context_window(reranked)
            gen_result = generate_answer(query, reranked, brand, model)
            eval_result = evaluate(gen_result["answer"], reranked, context_items, reference_answer)

            elapsed_ms = (time.time() - start) * 1000
            qlog.log_query(
                brand, model, query, elapsed_ms,
                "success" if gen_result["used_llm"] else "fallback",
                num_sources=len(gen_result["sources"]),
                answer_preview=gen_result["answer"],
                error=gen_result.get("llm_error", ""),
            )

            return {
                "answer": gen_result["answer"],
                "sources": gen_result["sources"],
                "used_llm": gen_result["used_llm"],
                "llm_error": gen_result.get("llm_error", ""),
                "evaluation": eval_result,
                "response_time_ms": round(elapsed_ms, 1),
            }

        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            qlog.log_query(brand, model, query, elapsed_ms, "failed", error=str(e))
            return {
                "answer": "Something went wrong while processing your question.",
                "sources": [],
                "evaluation": {},
                "response_time_ms": round(elapsed_ms, 1),
                "error": str(e),
            }


if __name__ == "__main__":
    pipeline = DriveWisePipeline()
    print("Available cars:", pipeline.list_options())
    res = pipeline.ask("Hyundai", "Creta", "What is the mileage of the diesel automatic variant?")
    print(json.dumps(res, indent=2)) if False else print(res)
