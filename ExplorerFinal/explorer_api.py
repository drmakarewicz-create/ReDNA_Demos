import os, requests

CORE = os.getenv("CORE_URL",  "http://127.0.0.1:8015").rstrip("/")
UCNRR = os.getenv("UCNRR_URL", "http://127.0.0.1:8011").rstrip("/")

def ucnrr_init_user(user_id: str) -> dict:
    r = requests.post(f"{UCNRR}/users/init", json={"username": user_id}, timeout=8)
    r.raise_for_status()
    return r.json()

def ucnrr_ingest_text(user_id: str, text: str) -> dict:
    r = requests.post(f"{UCNRR}/ingest_text", json={"user_id": user_id, "text": text}, timeout=20)
    r.raise_for_status()
    return r.json()

def core_nudge(user_id: str) -> dict:
    # tolerant; ok if UCN/RR already pushed
    r = requests.post(f"{CORE}/ingest_from_ucnrr", json={"user_id": user_id}, timeout=10)
    r.raise_for_status()
    return r.json()

def core_get_resolved(user_id: str) -> dict:
    r = requests.get(f"{CORE}/resolved/{user_id}", timeout=8)
    r.raise_for_status()
    return r.json()