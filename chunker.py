def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    chunks = []
    start = 0
    text = text.strip()

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if len(chunk) > 50:
            chunks.append(chunk)
        start += chunk_size - overlap

    return chunks