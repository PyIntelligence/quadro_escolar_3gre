const CACHE_NAME = 'quadro-escolar-3gre-v1.0.0';

// Arquivos estáticos essenciais salvos na inicialização
const ESSENTIAL_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

// Instalação do Service Worker e salvamento seguro em cache
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        // Tenta cachear cada arquivo de forma independente sem travar a instalação caso algum falhe
        return Promise.allSettled(
          ESSENTIAL_ASSETS.map(url => 
            cache.add(url).catch(err => console.warn(`Aviso: Não foi possível cachear ${url}:`, err))
          )
        );
      })
      .then(() => self.skipWaiting())
  );
});

// Ativação e limpeza de versões antigas do cache
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log('Removendo cache antigo:', cache);
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Estratégia de busca: Network First com Fallback para Cache
self.addEventListener('fetch', (event) => {
  // Ignora requisições de alteração de dados (POST, PUT, DELETE)
  if (event.request.method !== 'GET') return;

  // Ignora requisições de extensões ou esquemas não-http
  if (!event.request.url.startsWith('http')) return;

  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        // Se houver conexão e a resposta for 200 OK, atualiza o cache local
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      })
      .catch(() => {
        // Se a rede falhar ou estiver offline, busca do cache
        return caches.match(event.request);
      })
  );
});