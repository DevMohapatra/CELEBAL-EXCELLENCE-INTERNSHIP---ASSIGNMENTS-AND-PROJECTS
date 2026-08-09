
import re
from pathlib import Path
from dataclasses import dataclass, field

import pdfplumber

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Canonical sections and the keywords that signal them. Order doesn't matter;
# scoring picks the best match. Extend these lists to match your brochures'
# vocabulary (e.g. add "boot capacity", "cargo volume" under dimensions).
SECTION_KEYWORDS = {
    "engine_and_performance": [
        "engine", "power", "torque", "displacement", "transmission", "bhp",
        "ps ", "nm ", "horsepower", "gearbox", "cc ", "cylinder", "turbo",
        "manual", "automatic", "amt", "dct", "ivt", "cvt",
    ],
    "mileage_and_fuel_efficiency": [
        "mileage", "kmpl", "km/l", "km/kg", "fuel efficiency", "fuel tank",
        "arai", "fuel economy", "range", "cng",
    ],
    "safety": [
        "airbag", "safety", "abs", "ebd", "esc", "isofix", "ncap", "adas",
        "crash", "seatbelt", "hill-assist", "hill assist", "tpms",
        "stability control", "collision",
    ],
    "dimensions": [
        "length", "width", "height", "wheelbase", "ground clearance",
        "boot space", "dimensions", " mm", "turning radius", "kerb weight",
        "cargo",
    ],
    "interior_and_comfort": [
        "seat", "interior", "sunroof", "upholstery", "climate control",
        "cabin", "comfort", "ventilated", "legroom", "armrest", "glovebox",
    ],
    "infotainment_and_connectivity": [
        "infotainment", "touchscreen", "bluetooth", "android auto",
        "apple carplay", "speaker", "connectivity", "app ", "sound system",
        "cluster", "navigation", "voice command",
    ],
}

# A short, mostly-uppercase or title-case line is almost always a section
# header in brochure layouts. Map header text -> canonical section directly
# when it matches, which is more reliable than keyword-scoring body text alone.
HEADER_ALIASES = {
    "engine_and_performance": ["engine", "performance", "powertrain"],
    "mileage_and_fuel_efficiency": ["mileage", "fuel efficiency", "fuel economy"],
    "safety": ["safety", "safety features"],
    "dimensions": ["dimensions", "specifications", "specs"],
    "interior_and_comfort": ["interior", "comfort", "interior & comfort", "interior and comfort"],
    "infotainment_and_connectivity": ["infotainment", "connectivity", "infotainment & connectivity", "infotainment and connectivity"],
}

MIN_CHUNK_CHARS = 40  # drop near-empty blocks (stray headers, page numbers, etc.)


@dataclass
class ParsedChunk:
    text: str
    brand: str
    model: str
    section: str
    page: int
    brochure_name: str
    document_version: str

    def to_dict(self):
        return {
            "text": self.text,
            "metadata": {
                "brand": self.brand,
                "model": self.model,
                "section": self.section,
                "page": self.page,
                "brochure_name": self.brochure_name,
                "document_version": self.document_version,
            },
        }


def _looks_like_header(line: str) -> str | None:
    
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return None
    # Header cues: short line, no trailing period, mostly uppercase or title case
    is_short = len(stripped.split()) <= 6
    is_shouty = stripped.upper() == stripped and any(c.isalpha() for c in stripped)
    if not (is_short and (is_shouty or stripped.istitle())):
        return None
    lowered = stripped.lower()
    for section, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                return section
    return None


def _classify_by_keywords(text: str, min_score: int = 2) -> str:
    lowered = text.lower()
    scores = {section: sum(lowered.count(kw) for kw in kws) for section, kws in SECTION_KEYWORDS.items()}
    best_section = max(scores, key=scores.get)
    # Require a minimum keyword hit count before committing to a section -
    # a single incidental keyword (e.g. "ARAI" mentioned in passing on a
    # cover page) shouldn't be enough to mislabel unrelated content.
    return best_section if scores[best_section] >= min_score else "general"


def _split_into_blocks(page_text: str) -> list[str]:
    
    blocks = [b.strip() for b in re.split(r"\n\s*\n", page_text) if b.strip()]
    return blocks if blocks else ([page_text.strip()] if page_text.strip() else [])


def parse_pdf(pdf_path: Path, brand: str, model: str) -> list[ParsedChunk]:
    chunks = []
    brochure_name = pdf_path.stem
    document_version = f"v-{pdf_path.stat().st_mtime_ns // 1_000_000_000}"  # unix seconds, changes when file is edited

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            try:
                raw_text = page.extract_text() or ""
            except Exception as e:
                # Some real-world brochure pages (corrupt fonts, odd encodings,
                # vector-only pages) can make pdfplumber raise mid-extraction.
                # Skip just that page rather than losing the whole brochure.
                print(f"  [warn] {brand}/{brochure_name} page {page_num}: text extraction failed ({e}) - skipped")
                continue
            if not raw_text.strip():
                continue  # likely a scanned/image page - see README for OCR fallback

            lines = raw_text.split("\n")
            current_section = None
            buffer: list[str] = []

            def flush():
                block_text = " ".join(buffer).strip()
                if len(block_text) >= MIN_CHUNK_CHARS:
                    section = current_section or _classify_by_keywords(block_text)
                    chunks.append(ParsedChunk(
                        text=block_text, brand=brand, model=model, section=section,
                        page=page_num, brochure_name=brochure_name, document_version=document_version,
                    ))
                buffer.clear()

            for line in lines:
                header_section = _looks_like_header(line)
                if header_section:
                    flush()
                    current_section = header_section
                    continue
                buffer.append(line.strip())
            flush()

    return chunks


def parse_all(data_dir: Path = DATA_DIR, verbose: bool = True, progress_callback=None) -> list[ParsedChunk]:
    
    all_chunks: list[ParsedChunk] = []
    if not data_dir.exists():
        return all_chunks

    brand_dirs = sorted(p for p in data_dir.iterdir() if p.is_dir())
    all_pdfs = [
        (brand_dir.name, pdf_path)
        for brand_dir in brand_dirs
        for pdf_path in sorted(brand_dir.glob("*.pdf"))
    ]
    total = len(all_pdfs)

    for i, (brand, pdf_path) in enumerate(all_pdfs, start=1):
        model = pdf_path.stem
        try:
            pdf_chunks = parse_pdf(pdf_path, brand, model)
        except Exception as e:
            print(f"[warn] Skipping unreadable PDF: {brand}/{pdf_path.name} ({e})")
            if progress_callback:
                progress_callback(i, total, f"{brand}/{pdf_path.name}")
            continue
        if verbose:
            print(f"Parsed {brand}/{pdf_path.name}: {len(pdf_chunks)} chunks")
        if not pdf_chunks:
            print(f"  [warn] {brand}/{pdf_path.name} produced 0 chunks - likely scanned/image-only "
                  f"(no text layer). See README's OCR note.")
        all_chunks.extend(pdf_chunks)
        if progress_callback:
            progress_callback(i, total, f"{brand}/{pdf_path.name}")

    return all_chunks


def list_brand_models(data_dir: Path = DATA_DIR) -> list[tuple[str, str]]:
    result = []
    if not data_dir.exists():
        return result
    for brand_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        for pdf_path in sorted(brand_dir.glob("*.pdf")):
            result.append((brand_dir.name, pdf_path.stem))
    return result


if __name__ == "__main__":
    chunks = parse_all()
    print(f"Parsed {len(chunks)} chunks from {len(list_brand_models())} PDFs.")
    section_counts = {}
    for c in chunks:
        section_counts[c.section] = section_counts.get(c.section, 0) + 1
    print("Section distribution:", section_counts)
    for c in chunks[:5]:
        print(f"[{c.brand}/{c.model} p.{c.page} - {c.section}] {c.text[:80]}...")
