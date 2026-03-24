import os
import json
from datetime import datetime
from groq import Groq
from vector_store import VectorStore
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
store = VectorStore()

MEMORY_FILE = "memory.json"
MAX_HISTORY = 20


def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"sessions": {}}


def save_memory(memory: dict):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)


def get_or_create_session(session_id: str) -> list:
    memory = load_memory()
    if session_id not in memory["sessions"]:
        memory["sessions"][session_id] = []
        save_memory(memory)
    return memory["sessions"][session_id]


def append_to_session(session_id: str, role: str, content: str):
    memory = load_memory()
    if session_id not in memory["sessions"]:
        memory["sessions"][session_id] = []
    memory["sessions"][session_id].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    memory["sessions"][session_id] = memory["sessions"][session_id][-MAX_HISTORY:]
    save_memory(memory)
    if role == "assistant":
        store.add_chunks([{
            "text": content,
            "metadata": {
                "source": f"memory:{session_id}",
                "type": "memory",
                "path": "memory"
            }
        }])


def list_sessions() -> list:
    memory = load_memory()
    sessions = []
    for sid, messages in memory["sessions"].items():
        sessions.append({
            "id": sid,
            "message_count": len(messages),
            "last_active": messages[-1]["timestamp"] if messages else None
        })
    return sorted(sessions, key=lambda x: x["last_active"] or "", reverse=True)


def delete_session(session_id: str):
    memory = load_memory()
    memory["sessions"].pop(session_id, None)
    save_memory(memory)


def load_profile_context() -> str:
    profile_file = "profile.json"
    if not os.path.exists(profile_file):
        return "No profile set yet."
    with open(profile_file, "r", encoding="utf-8") as f:
        p = json.load(f)
    parts = []
    if p.get("name"):     parts.append(f"Name: {p['name']}")
    if p.get("location"): parts.append(f"Location: {p['location']}")
    if p.get("bio"):      parts.append(f"Bio: {p['bio']}")
    if p.get("goals"):    parts.append(f"Goals: {p['goals']}")
    if p.get("context"):  parts.append(f"Context: {p['context']}")
    return "\n".join(parts) if parts else "No profile set yet."


def load_notes_context() -> str:
    notes_file = "notes.json"
    if not os.path.exists(notes_file):
        return ""
    with open(notes_file, "r", encoding="utf-8") as f:
        notes = json.load(f)
    if not notes:
        return ""
    notes_sorted = sorted(notes, key=lambda x: x.get("created", ""), reverse=True)
    lines = ["SAVED NOTES (most recent first):"]
    for n in notes_sorted[:20]:
        date = n.get("created", "")[:10]
        lines.append(f"[{date}] [{n.get('tag', 'general')}] {n['text']}")
    return "\n".join(lines)


def get_model() -> str:
    if os.path.exists("model_pref.txt"):
        return open("model_pref.txt").read().strip()
    return "llama-3.3-70b-versatile"


def ask(question: str, filter_sources: list = None, session_id: str = "main", space_prompt: str = "") -> dict:
    chunks, metadatas = store.query(
        question=question,
        n_results=20,
        filter_sources=filter_sources
    )

    if not chunks:
        return {
            "answer": "No relevant documents found. Please ingest some documents first.",
            "sources": [],
            "chunks_used": []
        }

    context = "\n\n---\n\n".join(chunks)
    history = get_or_create_session(session_id)
    profile_context = load_profile_context()
    notes_context = load_notes_context()
    today = datetime.now().strftime("%A, %B %d, %Y — %H:%M")

    space_section = f"\nSPACE PERSONALITY & INSTRUCTIONS:\n{space_prompt}\n" if space_prompt else ""

    system_prompt = f"""You are Yassir's personal AI second brain. You know everything about him.

CURRENT DATE & TIME: {today}

WHO YOU ARE TALKING TO:
{profile_context}
{space_section}
{notes_context}

RULES:
- Always use the profile above to personalize your answers.
- Be thorough. If asked for ALL details, find and list ALL of them.
- Use the context AND conversation history to give complete answers.
- Structure complex answers with headers and bullet points.
- If some info is present but incomplete, say what you found and flag what is missing.
- Only say "not found" if truly absent from context.
- Never use outside knowledge — only what is in the context and the profile above.
- When referencing info, mention which document it came from.
- CRITICAL: Answer the SPECIFIC question asked. Do not dump all available information.
- Never say "some details are incomplete" — either find it or explicitly state it is not in any document.
- When answering about lists or themes, always include ALL items, do not skip any.

CONTEXT FROM KNOWLEDGE BASE:
{context}"""

    messages = [{"role": "system", "content": system_prompt}]

    for msg in history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": question})

    try:
        response = client.chat.completions.create(
            model=get_model(),
            messages=messages,
            max_tokens=2048,
        )
        answer = response.choices[0].message.content
    except Exception as e:
        answer = f"Error generating answer: {str(e)}"

    append_to_session(session_id, "user", question)
    append_to_session(session_id, "assistant", answer)

    sources = list({m["source"] for m in metadatas})

    return {
        "answer": answer,
        "sources": sources,
        "chunks_used": chunks
    }
