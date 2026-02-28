"""
spotify/client.py
-----------------
Funciones para extraer datos del usuario autenticado en Spotify.
Cada función recibe un cliente spotipy ya autenticado.
"""

import math
import time
import datetime as dt
import spotipy


def get_user_profile(sp: spotipy.Spotify) -> dict:
    """Obtiene la información del perfil del usuario."""
    user = sp.current_user()
    return {
        "id": user.get("id"),
        "name": user.get("display_name"),
        "email": user.get("email"),
        "country": user.get("country"),
        "followers": user.get("followers", {}).get("total", 0),
        "image": user["images"][0]["url"] if user.get("images") else None,
        "spotify_url": user["external_urls"].get("spotify"),
        "product": user.get("product"),  # 'premium' o 'free'
    }


def get_top_artists(sp: spotipy.Spotify, time_range: str = "medium_term", limit: int = 10) -> list:
    """
    Obtiene los artistas más escuchados del usuario.

    Args:
        time_range: 'short_term' (4 semanas), 'medium_term' (6 meses), 'long_term' (todo)
        limit: Número de artistas a obtener (máx 50)
    """
    results = sp.current_user_top_artists(limit=limit, time_range=time_range)
    artists = []
    for item in results.get("items", []):
        artists.append({
            "id": item["id"],
            "name": item["name"],
            "genres": item.get("genres", []),
            "popularity": item.get("popularity", 0),
            "followers": item["followers"]["total"],
            "image": item["images"][0]["url"] if item.get("images") else None,
            "spotify_url": item["external_urls"].get("spotify"),
        })
    return artists


def get_top_tracks(sp: spotipy.Spotify, time_range: str = "medium_term", limit: int = 10) -> list:
    """
    Obtiene las canciones más escuchadas del usuario.

    Args:
        time_range: 'short_term', 'medium_term' o 'long_term'
        limit: Número de canciones (máx 50)
    """
    results = sp.current_user_top_tracks(limit=limit, time_range=time_range)
    tracks = []
    for item in results.get("items", []):
        album = item.get("album", {})
        artists = item.get("artists", [{}])
        tracks.append({
            "id": item["id"],
            "name": item["name"],
            "artist": artists[0].get("name", "Desconocido"),
            "album": album.get("name"),
            "popularity": item.get("popularity", 0),
            "duration_ms": item.get("duration_ms", 0),
            "duration_min": round(item.get("duration_ms", 0) / 60000, 2),
            "image": album["images"][0]["url"] if album.get("images") else None,
            "preview_url": item.get("preview_url"),
            "spotify_url": item["external_urls"].get("spotify"),
            "release_date": album.get("release_date"),
        })
    return tracks


def get_recently_played(sp: spotipy.Spotify, limit: int = 20) -> list:
    """Obtiene el historial de canciones reproducidas recientemente."""
    results = sp.current_user_recently_played(limit=limit)
    tracks = []
    for item in results.get("items", []):
        track = item.get("track", {})
        album = track.get("album", {})
        artists = track.get("artists", [{}])
        tracks.append({
            "id": track.get("id"),
            "name": track.get("name"),
            "artist": artists[0].get("name", "Desconocido"),
            "image": album["images"][0]["url"] if album.get("images") else None,
            "played_at": item.get("played_at"),
            "spotify_url": track.get("external_urls", {}).get("spotify"),
            "preview_url": track.get("preview_url"),
        })
    return tracks


def get_saved_tracks_sample(sp: spotipy.Spotify, limit: int = 50) -> list:
    """
    Obtiene una muestra de las canciones guardadas del usuario.
    Útil para el análisis de perfil musical.
    """
    results = sp.current_user_saved_tracks(limit=limit, offset=0)
    tracks = []
    for item in results.get("items", []):
        track = item.get("track", {})
        if not track or not track.get("id"):
            continue
        album = track.get("album", {})
        artists = track.get("artists", [{}])

        release_date = album.get("release_date", "")
        release_year = None
        try:
            if len(release_date) >= 4:
                release_year = int(release_date[:4])
        except Exception:
            pass

        tracks.append({
            "id": track["id"],
            "name": track.get("name"),
            "artist": artists[0].get("name", "Desconocido"),
            "artist_id": artists[0].get("id"),
            "album": album.get("name"),
            "popularity": track.get("popularity", 0),
            "duration_ms": track.get("duration_ms", 0),
            "duration_min": round(track.get("duration_ms", 0) / 60000, 2),
            "release_year": release_year,
            "image": album["images"][0]["url"] if album.get("images") else None,
            "spotify_url": track.get("external_urls", {}).get("spotify"),
        })
    return tracks


def get_audio_features(sp: spotipy.Spotify, track_ids: list) -> list:
    """
    Obtiene las audio features de una lista de IDs de canciones.
    Spotify acepta hasta 100 IDs por llamada.

    Returns:
        Lista de dicts con features (danceability, energy, valence, etc.)
    """
    if not track_ids:
        return []
    track_ids = list(set(track_ids))[:100]
    try:
        features = sp.audio_features(track_ids)
        return [f for f in (features or []) if f is not None]
    except Exception:
        return []


def get_genre_distribution(top_artists: list) -> dict:
    """
    Calcula la distribución de géneros a partir de los artistas favoritos.

    Args:
        top_artists: Lista de artistas devuelta por get_top_artists()

    Returns:
        Diccionario {género: cantidad}, ordenado de mayor a menor.
    """
    genre_count = {}
    for artist in top_artists:
        for genre in artist.get("genres", []):
            genre_count[genre] = genre_count.get(genre, 0) + 1

    # Ordenar de mayor a menor
    return dict(sorted(genre_count.items(), key=lambda x: x[1], reverse=True))
