import chromadb
from embedder import Embedder
from rank_bm25 import BM25Okapi
import uuid


class VectorStore:
    _instance = None

    def __new__(cls, persist_path="./chroma_db"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = chromadb.PersistentClient(path=persist_path)
            cls._instance.collection = cls._instance.client.get_or_create_collection(
                name="knowledge_base",
                metadata={"hnsw:space": "cosine"}
            )
            cls._instance.embedder = Embedder()
        return cls._instance

    def add_chunks(self, chunks: list[dict]):
        if not chunks:
            return
        texts = [c["text"] for c in chunks]
        embeddings = self.embedder.embed(texts)
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [c["metadata"] for c in chunks]
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

    def query(self, question: str, n_results: int = 30, filter_sources: list[str] = None):
        total = self.collection.count()
        if total == 0:
            return [], []

        n_results = min(n_results, total)
        embedding = self.embedder.embed([question])

        where = None
        if filter_sources:
            if len(filter_sources) == 1:
                where = {"source": {"$eq": filter_sources[0]}}
            else:
                where = {"source": {"$in": filter_sources}}

        # Step 1: semantic search — get 30 candidates
        results = self.collection.query(
            query_embeddings=embedding,
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        docs = results["documents"][0]
        metas = results["metadatas"][0]

        if not docs:
            return [], []

        # Step 2: BM25 keyword reranking on the 30 candidates
        tokenized = [d.lower().split() for d in docs]
        bm25 = BM25Okapi(tokenized)
        bm25_scores = bm25.get_scores(question.lower().split())

        # Step 3: combine semantic score + BM25 score
        semantic_scores = [1 - d for d in results["distances"][0]]
        combined = [
            (i, 0.6 * semantic_scores[i] + 0.4 * (bm25_scores[i] / (max(bm25_scores) + 1e-9)))
            for i in range(len(docs))
        ]

        # Step 4: take top 10 after reranking
        combined.sort(key=lambda x: x[1], reverse=True)
        top_indices = [i for i, _ in combined[:10]]

        top_docs = [docs[i] for i in top_indices]
        top_metas = [metas[i] for i in top_indices]

        return top_docs, top_metas

    def list_sources(self) -> list[str]:
        results = self.collection.get(include=["metadatas"])
        if not results["metadatas"]:
            return []
        return sorted(list({m["source"] for m in results["metadatas"]}))

    def delete_source(self, source: str):
        results = self.collection.get(where={"source": {"$eq": source}}, include=["metadatas"])
        if results["ids"]:
            self.collection.delete(ids=results["ids"])

    def count(self) -> int:
        return self.collection.count()