"""
ml/recommender.py
-----------------
Motor de recomendaciones de Melodix.

NOTA: Los endpoints sp.recommendations() y sp.audio_features() de Spotify
fueron DEPRECADOS en noviembre 2024 para apps nuevas. Este motor usa
únicamente endpoints disponibles:
  - sp.artist_related_artists()  -> artistas similares a los favoritos
  - sp.artist_top_tracks()       -> top canciones de esos artistas
"""

import spotipy


# ─────────────────────────────────────────────────────────────
# MOTOR PRINCIPAL — sin endpoints deprecados
# ─────────────────────────────────────────────────────────────

def get_recommendations_from_related_artists(
    sp: spotipy.Spotify,
    top_artists: list,
    top_tracks: list,
    limit: int = 20,
) -> list:
    """
    Genera recomendaciones buscando artistas relacionados a los favoritos
    del usuario y extrayendo sus canciones más populares.

    No usa sp.recommendations() ni sp.audio_features() (deprecados).

    Returns:
        Lista de dicts con info de la canción + explanation
    """
    if not top_artists:
        return []

    # IDs de canciones que el usuario ya conoce (para no recomendar)
    known_track_ids = {t["id"] for t in top_tracks if t.get("id")}

    # Artistas que ya conoce (para no recomendar canciones de ellos)
    known_artist_ids = {a["id"] for a in top_artists if a.get("id")}
    known_artist_names = {a["name"] for a in top_artists if a.get("name")}

    results = []
    seen_track_ids = set()

    # Para cada artista favorito (máx 3 para no saturar la API)
    for seed_artist in top_artists[:3]:
        seed_id   = seed_artist.get("id")
        seed_name = seed_artist.get("name", "")
        if not seed_id:
            continue

        try:
            # Obtener artistas relacionados
            related_data = sp.artist_related_artists(seed_id)
            related_artists = related_data.get("artists", [])

            # Tomamos los 3 artistas relacionados más populares
            # que el usuario no siga ya
            new_artists = [
                a for a in related_artists
                if a["id"] not in known_artist_ids
            ][:3]

            for artist in new_artists:
                artist_id   = artist["id"]
                artist_name = artist["name"]

                try:
                    # Top canciones del artista relacionado
                    top_data = sp.artist_top_tracks(artist_id, country="ES")
                    tracks   = top_data.get("tracks", [])

                    for track in tracks[:3]:  # Máx 3 canciones por artista
                        track_id = track.get("id")
                        if not track_id or track_id in seen_track_ids:
                            continue
                        if track_id in known_track_ids:
                            continue

                        seen_track_ids.add(track_id)
                        album   = track.get("album", {})
                        artists = track.get("artists", [{}])

                        results.append({
                            "id": track_id,
                            "name": track.get("name", ""),
                            "artist": artists[0].get("name", artist_name) if artists else artist_name,
                            "album": album.get("name", ""),
                            "image": album["images"][0]["url"] if album.get("images") else None,
                            "preview_url": track.get("preview_url"),
                            "spotify_url": track.get("external_urls", {}).get("spotify"),
                            "popularity": track.get("popularity", 0),
                            "score": artist.get("popularity", 50) / 100,
                            "explanation": f"Similar a {seed_name}",
                        })

                        if len(results) >= limit:
                            break

                except Exception:
                    continue

                if len(results) >= limit:
                    break

        except Exception:
            continue

        if len(results) >= limit:
            break

    # Ordenar por popularidad descendente
    results.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    return results[:limit]


def describe_profile(top_artists: list, top_tracks: list) -> str:
    """
    Genera una descripción del perfil musical del usuario
    basada en sus artistas y géneros favoritos.
    """
    if not top_artists:
        return "Perfil musical en construcción"

    # Recopilar géneros
    genre_count: dict[str, int] = {}
    for artist in top_artists:
        for genre in artist.get("genres", []):
            genre_count[genre] = genre_count.get(genre, 0) + 1

    top_genres = sorted(genre_count, key=genre_count.get, reverse=True)[:3]
    artist_names = [a["name"] for a in top_artists[:2] if a.get("name")]

    parts = []
    if artist_names:
        parts.append(f"Fan de {', '.join(artist_names)}")
    if top_genres:
        parts.append(" · ".join(top_genres[:2]))

    return " · ".join(parts) if parts else "Perfil musical variado"
