
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pipeline import DriveWisePipeline  # noqa: E402

LOADING_LINES = [
    "Waking up the brochures...",
    "Flipping through spec sheets...",
    "Chasing down every horsepower...",
    "Untangling mileage claims...",
    "Bribing the PDFs to cooperate...",
    "Counting airbags and cupholders...",
    "Reading the fine print, all of it...",
    "Almost there - polishing the dashboard...",
]

st.set_page_config(page_title="DriveWise - Car Brochure Assistant", page_icon="🚗", layout="centered")


if "pipeline" not in st.session_state:
    try:
        st.session_state.pipeline = DriveWisePipeline()
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

pipeline = st.session_state.pipeline
options = pipeline.list_options()

st.title("DriveWise")
st.caption("Ask questions about a car brochure - grounded, source-attributed answers.")

if not options:
    st.warning(
        "No PDFs found under `data/<Brand>/<Model>.pdf`. Add your brochure PDFs, "
        "commit them to the repo, and redeploy."
    )
    st.stop()

brands = sorted({b for b, _ in options})
col1, col2 = st.columns(2)
with col1:
    brand = st.selectbox("Brand", brands)
with col2:
    models = sorted(m for b, m in options if b == brand)
    model = st.selectbox("Model", models)

with st.form("ask_form"):
    query = st.text_input(
        "Your question",
        placeholder='e.g. "What is the mileage of the diesel automatic variant?"',
    )
    ask_clicked = st.form_submit_button("Ask", type="primary")

if ask_clicked and query.strip():
    with st.spinner("Retrieving brochure context and generating answer..."):
        result = pipeline.ask(brand, model, query.strip())

    st.markdown("### Answer")
    st.write(result["answer"])

    sources = result.get("sources") or []
    if sources:
        st.markdown("**Sources**")
        tags = " ".join(
            f"`{s['section'].replace('_', ' ')} · p.{s['page']}`" for s in sources
        )
        st.markdown(tags)

    eval_ = result.get("evaluation") or {}
    gen_mode = "LLM (Groq)" if result.get("used_llm") else "extractive fallback"
    st.caption(
        f"⏱ {result.get('response_time_ms', '-')} ms · "
        f"faithfulness: {eval_.get('faithfulness', '-')} · "
        f"context relevance: {eval_.get('context_relevance', '-')} · "
        f"generation: {gen_mode}"
    )
    if not result.get("used_llm") and result.get("llm_error"):
        st.warning(f"Groq call failed, used fallback: {result['llm_error']}")
elif ask_clicked:
    st.info("Type a question first.")

with st.expander("Stats"):
    import logger as qlog  # noqa: E402
    st.json(qlog.get_stats())
