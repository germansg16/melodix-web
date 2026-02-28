"""
ml/recommender.py
-----------------
Motor de recomendaciones de Melodix — v3

Dos modos:
  PARA TI  — explora la discografía completa de los artistas favoritos del
              usuario (artist_albums + album_tracks). Encuentra "deep cuts"
              que no ha escuchado. Intenta usar audio features para ordenar
              por similitud de energía/BPM cuando están disponibles.

  RECIENTES — analiza qué artistas dominan las últimas escuchas, detecta
              el "mood del momento" y recomienda más de ese estilo.

No usa sp.recommendations() ni sp.related_artists() (deprecated/restringidos).
"""

import random
import spotipy


# ─────────────────────────────────────────────────────────────
# HELPERS COMUNES
# ─────────────────────────────────────────────────────────────

def _known_track_ids(top_tracks: list, recent_tracks: list) -> set:
    ids = set()
    for t in top_tracks:
        if t.get("id"): ids.add(t["id"])
    for t in recent_tracks:
        if t.get("id"): ids.add(t["id"])
    return ids


def _format_track(raw: dict, explanation: str) -> dict:
    album   = raw.get("album", {})
    artists = raw.get("artists", [{}])
    return {
        "id":          raw.get("id"),
        "name":        raw.get("name", ""),
        "artist":      artists[0].get("name", "") if artists else "",
        "album":       album.get("name", ""),
        "image":       album.get("images", [{}])[0].get("url") if album.get("images") else None,
        "preview_url": raw.get("preview_url"),
        "spotify_url": raw.get("external_urls", {}).get("spotify"),
        "popularity":  raw.get("popularity", 0),
        "explanation": explanation,
    }


def _try_audio_features(sp: spotipy.Spotify, track_ids: list) -> dict:
    """
    Intenta obtener audio features. Si la API devuelve 403 / vacío (deprecated),
    retorna {} silenciosamente.

    Returns: dict {track_id: {energy, danceability, valence, tempo}}
    """
    if not track_ids:
        return {}
    try:
        raw = sp.audio_features(track_ids) or []
        result = {}
        for feat in raw:
            if feat and feat.get("id"):
                result[feat["id"]] = {
                    "energy":       feat.get("energy", 0.5),
                    "danceability": feat.get("danceability", 0.5),
                    "valence":      feat.get("valence", 0.5),
                    "tempo":        feat.get("tempo", 120),
                }
        return result
    except Exception:
        return {}


def _build_audio_profile(features_dict: dict) -> dict:
    """
    Calcula el perfil promedio de audio de un conjunto de tracks.
    Si no hay features disponibles, devuelve {}.
    """
    if not features_dict:
        return {}
    vals = list(features_dict.values())
    keys = ["energy", "danceability", "valence", "tempo"]
    return {k: sum(v[k] for v in vals) / len(vals) for k in keys}


def _audio_similarity(track_feat: dict, profile: dict) -> float:
    """
    Calcula qué tan parecido es un track al perfil del usuario.
    Devuelve un score 0-1 (1 = muy parecido).
    """
    if not track_feat or not profile:
        return 0.5  # Neutral si no hay datos

    # Diferencia absoluta normalizada por dimensión
    energy_sim      = 1 - abs(track_feat["energy"]       - profile["energy"])
    dance_sim       = 1 - abs(track_feat["danceability"]  - profile["danceability"])
    valence_sim     = 1 - abs(track_feat["valence"]       - profile["valence"])
    tempo_diff      = abs(track_feat["tempo"] - profile["tempo"])
    tempo_sim       = max(0.0, 1 - tempo_diff / 100)   # 100 BPM de margen

    return (energy_sim + dance_sim + valence_sim + tempo_sim) / 4


def _describe_audio_profile(profile: dict) -> str:
    """Devuelve texto descriptivo del perfil de audio."""
    if not profile:
        return ""
    parts = []
    energy = profile.get("energy", 0.5)
    dance  = profile.get("danceability", 0.5)
    valence= profile.get("valence", 0.5)
    bpm    = int(profile.get("tempo", 120))

    if energy > 0.7:     parts.append("muy enérgica")
    elif energy < 0.4:   parts.append("tranquila")

    if dance > 0.7:      parts.append("bailable")
    elif dance < 0.4:    parts.append("poco bailable")

    if valence > 0.6:    parts.append("animada")
    elif valence < 0.35: parts.append("melancólica")

    parts.append(f"{bpm} BPM")
    return " · ".join(parts) if parts else ""


# ─────────────────────────────────────────────────────────────
# MODO 1: PARA TI — discografía de top artists
# ─────────────────────────────────────────────────────────────

def _get_artist_deep_cuts(
    sp: spotipy.Spotify,
    artist_id: str,
    artist_name: str,
    known_ids: set,
    seen_ids: set,
    limit_per_artist: int = 12,
) -> list:
    """
    Obtiene tracks de los álbumes de un artista que el usuario
    no ha escuchado aún. Devuelve los más populares.
    """
    tracks_out = []
    try:
        # Obtener álbumes recientes del artista (álbumes + singles)
        albums_data = sp.artist_albums(
            artist_id,
            album_type="album,single",
            limit=5,       # últimos 5 lanzamientos
            country="ES",
        )
        albums = random.sample(
            albums_data.get("items", []),
            min(len(albums_data.get("items", [])), 5)
        )

        for album in albums:
            if len(tracks_out) >= limit_per_artist:
                break
            album_id = album.get("id")
            if not album_id:
                continue
            try:
                tracks_data = sp.album_tracks(album_id, limit=5)
                album_name  = album.get("name", "")
                images      = album.get("images", [])
                cover       = images[0]["url"] if images else None

                for t in tracks_data.get("items", []):
                    tid = t.get("id")
                    if not tid or tid in known_ids or tid in seen_ids:
                        continue
                    seen_ids.add(tid)

                    # Obtener popularidad: necesitamos sp.track()
                    try:
                        full_track = sp.track(tid)
                        popularity = full_track.get("popularity", 0)
                        preview    = full_track.get("preview_url")
                        spotify_url= full_track.get("external_urls", {}).get("spotify")
                    except Exception:
                        popularity = 0
                        preview    = None
                        spotify_url= None

                    tracks_out.append({
                        "id":          tid,
                        "name":        t.get("name", ""),
                        "artist":      artist_name,
                        "album":       album_name,
                        "image":       cover,
                        "preview_url": preview,
                        "spotify_url": spotify_url,
                        "popularity":  popularity,
                        "explanation": f"De {artist_name}",
                    })

                    if len(tracks_out) >= limit_per_artist:
                        break
            except Exception:
                continue
    except Exception:
        pass

    return tracks_out


def get_para_ti(
    sp: spotipy.Spotify,
    top_artists: list,
    top_tracks: list,
    recent_tracks: list,
    excluded_ids: set = None,
    limit: int = 20,
) -> tuple[list, dict, str]:
    """
    Recomienda canciones basándose en la discografía completa
    de los artistas favoritos del usuario.

    Returns:
        (recommendations_list, audio_profile_dict, profile_description_str)
    """
    known_ids = _known_track_ids(top_tracks, recent_tracks)
    if excluded_ids:
        known_ids.update(excluded_ids)
    seen_ids  = set()
    results   = []

    # Intentar obtener perfil de audio del usuario
    top_track_ids = [t["id"] for t in top_tracks if t.get("id")][:15]
    user_features = _try_audio_features(sp, top_track_ids)
    user_profile  = _build_audio_profile(user_features)
    audio_desc    = _describe_audio_profile(user_profile)

    # Para cada artista del top, obtener deep cuts
    # Mezclamos el orden para variar resultados entre llamadas
    artists_shuffled = list(top_artists)
    random.shuffle(artists_shuffled)

    for artist in artists_shuffled[:6]:
        if len(results) >= limit:
            break
        artist_id   = artist.get("id")
        artist_name = artist.get("name", "")
        if not artist_id:
            continue
        deep_cuts = _get_artist_deep_cuts(
            sp, artist_id, artist_name, known_ids, seen_ids,
            limit_per_artist=8,
        )
        results.extend(deep_cuts)

    # Si no hay suficientes tracks de discografía, completar con búsqueda
    if len(results) < limit:
        genre_counts: dict[str, int] = {}
        for a in top_artists:
            for g in a.get("genres", []):
                genre_counts[g] = genre_counts.get(g, 0) + 1
        top_genres = sorted(genre_counts, key=genre_counts.get, reverse=True)[:3]

        for genre in top_genres:
            if len(results) >= limit:
                break
            offset = random.randint(0, 20)
            try:
                search_res = sp.search(q=f'genre:"{genre}"', type="track", limit=8, offset=offset)
                for t in search_res.get("tracks", {}).get("items", []):
                    tid = t.get("id")
                    if not tid or tid in known_ids or tid in seen_ids:
                        continue
                    seen_ids.add(tid)
                    results.append(_format_track(t, f"Basado en {genre}"))
            except Exception:
                continue

    # Ordenar por similitud de audio si disponible, si no por popularidad
    if user_profile and results:
        # Obtener audio features de los resultados (batch)
        result_ids  = [r["id"] for r in results if r.get("id")][:30]
        res_features = _try_audio_features(sp, result_ids)

        for r in results:
            feat = res_features.get(r.get("id"), {})
            sim  = _audio_similarity(feat, user_profile)
            r["_score"] = sim * 0.6 + (r.get("popularity", 0) / 100) * 0.4
        results.sort(key=lambda x: x.get("_score", 0), reverse=True)
    else:
        # Sin audio features: ordenar por popularidad + algo de variedad
        results.sort(
            key=lambda x: x.get("popularity", 0) + random.randint(-3, 3),
            reverse=True,
        )

    # Limpiar clave interna
    for r in results:
        r.pop("_score", None)

    return results[:limit], user_profile, audio_desc


# ─────────────────────────────────────────────────────────────
# MODO 2: RECIENTES — detecta mood del momento
# ─────────────────────────────────────────────────────────────

def get_recientes(
    sp: spotipy.Spotify,
    top_artists: list,
    top_tracks: list,
    recent_tracks: list,
    excluded_ids: set = None,
    limit: int = 20,
) -> tuple[list, str]:
    """
    Analiza las últimas escuchas para detectar el "estado musical actual"
    y recomienda canciones acordes.

    Lógica:
      1. Cuenta qué artistas aparecen más en recent_tracks
      2. Los más frecuentes = estado musical ahora
      3. Busca más canciones de esos artistas (discografía)
      4. Si hay un "cambio de estilo" reciente, mezcla ambos
    """
    known_ids = _known_track_ids(top_tracks, recent_tracks)
    if excluded_ids:
        known_ids.update(excluded_ids)
    seen_ids  = set()
    results   = []

    # Contar artistas recientes
    recent_artist_count: dict[str, int] = {}
    recent_artist_ids:   dict[str, str] = {}
    for t in recent_tracks:
        aname = t.get("artist", "")
        aid   = t.get("artist_id", "")   # puede no existir en el formato actual
        if aname:
            recent_artist_count[aname] = recent_artist_count.get(aname, 0) + 1
            if aid and aname not in recent_artist_ids:
                recent_artist_ids[aname] = aid

    # Ordenar por frecuencia
    sorted_artists = sorted(recent_artist_count, key=recent_artist_count.get, reverse=True)

    # Detectar si hay un "cambio de momento" — artistas de los últimos 5 tracks
    # vs artistas de los tracks 5-20
    recent_5  = set(t.get("artist", "") for t in recent_tracks[:5]  if t.get("artist"))
    recent_old = set(t.get("artist", "") for t in recent_tracks[5:] if t.get("artist"))
    has_shift  = bool(recent_5 - recent_old)  # artistas nuevos en las últimas 5

    # Artistas a usar como semilla
    seed_artists = sorted_artists[:4]

    # Completar con IDs de artistas desde top_artists si no los tenemos
    top_artist_map = {a["name"]: a["id"] for a in top_artists if a.get("name") and a.get("id")}

    # Descripción del contexto
    if seed_artists:
        context_desc = f"Ahora escuchando: {', '.join(seed_artists[:2])}"
        if has_shift and recent_5:
            context_desc = f"Cambio de estilo detectado — {', '.join(list(recent_5)[:2])}"
    else:
        context_desc = "Basado en tu historial reciente"

    # Obtener deep cuts de los artistas del momento
    for artist_name in seed_artists:
        if len(results) >= limit:
            break

        artist_id = recent_artist_ids.get(artist_name) or top_artist_map.get(artist_name)

        if artist_id:
            # Tenemos el ID → discografía completa
            deep_cuts = _get_artist_deep_cuts(
                sp, artist_id, artist_name, known_ids, seen_ids,
                limit_per_artist=6,
            )
            for t in deep_cuts:
                t["explanation"] = f"Sigues escuchando {artist_name}"
            results.extend(deep_cuts)
        else:
            # Solo nombre → búsqueda por artista
            try:
                offset = random.randint(0, 10)
                search_res = sp.search(
                    q=f'artist:"{artist_name}"',
                    type="track", limit=6, offset=offset,
                )
                for t in search_res.get("tracks", {}).get("items", []):
                    tid = t.get("id")
                    if not tid or tid in known_ids or tid in seen_ids:
                        continue
                    seen_ids.add(tid)
                    ft = _format_track(t, f"Sigues escuchando {artist_name}")
                    results.append(ft)
            except Exception:
                continue

    # Si el cambio de estilo es reciente, también añadir los artistas nuevos
    if has_shift and len(results) < limit:
        for aname in list(recent_5)[:2]:
            if aname in [r.get("artist") for r in results]:
                continue
            aid = recent_artist_ids.get(aname) or top_artist_map.get(aname)
            if not aid:
                continue
            deep = _get_artist_deep_cuts(sp, aid, aname, known_ids, seen_ids, limit_per_artist=4)
            for t in deep:
                t["explanation"] = f"Tu nuevo rollo: {aname}"
            results.extend(deep[:4])

    # Fallback: si no hay suficientes, completar con top artists del usuario
    if len(results) < 8:
        for artist in top_artists[:3]:
            if len(results) >= limit:
                break
            aid   = artist.get("id")
            aname = artist.get("name", "")
            if not aid:
                continue
            deep = _get_artist_deep_cuts(sp, aid, aname, known_ids, seen_ids, limit_per_artist=5)
            for t in deep:
                t["explanation"] = f"Más de {aname}"
            results.extend(deep)

    random.shuffle(results)
    return results[:limit], context_desc


# ─────────────────────────────────────────────────────────────
# BÚSQUEDA LIBRE Y POR ARTISTA
# ─────────────────────────────────────────────────────────────

def get_custom_search(
    sp: spotipy.Spotify,
    query: str,
    mode: str = "libre",  # "artista" | "libre"
    excluded_ids: set = None,
    limit: int = 20,
) -> list:
    seen = set()
    results = []
    # Offset escalonado: incrementamos con cada llamada para no repetir
    # Usamos offset aleatorio simple — suficiente para variar resultados
    offset = random.randint(0, 40)
    try:
        q = f'artist:"{query}"' if mode == "artista" else query
        known = excluded_ids or set()
        res = sp.search(q=q, type="track", limit=limit + 10, offset=offset)
        for t in res.get("tracks", {}).get("items", []):
            tid = t.get("id")
            if not tid or tid in seen or tid in known:
                continue
            seen.add(tid)
            label = f"De {query}" if mode == "artista" else f'Búsqueda: "{query}"'
            results.append(_format_track(t, label))
    except Exception:
        # Si el offset es muy alto y no hay resultados, reintentamos sin offset
        try:
            q = f'artist:"{query}"' if mode == "artista" else query
            res = sp.search(q=q, type="track", limit=limit)
            for t in res.get("tracks", {}).get("items", []):
                tid = t.get("id")
                if not tid or tid in seen:
                    continue
                seen.add(tid)
                label = f"De {query}" if mode == "artista" else f'Búsqueda: "{query}"'
                results.append(_format_track(t, label))
        except Exception:
            pass
    return results[:limit]


# ─────────────────────────────────────────────────────────────
# DESCRIPCIÓN DEL PERFIL
# ─────────────────────────────────────────────────────────────

def describe_profile(top_artists: list, top_tracks: list, audio_desc: str = "") -> str:
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
    if audio_desc:
        parts.append(audio_desc)

    return " · ".join(parts) if parts else "Perfil musical variado"
