import json
import os

PROFILE_FILE = "profile.json"

def load_profile_context() -> str:
    if not os.path.exists(PROFILE_FILE):
        return "No profile set yet."
    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        p = json.load(f)
    parts = []
    if p.get("name"):       parts.append(f"Name: {p['name']}")
    if p.get("location"):   parts.append(f"Location: {p['location']}")
    if p.get("bio"):        parts.append(f"Bio: {p['bio']}")
    if p.get("goals"):      parts.append(f"Goals: {p['goals']}")
    if p.get("context"):    parts.append(f"Context: {p['context']}")
    return "\n".join(parts) if parts else "No profile set yet."