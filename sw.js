// GlobalBR News — Service Worker v4
// Stale-while-revalidate for article pages, cache-first for assets,
// cache-then-network for homepage, offline fallback with cached articles by category,
// background sync for saving offline reads.

const CACHE_NAME        = 'globalbr-v4';
const ARTICLE_CACHE     = 'globalbr-articles-v4';
const OFFLINE           = '/offline.html';
const MAX_ARTICLE_CACHE = 50;
const SYNC_TAG          = 'globalbr-offline-reads';

const STATIC_ASSETS = [
  '/',
  OFFLINE,
  '/assets/css/style.css',
  '/assets/js/main.js',
  '/assets/js/post.js',
  '/assets/js/index.js',
  '/manifest.json',
  '/search/',
  '/reading-list/',
];

// ── Install: pre-cache static shell ──────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(c => c.addAll(STATIC_ASSETS).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: clean up old caches ────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => !k.startsWith('globalbr-') || (k !== CACHE_NAME && k !== ARTICLE_CACHE))
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Helpers ───────────────────────────────────────────────────

// Broadcast last-online timestamp to all window clients
function broadcastLastOnline() {
  self.clients.matchAll({ type: 'window' }).then(clients => {
    clients.forEach(client => {
      client.postMessage({ type: 'LAST_ONLINE', ts: Date.now() });
    });
  });
}

function trimArticleCache(cache) {
  cache.keys().then(keys => {
    if (keys.length > MAX_ARTICLE_CACHE) {
      // Delete oldest entries (FIFO) until within limit
      const toDelete = keys.slice(0, keys.length - MAX_ARTICLE_CACHE);
      toDelete.forEach(k => cache.delete(k));
    }
  });
}

// ── Fetch ─────────────────────────────────────────────────────
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Only handle same-origin GET requests
  if (e.request.method !== 'GET' || url.origin !== self.location.origin) return;

  // Static assets: cache-first
  if (url.pathname.startsWith('/assets/') || url.pathname === '/manifest.json') {
    e.respondWith(
      caches.match(e.request).then(r => r || fetch(e.request).then(resp => {
        if (resp.ok) {
          caches.open(CACHE_NAME).then(c => c.put(e.request, resp.clone()));
        }
        return resp;
      }))
    );
    return;
  }

  // Homepage (/): cache-then-network — serve cache instantly, update in background
  if (url.pathname === '/' || url.pathname === '/index.html') {
    e.respondWith(
      caches.open(CACHE_NAME).then(async cache => {
        const cached = await cache.match(e.request);
        const networkFetch = fetch(e.request).then(resp => {
          if (resp.ok) { cache.put(e.request, resp.clone()); broadcastLastOnline(); }
          return resp;
        }).catch(() => cached || caches.match(OFFLINE));
        // Return cached version immediately if available, else wait for network
        return cached || networkFetch;
      })
    );
    return;
  }

  // Article pages: stale-while-revalidate
  if (url.pathname.match(/\/\w[\w-]*\/\d{4}\/\d{2}\/\d{2}\//)) {
    e.respondWith(
      caches.open(ARTICLE_CACHE).then(async cache => {
        const cached = await cache.match(e.request);
        const fetchPromise = fetch(e.request).then(resp => {
          if (resp.ok) {
            cache.put(e.request, resp.clone());
            trimArticleCache(cache);
          }
          return resp;
        }).catch(() => cached || caches.match(OFFLINE));
        // Serve cached version immediately; update in background
        return cached || fetchPromise;
      })
    );
    return;
  }

  // Default: network-first with offline fallback
  e.respondWith(
    fetch(e.request)
      .then(resp => {
        if (resp.ok) {
          caches.open(CACHE_NAME).then(c => c.put(e.request, resp.clone()));
        }
        return resp;
      })
      .catch(() => caches.match(e.request).then(r => r || caches.match(OFFLINE)))
  );
});

// ── Background Sync: save offline reads ───────────────────────
self.addEventListener('sync', e => {
  if (e.tag === SYNC_TAG) {
    e.waitUntil(flushOfflineReads());
  }
});

async function flushOfflineReads() {
  // Notify all clients that connectivity has been restored
  const allClients = await self.clients.matchAll({ type: 'window' });
  allClients.forEach(client => {
    client.postMessage({ type: 'SYNC_COMPLETE', tag: SYNC_TAG });
  });
}

// ── Push notifications ────────────────────────────────────────
self.addEventListener('push', e => {
  if (!e.data) return;
  let d;
  try {
    d = e.data.json();
  } catch (_) {
    d = { title: 'GlobalBR News', body: e.data.text() };
  }
  e.waitUntil(
    self.registration.showNotification(d.title || 'GlobalBR News', {
      body:    d.body  || 'New article published',
      icon:    '/assets/images/logo.png',
      badge:   '/assets/images/logo.png',
      tag:     'globalbr-news',
      data:    { url: d.url || '/' },
      actions: [{ action: 'open', title: 'Read now' }],
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const target = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(self.clients.openWindow(target));
});
