"""
ml/recommender.py
-----------------
Motor de recomendaciones inteligente de Melodix.

Totalmente personalizado: los géneros del usuario son always la base.
El mood solo ajusta el contexto — no cambia el perfil musical.

Soporta los moods:
  default   → Basado en tus géneros + historial reciente
  fiesta    → Tus géneros + vibe festivo
  emocional → Tus géneros + canciones lentas/emocionales
  bailar    → Tus géneros + más energético
  relajado  → Tus géneros + chill / acústico
  amigos    → Tus géneros + good vibes
  verano    → Tus géneros + playa / verano
  tendencias→ Tus géneros + lanzamientos recientes
  artista   → Artista específico (query libre)
  custom    → Búsqueda libre del usuario
"""

import spotipy

# ─────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE MOODS
# ─────────────────────────────────────────────────────────────

MOOD_CONFIG = {
    "default": {
        "label": "Para ti",
        "emoji": "🎵",
        "extra_terms": [],           # Sin modificación, máxima personalización
        "use_recent": True,          # Usa historial reciente para ajustar
    },
    "fiesta": {
        "label": "Fiesta",
        "emoji": "🎉",
        "extra_terms": ["party", "fiesta"],
        "use_recent": False,
    },
    "emocional": {
        "label": "Emocional",
        "emoji": "😢",
        "extra_terms": ["sad", "emotional", "triste"],
        "use_recent": False,
    },
    "bailar": {
        "label": "Pa' bailar",
        "emoji": "🕺",
        "extra_terms": ["dance", "bailar"],
        "use_recent": False,
    },
    "relajado": {
        "label": "Relajado",
        "emoji": "😌",
        "extra_terms": ["chill", "relax", "tranquilo"],
        "use_recent": False,
    },
    "amigos": {
        "label": "Con amigos",
        "emoji": "👯",
        "extra_terms": ["good vibes", "fun"],
        "use_recent": False,
    },
    "verano": {
        "label": "Verano",
        "emoji": "☀️",
        "extra_terms": ["verano", "summer", "playa"],
        "use_recent": False,
    },
    "tendencias": {
        "label": "Tendencias",
        "emoji": "🔥",
        "extra_terms": ["new", "2024", "2025"],
        "use_recent": False,
    },
    "artista": {
        "label": "Por artista",
        "emoji": "🎤",
        "extra_terms": [],
        "use_recent": False,
        "artist_mode": True,         # Usa query directamente como artista
    },
    "custom": {
        "label": "Búsqueda",
        "emoji": "🔍",
        "extra_terms": [],
        "use_recent": False,
        "free_search": True,         # Búsqueda completamente libre
    },
}


# ─────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────

def _extract_user_genres(top_artists: list, max_genres: int = 5) -> list[str]:
    """
    Extrae los géneros principales del usuario de sus top artists.
    Devuelve los más frecuentes primero.
    """
    genre_count: dict[str, int] = {}
    for artist in top_artists:
        for genre in artist.get("genres", []):
            genre_count[genre] = genre_count.get(genre, 0) + 1

    return sorted(genre_count, key=genre_count.get, reverse=True)[:max_genres]


def _extract_known_ids(top_tracks: list, recent_tracks: list) -> set[str]:
    """IDs de canciones que el usuario ya conoce (no recomendar estas)."""
    ids = set()
    for t in top_tracks:
        if t.get("id"):
            ids.add(t["id"])
    for t in recent_tracks:
        if t.get("id"):
            ids.add(t["id"])
    return ids


def _extract_recent_genres(recent_tracks: list) -> list[str]:
    """
    Detecta los géneros del historial reciente del usuario
    para tender hacia lo que está escuchando ahora.
    """
    # El historial reciente contiene info del artista, pero no géneros directamente.
    # Usamos los nombres de artistas para contexto.
    artists = []
    for t in recent_tracks:
        artist = t.get("artist", "")
        if artist and artist not in artists:
            artists.append(artist)
    return artists[:3]


def _search_tracks(
    sp: spotipy.Spotify,
    query: str,
    known_ids: set[str],
    seen_ids: set[str],
    limit: int = 10,
) -> list[dict]:
    """
    Ejecuta una búsqueda y devuelve tracks no conocidos por el usuario.
    """
    try:
        results = sp.search(q=query, type="track", limit=limit)
        tracks = results.get("tracks", {}).get("items", [])
    except Exception:
        return []

    out = []
    for track in tracks:
        tid = track.get("id")
        if not tid or tid in known_ids or tid in seen_ids:
            continue
        seen_ids.add(tid)
        album   = track.get("album", {})
        artists = track.get("artists", [{}])
        out.append({
            "id": tid,
            "name": track.get("name", ""),
            "artist": artists[0].get("name", "") if artists else "",
            "album": album.get("name", ""),
            "image": album["images"][0]["url"] if album.get("images") else None,
            "preview_url": track.get("preview_url"),
            "spotify_url": track.get("external_urls", {}).get("spotify"),
            "popularity": track.get("popularity", 0),
        })
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
) -> list[dict]:
    """
    Genera recomendaciones personalizadas para el usuario.

    La base siempre son los géneros reales del usuario.
    El mood ajusta el contexto (festivo, relajado, etc.) sin perder
    la esencia del perfil musical.

    Args:
        sp: cliente Spotify autenticado
        top_artists: lista de artistas favoritos del usuario
        top_tracks: lista de canciones favoritas del usuario
        recent_tracks: historial reciente (últimas 20 canciones)
        mood: uno de los moods definidos en MOOD_CONFIG
        custom_query: texto libre para modos artista/custom
        limit: número máximo de resultados

    Returns:
        Lista de dicts con info de la canción + explanation
    """
    config     = MOOD_CONFIG.get(mood, MOOD_CONFIG["default"])
    known_ids  = _extract_known_ids(top_tracks, recent_tracks)
    seen_ids   = set()
    results    = []

    # ── Modo artista específico ──────────────────────────────
    if config.get("artist_mode") and custom_query:
        artist_name = custom_query.strip()
        tracks = _search_tracks(
            sp,
            query=f'artist:"{artist_name}"',
            known_ids=set(),     # En modo artista, SÍ mostramos sus canciones aunque las conozca
            seen_ids=seen_ids,
            limit=limit,
        )
        for t in tracks:
            t["explanation"] = f"De {artist_name}"
        return sorted(tracks, key=lambda x: x.get("popularity", 0), reverse=True)[:limit]

    # ── Modo búsqueda libre ──────────────────────────────────
    if config.get("free_search") and custom_query:
        tracks = _search_tracks(
            sp,
            query=custom_query.strip(),
            known_ids=known_ids,
            seen_ids=seen_ids,
            limit=limit,
        )
        for t in tracks:
            t["explanation"] = f"Búsqueda: {custom_query}"
        return sorted(tracks, key=lambda x: x.get("popularity", 0), reverse=True)[:limit]

    # ── Extraer géneros del usuario ─────────────────────────
    user_genres    = _extract_user_genres(top_artists, max_genres=4)
    extra_terms    = config.get("extra_terms", [])
    use_recent     = config.get("use_recent", False)

    # Si el usuario no tiene géneros definidos, usamos artistas directamente
    if not user_genres:
        artist_names = [a["name"] for a in top_artists[:3] if a.get("name")]
        user_genres  = artist_names  # Búsqueda por nombre de artista como fallback

    # ── Búsqueda por género + mood ───────────────────────────
    for genre in user_genres:
        if len(results) >= limit:
            break

        # Query base: el género exacto del usuario
        base_query = f'genre:"{genre}"'

        # Con términos extra del mood
        if extra_terms:
            # Intentamos con el término extra
            extra = extra_terms[0]
            query_with_mood = f'{base_query} {extra}'
            tracks = _search_tracks(sp, query_with_mood, known_ids, seen_ids, limit=8)

            for t in tracks:
                t["explanation"] = f"{genre} · {config['label']}"
            results.extend(tracks)

        # También sin términos extra (para completar si hay pocos resultados)
        if len(results) < limit:
            tracks_base = _search_tracks(sp, base_query, known_ids, seen_ids, limit=8)
            for t in tracks_base:
                t["explanation"] = f"Basado en {genre}"
            results.extend(tracks_base)

    # ── Boost por historial reciente (solo en modo default) ──
    if use_recent and len(results) < limit:
        recent_artists = _extract_recent_genres(recent_tracks)
        for artist_name in recent_artists:
            if len(results) >= limit:
                break
            tracks = _search_tracks(
                sp,
                query=f'artist:"{artist_name}"',
                known_ids=known_ids,
                seen_ids=seen_ids,
                limit=5,
            )
            for t in tracks:
                t["explanation"] = f"Similar a {artist_name}"
            results.extend(tracks)

    # ── Fallback: búsqueda por artistas favoritos ────────────
    if len(results) < 8:
        top_artist_names = [a["name"] for a in top_artists[:2] if a.get("name")]
        for artist_name in top_artist_names:
            if len(results) >= limit:
                break
            tracks = _search_tracks(
                sp,
                query=f'artist:"{artist_name}"',
                known_ids=known_ids,
                seen_ids=seen_ids,
                limit=6,
            )
            for t in tracks:
                t["explanation"] = f"Más de {artist_name}"
            results.extend(tracks)

    # ── Ordenar por popularidad y limitar ───────────────────
    results.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    return results[:limit]


# ─────────────────────────────────────────────────────────────
# DESCRIPCIÓN DEL PERFIL
# ─────────────────────────────────────────────────────────────

def describe_profile(top_artists: list, top_tracks: list) -> str:
    """
    Genera una descripción del perfil musical del usuario
    basada en sus artistas y géneros favoritos.
    """
    if not top_artists:
        return "Perfil musical en construcción"

    genre_count: dict[str, int] = {}
    for artist in top_artists:
        for genre in artist.get("genres", []):
            genre_count[genre] = genre_count.get(genre, 0) + 1

    top_genres   = sorted(genre_count, key=genre_count.get, reverse=True)[:2]
    artist_names = [a["name"] for a in top_artists[:2] if a.get("name")]

    parts = []
    if artist_names:
        parts.append(f"Fan de {', '.join(artist_names)}")
    if top_genres:
        parts.append(" · ".join(top_genres))

    return " · ".join(parts) if parts else "Perfil musical variado"


def get_mood_list() -> list[dict]:
    """
    Devuelve la lista de moods disponibles para el frontend.
    """
    return [
        {"id": mid, "label": cfg["label"], "emoji": cfg["emoji"]}
        for mid, cfg in MOOD_CONFIG.items()
    ]
