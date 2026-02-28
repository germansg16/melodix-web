"""
ml/exclusions.py
-----------------
Sistema de exclusiones persistentes por usuario.

Guarda en data/exclusions/<user_id>.json la lista de track IDs
que el usuario no quiere ver, junto con información básica.

Operaciones:
  get_exclusions(user_id)          → set de IDs excluidos
  add_exclusion(user_id, track_id, track_name, artist)
  remove_exclusion(user_id, track_id)
  get_exclusion_list(user_id)      → lista completa con metadatos
"""

import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "exclusions")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _path(user_id: str) -> str:
    # Sanitize user_id para evitar path traversal
    safe_id = "".join(c for c in user_id if c.isalnum() or c in "_-")
    return os.path.join(DATA_DIR, f"{safe_id}.json")


def _load(user_id: str) -> dict:
    path = _path(user_id)
    if not os.path.exists(path):
        return {"exclusions": []}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"exclusions": []}


def _save(user_id: str, data: dict):
    _ensure_dir()
    with open(_path(user_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────

def get_exclusions(user_id: str) -> set:
    """Devuelve el set de track_ids que el usuario no quiere ver."""
    data = _load(user_id)
    return {e["id"] for e in data.get("exclusions", []) if e.get("id")}


def add_exclusion(user_id: str, track_id: str, track_name: str = "", artist: str = ""):
    """Añade un track a las exclusiones del usuario."""
    data  = _load(user_id)
    ids   = {e["id"] for e in data.get("exclusions", [])}
    if track_id in ids:
        return  # Ya está excluido
    data.setdefault("exclusions", []).append({
        "id":         track_id,
        "name":       track_name,
        "artist":     artist,
        "excluded_at": datetime.now().isoformat(),
    })
    _save(user_id, data)


def remove_exclusion(user_id: str, track_id: str):
    """Elimina un track de las exclusiones (deshacer)."""
    data = _load(user_id)
    data["exclusions"] = [
        e for e in data.get("exclusions", []) if e.get("id") != track_id
    ]
    _save(user_id, data)


def get_exclusion_list(user_id: str) -> list:
    """Devuelve la lista completa de exclusiones con metadatos."""
    data = _load(user_id)
    return data.get("exclusions", [])
