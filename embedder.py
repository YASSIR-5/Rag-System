from sentence_transformers import SentenceTransformer

class Embedder:
    _instance = None

    def __new__(cls):
        # Singleton so model loads only once
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.model = SentenceTransformer("all-MiniLM-L6-v2")
        return cls._instance

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, show_progress_bar=False).tolist()
