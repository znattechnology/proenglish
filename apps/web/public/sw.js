/*
 * Service worker do ProEnglish.
 *
 * - Guarda só o que é estático (CSS, JS, ícones, fontes) e a página "Sem ligação".
 *   As páginas com dados da conta e a API nunca ficam guardadas no telemóvel.
 * - Sem Internet, a navegação mostra /offline.
 * - Uma versão nova só entra quando a app pede (botão "Actualizar"), nunca a meio de uma lição.
 *
 * Mude VERSAO a cada publicação que altere este ficheiro ou a página /offline.
 */
const VERSAO = "2026-11-14.4";
const CACHE = `pe-estatico-${VERSAO}`;
const OFFLINE = "/offline";
const DEV = new URL(self.location.href).searchParams.get("dev") === "1";

const ESTATICOS = ["/icons/app-192.png", "/icons/app-512.png", "/logo/Logo_azul.png"];

async function guardarOffline(cache) {
  const r = await fetch(OFFLINE, { cache: "no-store" });
  if (!r.ok) return;
  await cache.put(OFFLINE, r.clone());
  // A página sem ligação precisa do seu CSS: guarda as folhas de estilo que ela pede.
  const html = await r.text();
  const css = [...html.matchAll(/href="(\/_next\/static\/[^"]+\.css)"/g)].map((m) => m[1]);
  await Promise.all(css.map((u) => cache.add(u).catch(() => {})));
}

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then(async (cache) => {
      await Promise.all(ESTATICOS.map((u) => cache.add(u).catch(() => {})));
      await guardarOffline(cache).catch(() => {});
    })
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    (async () => {
      const nomes = await caches.keys();
      await Promise.all(nomes.filter((n) => n.startsWith("pe-") && n !== CACHE).map((n) => caches.delete(n)));
      await self.clients.claim();
    })()
  );
});

self.addEventListener("message", (e) => {
  if (e.data && e.data.tipo === "actualizar") self.skipWaiting();
});

function eEstatico(url) {
  return url.pathname.startsWith("/_next/static/") || /^\/(icons|logo|fonts)\//.test(url.pathname);
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // API e serviços externos: sem intervenção

  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req).catch(async () => (await caches.match(OFFLINE)) || new Response("Sem ligação à Internet.", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } }))
    );
    return;
  }

  // Em desenvolvimento os ficheiros mudam sem mudar de nome: primeiro a rede, a cópia só sem ligação.
  if (DEV && url.pathname.startsWith("/_next/static/")) {
    e.respondWith(fetch(req).catch(() => caches.match(req).then((r) => r || Response.error())));
    return;
  }

  if (eEstatico(url)) {
    e.respondWith(
      caches.match(req).then(
        (guardado) =>
          guardado ||
          fetch(req).then((r) => {
            if (r.ok) {
              const copia = r.clone();
              caches.open(CACHE).then((c) => c.put(req, copia));
            }
            return r;
          })
      )
    );
  }
});

/* ------------------------------------------------------------------ */
/* Notificações push (lembrete da meta diária e outros avisos)          */
/* ------------------------------------------------------------------ */
self.addEventListener("push", (e) => {
  let d = {};
  try {
    d = e.data ? e.data.json() : {};
  } catch {
    d = { title: "ProEnglish", body: e.data ? e.data.text() : "" };
  }
  const link = typeof d.link === "string" && d.link.startsWith("/") ? d.link : "/user/notifications";
  e.waitUntil(
    self.registration.showNotification(d.title || "ProEnglish", {
      body: d.body || "",
      icon: "/icons/app-192.png",
      badge: "/icons/app-192.png",
      tag: d.tag || undefined,
      lang: "pt-PT",
      data: { link },
    })
  );
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const link = (e.notification.data && e.notification.data.link) || "/user/notifications";
  e.waitUntil(
    (async () => {
      const janelas = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      // Não tira ninguém do meio de uma lição ou de uma conversa: usa outra janela ou abre uma nova.
      const ocupada = (u) => /\/laboratory\/learn\/lesson\/|\/speaking\/real-time|\/chapters\//.test(new URL(u).pathname);
      for (const j of janelas) {
        if (new URL(j.url).origin !== self.location.origin || ocupada(j.url)) continue;
        try {
          await j.focus();
          if ("navigate" in j) {
            const r = await j.navigate(link).catch(() => null);
            if (r) return r;
          }
        } catch {}
      }
      return self.clients.openWindow(link);
    })()
  );
});
