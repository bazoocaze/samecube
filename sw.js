/* Service worker for the Cubes PWA — the game is one HTML file, so the cache is
 * tiny: the page, the manifest and the icons.
 *
 * The page itself is network-first (an update lands on the next visit) and falls
 * back to the cache when offline; the other assets are cache-first.
 * Only same-origin GET requests are touched.
 */
const CACHE = 'cubes-v1';
const SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-512.png',
  './icons/apple-touch-icon.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    for (const u of SHELL) {
      try { await c.add(new URL(u, self.location)); } catch (_) {}   // a missing icon is not fatal
    }
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== CACHE) await caches.delete(k);
    self.clients.claim();
  })());
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;

  e.respondWith((async () => {
    const c = await caches.open(CACHE);

    if (req.mode === 'navigate') {
      try {
        const res = await fetch(req);
        c.put(req, res.clone());
        return res;
      } catch {
        return (await c.match(req)) || (await c.match(new URL('./index.html', self.location))) || Response.error();
      }
    }

    const hit = await c.match(req);
    if (hit) return hit;
    try {
      const res = await fetch(req);
      c.put(req, res.clone());
      return res;
    } catch {
      return Response.error();
    }
  })());
});
