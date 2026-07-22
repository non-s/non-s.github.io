// Web Speech Synthesis TTS Engine

let synth = window.speechSynthesis;
let currentUtterance = null;
let ptVoice = null;

export function initSpeechVoices(voiceSelectEl) {
    if (!('speechSynthesis' in window)) {
        if (voiceSelectEl) {
            voiceSelectEl.innerHTML = '<option value="">TTS não suportado no navegador</option>';
        }
        return;
    }

    function populateVoices() {
        const voices = synth.getVoices();
        if (voiceSelectEl) {
            voiceSelectEl.innerHTML = '';
            
            // Prefer Portuguese voices (pt-BR, pt-PT)
            const ptVoices = voices.filter(v => v.lang.startsWith('pt'));
            const listToUse = ptVoices.length > 0 ? ptVoices : voices;

            listToUse.forEach((v, index) => {
                const option = document.createElement('option');
                option.value = v.name;
                option.textContent = `${v.name} (${v.lang})`;
                if (v.lang === 'pt-BR' && !ptVoice) {
                    ptVoice = v;
                    option.selected = true;
                }
                voiceSelectEl.appendChild(option);
            });

            if (!ptVoice && listToUse.length > 0) {
                ptVoice = listToUse[0];
            }
        }
    }

    populateVoices();
    if (speechSynthesis.onvoiceschanged !== undefined) {
        speechSynthesis.onvoiceschanged = populateVoices;
    }
}

export function speakScript(text, voiceName, volume = 1.0, onBoundary = null, onEnd = null) {
    stopSpeech();

    if (!text || !text.trim()) return;

    currentUtterance = new SpeechSynthesisUtterance(text);
    currentUtterance.rate = 0.92; // Slightly calm and relaxed speed
    currentUtterance.pitch = 0.98; // Relaxing pitch
    currentUtterance.volume = volume;

    if (voiceName) {
        const voices = synth.getVoices();
        const selected = voices.find(v => v.name === voiceName);
        if (selected) {
            currentUtterance.voice = selected;
        }
    } else if (ptVoice) {
        currentUtterance.voice = ptVoice;
    }

    if (onBoundary) {
        currentUtterance.onboundary = (event) => {
            onBoundary(event);
        };
    }

    if (onEnd) {
        currentUtterance.onend = () => {
            onEnd();
        };
    }

    synth.speak(currentUtterance);
}

export function stopSpeech() {
    if (synth && synth.speaking) {
        synth.cancel();
    }
}

export function setSpeechVolume(vol) {
    if (currentUtterance) {
        currentUtterance.volume = vol;
    }
}
