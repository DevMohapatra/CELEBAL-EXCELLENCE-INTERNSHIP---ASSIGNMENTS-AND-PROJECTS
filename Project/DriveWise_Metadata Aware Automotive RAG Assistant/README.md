# DriveWise - Car Brochure Assistant

Ask a question about a car and get an answer pulled straight from the actual manufacturer brochure, with the source (section + page number) shown alongside it. Built as a RAG pipeline over real PDF brochures.

## How it's organized

Drop your PDFs into `data/<Brand>/<Model>.pdf` - one folder per brand:

```
data/
├── Honda/
│   ├── All_New_ZR_V.pdf
│   ├── Amaze_2nd_Gen.pdf
│   ├── Elevate.pdf
│   ├── New_Amaze.pdf
│   └── New_City.pdf
│
├── Hyundai/
│   ├── alcazar.pdf
│   ├── aura.pdf
│   ├── creta_ev.pdf
│   ├── creta_n_line.pdf
│   ├── creta.pdf
│   ├── exter.pdf
│   ├── grand_i10_nios.pdf
│   ├── i20_n_line.pdf
│   ├── i20.pdf
│   ├── ioniq_5.pdf
│   ├── venue.pdf
│   └── verna.pdf
│
├── Kia/
│   ├── Carens_Leaflet.pdf
│   ├── EV6_Desktop_2025.pdf
│   ├── Kia_Carens_Clavis_Brochure_Desktop.pdf
│   ├── Kia_CarensClavisEV_Brochure_Desktop.pdf
│   ├── Kia_Carnival_Brochure_Desktop.pdf
│   ├── Kia_EV9_Brochure_Desktop.pdf
│   └── Kia_Seltos_Brochure_Desktop_2026.pdf
│
├── Tata/
│   ├── altroz_brochure_may_2026_new.pdf
│   ├── curvv_nov.pdf
│   ├── harrier_master_brochure.pdf
│   ├── Nexon_Brochure.pdf
│   ├── next_gen_tiago_brochure_may.pdf
│   ├── safari_master_brochure.pdf
│   ├── sierra_web_brochure_june.pdf
│   ├── tata_punch_brochure_may_new.pdf
│   ├── tigor_brochure.pdf
│   └── XPRES_Brochure.pdf
│
└── Toyota/
    ├── 2026_gr86_brochure.pdf
    ├── 2026_grcorolla_brochure.pdf
    ├── 2026_grsupra_brochure.pdf
    ├── camry_ebrochure.pdf
    ├── corolla_ebrochure.pdf
    ├── corollahatchback_ebrochure.pdf
    ├── crown_ebrochure.pdf
    ├── mirai_brochure.pdf
    ├── prius_ebrochure.pdf
    ├── priuspluginhybrid_ebrochure.pdf
    └── sienna_brochure.pdf
    
```

The brand comes from the folder name, the model from the filename - nothing to configure. Filenames can have spaces, hyphens, years, whatever the manufacturer actually named the file.

## What happens under the hood

```
Question in → filtered to the chosen brand/model → TF-IDF search over that brochure's
chunks → BM25 re-ranking → top few chunks kept within a character budget →
sent to Groq for a real generated answer (falls back to just returning the best-matching
excerpt if Groq isn't reachable) → answer comes back with its source page(s) attached
```

Every query also gets logged to a small SQLite file so you can see response times and whether the LLM actually fired or it fell back to raw extraction.

## Running it

```bash
cd drivewise
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Opens at `http://localhost:8501`. First run parses every PDF in `data/` - takes a few seconds per brochure, and you'll see a live progress bar climbing through them (e.g. "Parsing Honda/Elevate.pdf (3/23)"). After that first parse, results are cached to `logs/chunk_cache.json`, so every run after is close to instant - it only re-parses a brochure if that specific PDF file has changed.

**Adding your own brochures:** just drop the PDF into `data/<Brand>/<Model>.pdf` and restart. No limit on how many brands or models - add as many as you want. If one PDF happens to be corrupt or unreadable, it gets skipped with a warning instead of taking the whole app down.

## Getting real LLM answers instead of raw excerpts

Without any setup, DriveWise still works - it just returns the closest-matching brochure excerpt verbatim instead of a properly generated answer. To get real generated answers:

1. Grab a free key at [console.groq.com/keys](https://console.groq.com/keys) - no card needed.
2. Create a `.env` file in the project root (copy `.env.example`) and put your key in:
   ```
   GROQ_API_KEY=gsk_your_key_here
   GROQ_MODEL=llama-3.1-8b-instant
   ```
3. Restart the app.

If a call fails for any reason (bad key, network issue, model deprecated), the app tells you exactly why right under the answer instead of silently falling back - worth keeping an eye on that message if answers start looking too "extractive."

## Deploying it live (free) - Streamlit Community Cloud

1. Push the repo to GitHub, **PDFs included** - Streamlit Cloud only sees what's actually committed, not what's on your disk.
2. Go to [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub → New app.
3. Point it at your repo, set the main file to `streamlit_app.py`.
4. In **Settings → Secrets**, add the same two lines as your `.env`:
   ```
   GROQ_API_KEY = "gsk_..."
   GROQ_MODEL = "llama-3.1-8b-instant"
   ```
5. Deploy. First load will parse everything (same progress bar), then it's cached for everyone after.

You end up with a public `your-app-name.streamlit.app` URL.

*(Not on Vercel - it's serverless with no persistent disk, and this needs `faiss-cpu` + `pdfplumber` running as a real long-lived process. Streamlit Cloud is just the right shape for this.)*

## How the PDF parsing actually works

Brochures don't come pre-labeled with sections, so `parser.py` does two passes per page:

1. Looks for short header-like lines ("SAFETY", "Dimensions & Specifications") and treats everything until the next header as belonging to that section.
2. If no header shows up on a page - common on cover pages or dense spec tables - it scores the text against a keyword list per section and assigns whichever one scores highest. If nothing scores well, it's tagged `general` rather than forced somewhere wrong.

If your brochures use different section names, extend `SECTION_KEYWORDS` and `HEADER_ALIASES` at the top of `parser.py` - everything else adapts automatically.

For scanned/image-only PDFs with no actual text layer, `pdfplumber` comes back empty and that page gets silently skipped. Check with `pdffonts yourfile.pdf` - no fonts listed means you'd need an OCR pass first.

## What this doesn't do (on purpose)

- **Embeddings** are TF-IDF, not a neural model - keeps it fully offline with zero model downloads. Swap in `sentence-transformers` in `vectorstore.py` if you want better semantic matching at some added weight/latency cost.
- **Generation** depends on Groq being reachable; no paid API involved anywhere.
- **Parsing** is heuristic (headers + keywords), not layout-ML - brochures that are mostly graphics or complex multi-column tables will extract worse than plain text-heavy ones.
