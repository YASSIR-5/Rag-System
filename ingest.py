import os
from chunker import chunk_text
from vector_store import VectorStore
from loaders.pdf_loader import load_pdf
from loaders.text_loader import load_text
from loaders.web_loader import load_url
from loaders.email_loader import load_email

store = VectorStore()

LOADERS = {
    ".pdf":  load_pdf,
    ".txt":  load_text,
    ".md":   load_text,
    ".eml":  load_email,
    ".html": load_text,
    ".json": load_text,

}


def ingest_file(path: str) -> int:
    ext = os.path.splitext(path)[1].lower()
    loader = LOADERS.get(ext)
    if not loader:
        raise ValueError(f"Unsupported file type: '{ext}'. Supported: {list(LOADERS.keys())}")

    text = loader(path)
    if not text.strip():
        raise ValueError("Document appears to be empty or unreadable.")

    chunks = chunk_text(text)
    filename = os.path.basename(path)

    chunk_dicts = [
        {
            "text": chunk,
            "metadata": {
                "source": filename,
                "type": ext.lstrip("."),
                "path": path,
            }
        }
        for chunk in chunks
    ]

    store.add_chunks(chunk_dicts)
    return len(chunk_dicts)


def ingest_url(url: str) -> int:
    text = load_url(url)
    if not text.strip():
        raise ValueError("Could not extract content from the URL.")

    chunks = chunk_text(text)

    chunk_dicts = [
        {
            "text": chunk,
            "metadata": {
                "source": url,
                "type": "web",
                "path": url,
            }
        }
        for chunk in chunks
    ]

    store.add_chunks(chunk_dicts)
    return len(chunk_dicts)
