"""
ml/recommender.py
-----------------
Motor de recomendaciones de Melodix.

Usa sp.search() por géneros — el único endpoint no deprecado
que permite descubrir música nueva para el usuario.
"""

import spotipy


def get_recommendations_by_genre_search(
    sp: spotipy.Spotify,
    top_artists: list,
    top_tracks: list,
    limit: int = 20,
) -> list:
    """
    Descubre canciones nuevas buscando por los géneros favoritos del usuario.
    Usa sp.search() que no está deprecado.

    Algoritmo:
      1. Extrae los géneros de los top artists del usuario
      2. Busca tracks por cada género en Spotify
      3. Filtra canciones que el usuario ya conoce
      4. Devuelve las más populares con explicación del porqué
    """
    # IDs y nombres que el usuario ya conoce
    known_track_ids   = {t["id"] for t in top_tracks  if t.get("id")}
    known_artist_ids  = {a["id"] for a in top_artists  if a.get("id")}
    known_artist_names = [a["name"] for a in top_artists[:2] if a.get("name")]

    # Extraer géneros del usuario
    genre_count: dict[str, int] = {}
    for artist in top_artists:
        for genre in artist.get("genres", []):
            genre_count[genre] = genre_count.get(genre, 0) + 1

    top_genres = sorted(genre_count, key=genre_count.get, reverse=True)[:5]

    results  = []
    seen_ids = set()

    # Buscar por cada género
    for genre in top_genres:
        if len(results) >= limit:
            break
        try:
            search_data = sp.search(
                q=f'genre:"{genre}"',
                type="track",
                limit=10,
            )
            tracks = search_data.get("tracks", {}).get("items", [])

            for track in tracks:
                if len(results) >= limit:
                    break

                track_id = track.get("id")
                if not track_id or track_id in seen_ids:
                    continue
                if track_id in known_track_ids:
                    continue

                # Preferimos artistas que el usuario no conoce ya
                artists = track.get("artists", [{}])
                artist_id = artists[0].get("id") if artists else None

                seen_ids.add(track_id)
                album = track.get("album", {})

                results.append({
                    "id": track_id,
                    "name": track.get("name", ""),
                    "artist": artists[0].get("name", "") if artists else "",
                    "album": album.get("name", ""),
                    "image": album["images"][0]["url"] if album.get("images") else None,
                    "preview_url": track.get("preview_url"),
                    "spotify_url": track.get("external_urls", {}).get("spotify"),
                    "popularity": track.get("popularity", 0),
                    "score": track.get("popularity", 0) / 100,
                    "explanation": f"Género: {genre}",
                })

        except Exception:
            continue

    # Si no encontramos nada por géneros, buscamos por nombre de artista
    if not results and known_artist_names:
        for artist_name in known_artist_names[:2]:
            try:
                search_data = sp.search(
                    q=f'artist:"{artist_name}"',
                    type="track",
                    limit=10,
                )
                tracks = search_data.get("tracks", {}).get("items", [])
                for track in tracks:
                    track_id = track.get("id")
                    if not track_id or track_id in seen_ids or track_id in known_track_ids:
                        continue
                    seen_ids.add(track_id)
                    album = track.get("album", {})
                    artists = track.get("artists", [{}])
                    results.append({
                        "id": track_id,
                        "name": track.get("name", ""),
                        "artist": artists[0].get("name", "") if artists else "",
                        "album": album.get("name", ""),
                        "image": album["images"][0]["url"] if album.get("images") else None,
                        "preview_url": track.get("preview_url"),
                        "spotify_url": track.get("external_urls", {}).get("spotify"),
                        "popularity": track.get("popularity", 0),
                        "score": track.get("popularity", 0) / 100,
                        "explanation": f"Más de {artist_name}",
                    })
                    if len(results) >= limit:
                        break
            except Exception:
                continue

    # Ordenar por popularidad y devolver
    results.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    return results[:limit]


def describe_profile(top_artists: list, top_tracks: list) -> str:
    """
    Genera una descripción del perfil musical basada en artistas y géneros.
    """
    if not top_artists:
        return "Perfil musical en construcción"

    genre_count: dict[str, int] = {}
    for artist in top_artists:
        for genre in artist.get("genres", []):
            genre_count[genre] = genre_count.get(genre, 0) + 1

    top_genres    = sorted(genre_count, key=genre_count.get, reverse=True)[:2]
    artist_names  = [a["name"] for a in top_artists[:2] if a.get("name")]

    parts = []
    if artist_names:
        parts.append(f"Fan de {', '.join(artist_names)}")
    if top_genres:
        parts.append(" · ".join(top_genres))

    return " · ".join(parts) if parts else "Perfil musical variado"
