const CACHE_NAME = 'quadro-aulas-v1.0.0';

// Arquivos estáticos essenciais para funcionamento offline
const ASSETS_TO_CACHE = [
  '/',
  '/login',
  '/static/manifest.json',
  '/api/versao-cache'
];

// Instalação e armazenamento do cache inicial
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    }).then(() => self.skipWaiting())
  );
});

// Ativação e limpeza de caches antigos
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Estratégia de Fetch: Network First com Fallback para Cache
self.addEventListener('fetch', (event) => {
  // Ignora requisições POST/PUT/DELETE no cache
  if (event.request.method !== 'GET') return;

  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        // Atualiza o cache dinamicamente para requisições bem-sucedidas
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      })
      .catch(() => {
        // Se a rede falhar, busca no cache
        return caches.match(event.request);
      })
  );
});