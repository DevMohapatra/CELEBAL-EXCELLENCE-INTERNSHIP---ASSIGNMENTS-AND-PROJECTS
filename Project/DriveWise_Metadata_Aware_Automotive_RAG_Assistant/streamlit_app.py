
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
    needs_parse = not Path("logs/chunk_cache.json").exists()
    if needs_parse:
        wave_placeholder = st.empty()
        text_placeholder = st.empty()

        wave_placeholder.markdown(
            """
            <style>
            .dw-loader-wrap {
                display: flex;
                justify-content: center;
                margin: 40px 0 12px 0;
            }
            .dw-loader {
                position: relative;
                width: 420px;
                max-width: 90vw;
                height: 64px;
                border-radius: 32px;
                background: #12141c;
                border: 1px solid #2a2d3a;
                overflow: hidden;
                box-shadow: 0 0 24px rgba(255,90,90,0.08);
            }
            .dw-water {
                position: absolute;
                bottom: 0;
                left: -25%;
                width: 150%;
                height: 100%;
                background: linear-gradient(90deg, #ff5a5a, #ff8a5a, #ff5a5a);
                border-radius: 45%;
                animation: dw-flow 3.2s linear infinite, dw-rise 2.4s ease-in-out infinite alternate;
                opacity: 0.85;
            }
            .dw-water::after {
                content: "";
                position: absolute;
                inset: 0;
                background: linear-gradient(90deg, #ff8a5a, #ffb35a, #ff8a5a);
                border-radius: 45%;
                animation: dw-flow 4.5s linear infinite reverse;
                opacity: 0.5;
            }
            @keyframes dw-flow {
                from { transform: translateX(0) rotate(0deg); }
                to   { transform: translateX(-33%) rotate(360deg); }
            }
            @keyframes dw-rise {
                from { height: 28%; }
                to   { height: 62%; }
            }
            .dw-loader-label {
                position: absolute;
                inset: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 600;
                font-size: 15px;
                letter-spacing: 0.02em;
                color: #fff;
                text-shadow: 0 1px 4px rgba(0,0,0,0.5);
                z-index: 2;
            }
            .dw-status-text {
                text-align: center;
                color: #aab0c0;
                font-size: 14px;
                margin-top: 4px;
            }
            </style>
            <div class="dw-loader-wrap">
                <div class="dw-loader">
                    <div class="dw-water"></div>
                    <div class="dw-loader-label" id="dw-label">Getting started...</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        def _update_progress(i, total, label):
            pct = int(i / total * 100) if total else 100
            line = LOADING_LINES[i % len(LOADING_LINES)]
            text_placeholder.markdown(
                f"""
                <div class="dw-status-text">
                    {line}<br>
                    <span style="opacity:0.7;">{label} · {pct}% ({i}/{total})</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.session_state.pipeline = DriveWisePipeline(progress_callback=_update_progress)
        wave_placeholder.empty()
        text_placeholder.empty()
    else:
        st.session_state.pipeline = DriveWisePipeline()

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
