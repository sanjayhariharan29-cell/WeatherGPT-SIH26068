// WeatherGPT Mobile Service Worker
const PREVIOUS_CACHE = "weathergpt-mobile-v1";
const CACHE_NAME = "weathergpt-mobile-v2-skyzen";
const ASSETS_TO_CACHE = [
  "/",
  "/index.html",
  "/styles.css",
  "/app.js",
  "/mobile/apiClient.js",
  "/manifest.json",
  "/assets/skyzen_official_logo.png"
];

// Install Event — Cache Core App Shell
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch((err) => {
        console.warn("Pre-caching warning:", err);
      });
    })
  );
  self.skipWaiting();
});

// Activate Event — Clean Old Caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch Event — Network First with Cache Fallback for API / Assets
self.addEventListener("fetch", (event) => {
  // Only handle GET requests
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);

  // API Requests: Network First, fallback to cached or offline error JSON
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          return response;
        })
        .catch(() => {
          return new Response(
            JSON.stringify({
              error: {
                code: "NETWORK_OFFLINE",
                message: "You are currently offline. Please check your internet connection."
              }
            }),
            {
              status: 503,
              headers: { "Content-Type": "application/json" }
            }
          );
        })
    );
    return;
  }

  // App Shell & Static Assets: Network First with Cache Fallback
  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      })
      .catch(() => caches.match(event.request))
  );
});
