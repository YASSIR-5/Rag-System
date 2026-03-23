# 🧠 Personal Knowledge Base — RAG System

A fully local, free RAG (Retrieval-Augmented Generation) system with a clean web UI.
Ask questions about your documents and get answers powered by Gemini AI.

---

## ⚡ Quick Start

### 1. Get your Gemini API key
Go to → https://aistudio.google.com/app/apikey
Create a free key (no credit card needed).

### 2. Set up the project

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Add your API key

Copy `.env.example` to `.env` and fill in your key:

```bash
cp .env.example .env
# Then open .env and replace "your_gemini_api_key_here" with your real key
```

### 4. Run

```bash
python app.py
```

Open your browser at → **http://localhost:5000**

---

## 🗂 Supported File Types

| Type | Extension |
|---|---|
| PDF | `.pdf` |
| Plain text | `.txt` |
| Markdown | `.md` |
| Email | `.eml` |
| Web page | `.html` or paste a URL |

---

## 🔍 How to Use

1. **Upload documents** — drag & drop or click "browse" on the left sidebar
2. **Ingest a URL** — paste any web page URL and click →
3. **Ask questions** — type in the chat box and press Enter
4. **Filter by source** — check specific documents on the left to restrict the search
5. **Delete a source** — click ✕ next to any document to remove it

---

## 📁 Project Structure

```
rag-system/
├── app.py              # Flask web server + UI
├── ingest.py           # Document ingestion pipeline
├── query.py            # Query engine (Gemini integration)
├── chunker.py          # Text chunking logic
├── embedder.py         # Sentence-transformers embeddings
├── vector_store.py     # ChromaDB wrapper
├── loaders/
│   ├── pdf_loader.py
│   ├── text_loader.py
│   ├── web_loader.py
│   └── email_loader.py
├── chroma_db/          # Auto-created — your vector database
├── uploads/            # Auto-created — uploaded files
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🧠 How It Works

1. Documents are split into 500-character overlapping chunks
2. Each chunk is converted to a vector using `all-MiniLM-L6-v2` (runs locally, free)
3. Vectors are stored in ChromaDB on disk
4. When you ask a question, it's also converted to a vector
5. The 5 most semantically similar chunks are retrieved
6. Gemini generates an answer **strictly based on those chunks**

---

## 🔑 Notes

- The embedding model (~90MB) downloads automatically on first run
- Your data stays local — only the final question + context goes to Gemini
- ChromaDB persists to `./chroma_db/` — your data survives restarts
- Gemini 1.5 Flash has a generous free tier (15 requests/min, 1500/day)
