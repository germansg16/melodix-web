# SpotifyIA Web 🎵

Una aplicación web completa que conecta con tu cuenta de Spotify, analiza tus datos musicales con IA y te recomienda canciones con explicaciones transparentes (XAI + AHP).

## 🚀 Cómo ejecutar

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Configurar credenciales
El archivo `.env` ya está configurado con tus credenciales de Spotify.

### 3. Arrancar el servidor
```bash
python app.py
```

### 4. Abrir en el navegador
```
http://127.0.0.1:8888
```

## 📁 Estructura del proyecto
```
spotifyIA-web/
├── app.py              # Servidor Flask principal
├── .env                # Credenciales (no subir a Git)
├── requirements.txt    # Dependencias Python
├── spotify/
│   ├── auth.py         # OAuth 2.0 Spotify
│   └── client.py       # Funciones de la API
├── ml/                 # Pipeline de Machine Learning (próximamente)
├── static/
│   ├── css/style.css   # Estilos dark mode + glassmorphism
│   └── js/
│       ├── main.js     # Landing page JS
│       └── dashboard.js # Dashboard con Chart.js
└── templates/
    ├── index.html      # Landing page
    └── dashboard.html  # Dashboard del usuario
```

## 🔑 API Endpoints
| Endpoint | Descripción |
|----------|-------------|
| `GET /` | Landing page |
| `GET /login` | Inicia OAuth con Spotify |
| `GET /callback` | Callback de autorización |
| `GET /dashboard` | Dashboard del usuario |
| `GET /api/me` | Perfil del usuario (JSON) |
| `GET /api/top/artists?time_range=medium_term` | Top artistas |
| `GET /api/top/tracks?time_range=medium_term` | Top canciones |
| `GET /api/recent` | Historial reciente |
| `GET /api/genres` | Distribución de géneros |
| `GET /api/dashboard/summary` | Todos los datos en una llamada |

## 🛣️ Roadmap
- [x] Fase 1: Estructura y credenciales seguras
- [x] Fase 2: Backend Flask + OAuth Spotify
- [x] Fase 3: Frontend (Landing + Dashboard)
- [ ] Fase 4: Motor de recomendaciones IA
- [ ] Fase 5: Despliegue en producción

---
**Autor:** Germán Sierra González · Proyecto de Inteligencia Artificial
