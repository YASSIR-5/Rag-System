import os
import json
import zipfile
import csv
import io
from chunker import chunk_text
from vector_store import VectorStore
from loaders.pdf_loader import load_pdf
from loaders.text_loader import load_text
from loaders.web_loader import load_url
from loaders.email_loader import load_email

store = VectorStore()


def load_json(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        data = json.load(f)
    return json_to_text(data)


def json_to_text(data, indent=0) -> str:
    text = ""
    if isinstance(data, dict):
        for k, v in data.items():
            text += "  " * indent + f"{k}: "
            if isinstance(v, (dict, list)):
                text += "\n" + json_to_text(v, indent + 1)
            else:
                text += str(v) + "\n"
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                text += json_to_text(item, indent)
            else:
                text += "  " * indent + str(item) + "\n"
    else:
        text += str(data) + "\n"
    return text


def load_csv(path: str) -> str:
    rows = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(", ".join(row))
    return "\n".join(rows)


def load_image_text(path: str) -> str:
    # Images can't be read as text — return metadata only
    filename = os.path.basename(path)
    size = os.path.getsize(path)
    return f"[Image file: {filename}, size: {size} bytes. Visual content not extractable without OCR.]"


LOADERS = {
    # Documents
    ".pdf":  load_pdf,
    ".txt":  load_text,
    ".md":   load_text,
    ".rst":  load_text,
    ".eml":  load_email,
    ".html": load_text,
    ".htm":  load_text,
    ".xml":  load_text,
    # Data
    ".json": load_json,
    ".csv":  load_csv,
    ".tsv":  load_csv,
    # Code (treated as plain text)
    ".py":   load_text,
    ".js":   load_text,
    ".ts":   load_text,
    ".css":  load_text,
    ".sql":  load_text,
    ".sh":   load_text,
    ".yaml": load_text,
    ".yml":  load_text,
    ".toml": load_text,
    ".ini":  load_text,
    ".env":  load_text,
    # Images (metadata only — no OCR)
    ".jpg":  load_image_text,
    ".jpeg": load_image_text,
    ".png":  load_image_text,
    ".gif":  load_image_text,
    ".webp": load_image_text,
}


def ingest_file(path: str) -> int:
    ext = os.path.splitext(path)[1].lower()

    # Handle ZIP — extract and ingest each file inside
    if ext == ".zip":
        return ingest_zip(path)

    loader = LOADERS.get(ext)
    if not loader:
        raise ValueError(f"Unsupported file type: '{ext}'. Supported: {sorted(LOADERS.keys())} + .zip")

    text = loader(path)
    if not text or not text.strip():
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


def ingest_zip(path: str) -> int:
    total = 0
    filename = os.path.basename(path)
    extract_dir = path + "_extracted"
    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(path, "r") as zf:
        zf.extractall(extract_dir)

    for root, dirs, files in os.walk(extract_dir):
        # Skip hidden/system folders
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__MACOSX']
        for fname in files:
            if fname.startswith('.'):
                continue
            fpath = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            loader = LOADERS.get(ext)
            if not loader:
                continue
            try:
                text = loader(fpath)
                if not text or not text.strip():
                    continue
                chunks = chunk_text(text)
                rel_path = os.path.relpath(fpath, extract_dir)
                source_name = f"{filename}/{rel_path}".replace("\\", "/")
                store.add_chunks([
                    {
                        "text": chunk,
                        "metadata": {
                            "source": source_name,
                            "type": ext.lstrip("."),
                            "path": fpath,
                        }
                    }
                    for chunk in chunks
                ])
                total += len(chunks)
            except Exception:
                continue

    return total


def ingest_url(url: str) -> int:
    text = load_url(url)
    if not text.strip():
        raise ValueError("Could not extract content from the URL.")

    chunks = chunk_text(text)

    store.add_chunks([
        {
            "text": chunk,
            "metadata": {
                "source": url,
                "type": "web",
                "path": url,
            }
        }
        for chunk in chunks
    ])
    return len(chunks)
