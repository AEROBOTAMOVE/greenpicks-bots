/* The Green Room · service worker — само за да е инсталируемо и черупката да
   отваря бързо. Данните (/api/*) НИКОГА не се кешират — винаги свежи от мрежата. */
const KESH = "gr-shell-v2";
const CHERUPKA = ["/", "/app.css", "/app.js", "/logo.svg", "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(KESH).then((c) => c.addAll(CHERUPKA)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== KESH).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
// Push известия (изпращат се от бота с web-push + VAPID ключовете)
self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = { telo: e.data ? e.data.text() : "" }; }
  const zag = d.zaglavie || "The Green Room";
  const opt = { body: d.telo || d.body || "", icon: "/img/app-icon.png", badge: "/logo.svg", data: { url: d.url || "/" }, tag: d.tag || "gr" };
  e.waitUntil(self.registration.showNotification(zag, opt));
});
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((cs) => {
    for (const c of cs) { if (c.url.indexOf(location.origin) === 0 && "focus" in c) return c.focus(); }
    if (self.clients.openWindow) return self.clients.openWindow(url);
  }));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/")) return; // данните минават направо към мрежата
  // черупката: мрежата води, кешът е резерва при офлайн
  e.respondWith(
    fetch(req).then((r) => {
      if (r && r.ok) { const cp = r.clone(); caches.open(KESH).then((c) => c.put(req, cp)); }
      return r;
    }).catch(() => caches.match(req).then((m) => m || caches.match("/")))
  );
});
