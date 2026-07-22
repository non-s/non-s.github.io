// Jamendo Royalty-Free Music API & Audio Player

import { CONFIG } from './config.js';

// Curated high quality fallback relaxing audio streams
const FALLBACK_TRACKS = [
    {
        id: 'jam-1',
        title: 'Deep Meditation & Ocean Waves',
        artist: 'Relaxing Mind Studio',
        genre: 'Meditation',
        audioUrl: 'https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3?filename=meditation-piano-112015.mp3'
    },
    {
        id: 'jam-2',
        title: 'Calm Night Lo-Fi Chill',
        artist: 'AuraZen Beats',
        genre: 'Lo-Fi',
        audioUrl: 'https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a73467.mp3?filename=soft-rain-ambient-111154.mp3'
    },
    {
        id: 'jam-3',
        title: 'Peaceful Forest Ambient',
        artist: 'Nature Echoes',
        genre: 'Ambient',
        audioUrl: 'https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0a13f69d2.mp3?filename=relaxing-mountains-rivers-141322.mp3'
    },
    {
        id: 'jam-4',
        title: 'Soft Piano & Evening Glow',
        artist: 'Serenity Keys',
        genre: 'Piano',
        audioUrl: 'https://cdn.pixabay.com/download/audio/2022/11/06/audio_c6f2a89366.mp3?filename=deep-relax-piano-126262.mp3'
    }
];

export async function searchJamendoTracks(tag = 'meditation') {
    const clientId = CONFIG.JAMENDO_CLIENT_ID;
    if (clientId) {
        try {
            const url = `https://api.jamendo.com/v3.0/tracks/?client_id=${clientId}&format=json&limit=15&tags=${encodeURIComponent(tag)}&audioformat=mp32`;
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                if (data.results && data.results.length > 0) {
                    return data.results.map(track => ({
                        id: track.id,
                        title: track.name,
                        artist: track.artist_name,
                        genre: tag,
                        audioUrl: track.audio
                    }));
                }
            }
        } catch (err) {
            console.warn("Jamendo API fetch error, returning fallback tracks:", err);
        }
    }
    return FALLBACK_TRACKS;
}

export function renderJamendoList(tracks, containerEl, onSelectTrack, onPreviewTrack) {
    containerEl.innerHTML = '';

    if (!tracks || tracks.length === 0) {
        containerEl.innerHTML = '<div class="loading-placeholder">Nenhuma música encontrada.</div>';
        return;
    }

    tracks.forEach(track => {
        const item = document.createElement('div');
        item.className = 'track-card';
        item.innerHTML = `
            <div class="track-icon btn-play-preview" title="Ouvir prévia">
                <i class="fa-solid fa-play"></i>
            </div>
            <div class="track-info">
                <div class="track-title">${track.title}</div>
                <div class="track-artist">${track.artist}</div>
            </div>
            <button class="btn-select-track">Usar no Mix</button>
        `;

        const playBtn = item.querySelector('.btn-play-preview');
        playBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            onPreviewTrack(track, playBtn);
        });

        const selectBtn = item.querySelector('.btn-select-track');
        selectBtn.addEventListener('click', () => {
            onSelectTrack(track);
        });

        containerEl.appendChild(item);
    });
}
