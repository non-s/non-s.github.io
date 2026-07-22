// Pixabay Video API & Visual Background Player

import { CONFIG } from './config.js';

// High quality default fallback background video loops
const FALLBACK_VIDEOS = [
    {
        id: 'rain-1',
        title: 'Chuva na Janela',
        thumbnail: 'https://images.unsplash.com/photo-1515694346937-94d85e41e6f0?w=400&q=80',
        videoUrl: 'https://cdn.pixabay.com/video/2020/05/25/40149-425173738_tiny.mp4'
    },
    {
        id: 'forest-1',
        title: 'Floresta Serena',
        thumbnail: 'https://images.unsplash.com/photo-1448375240586-882707db888b?w=400&q=80',
        videoUrl: 'https://cdn.pixabay.com/video/2019/04/20/22906-331828751_tiny.mp4'
    },
    {
        id: 'fireplace-1',
        title: 'Lareira Aconchegante',
        thumbnail: 'https://images.unsplash.com/photo-1542296332-2e4473faf563?w=400&q=80',
        videoUrl: 'https://cdn.pixabay.com/video/2016/09/21/5393-183787723_tiny.mp4'
    },
    {
        id: 'ocean-1',
        title: 'Ondas do Mar',
        thumbnail: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=400&q=80',
        videoUrl: 'https://cdn.pixabay.com/video/2020/06/18/42436-433060423_tiny.mp4'
    },
    {
        id: 'space-1',
        title: 'Céu Estrelado',
        thumbnail: 'https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?w=400&q=80',
        videoUrl: 'https://cdn.pixabay.com/video/2020/09/24/50952-463870643_tiny.mp4'
    }
];

export async function searchPixabayVideos(query = 'rain') {
    const apiKey = CONFIG.PIXABAY_API_KEY;
    if (apiKey) {
        try {
            const url = `https://pixabay.com/api/videos/?key=${apiKey}&q=${encodeURIComponent(query)}&per_page=12&video_type=film`;
            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                if (data.hits && data.hits.length > 0) {
                    return data.hits.map(item => ({
                        id: item.id,
                        title: item.tags,
                        thumbnail: item.userImageURL || `https://i.vimeocdn.com/video/${item.picture_id}_640x360.jpg`,
                        videoUrl: item.videos.tiny.url || item.videos.small.url
                    }));
                }
            }
        } catch (err) {
            console.warn("Pixabay API fetch error, returning default fallback videos:", err);
        }
    }
    return FALLBACK_VIDEOS;
}

export function renderPixabayGrid(videos, containerEl, onSelectVideo) {
    containerEl.innerHTML = '';

    if (!videos || videos.length === 0) {
        containerEl.innerHTML = '<div class="loading-placeholder">Nenhum vídeo encontrado.</div>';
        return;
    }

    videos.forEach(video => {
        const card = document.createElement('div');
        card.className = 'video-card';
        card.innerHTML = `
            <img src="${video.thumbnail}" alt="${video.title}" loading="lazy" onerror="this.src='https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=400&q=80'">
            <div class="play-badge">
                <i class="fa-solid fa-play"></i>
            </div>
        `;
        card.addEventListener('click', () => {
            onSelectVideo(video);
        });
        containerEl.appendChild(card);
    });
}
