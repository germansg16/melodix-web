"""
ml/recommender.py
-----------------
Motor de recomendaciones inteligente de Melodix.

ESTRATEGIA PRINCIPAL: Búsqueda por ARTISTAS del usuario + mood keywords.
  → `artist:"Yung Beef" triste` encuentra canciones tristes de Yung Beef
  → `artist:"Mda" fiesta` encuentra sus canciones de fiesta
  → Mucho más preciso que genre+keyword que no filtra semánticamente

También añade offset aleatorio para variar resultados en cada llamada.
"""

import random
import spotipy

# ─────────────────────────────────────────────────────────────
# KEYWORDS POR MOOD
# ─────────────────────────────────────────────────────────────

MOOD_KEYWORDS = {
    "default":    [],
    "fiesta":     ["fiesta", "party", "beber", "noche"],
    "emocional":  ["triste", "sad", "llorar", "dolor", "solo", "lento"],
    "bailar":     ["baile", "pista", "perrear", "twerk", "boogaloo"],
    "relajado":   ["chill", "tranquilo", "relax", "slow"],
    "amigos":     ["amigos", "friends", "squad", "crew"],
    "verano":     ["verano", "playa", "summer", "sol", "calor"],
    "tendencias": ["2024", "2025", "new", "nuevo"],
    "artista":    [],   # se maneja como caso especial
    "custom":     [],   # búsqueda libre
}

MOOD_LABELS = {
    "default":    ("🎵", "Para ti"),
    "fiesta":     ("🎉", "Fiesta"),
    "emocional":  ("😢", "Emocional"),
    "bailar":     ("🕺", "Pa' bailar"),
    "relajado":   ("😌", "Relajado"),
    "amigos":     ("👯", "Con amigos"),
    "verano":     ("☀️", "Verano"),
    "tendencias": ("🔥", "Tendencias"),
    "artista":    ("🎤", "Por artista"),
    "custom":     ("🔍", "Búsqueda"),
}


# ─────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────

def _known_ids(top_tracks: list, recent_tracks: list) -> set:
    ids = set()
    for t in top_tracks:
        if t.get("id"): ids.add(t["id"])
    for t in recent_tracks:
        if t.get("id"): ids.add(t["id"])
    return ids


def _top_genres(top_artists: list, n: int = 4) -> list:
    counts: dict[str, int] = {}
    for a in top_artists:
        for g in a.get("genres", []):
            counts[g] = counts.get(g, 0) + 1
    return sorted(counts, key=counts.get, reverse=True)[:n]


def _top_artist_names(top_artists: list, n: int = 5) -> list:
    return [a["name"] for a in top_artists[:n] if a.get("name")]


def _recent_artist_names(recent_tracks: list, n: int = 3) -> list:
    seen, names = set(), []
    for t in recent_tracks:
        name = t.get("artist", "")
        if name and name not in seen:
            seen.add(name)
            names.append(name)
        if len(names) >= n:
            break
    return names


def _format_track(track: dict, explanation: str) -> dict:
    album   = track.get("album", {})
    artists = track.get("artists", [{}])
    return {
        "id":          track.get("id"),
        "name":        track.get("name", ""),
        "artist":      artists[0].get("name", "") if artists else "",
        "album":       album.get("name", ""),
        "image":       album["images"][0]["url"] if album.get("images") else None,
        "preview_url": track.get("preview_url"),
        "spotify_url": track.get("external_urls", {}).get("spotify"),
        "popularity":  track.get("popularity", 0),
        "explanation": explanation,
    }


def _search(sp, query: str, known: set, seen: set, limit: int = 8, offset: int = 0) -> list:
    """Ejecuta una búsqueda y devuelve tracks filtrados."""
    try:
        res = sp.search(q=query, type="track", limit=limit, offset=offset)
        tracks = res.get("tracks", {}).get("items", [])
    except Exception:
        return []

    out = []
    for t in tracks:
        tid = t.get("id")
        if not tid or tid in known or tid in seen:
            continue
        seen.add(tid)
        out.append(t)
    return out


# ─────────────────────────────────────────────────────────────
# MOTOR PRINCIPAL
# ─────────────────────────────────────────────────────────────

def get_smart_recommendations(
    sp: spotipy.Spotify,
    top_artists: list,
    top_tracks: list,
    recent_tracks: list,
    mood: str = "default",
    custom_query: str = "",
    limit: int = 20,
) -> list:
    """
    Genera recomendaciones personalizadas ajustadas al mood elegido.

    Estrategia por prioridad:
      1. Artistas del usuario + keyword del mood  (principal)
      2. Géneros del usuario + keyword del mood   (complementario)
      3. Historial reciente como semilla          (solo en modo default)
    """
    known    = _known_ids(top_tracks, recent_tracks)
    seen     = set()
    results  = []

    # Offset aleatorio para variar resultados entre llamadas
    base_offset = random.randint(0, 15)

    # ── Modo artista específico ──────────────────────────────
    if mood == "artista" and custom_query:
        tracks_raw = _search(sp, f'artist:"{custom_query.strip()}"', set(), seen, limit=limit, offset=0)
        for t in tracks_raw:
            results.append(_format_track(t, f"De {custom_query}"))
        return sorted(results, key=lambda x: x["popularity"], reverse=True)[:limit]

    # ── Modo búsqueda libre ──────────────────────────────────
    if mood == "custom" and custom_query:
        tracks_raw = _search(sp, custom_query.strip(), known, seen, limit=limit, offset=0)
        for t in tracks_raw:
            results.append(_format_track(t, f'Búsqueda: "{custom_query}"'))
        return sorted(results, key=lambda x: x["popularity"], reverse=True)[:limit]

    # ── Configuración del mood ───────────────────────────────
    keywords = MOOD_KEYWORDS.get(mood, [])
    label_emoji, label_text = MOOD_LABELS.get(mood, ("🎵", mood))

    artist_names = _top_artist_names(top_artists, n=5)
    genres       = _top_genres(top_artists, n=4)

    # ── Paso 1: artista del usuario + keyword mood ───────────
    # Esta es la clave — busca dentro del universo musical del usuario
    if keywords:
        # Mezclar artistas para no siempre mostrar el mismo primero
        artists_shuffled = artist_names.copy()
        random.shuffle(artists_shuffled)

        for artist in artists_shuffled:
            if len(results) >= limit:
                break
            # Probar cada keyword con el artista
            kw = random.choice(keywords)
            query = f'artist:"{artist}" {kw}'
            raw = _search(sp, query, known, seen, limit=6, offset=base_offset)
            for t in raw:
                results.append(_format_track(t, f"{artist} · {label_text}"))

    # ── Paso 2: género del usuario + keyword mood ────────────
    if len(results) < limit and keywords:
        genres_shuffled = genres.copy()
        random.shuffle(genres_shuffled)
        for genre in genres_shuffled:
            if len(results) >= limit:
                break
            kw = random.choice(keywords)
            raw = _search(sp, f'genre:"{genre}" {kw}', known, seen, limit=6, offset=base_offset)
            for t in raw:
                results.append(_format_track(t, f"{genre} · {label_text}"))

    # ── Paso 3: sólo géneros (sin keyword) como relleno ─────
    if len(results) < limit:
        genres_shuffled = genres.copy()
        random.shuffle(genres_shuffled)
        for genre in genres_shuffled:
            if len(results) >= limit:
                break
            raw = _search(sp, f'genre:"{genre}"', known, seen, limit=6, offset=base_offset)
            for t in raw:
                results.append(_format_track(t, f"Basado en {genre}"))

    # ── Paso 4 (default): historial reciente ─────────────────
    if mood == "default" and len(results) < limit:
        recent_artists = _recent_artist_names(recent_tracks, n=3)
        random.shuffle(recent_artists)
        for artist in recent_artists:
            if len(results) >= limit:
                break
            if artist in artist_names:
                continue  # ya lo usamos arriba
            raw = _search(sp, f'artist:"{artist}"', known, seen, limit=5, offset=base_offset)
            for t in raw:
                results.append(_format_track(t, f"Similar a {artist}"))

    # ── Fallback: artistas directamente ─────────────────────
    if len(results) < 8:
        for artist in artist_names[:3]:
            if len(results) >= limit:
                break
            raw = _search(sp, f'artist:"{artist}"', known, seen, limit=5, offset=base_offset)
            for t in raw:
                results.append(_format_track(t, f"Más de {artist}"))

    # ── Resultado final ──────────────────────────────────────
    # Mezclamos un poco para no ordenar solo por popularidad (más variedad)
    results.sort(key=lambda x: x["popularity"] + random.randint(-5, 5), reverse=True)
    return results[:limit]


# ─────────────────────────────────────────────────────────────
# DESCRIPCIÓN DEL PERFIL
# ─────────────────────────────────────────────────────────────

def describe_profile(top_artists: list, top_tracks: list) -> str:
    if not top_artists:
        return "Perfil musical en construcción"

    counts: dict[str, int] = {}
    for a in top_artists:
        for g in a.get("genres", []):
            counts[g] = counts.get(g, 0) + 1

    top_genres   = sorted(counts, key=counts.get, reverse=True)[:2]
    artist_names = [a["name"] for a in top_artists[:2] if a.get("name")]

    parts = []
    if artist_names:
        parts.append(f"Fan de {', '.join(artist_names)}")
    if top_genres:
        parts.append(" · ".join(top_genres))
    return " · ".join(parts) if parts else "Perfil musical variado"


def get_mood_list() -> list:
    return [
        {"id": mid, "emoji": MOOD_LABELS[mid][0], "label": MOOD_LABELS[mid][1]}
        for mid in MOOD_LABELS
    ]
