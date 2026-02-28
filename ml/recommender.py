"""
ml/recommender.py
-----------------
Motor de recomendaciones personalizadas de Melodix.

Flujo:
  1. Obtiene las audio features de las top tracks del usuario
  2. Construye un "perfil de audio" promediando esas features
  3. Llama a sp.recommendations() usando sus top artists/tracks/genres
  4. Puntúa y explica cada recomendación comparándola con el perfil
"""

import spotipy


# ─────────────────────────────────────────────────────────────
# AUDIO FEATURES
# ─────────────────────────────────────────────────────────────

FEATURE_KEYS = [
    "danceability",   # 0-1: cuánto está hecha para bailar
    "energy",         # 0-1: intensidad y actividad
    "valence",        # 0-1: positividad musical (alto = feliz)
    "acousticness",   # 0-1: cuánto es acústica
    "instrumentalness",  # 0-1: sin voz
    "speechiness",    # 0-1: palabras habladas
    "tempo",          # BPM
    "loudness",       # dB (negativo)
]


def get_audio_features(sp: spotipy.Spotify, track_ids: list) -> list:
    """
    Obtiene las audio features de una lista de track IDs.
    Spotify acepta hasta 100 IDs por llamada.
    Devuelve solo los features válidos (ignora None).
    """
    if not track_ids:
        return []

    # Limitar a 100 por llamada
    track_ids = list(set(track_ids))[:100]

    try:
        features = sp.audio_features(track_ids)
        return [f for f in features if f is not None]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────
# PERFIL DEL USUARIO
# ─────────────────────────────────────────────────────────────

def build_user_profile(audio_features: list) -> dict:
    """
    Construye el perfil de audio del usuario promediando
    las features de sus canciones favoritas.

    Returns:
        dict con el promedio de cada feature, o {} si no hay datos.
    """
    if not audio_features:
        return {}

    profile = {}
    for key in FEATURE_KEYS:
        values = [f[key] for f in audio_features if f.get(key) is not None]
        if values:
            profile[key] = round(sum(values) / len(values), 4)

    return profile


def describe_profile(profile: dict) -> str:
    """
    Genera una descripción textual del perfil musical del usuario.
    Útil para mostrar en la UI.
    """
    if not profile:
        return "Perfil musical no disponible"

    parts = []

    energy = profile.get("energy", 0)
    if energy > 0.75:
        parts.append("música muy enérgica")
    elif energy > 0.45:
        parts.append("energía media")
    else:
        parts.append("música tranquila")

    valence = profile.get("valence", 0)
    if valence > 0.65:
        parts.append("ambiente positivo")
    elif valence < 0.35:
        parts.append("tono oscuro/melancólico")

    danceability = profile.get("danceability", 0)
    if danceability > 0.7:
        parts.append("muy bailable")

    acousticness = profile.get("acousticness", 0)
    if acousticness > 0.6:
        parts.append("sonido acústico")

    tempo = profile.get("tempo", 0)
    if tempo > 140:
        parts.append(f"ritmo rápido ({int(tempo)} BPM)")
    elif tempo > 100:
        parts.append(f"ritmo medio ({int(tempo)} BPM)")
    else:
        parts.append(f"ritmo lento ({int(tempo)} BPM)")

    return " · ".join(parts) if parts else "Perfil musical variado"


# ─────────────────────────────────────────────────────────────
# MOTOR DE RECOMENDACIONES
# ─────────────────────────────────────────────────────────────

def get_recommendations(
    sp: spotipy.Spotify,
    top_artists: list,
    top_tracks: list,
    top_genres: list,
    limit: int = 20,
) -> list:
    """
    Llama a la Spotify Recommendations API usando como semillas
    los top artists, tracks y genres del usuario.

    Spotify permite máximo 5 semillas en total.

    Returns:
        Lista de tracks recomendados (formato raw de Spotify).
    """
    # Preparamos semillas (máx 5 en total)
    seed_artists = [a["id"] for a in top_artists[:2] if a.get("id")]
    seed_tracks  = [t["id"] for t in top_tracks[:2]  if t.get("id")]
    seed_genres  = top_genres[:1]  # Solo 1 género para no superar el límite

    # Si no hay suficientes semillas, lo que haya
    if not seed_artists and not seed_tracks and not seed_genres:
        return []

    try:
        results = sp.recommendations(
            seed_artists=seed_artists,
            seed_tracks=seed_tracks,
            seed_genres=seed_genres,
            limit=limit,
        )
        return results.get("tracks", [])
    except Exception as e:
        # Si los géneros no son válidos para la API, reintentamos sin géneros
        try:
            results = sp.recommendations(
                seed_artists=seed_artists,
                seed_tracks=seed_tracks,
                seed_genres=[],
                limit=limit,
            )
            return results.get("tracks", [])
        except Exception:
            return []


# ─────────────────────────────────────────────────────────────
# PUNTUACIÓN Y EXPLICACIÓN
# ─────────────────────────────────────────────────────────────

def _cosine_similarity(a: dict, b: dict) -> float:
    """Similitud coseno entre dos perfiles de features (sin tempo/loudness)."""
    keys = ["danceability", "energy", "valence", "acousticness", "instrumentalness"]
    dot, mag_a, mag_b = 0.0, 0.0, 0.0
    for k in keys:
        va = a.get(k, 0)
        vb = b.get(k, 0)
        dot   += va * vb
        mag_a += va ** 2
        mag_b += vb ** 2
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return round(dot / ((mag_a ** 0.5) * (mag_b ** 0.5)), 4)


def _generate_explanation(track_features: dict, user_profile: dict, top_artist_names: list) -> str:
    """
    Genera una frase corta explicando por qué se recomienda la canción.
    Compara las features de la canción con el perfil del usuario.
    """
    if not track_features or not user_profile:
        return "Basado en tus gustos"

    parts = []

    # Energía
    te = track_features.get("energy", 0)
    ue = user_profile.get("energy", 0)
    if abs(te - ue) < 0.15:
        if te > 0.7:
            parts.append("Alta energía como tus favoritas")
        elif te < 0.4:
            parts.append("Tan tranquila como tus favoritas")

    # Bailabilidad
    td = track_features.get("danceability", 0)
    ud = user_profile.get("danceability", 0)
    if td > 0.7 and ud > 0.65:
        parts.append("Muy bailable")

    # Positividad / mood
    tv = track_features.get("valence", 0)
    uv = user_profile.get("valence", 0)
    if abs(tv - uv) < 0.2:
        if tv > 0.65:
            parts.append("Ambiente positivo")
        elif tv < 0.35:
            parts.append("Tono oscuro como tu música")

    # Acústica
    ta = track_features.get("acousticness", 0)
    ua = user_profile.get("acousticness", 0)
    if ta > 0.6 and ua > 0.5:
        parts.append("Sonido acústico")

    # Artista en común
    if top_artist_names:
        parts.append(f"Basado en {top_artist_names[0]}")

    if not parts:
        parts.append("Basado en tus gustos")

    return " · ".join(parts[:2])  # Máx 2 razones para no saturar


def score_and_explain(
    candidate_tracks: list,
    candidate_features: list,
    user_profile: dict,
    top_artist_names: list,
) -> list:
    """
    Puntúa cada track candidato por similitud con el perfil del usuario,
    añade una explicación y devuelve la lista ordenada por score.

    Args:
        candidate_tracks: Lista raw de tracks de Spotify
        candidate_features: Lista de audio_features de esos tracks
        user_profile: Perfil del usuario (build_user_profile)
        top_artist_names: Nombres de los top artistas del usuario

    Returns:
        Lista de dicts con info de la canción + score + explanation
    """
    # Indexar features por track id
    features_by_id = {f["id"]: f for f in candidate_features if f}

    results = []
    for track in candidate_tracks:
        if not track or not track.get("id"):
            continue

        track_id = track["id"]
        album = track.get("album", {})
        artists = track.get("artists", [{}])

        tf = features_by_id.get(track_id, {})
        score = _cosine_similarity(tf, user_profile) if tf and user_profile else 0.5
        explanation = _generate_explanation(tf, user_profile, top_artist_names)

        results.append({
            "id": track_id,
            "name": track.get("name", ""),
            "artist": artists[0].get("name", "Desconocido") if artists else "Desconocido",
            "album": album.get("name", ""),
            "image": album["images"][0]["url"] if album.get("images") else None,
            "preview_url": track.get("preview_url"),
            "spotify_url": track.get("external_urls", {}).get("spotify"),
            "popularity": track.get("popularity", 0),
            "score": score,
            "explanation": explanation,
        })

    # Ordenar por score descendente
    results.sort(key=lambda x: x["score"], reverse=True)
    return results
