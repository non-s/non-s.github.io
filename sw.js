// GlobalBR News — Service Worker
// Caches shell assets for offline access; always fetches fresh news from network.

const CACHE    = "globalbr-v1";
const OFFLINE  = "/offline.html";

// Assets to cache on install
const SHELL = [
  "/",
  "/assets/css/style.css",
  "/assets/images/logo.png",
  "/favicon.ico",
  OFFLINE,
];

self.addEventListener("install", (e) => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL).catch(() => {}))
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const { request } = e;
  const url = new URL(request.url);

  // Only handle same-origin GET requests
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  // News pages: network-first, fall back to cache, then offline page
  if (url.pathname.match(/\/\d{4}\/\d{2}\/\d{2}\//)) {
    e.respondWith(
      fetch(request)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(request, clone));
          return res;
        })
        .catch(() =>
          caches.match(request).then((cached) => cached || caches.match(OFFLINE))
        )
    );
    return;
  }

  // Static assets: cache-first
  e.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ||
        fetch(request).then((res) => {
          if (res.ok) {
            const clone = res.clone();
            caches.open(CACHE).then((c) => c.put(request, clone));
          }
          return res;
        })
    )
  );
});

// Push notification handler
self.addEventListener("push", (e) => {
  if (!e.data) return;
  const data = e.data.json().catch(() => ({ title: "GlobalBR News", body: e.data.text() }));
  e.waitUntil(
    data.then((d) =>
      self.registration.showNotification(d.title || "GlobalBR News", {
        body:    d.body  || "New article published",
        icon:    "/assets/images/logo.png",
        badge:   "/assets/images/logo.png",
        tag:     "globalbr-news",
        data:    { url: d.url || "/" },
        actions: [{ action: "open", title: "Read now" }],
      })
    )
  );
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const target = e.notification.data?.url || "/";
  e.waitUntil(clients.openWindow(target));
});
