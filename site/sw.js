/* Service worker voor Wandeltochten.
 *
 * Strategie:
 * - Eigen bestanden (pagina, app.js, style.css, config, tochten.json, iconen):
 *   eerst het netwerk, bij geen verbinding (of na 6 s) de opgeslagen versie.
 *   Zo ziet de gebruiker altijd de nieuwste versie als er bereik is.
 * - Libraries en lettertype van de CDN (vaste versies): uit de cache, anders netwerk.
 * - Kaarttegels (OpenStreetMap) en adres zoeken (Nominatim): niet opslaan.
 *
 * VERSION wordt bij elke deploy door de workflow vervangen door de commit-hash.
 */
const VERSION = "dev";
const CACHE = "wandeltochten-" + VERSION;
const CDN_CACHE = "wandeltochten-cdn-v1";
const TIMEOUT_MS = 6000;

const SHELL = [
  "./",
  "index.html",
  "style.css?v=" + VERSION,
  "app.js?v=" + VERSION,
  "config.json",
  "data/tochten.json",
  "manifest.webmanifest",
  "icon.svg",
  "icons/icon-192.png",
  "icons/apple-touch-icon.png",
];

const CDN_HOSTS = ["cdnjs.cloudflare.com", "fonts.googleapis.com", "fonts.gstatic.com"];

// Vaste versies; moeten gelijk zijn aan index.html.
const CDN_FILES = [
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.min.css",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.min.js",
  "https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap",
];

async function precacheCdn() {
  const cache = await caches.open(CDN_CACHE);
  await Promise.all(CDN_FILES.map(async (u) => {
    try {
      if (await cache.match(u)) return;
      const resp = await fetch(new Request(u, { mode: "cors", credentials: "omit" }));
      if (resp.ok) await cache.put(u, resp);
    } catch (e) { /* niet fataal: wordt later alsnog opgeslagen */ }
  }));
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(SHELL.map((u) => new Request(u, { cache: "reload" }))))
      .then(precacheCdn)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys
        .filter((k) => k.startsWith("wandeltochten-") && k !== CACHE && k !== CDN_CACHE)
        .map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function markOffline(resp) {
  // Laat de app weten dat dit een opgeslagen versie is.
  const headers = new Headers(resp.headers);
  headers.set("X-Offline-Cache", "1");
  return resp.blob().then((body) => new Response(body, { status: resp.status, statusText: resp.statusText, headers }));
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE);
  // Zoeken zonder query (?v=, ?r=) zodat ook een oudere versie als noodoplossing werkt.
  const cached = () => cache.match(request).then((r) => r || cache.match(request, { ignoreSearch: true }));
  const network = fetch(request).then((resp) => {
    if (resp.ok) cache.put(request, resp.clone());
    return resp;
  });
  network.catch(() => {}); // fout wordt hieronder afgehandeld
  const timeout = new Promise((resolve) => setTimeout(resolve, TIMEOUT_MS));
  try {
    const first = await Promise.race([network, timeout]);
    if (first) return first;
    const old = await cached();
    if (old) return markOffline(old);
    return await network;
  } catch (e) {
    const old = await cached();
    if (old) return markOffline(old);
    if (request.mode === "navigate") {
      const page = await cache.match("index.html");
      if (page) return page;
    }
    throw e;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CDN_CACHE);
  const hit = await cache.match(request);
  if (hit) return hit;
  const resp = await fetch(request);
  if (resp.ok || resp.type === "opaque") cache.put(request, resp.clone());
  return resp;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  if (url.origin === self.location.origin) {
    // Alleen bestanden binnen de app (scope), niet de rest van het domein.
    if (!url.pathname.startsWith(new URL(self.registration.scope).pathname)) return;
    event.respondWith(networkFirst(req));
    return;
  }
  if (CDN_HOSTS.includes(url.hostname)) {
    event.respondWith(cacheFirst(req));
  }
  // Overige verzoeken (kaarttegels, Nominatim) gaan gewoon naar het netwerk.
});
