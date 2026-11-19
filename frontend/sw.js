// Pepito: apertura immediata e uso senza rete (es. al supermercato).
// - pagina e icone: prima la rete, se non risponde la copia salvata;
// - ricette e volantini: subito la copia salvata, intanto si scarica quella
//   nuova; se è cambiata l'app viene avvisata e si aggiorna da sola.
const VERSION = 'pepito-v1';
const SHELL = ['/', '/manifest.webmanifest', '/icons/apple-touch-icon.png', '/icons/icon-192.png', '/icons/favicon-64.png'];
const DATI = ['/api/recipes', '/api/volantini'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function avvisa(path) {
  const clients = await self.clients.matchAll({ type: 'window' });
  clients.forEach(c => c.postMessage({ type: 'dati-aggiornati', path }));
}

async function datiConAggiornamento(request, event) {
  const cache = await caches.open(VERSION);
  const key = new URL(request.url).pathname;
  const salvata = await cache.match(key);
  const rete = fetch(request, { cache: 'no-store' }).then(async res => {
    if (res.ok) {
      const nuovo = await res.clone().text();
      const vecchio = salvata ? await salvata.clone().text() : null;
      await cache.put(key, res.clone());
      if (salvata && nuovo !== vecchio) await avvisa(key);
    }
    return res;
  });
  if (salvata) {
    event.waitUntil(rete.catch(() => {}));
    return salvata;
  }
  return rete;
}

async function primaLaRete(request) {
  const cache = await caches.open(VERSION);
  const key = new URL(request.url).pathname;
  try {
    const res = await fetch(request);
    if (res.ok) await cache.put(key, res.clone());
    return res;
  } catch (e) {
    const salvata = await cache.match(key) || (request.mode === 'navigate' ? await cache.match('/') : null);
    if (salvata) return salvata;
    throw e;
  }
}

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // foto e siti esterni: come sempre
  if (DATI.includes(url.pathname)) { event.respondWith(datiConAggiornamento(req, event)); return; }
  if (req.mode === 'navigate' || SHELL.includes(url.pathname)) event.respondWith(primaLaRete(req));
});
