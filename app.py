import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from ingest import ingest_file, ingest_url
from query import ask, list_sessions, delete_session, load_memory, save_memory
from vector_store import VectorStore
from chunker import chunk_text
from loaders.web_crawler import crawl_site

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
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
            spaces = json.load(f)
        # Migration: add threads/prompt fields if missing
        changed = False
        for s in spaces:
            if "threads" not in s:
                s["threads"] = []
                changed = True
            if "prompt" not in s:
                s["prompt"] = ""
                changed = True
            # Migrate existing space session to a General thread
            old_session = f"space-{s['id']}"
            memory = load_memory()
            if old_session in memory["sessions"] and len(memory["sessions"][old_session]) > 0:
                already_migrated = any(t.get("migrated") for t in s["threads"])
                if not already_migrated:
                    thread_id = str(uuid.uuid4())
                    thread_session = f"thread-{thread_id}"
                    memory["sessions"][thread_session] = memory["sessions"][old_session]
                    save_memory(memory)
                    s["threads"].append({
                        "id": thread_id,
                        "name": "General",
                        "summary": "Migrated from previous space chat.",
                        "created": datetime.now().isoformat(),
                        "last_active": datetime.now().isoformat(),
                        "message_count": len(memory["sessions"][thread_session]),
                        "migrated": True
                    })
                    changed = True
        if changed:
            save_spaces(spaces)
        return spaces
    return []

def save_spaces(spaces):
    with open(SPACES_FILE, "w", encoding="utf-8") as f:
        json.dump(spaces, f, indent=2, ensure_ascii=False)

def get_space(space_id):
    for s in load_spaces():
        if s["id"] == space_id:
            return s
    return None


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

@app.route("/ingest/folder", methods=["POST"])
def ingest_folder_route():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided"}), 400
    total_chunks = 0
    results = []
    for file in files:
        path = os.path.join(UPLOAD_FOLDER, file.filename.replace("/", "_").replace("\\", "_"))
        file.save(path)
        try:
            count = ingest_file(path)
            total_chunks += count
            results.append({"file": file.filename, "chunks": count})
        except Exception as e:
            results.append({"file": file.filename, "error": str(e)})
    return jsonify({"message": f"{len(files)} files processed — {total_chunks} total chunks added.", "results": results})


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
    space_prompt = data.get("space_prompt", "")
    if not question:
        return jsonify({"error": "No question provided"}), 400
    try:
        result = ask(question, filter_sources=sources, session_id=session_id, space_prompt=space_prompt)
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


# ── Spaces ─────────────────────────────────────────────────

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
        "prompt": data.get("prompt", ""),
        "default_sources": data.get("default_sources", []),
        "pinned": data.get("pinned", True),
        "threads": [],
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
            s.update({k: v for k, v in data.items() if k not in ["id", "threads"]})
            break
    save_spaces(spaces)
    return jsonify({"message": "Space updated."})



@app.route("/spaces/<space_id>", methods=["DELETE"])
def delete_space_route(space_id):
    spaces = [s for s in load_spaces() if s["id"] != space_id]
    save_spaces(spaces)
    return jsonify({"message": "Space deleted."})


# ── Threads ─────────────────────────────────────────────────

@app.route("/spaces/<space_id>/threads", methods=["GET"])
def get_threads(space_id):
    space = get_space(space_id)
    if not space:
        return jsonify({"error": "Space not found"}), 404
    return jsonify({"threads": space.get("threads", [])})


@app.route("/spaces/<space_id>/threads", methods=["POST"])
def create_thread(space_id):
    spaces = load_spaces()
    data = request.json
    thread = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", "New Thread"),
        "summary": "",
        "created": datetime.now().isoformat(),
        "last_active": datetime.now().isoformat(),
        "message_count": 0
    }
    for s in spaces:
        if s["id"] == space_id:
            if "threads" not in s:
                s["threads"] = []
            s["threads"].append(thread)
            break
    save_spaces(spaces)
    return jsonify({"message": "Thread created.", "thread": thread})


@app.route("/spaces/<space_id>/threads/<thread_id>", methods=["DELETE"])
def delete_thread(space_id, thread_id):
    spaces = load_spaces()
    for s in spaces:
        if s["id"] == space_id:
            s["threads"] = [t for t in s.get("threads", []) if t["id"] != thread_id]
            break
    save_spaces(spaces)
    # Also delete thread session from memory
    delete_session(f"thread-{thread_id}")
    return jsonify({"message": "Thread deleted."})


@app.route("/spaces/<space_id>/threads/<thread_id>/summary", methods=["POST"])
def update_thread_summary(space_id, thread_id):
    """Generate and save a summary for a thread."""
    spaces = load_spaces()
    space = next((s for s in spaces if s["id"] == space_id), None)
    if not space:
        return jsonify({"error": "Space not found"}), 404

    thread = next((t for t in space.get("threads", []) if t["id"] == thread_id), None)
    if not thread:
        return jsonify({"error": "Thread not found"}), 404

    # Get thread messages
    memory = load_memory()
    session_id = f"thread-{thread_id}"
    messages = memory["sessions"].get(session_id, [])
    if not messages:
        return jsonify({"summary": ""})

    # Build conversation text for summarization
    convo = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages[-20:]])
    summary_question = f"Summarize this conversation in 1-2 sentences, focus on key facts and decisions:\n\n{convo}"

    try:
        result = ask(summary_question, session_id="summary-temp")
        summary = result["answer"][:200]  # keep it short
    except Exception as e:
        summary = "Summary unavailable."

    # Save summary and update thread metadata
    for s in spaces:
        if s["id"] == space_id:
            for t in s.get("threads", []):
                if t["id"] == thread_id:
                    t["summary"] = summary
                    t["message_count"] = len(messages)
                    t["last_active"] = messages[-1].get("timestamp", datetime.now().isoformat())
                    break
            break
    save_spaces(spaces)

    return jsonify({"summary": summary})


@app.route("/spaces/<space_id>/threads/<thread_id>/activity", methods=["POST"])
def update_thread_activity(space_id, thread_id):
    """Update thread message count and last active time."""
    spaces = load_spaces()
    data = request.json
    for s in spaces:
        if s["id"] == space_id:
            for t in s.get("threads", []):
                if t["id"] == thread_id:
                    t["message_count"] = data.get("message_count", t.get("message_count", 0))
                    t["last_active"] = datetime.now().isoformat()
                    break
            break
    save_spaces(spaces)
    return jsonify({"message": "Updated."})


@app.route("/model", methods=["POST"])
def set_model():
    model = request.json.get("model", "llama-3.3-70b-versatile")
    open("model_pref.txt", "w").write(model)
    return jsonify({"message": "Model updated."})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
