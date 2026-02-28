"""
app.py
------
Servidor Flask principal de Melodix.
Gestiona la autenticación OAuth con Spotify y expone los endpoints
de la API para el frontend.

Ejecutar:
    python app.py

O en producción:
    gunicorn app:app -b 0.0.0.0:8888
"""

import os
import json
from flask import (
    Flask, redirect, request, session,
    jsonify, render_template, url_for
)
from dotenv import load_dotenv

# Importamos nuestros módulos
from spotify.auth import get_auth_manager, get_spotify_client, refresh_token_if_needed
from spotify.client import (
    get_user_profile,
    get_top_artists,
    get_top_tracks,
    get_recently_played,
    get_saved_tracks_sample,
    get_genre_distribution,
)
from ml.recommender import (
    get_smart_recommendations,
    describe_profile,
    get_mood_list,
)

# ─────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-cambiar-en-produccion")
app.config["SESSION_COOKIE_NAME"] = "melodix_session"

PORT = int(os.getenv("FLASK_PORT", 8888))


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def get_current_sp():
    """
    Obtiene un cliente de Spotify autenticado para el usuario actual.
    Si el token ha expirado, lo refresca automáticamente.
    Devuelve None si el usuario no está logueado.
    """
    token_info = session.get("token_info")
    if not token_info:
        return None

    auth_manager = get_auth_manager()
    token_info = refresh_token_if_needed(auth_manager, token_info)
    session["token_info"] = token_info  # Guardamos el token actualizado

    return get_spotify_client(token_info)


def is_logged_in() -> bool:
    """Comprueba si el usuario tiene sesión activa."""
    return session.get("token_info") is not None


# ─────────────────────────────────────────────────────────────
# RUTAS DE PÁGINAS (HTML)
# ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    """Landing page principal."""
    logged_in = is_logged_in()
    return render_template("index.html", logged_in=logged_in)


@app.route("/dashboard")
def dashboard():
    """Dashboard del usuario. Requiere estar logueado."""
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("dashboard.html")


# ─────────────────────────────────────────────────────────────
# RUTAS DE AUTENTICACIÓN
# ─────────────────────────────────────────────────────────────
@app.route("/login")
def login():
    """
    Inicia el flujo OAuth. Redirige al usuario a la página de
    autorización de Spotify.
    """
    # Limpiamos cualquier sesión anterior
    session.clear()

    auth_manager = get_auth_manager()
    auth_url = auth_manager.get_authorize_url()

    return redirect(auth_url)


@app.route("/callback")
def callback():
    """
    Spotify redirige aquí tras la autorización del usuario.
    Intercambiamos el 'code' por un token de acceso.
    """
    # Si el usuario canceló el login en Spotify
    error = request.args.get("error")
    if error:
        return redirect(url_for("index"))

    code = request.args.get("code")
    if not code:
        return jsonify({"error": "No se recibió código de autorización"}), 400

    auth_manager = get_auth_manager()
    token_info = auth_manager.get_access_token(code)

    if not token_info or not token_info.get("access_token"):
        return jsonify({"error": "No se pudo obtener el token"}), 400

    # Guardamos el token en la sesión del usuario
    session["token_info"] = token_info

    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    """Cierra la sesión del usuario."""
    session.clear()
    return redirect(url_for("index"))


# ─────────────────────────────────────────────────────────────
# API ENDPOINTS (JSON) — El frontend los consume con fetch()
# ─────────────────────────────────────────────────────────────
@app.route("/api/me")
def api_me():
    """Devuelve el perfil del usuario autenticado."""
    sp = get_current_sp()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401

    try:
        profile = get_user_profile(sp)
        return jsonify(profile)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/top/artists")
def api_top_artists():
    """
    Devuelve los artistas más escuchados.
    Query params:
        - time_range: short_term | medium_term | long_term (default: medium_term)
        - limit: 1-50 (default: 12)
    """
    sp = get_current_sp()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401

    time_range = request.args.get("time_range", "medium_term")
    limit = int(request.args.get("limit", 12))
    limit = max(1, min(limit, 50))  # Clamp entre 1 y 50

    try:
        artists = get_top_artists(sp, time_range=time_range, limit=limit)
        return jsonify({"artists": artists, "time_range": time_range})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/top/tracks")
def api_top_tracks():
    """
    Devuelve las canciones más escuchadas.
    Query params:
        - time_range: short_term | medium_term | long_term (default: medium_term)
        - limit: 1-50 (default: 10)
    """
    sp = get_current_sp()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401

    time_range = request.args.get("time_range", "medium_term")
    limit = int(request.args.get("limit", 10))
    limit = max(1, min(limit, 50))

    try:
        tracks = get_top_tracks(sp, time_range=time_range, limit=limit)
        return jsonify({"tracks": tracks, "time_range": time_range})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/recent")
def api_recent():
    """Devuelve las últimas canciones reproducidas."""
    sp = get_current_sp()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401

    try:
        tracks = get_recently_played(sp, limit=20)
        return jsonify({"tracks": tracks})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/genres")
def api_genres():
    """
    Devuelve la distribución de géneros del usuario
    basada en sus artistas favoritos.
    """
    sp = get_current_sp()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401

    try:
        artists = get_top_artists(sp, time_range="long_term", limit=50)
        genres = get_genre_distribution(artists)
        # Devolvemos los top 15 géneros
        top_genres = dict(list(genres.items())[:15])
        return jsonify({"genres": top_genres})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboard/summary")
def api_dashboard_summary():
    """
    Endpoint combinado que devuelve todos los datos necesarios
    para el dashboard en una sola llamada (más eficiente).
    """
    sp = get_current_sp()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401

    try:
        # Llamadas paralelas (en el futuro se puede optimizar con threading)
        profile = get_user_profile(sp)
        top_artists = get_top_artists(sp, time_range="medium_term", limit=10)
        top_tracks = get_top_tracks(sp, time_range="medium_term", limit=10)
        recent = get_recently_played(sp, limit=10)
        genres = get_genre_distribution(top_artists)

        return jsonify({
            "profile": profile,
            "top_artists": top_artists,
            "top_tracks": top_tracks,
            "recent_tracks": recent,
            "genre_distribution": dict(list(genres.items())[:12]),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommendations")
def api_recommendations():
    """
    Recomendaciones inteligentes personalizadas para el usuario.
    Acepta: ?mood=fiesta|emocional|bailar|relajado|amigos|verano|tendencias|artista|custom
            &query=texto libre (para modos artista y custom)
    """
    sp = get_current_sp()
    if not sp:
        return jsonify({"error": "No autenticado"}), 401

    mood         = request.args.get("mood", "default")
    custom_query = request.args.get("query", "").strip()

    try:
        # Datos del usuario (limit=10 para mayor precisión del perfil)
        top_artists   = get_top_artists(sp, time_range="medium_term", limit=10)
        top_tracks    = get_top_tracks(sp,  time_range="medium_term", limit=10)
        recent_tracks = get_recently_played(sp, limit=20)

        if not top_artists:
            return jsonify({
                "recommendations": [],
                "profile_description": "Escucha más música para generar recomendaciones",
                "moods": get_mood_list(),
            })

        profile_desc    = describe_profile(top_artists, top_tracks)
        recommendations = get_smart_recommendations(
            sp,
            top_artists=top_artists,
            top_tracks=top_tracks,
            recent_tracks=recent_tracks,
            mood=mood,
            custom_query=custom_query,
            limit=20,
        )

        return jsonify({
            "recommendations": recommendations[:12],
            "profile_description": profile_desc,
            "moods": get_mood_list(),
            "active_mood": mood,
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


# ─────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA

# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  🎵 Melodix Web Server")
    print(f"  Servidor corriendo en: http://127.0.0.1:{PORT}")
    print(f"  Presiona Ctrl+C para detener")
    print(f"{'='*50}\n")

    app.run(
        host="127.0.0.1",
        port=PORT,
        debug=True,
    )
