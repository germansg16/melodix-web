"""
spotify/auth.py
---------------
Gestión del flujo OAuth 2.0 con Spotify usando spotipy.
Las credenciales se leen del archivo .env, nunca están hardcodeadas.
"""

import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Cargamos las variables de entorno desde .env
load_dotenv()

# Permisos que pedimos al usuario de Spotify
SCOPE = " ".join([
    "user-library-read",        # Canciones guardadas
    "user-read-private",        # Info del perfil
    "user-top-read",            # Top artistas y canciones
    "user-read-recently-played",# Historial reciente
    "playlist-read-private",    # Playlists privadas
])


def get_auth_manager(cache_path: str = None) -> SpotifyOAuth:
    """
    Crea y devuelve un gestor de autenticación OAuth de Spotify.
    Si se proporciona cache_path, se guarda el token en ese archivo.
    """
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope=SCOPE,
        cache_path=cache_path,
        open_browser=False,
        show_dialog=True,  # Siempre pide login (para multi-usuario)
    )


def get_spotify_client(token_info: dict) -> spotipy.Spotify:
    """
    Crea un cliente de Spotify a partir de un token de acceso ya obtenido.

    Args:
        token_info: Diccionario con access_token, refresh_token, etc.

    Returns:
        Instancia de spotipy.Spotify lista para usar.
    """
    return spotipy.Spotify(auth=token_info["access_token"])


def refresh_token_if_needed(auth_manager: SpotifyOAuth, token_info: dict) -> dict:
    """
    Comprueba si el token ha expirado y lo refresca automáticamente.

    Returns:
        token_info actualizado (o el mismo si aún es válido).
    """
    if auth_manager.is_token_expired(token_info):
        token_info = auth_manager.refresh_access_token(token_info["refresh_token"])
    return token_info
