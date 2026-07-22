// Main Studio App Controller

import { CONFIG, saveApiKeys, loadStoredKeys } from './config.js';
import { generateContentWithGemini } from './gemini.js';
import { searchPixabayVideos, renderPixabayGrid } from './pixabay.js';
import { searchJamendoTracks, renderJamendoList } from './jamendo.js';
import { initSpeechVoices, speakScript, stopSpeech } from './speech.js';

// Application State
const state = {
    themeKey: 'meditation',
    isPlaying: false,
    activeVideo: null,
    activeTrack: null,
    generatedScript: '',
    previewAudioElement: new Audio()
};

// DOM Elements
const elements = {
    // Header & Modal
    btnApiConfig: document.getElementById('btn-api-config'),
    apiModal: document.getElementById('api-modal'),
    btnCloseModal: document.getElementById('btn-close-modal'),
    btnSaveKeys: document.getElementById('btn-save-keys'),
    inputGeminiKey: document.getElementById('api-key-gemini'),
    inputPixabayKey: document.getElementById('api-key-pixabay'),
    inputJamendoKey: document.getElementById('api-key-jamendo'),
    statusText: document.getElementById('status-text'),

    // Gemini Left Panel
    presetChips: document.getElementById('preset-chips'),
    customPrompt: document.getElementById('custom-prompt'),
    scriptTone: document.getElementById('script-tone'),
    scriptLength: document.getElementById('script-length'),
    btnGenerateScript: document.getElementById('btn-generate-script'),
    scriptText: document.getElementById('script-text'),
    ytTitle: document.getElementById('yt-title'),
    ytDescription: document.getElementById('yt-description'),
    ytTags: document.getElementById('yt-tags'),
    voiceSelect: document.getElementById('voice-select'),
    btnPlayTts: document.getElementById('btn-play-tts'),

    // Studio Center Panel
    studioVideo: document.getElementById('studio-video'),
    studioAudio: document.getElementById('studio-audio'),
    scriptOverlay: document.getElementById('script-overlay'),
    overlayText: document.getElementById('overlay-text'),
    btnTogglePlay: document.getElementById('btn-toggle-play'),
    btnStartMix: document.getElementById('btn-start-mix'),
    badgeVideoName: document.getElementById('badge-video-name'),
    badgeAudioName: document.getElementById('badge-audio-name'),
    volMusic: document.getElementById('volume-music'),
    volNarration: document.getElementById('volume-narration'),
    volAmbient: document.getElementById('volume-ambient'),
    valMusic: document.getElementById('val-music'),
    valNarration: document.getElementById('val-narration'),
    valAmbient: document.getElementById('val-ambient'),

    // Media Explorer Right Panel
    searchPixabay: document.getElementById('search-pixabay'),
    btnSearchPixabay: document.getElementById('btn-search-pixabay'),
    pixabayGrid: document.getElementById('pixabay-grid'),
    pixabayQuickTags: document.getElementById('pixabay-quick-tags'),
    
    searchJamendo: document.getElementById('search-jamendo'),
    btnSearchJamendo: document.getElementById('btn-search-jamendo'),
    jamendoList: document.getElementById('jamendo-list'),
    jamendoQuickTags: document.getElementById('jamendo-quick-tags'),

    toastContainer: document.getElementById('toast-container')
};

// INITIALIZATION
document.addEventListener('DOMContentLoaded', async () => {
    initModal();
    initTabs();
    initCopyButtons();
    initSpeechVoices(elements.voiceSelect);
    initMixerControls();

    // Load initial media and default script
    await loadInitialPixabayMedia('rain');
    await loadInitialJamendoMedia('meditation');
    
    // Auto-generate initial script
    handleGenerateScript();
});

// MODAL HANDLERS
function initModal() {
    elements.btnApiConfig.addEventListener('click', () => {
        const keys = loadStoredKeys();
        elements.inputGeminiKey.value = keys.gemini;
        elements.inputPixabayKey.value = keys.pixabay;
        elements.inputJamendoKey.value = keys.jamendo;
        elements.apiModal.classList.add('active');
    });

    elements.btnCloseModal.addEventListener('click', () => {
        elements.apiModal.classList.remove('active');
    });

    elements.btnSaveKeys.addEventListener('click', () => {
        saveApiKeys(
            elements.inputGeminiKey.value,
            elements.inputPixabayKey.value,
            elements.inputJamendoKey.value
        );
        elements.apiModal.classList.remove('active');
        showToast('Chaves de API salvas com sucesso!');
    });
}

// TAB SYSTEM
function initTabs() {
    // Left Output Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            const targetId = `tab-${btn.dataset.tab}`;
            document.getElementById(targetId).classList.add('active');
        });
    });

    // Right Media Tabs
    document.querySelectorAll('.media-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.media-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.media-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const targetId = `mediatab-${btn.dataset.mediatab}`;
            document.getElementById(targetId).classList.add('active');
        });
    });

    // Preset Chips Selection
    elements.presetChips.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            elements.presetChips.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            state.themeKey = chip.dataset.theme;
            handleGenerateScript();
        });
    });
}

// COPY TO CLIPBOARD
function initCopyButtons() {
    document.querySelectorAll('.btn-copy').forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.target;
            const targetEl = document.getElementById(targetId);
            if (targetEl) {
                const text = targetEl.value || targetEl.innerText;
                navigator.clipboard.writeText(text).then(() => {
                    showToast('Copiado para a área de transferência! 📋');
                });
            }
        });
    });
}

// SCRIPT GENERATION (GEMINI)
async function handleGenerateScript() {
    elements.btnGenerateScript.disabled = true;
    elements.btnGenerateScript.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Gerando com Gemini...</span>';
    elements.statusText.textContent = 'Gerando Roteiro...';

    try {
        const result = await generateContentWithGemini(
            state.themeKey,
            elements.customPrompt.value,
            elements.scriptTone.value,
            elements.scriptLength.value
        );

        state.generatedScript = result.script;
        elements.scriptText.innerText = result.script;
        elements.overlayText.innerText = result.title;

        elements.ytTitle.value = result.title;
        elements.ytDescription.value = `${result.description}\n\n${result.tags}`;
        elements.ytTags.value = result.tags;

        showToast('Novo roteiro gerado pela IA!');
    } catch (err) {
        showToast('Erro ao gerar roteiro. Tente novamente.');
        console.error(err);
    } finally {
        elements.btnGenerateScript.disabled = false;
        elements.btnGenerateScript.innerHTML = '<i class="fa-solid fa-sparkles"></i> <span>Gerar Roteiro & Metadados</span>';
        elements.statusText.textContent = 'Studio Pronto';
    }
}
elements.btnGenerateScript.addEventListener('click', handleGenerateScript);

// TTS NARRATION
elements.btnPlayTts.addEventListener('click', () => {
    if (elements.scriptText.innerText) {
        speakScript(
            elements.scriptText.innerText,
            elements.voiceSelect.value,
            parseFloat(elements.volNarration.value)
        );
        showToast('Testando narração do roteiro...');
    }
});

// MEDIA LOADING & EVENTS
async function loadInitialPixabayMedia(query) {
    const videos = await searchPixabayVideos(query);
    renderPixabayGrid(videos, elements.pixabayGrid, (selectedVideo) => {
        state.activeVideo = selectedVideo;
        elements.studioVideo.src = selectedVideo.videoUrl;
        elements.studioVideo.play();
        elements.badgeVideoName.innerHTML = `<i class="fa-solid fa-video"></i> Vídeo: ${selectedVideo.title.substring(0, 15)}...`;
        showToast('Vídeo selecionado!');
    });
}

async function loadInitialJamendoMedia(tag) {
    const tracks = await searchJamendoTracks(tag);
    renderJamendoList(
        tracks,
        elements.jamendoList,
        (selectedTrack) => {
            state.activeTrack = selectedTrack;
            elements.studioAudio.src = selectedTrack.audioUrl;
            elements.studioAudio.volume = parseFloat(elements.volMusic.value);
            if (state.isPlaying) {
                elements.studioAudio.play();
            }
            elements.badgeAudioName.innerHTML = `<i class="fa-solid fa-music"></i> Áudio: ${selectedTrack.title}`;
            showToast('Música aplicada ao Studio Mix!');
        },
        (previewTrack, playBtn) => {
            if (state.previewAudioElement.src === previewTrack.audioUrl && !state.previewAudioElement.paused) {
                state.previewAudioElement.pause();
                playBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
            } else {
                state.previewAudioElement.src = previewTrack.audioUrl;
                state.previewAudioElement.play();
                playBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
            }
        }
    );
}

// SEARCH LISTENERS
elements.btnSearchPixabay.addEventListener('click', () => {
    loadInitialPixabayMedia(elements.searchPixabay.value || 'rain');
});

elements.pixabayQuickTags.querySelectorAll('.tag-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        loadInitialPixabayMedia(btn.dataset.query);
    });
});

elements.btnSearchJamendo.addEventListener('click', () => {
    loadInitialJamendoMedia(elements.searchJamendo.value || 'meditation');
});

elements.jamendoQuickTags.querySelectorAll('.tag-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        loadInitialJamendoMedia(btn.dataset.genre);
    });
});

// MIXER & PLAYBACK CONTROLS
function initMixerControls() {
    elements.volMusic.addEventListener('input', (e) => {
        const val = e.target.value;
        elements.studioAudio.volume = parseFloat(val);
        elements.valMusic.textContent = `${Math.round(val * 100)}%`;
    });

    elements.volNarration.addEventListener('input', (e) => {
        const val = e.target.value;
        elements.valNarration.textContent = `${Math.round(val * 100)}%`;
    });

    elements.volAmbient.addEventListener('input', (e) => {
        const val = e.target.value;
        elements.valAmbient.textContent = `${Math.round(val * 100)}%`;
    });

    elements.btnTogglePlay.addEventListener('click', toggleStudioMix);
    elements.btnStartMix.addEventListener('click', toggleStudioMix);
}

function toggleStudioMix() {
    if (state.isPlaying) {
        // Pause All
        elements.studioVideo.pause();
        elements.studioAudio.pause();
        stopSpeech();
        state.isPlaying = false;
        elements.btnTogglePlay.innerHTML = '<i class="fa-solid fa-play"></i>';
        elements.btnStartMix.innerHTML = '<i class="fa-solid fa-circle-play"></i> Reproduzir Studio Mix Completo';
        showToast('Mix Pausado');
    } else {
        // Start All in Sync
        elements.studioVideo.play();
        if (elements.studioAudio.src) {
            elements.studioAudio.play();
        }
        if (state.generatedScript) {
            speakScript(
                state.generatedScript,
                elements.voiceSelect.value,
                parseFloat(elements.volNarration.value)
            );
        }
        state.isPlaying = true;
        elements.btnTogglePlay.innerHTML = '<i class="fa-solid fa-pause"></i>';
        elements.btnStartMix.innerHTML = '<i class="fa-solid fa-circle-pause"></i> Pausar Studio Mix Completo';
        showToast('Tocando Studio Mix (Vídeo + Áudio + Narração)! 🎬');
    }
}

// TOAST HELPER
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, 3000);
}
