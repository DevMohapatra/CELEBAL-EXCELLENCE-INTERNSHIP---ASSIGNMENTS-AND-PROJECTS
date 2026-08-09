
import json
import uuid
from pathlib import Path

from parser import parse_all, list_brand_models, DATA_DIR

CACHE_PATH = Path(__file__).resolve().parent.parent / "logs" / "chunk_cache.json"


class Chunk:
    def __init__(self, chunk_id, text, brand, model, section, page, doc_version, brochure_name):
        self.chunk_id = chunk_id
        self.text = text
        self.metadata = {
            "brand": brand,
            "model": model,
            "section": section,
            "page": page,
            "document_version": doc_version,
            "brochure_name": brochure_name,
        }

    @property
    def search_text(self) -> str:
        
        section_label = self.metadata["section"].replace("_", " ")
        return f"{self.metadata['brand']} {self.metadata['model']} {section_label}: {self.text}"

    def to_dict(self):
        return {"chunk_id": self.chunk_id, "text": self.text, "metadata": self.metadata}

    def __repr__(self):
        return f"<Chunk {self.metadata['brand']} {self.metadata['model']} / {self.metadata['section']}>"


def _pdf_fingerprint(data_dir: Path = DATA_DIR) -> dict:
    """Maps 'Brand/Model.pdf' -> mtime, used to detect changed/new/removed PDFs."""
    fp = {}
    if not data_dir.exists():
        return fp
    for brand_dir in data_dir.iterdir():
        if not brand_dir.is_dir():
            continue
        for pdf_path in brand_dir.glob("*.pdf"):
            fp[f"{brand_dir.name}/{pdf_path.name}"] = pdf_path.stat().st_mtime_ns
    return fp


def build_chunks(data_dir: Path = DATA_DIR, use_cache: bool = True, force_rebuild: bool = False, progress_callback=None) -> list[Chunk]:
    fingerprint = _pdf_fingerprint(data_dir)

    if use_cache and not force_rebuild and CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text())
            if cached.get("fingerprint") == fingerprint:
                return [
                    Chunk(
                        chunk_id=c["chunk_id"], text=c["text"],
                        brand=c["metadata"]["brand"], model=c["metadata"]["model"],
                        section=c["metadata"]["section"], page=c["metadata"]["page"],
                        doc_version=c["metadata"]["document_version"],
                        brochure_name=c["metadata"]["brochure_name"],
                    )
                    for c in cached["chunks"]
                ]
        except (json.JSONDecodeError, KeyError):
            pass  # fall through to a fresh parse

    parsed = parse_all(data_dir, progress_callback=progress_callback)
    chunks = [
        Chunk(
            chunk_id=str(uuid.uuid4()), text=p.text, brand=p.brand, model=p.model,
            section=p.section, page=p.page, doc_version=p.document_version,
            brochure_name=p.brochure_name,
        )
        for p in parsed
    ]

    if use_cache:
        CACHE_PATH.parent.mkdir(exist_ok=True)
        CACHE_PATH.write_text(json.dumps({
            "fingerprint": fingerprint,
            "chunks": [c.to_dict() for c in chunks],
        }))

    return chunks
def load_chunks_cache_only() -> list[Chunk]:
    if not CACHE_PATH.exists():
        raise FileNotFoundError(
            "No chunk cache found. Run `python src/ingest.py` first to parse the data folder."
        )
    cached = json.loads(CACHE_PATH.read_text())
    return [
        Chunk(
            chunk_id=c["chunk_id"], text=c["text"],
            brand=c["metadata"]["brand"], model=c["metadata"]["model"],
            section=c["metadata"]["section"], page=c["metadata"]["page"],
            doc_version=c["metadata"]["document_version"],
            brochure_name=c["metadata"]["brochure_name"],
        )
        for c in cached["chunks"]
    ]


def brands_models_from_chunks(chunks: list[Chunk]) -> list[tuple]:
    return sorted({(c.metadata["brand"], c.metadata["model"]) for c in chunks})

def available_brands_models(data_dir: Path = DATA_DIR) -> list[tuple]:
    return list_brand_models(data_dir)


if __name__ == "__main__":
    chunks = build_chunks(force_rebuild=True)
    print(f"Built {len(chunks)} chunks from {len(available_brands_models())} car models.")
    for c in chunks[:3]:
        print(c, "->", c.text[:80], "...")
