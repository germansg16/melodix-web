/**
 * dashboard.js
 * Lógica completa del dashboard: carga de datos, renderizado y gráficas.
 */

// ─────────────────────────────────────────────────────────────
// ESTADO GLOBAL
// ─────────────────────────────────────────────────────────────
let currentTimeRange = 'medium_term';
let genreChart = null;

// ─────────────────────────────────────────────────────────────
// UTILIDADES
// ─────────────────────────────────────────────────────────────

/** Formatea números grandes (1200 → 1.2K) */
function formatNumber(n) {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return n.toString();
}

/** Formatea una fecha ISO a "hace X min/h" */
function timeAgo(isoString) {
    if (!isoString) return '';
    const diff = Date.now() - new Date(isoString).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `hace ${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `hace ${hrs}h`;
    return `hace ${Math.floor(hrs / 24)}d`;
}

/** Hace una petición al backend y devuelve JSON */
async function apiFetch(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Error ${res.status} en ${url}`);
    return res.json();
}

/** Muestra / oculta el estado de carga */
function setLoading(loading) {
    document.getElementById('loadingScreen').style.display = loading ? 'flex' : 'none';
    document.getElementById('dashboardContent').style.display = loading ? 'none' : 'block';
}

// ─────────────────────────────────────────────────────────────
// RENDERIZADORES
// ─────────────────────────────────────────────────────────────

function renderProfile(profile) {
    const avatar = profile.image || 'https://via.placeholder.com/72';

    // Topbar
    document.querySelector('.topbar-greeting').textContent = `Hola, ${profile.name} 👋`;
    document.getElementById('userAvatar').src = avatar;

    // Tarjeta de perfil
    document.getElementById('profileAvatar').src = avatar;
    document.getElementById('profileName').textContent = profile.name || '—';
    document.getElementById('profileMeta').textContent = profile.email || profile.id || '—';
    document.getElementById('profilePlan').textContent = profile.product === 'premium' ? '⭐ Premium' : 'Free';
    document.getElementById('profileCountry').textContent = profile.country || '—';
}

function renderTopArtists(artists) {
    const grid = document.getElementById('artistsGrid');
    grid.innerHTML = '';

    // Stat card con artista #1
    if (artists[0]) {
        document.getElementById('statTopArtist').textContent = artists[0].name;
    }

    artists.forEach((artist, i) => {
        const card = document.createElement('a');
        card.href = artist.spotify_url || '#';
        card.target = '_blank';
        card.className = 'artist-card';

        const imgHtml = artist.image
            ? `<img src="${artist.image}" alt="${artist.name}" class="artist-img" loading="lazy" />`
            : `<div class="artist-img-placeholder">🎵</div>`;

        card.innerHTML = `
      ${imgHtml}
      <div class="artist-info">
        <div class="artist-name">${artist.name}</div>
        <div class="artist-rank">#${i + 1} · ${formatNumber(artist.followers)} seguidores</div>
      </div>
    `;
        grid.appendChild(card);
    });
}

function renderTopTracks(tracks) {
    const list = document.getElementById('tracksList');
    list.innerHTML = '';

    // Stat card con canción #1
    if (tracks[0]) {
        document.getElementById('statTopTrack').textContent = tracks[0].name;
    }

    tracks.forEach((track, i) => {
        const item = document.createElement('div');
        item.className = 'track-item';

        const imgHtml = track.image
            ? `<img src="${track.image}" alt="${track.name}" class="track-img" loading="lazy" />`
            : `<div class="track-img-placeholder">🎵</div>`;

        const popPct = track.popularity || 0;

        item.innerHTML = `
      <span class="track-num">${i + 1}</span>
      ${imgHtml}
      <div class="track-info">
        <div class="track-name">${track.name}</div>
        <div class="track-artist">${track.artist}</div>
      </div>
      <div class="track-pop">
        <div class="pop-bar"><div class="pop-fill" style="width:${popPct}%"></div></div>
        <span>${popPct}</span>
      </div>
      ${track.spotify_url ? `<a href="${track.spotify_url}" target="_blank" class="track-link" title="Abrir en Spotify">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
      </a>` : ''}
    `;
        list.appendChild(item);
    });
}

function renderGenres(genres) {
    const entries = Object.entries(genres);
    if (!entries.length) return;

    // Stat card con género #1
    document.getElementById('statTopGenre').textContent = entries[0][0];

    // Lista
    const genresList = document.getElementById('genresList');
    genresList.innerHTML = '';
    entries.slice(0, 10).forEach(([name, count], i) => {
        const item = document.createElement('div');
        item.className = 'genre-item';
        item.innerHTML = `
      <span class="genre-idx">${i + 1}</span>
      <span class="genre-name">${name}</span>
      <span class="genre-count">${count}</span>
    `;
        genresList.appendChild(item);
    });

    // Gráfico de donut con Chart.js
    const ctx = document.getElementById('genreChart').getContext('2d');
    if (genreChart) genreChart.destroy();

    const colors = [
        '#1db954', '#3b82f6', '#ec4899', '#f59e0b', '#8b5cf6',
        '#06b6d4', '#ef4444', '#84cc16', '#f97316', '#14b8a6'
    ];

    genreChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: entries.slice(0, 10).map(([k]) => k),
            datasets: [{
                data: entries.slice(0, 10).map(([, v]) => v),
                backgroundColor: colors,
                borderColor: '#0a0a0f',
                borderWidth: 3,
                hoverOffset: 8,
            }]
        },
        options: {
            responsive: true,
            cutout: '65%',
            plugins: {
                legend: {
                    display: false,
                },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ${ctx.label}: ${ctx.raw} artistas`
                    }
                }
            }
        }
    });
}

function renderRecentTracks(tracks) {
    const list = document.getElementById('recentList');
    list.innerHTML = '';

    tracks.forEach(track => {
        const item = document.createElement('div');
        item.className = 'recent-item';

        const imgHtml = track.image
            ? `<img src="${track.image}" alt="${track.name}" class="recent-img" loading="lazy" />`
            : `<div class="recent-img" style="background:linear-gradient(135deg,#1db954,#3b82f6);border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:1.2rem">🎵</div>`;

        item.innerHTML = `
      ${imgHtml}
      <div class="recent-info">
        <div class="recent-name">${track.name}</div>
        <div class="recent-artist">${track.artist}</div>
      </div>
      <span class="recent-time">${timeAgo(track.played_at)}</span>
    `;
        list.appendChild(item);
    });
}

function renderStats(profile) {
    document.getElementById('statFollowers').textContent = formatNumber(profile.followers || 0);
}

function renderRecommendations(data) {
    const grid = document.getElementById('recommendationsGrid');
    const subtitle = document.getElementById('profileDescription');
    grid.innerHTML = '';

    if (data.profile_description) {
        subtitle.textContent = '🎵 Tu perfil: ' + data.profile_description;
    }

    if (!data.recommendations || data.recommendations.length === 0) {
        grid.innerHTML = '<p style="color:var(--text-muted);padding:2rem">No se encontraron recomendaciones. Escucha más música en Spotify y vuelve a intentarlo.</p>';
        return;
    }

    data.recommendations.forEach(track => {
        const card = document.createElement('div');
        card.className = 'rec-card glass-card';

        const imgHtml = track.image
            ? `<img src="${track.image}" alt="${track.name}" class="rec-img" loading="lazy" />`
            : `<div class="rec-img rec-img-placeholder">🎵</div>`;

        const previewBtn = track.preview_url
            ? `<button class="rec-preview-btn" data-url="${track.preview_url}" title="Previsualizar">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
               </button>`
            : '';

        card.innerHTML = `
            ${imgHtml}
            <div class="rec-info">
                <div class="rec-name">${track.name}</div>
                <div class="rec-artist">${track.artist}</div>
                <div class="rec-explanation">${track.explanation}</div>
            </div>
            <div class="rec-actions">
                ${previewBtn}
                ${track.spotify_url ? `<a href="${track.spotify_url}" target="_blank" class="rec-spotify-btn" title="Abrir en Spotify">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                </a>` : ''}
            </div>
        `;
        grid.appendChild(card);
    });

    // Preview player: reproduce 30s al hacer clic
    let currentAudio = null;
    grid.querySelectorAll('.rec-preview-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const url = btn.dataset.url;
            if (currentAudio && !currentAudio.paused) {
                currentAudio.pause();
                grid.querySelectorAll('.rec-preview-btn').forEach(b => b.classList.remove('playing'));
                if (currentAudio._url === url) { currentAudio = null; return; }
            }
            currentAudio = new Audio(url);
            currentAudio._url = url;
            currentAudio.volume = 0.5;
            currentAudio.play();
            btn.classList.add('playing');
            currentAudio.onended = () => btn.classList.remove('playing');
        });
    });
}

// ─────────────────────────────────────────────────────────────
// CARGA PRINCIPAL DE DATOS
// ─────────────────────────────────────────────────────────────

async function loadDashboard(timeRange = 'medium_term') {
    setLoading(true);
    try {
        const [summaryData] = await Promise.all([
            apiFetch(`/api/dashboard/summary`),
        ]);

        renderProfile(summaryData.profile);
        renderStats(summaryData.profile);
        renderTopArtists(summaryData.top_artists);
        renderTopTracks(summaryData.top_tracks);
        renderGenres(summaryData.genre_distribution);
        renderRecentTracks(summaryData.recent_tracks);

        setLoading(false);

        // Recomendaciones en segundo plano (no bloquea el dashboard)
        loadRecommendations();
    } catch (err) {
        console.error('Error cargando el dashboard:', err);
        document.getElementById('loadingScreen').innerHTML = `
      <p style="color:#ef4444">❌ Error al cargar datos: ${err.message}</p>
      <a href="/" style="color:#1db954;margin-top:1rem">Volver al inicio</a>
    `;
    }
}

// ─────────────────────────────────────────────────────────────
// RECARGA CON DISTINTO PERÍODO DE TIEMPO
// ─────────────────────────────────────────────────────────────

async function reloadWithTimeRange(timeRange) {
    currentTimeRange = timeRange;
    try {
        const [artists, tracks] = await Promise.all([
            apiFetch(`/api/top/artists?time_range=${timeRange}&limit=10`),
            apiFetch(`/api/top/tracks?time_range=${timeRange}&limit=10`),
        ]);
        renderTopArtists(artists.artists);
        renderTopTracks(tracks.tracks);
    } catch (err) {
        console.error('Error recargando por tiempo:', err);
    }
}

// ─────────────────────────────────────────────────────────────
// EVENT LISTENERS
// ─────────────────────────────────────────────────────────────

// Sidebar toggle (móvil)
const sidebarToggle = document.getElementById('sidebarToggle');
const sidebar = document.getElementById('sidebar');
if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => sidebar.classList.toggle('open'));
}

// Botones de período de tiempo
document.querySelectorAll('.time-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        reloadWithTimeRange(btn.dataset.range);
    });
});

// Sidebar links — marcar activo según scroll
const sections = document.querySelectorAll('.dash-section');
const sidebarLinks = document.querySelectorAll('.sidebar-link');

const sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const id = entry.target.getAttribute('id');
            sidebarLinks.forEach(link => {
                link.classList.toggle('active', link.dataset.section === id);
            });
        }
    });
}, { rootMargin: '-40% 0px -55% 0px' });

sections.forEach(s => sectionObserver.observe(s));

// ─────────────────────────────────────────────────────────────
// RECOMENDACIONES
// ─────────────────────────────────────────────────────────────

async function loadRecommendations() {
    const grid = document.getElementById('recommendationsGrid');
    grid.innerHTML = '<div class="rec-loading"><div class="loading-spinner" style="width:32px;height:32px"></div><p>Generando recomendaciones...</p></div>';
    try {
        const data = await apiFetch('/api/recommendations');
        renderRecommendations(data);
    } catch (err) {
        grid.innerHTML = `<p style="color:var(--text-muted);padding:2rem">❌ Error: ${err.message}</p>`;
    }
}

// Botón de actualizar recomendaciones
const refreshBtn = document.getElementById('refreshRecommendations');
if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
        refreshBtn.disabled = true;
        setTimeout(() => refreshBtn.disabled = false, 5000);
        loadRecommendations();
    });
}

// ─────────────────────────────────────────────────────────────
// INICIO
// ─────────────────────────────────────────────────────────────
loadDashboard();
