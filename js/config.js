// Config & API Keys Manager

const STORAGE_KEYS = {
    GEMINI_KEY: 'aurazen_gemini_key',
    PIXABAY_KEY: 'aurazen_pixabay_key',
    JAMENDO_KEY: 'aurazen_jamendo_key'
};

// Default public API credentials / demo keys
export const CONFIG = {
    // Default demo Jamendo client ID
    JAMENDO_CLIENT_ID: localStorage.getItem(STORAGE_KEYS.JAMENDO_KEY) || 'b67d9e69',
    
    // Pixabay default key (Public key for web applications)
    PIXABAY_API_KEY: localStorage.getItem(STORAGE_KEYS.PIXABAY_KEY) || '48291039-b9d9df3c96d5b06f8cfa40a92',
    
    // Gemini API Key
    GEMINI_API_KEY: localStorage.getItem(STORAGE_KEYS.GEMINI_KEY) || ''
};

export function saveApiKeys(geminiKey, pixabayKey, jamendoKey) {
    if (geminiKey !== undefined) {
        localStorage.setItem(STORAGE_KEYS.GEMINI_KEY, geminiKey.trim());
        CONFIG.GEMINI_API_KEY = geminiKey.trim();
    }
    if (pixabayKey !== undefined) {
        localStorage.setItem(STORAGE_KEYS.PIXABAY_KEY, pixabayKey.trim());
        CONFIG.PIXABAY_API_KEY = pixabayKey.trim();
    }
    if (jamendoKey !== undefined) {
        localStorage.setItem(STORAGE_KEYS.JAMENDO_KEY, jamendoKey.trim());
        CONFIG.JAMENDO_CLIENT_ID = jamendoKey.trim();
    }
}

export function loadStoredKeys() {
    return {
        gemini: localStorage.getItem(STORAGE_KEYS.GEMINI_KEY) || '',
        pixabay: localStorage.getItem(STORAGE_KEYS.PIXABAY_KEY) || '',
        jamendo: localStorage.getItem(STORAGE_KEYS.JAMENDO_KEY) || ''
    };
}
