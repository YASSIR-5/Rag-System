import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from ingest import ingest_file, ingest_url
from query import ask, list_sessions, delete_session, load_memory
from vector_store import VectorStore
from chunker import chunk_text
from loaders.web_crawler import crawl_site

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
NOTES_FILE = "notes.json"
PROFILE_FILE = "profile.json"
SPACES_FILE = "spaces.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
store = VectorStore()


# ── Helpers ────────────────────────────────────────────────

def load_notes():
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_notes(notes):
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)

def load_profile():
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"name": "Yassir", "location": "Albi, France",
            "bio": "BTS CIEL student & founder of WabiAgency", "goals": "", "context": ""}

def save_profile(profile):
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

def load_spaces():
    if os.path.exists(SPACES_FILE):
        with open(SPACES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_spaces(spaces):
    with open(SPACES_FILE, "w", encoding="utf-8") as f:
        json.dump(spaces, f, indent=2, ensure_ascii=False)


# ── Routes ─────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ingest/file", methods=["POST"])
def ingest_file_route():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    try:
        count = ingest_file(path)
        return jsonify({"message": f"'{file.filename}' ingested — {count} chunks added."})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/ingest/url", methods=["POST"])
def ingest_url_route():
    url = request.json.get("url", "").strip()
    crawl = request.json.get("crawl", False)
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        if crawl:
            pages = crawl_site(url, max_pages=50)
            total_chunks = 0
            for page in pages:
                chunks = chunk_text(page["text"])
                store.add_chunks([{
                    "text": c,
                    "metadata": {"source": page["url"], "type": "web", "path": page["url"]}
                } for c in chunks])
                total_chunks += len(chunks)
            return jsonify({"message": f"Crawled {len(pages)} pages — {total_chunks} chunks added."})
        else:
            count = ingest_url(url)
            return jsonify({"message": f"URL ingested — {count} chunks added."})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/query", methods=["POST"])
def query_route():
    data = request.json
    question = data.get("question", "").strip()
    sources = data.get("sources") or None
    session_id = data.get("session_id", "main")
    if not question:
        return jsonify({"error": "No question provided"}), 400
    try:
        result = ask(question, filter_sources=sources, session_id=session_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "answer": f"Error: {str(e)}", "sources": [], "chunks_used": []}), 500


@app.route("/sources")
def sources_route():
    return jsonify({"sources": store.list_sources()})


@app.route("/delete", methods=["POST"])
def delete_route():
    source = request.json.get("source", "").strip()
    store.delete_source(source)
    return jsonify({"message": "Deleted."})


@app.route("/stats")
def stats_route():
    return jsonify({"chunks": store.count()})


@app.route("/sessions")
def sessions_route():
    return jsonify({"sessions": list_sessions()})


@app.route("/sessions/<session_id>", methods=["DELETE"])
def delete_session_route(session_id):
    delete_session(session_id)
    return jsonify({"message": "Deleted."})


@app.route("/session/<session_id>")
def get_session_route(session_id):
    memory = load_memory()
    messages = memory["sessions"].get(session_id, [])
    return jsonify({"messages": messages})


@app.route("/notes", methods=["GET"])
def get_notes():
    return jsonify({"notes": load_notes()})


@app.route("/notes", methods=["POST"])
def add_note():
    data = request.json
    text = data.get("text", "").strip()
    tag = data.get("tag", "general")
    if not text:
        return jsonify({"error": "Empty note"}), 400
    notes = load_notes()
    note = {"id": str(uuid.uuid4()), "text": text, "tag": tag, "created": datetime.now().isoformat()}
    notes.append(note)
    save_notes(notes)
    store.add_chunks([{"text": f"[Note - {tag}] {text}",
                       "metadata": {"source": f"note:{note['id']}", "type": "note", "path": "notes"}}])
    return jsonify({"message": "Note saved.", "note": note})


@app.route("/notes/<note_id>", methods=["DELETE"])
def delete_note_route(note_id):
    notes = [n for n in load_notes() if n["id"] != note_id]
    save_notes(notes)
    store.delete_source(f"note:{note_id}")
    return jsonify({"message": "Deleted."})


@app.route("/profile", methods=["GET"])
def get_profile():
    return jsonify(load_profile())


@app.route("/profile", methods=["POST"])
def set_profile():
    save_profile(request.json)
    return jsonify({"message": "Profile saved."})


@app.route("/spaces", methods=["GET"])
def get_spaces():
    return jsonify({"spaces": load_spaces()})


@app.route("/spaces", methods=["POST"])
def create_space():
    data = request.json
    spaces = load_spaces()
    space = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", "New Space"),
        "icon": data.get("icon", "◈"),
        "color": data.get("color", "#929876"),
        "description": data.get("description", ""),
        "pinned": data.get("pinned", True),
        "created": datetime.now().isoformat()
    }
    spaces.append(space)
    save_spaces(spaces)
    return jsonify({"message": "Space created.", "space": space})


@app.route("/spaces/<space_id>", methods=["PUT"])
def update_space(space_id):
    spaces = load_spaces()
    data = request.json
    for s in spaces:
        if s["id"] == space_id:
            s.update({k: v for k, v in data.items() if k != "id"})
            break
    save_spaces(spaces)
    return jsonify({"message": "Space updated."})


@app.route("/spaces/<space_id>", methods=["DELETE"])
def delete_space(space_id):
    spaces = [s for s in load_spaces() if s["id"] != space_id]
    save_spaces(spaces)
    return jsonify({"message": "Space deleted."})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
