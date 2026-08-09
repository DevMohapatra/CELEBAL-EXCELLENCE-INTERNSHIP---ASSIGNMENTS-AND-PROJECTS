
import os
import json
import urllib.request
import urllib.error

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads .env in the project root if present; no-op if missing
except ImportError:
    pass

GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")


def _get_groq_api_key() -> str | None:

    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("GROQ_API_KEY")
    except Exception:
        return None


def control_context_window(reranked: list[dict], max_chunks: int = 3, max_chars: int = 1200) -> list[dict]:
    selected = []
    used_chars = 0
    for r in reranked[:max_chunks]:
        text = r["chunk"].text
        if used_chars + len(text) > max_chars and selected:
            break
        selected.append(r)
        used_chars += len(text)
    return selected


def _build_prompt(query: str, context_items: list[dict], brand: str, model: str) -> str:
    context_block = "\n\n".join(
        f"[Source {i+1} | {c['chunk'].metadata['section'].replace('_', ' ')} | page {c['chunk'].metadata['page']}]\n{c['chunk'].text}"
        for i, c in enumerate(context_items)
    )
    return (
        f"You are DriveWise, an assistant that answers questions about the {brand} {model} "
        f"strictly using the brochure excerpts below. Do not use outside knowledge. "
        f"If the answer isn't in the excerpts, say so.\n\n"
        f"Brochure excerpts:\n{context_block}\n\n"
        f"Question: {query}\n\nAnswer concisely and cite which source(s) you used."
    )


def _call_groq(prompt: str) -> tuple[str | None, str]:
    
    api_key = _get_groq_api_key()
    if not api_key:
        return None, "No GROQ_API_KEY found in environment or Streamlit secrets."
    try:
        req_body = json.dumps({
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400,
            "temperature": 0.2,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=req_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"].strip()
            return (content or None), ("" if content else "Groq returned an empty completion.")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return None, f"Groq HTTP {e.code}: {body[:300]}"
    except Exception as e:
        return None, f"Groq call failed: {type(e).__name__}: {e}"


def _extractive_fallback(query: str, context_items: list[dict]) -> str:
    """Simple, fully offline fallback: return the best-matching chunk(s) verbatim
    as the answer when no Groq key is set or the call fails."""
    if not context_items:
        return "I couldn't find relevant information in the brochure for this question."
    best = context_items[0]["chunk"]
    return best.text


def generate_answer(query: str, reranked: list[dict], brand: str, model: str) -> dict:
    context_items = control_context_window(reranked)

    prompt = _build_prompt(query, context_items, brand, model)
    answer, llm_error = _call_groq(prompt)
    used_llm = answer is not None
    if not used_llm:
        answer = _extractive_fallback(query, context_items)

    sources = [
        {
            "brochure_name": c["chunk"].metadata["brochure_name"],
            "section": c["chunk"].metadata["section"],
            "page": c["chunk"].metadata["page"],
            "document_version": c["chunk"].metadata["document_version"],
        }
        for c in context_items
    ]

    return {
        "answer": answer,
        "sources": sources,
        "used_llm": used_llm,
        "llm_error": llm_error if not used_llm else "",
        "num_context_chunks": len(context_items),
    }

