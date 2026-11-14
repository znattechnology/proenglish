"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { Check, Download, Share, SquarePlus, WifiOff, X } from "lucide-react";
import { Botao } from "@/components/pe";

/**
 * A app instalável:
 * - regista o service worker (public/sw.js);
 * - avisa quando há uma versão nova, mas nunca a meio de uma lição ou de uma conversa;
 * - avisa quando a Internet cai;
 * - convida a instalar (Android: o pedido do browser; iPhone: os passos no Safari)
 *   depois da primeira lição concluída. "Agora não" adia 14 dias.
 */

type PedidoInstalar = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: "accepted" | "dismissed" }> };

const ADIAR_DIAS = 14;
const CHAVE_ADIADO = "pe_instalar_adiado_ate";

const emAtividade = (p: string) => p.includes("/laboratory/learn/lesson") || p.startsWith("/user/laboratory/speaking/real-time") || p.includes("/chapters/");
const instalada = () =>
  typeof window !== "undefined" && (window.matchMedia("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true);
const ler = (k: string) => {
  try {
    return localStorage.getItem(k);
  } catch {
    return null;
  }
};

export function AppInstalavel() {
  const pathname = usePathname() ?? "";
  const [espera, setEspera] = useState<ServiceWorker | null>(null);
  const [semNet, setSemNet] = useState(false);
  const [pedido, setPedido] = useState<PedidoInstalar | null>(null);
  const [mostrar, setMostrar] = useState<"android" | "iphone" | null>(null);
  const aActualizar = useRef(false);

  // Service worker e versão nova.
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const dev = process.env.NODE_ENV !== "production";
    navigator.serviceWorker
      .register(dev ? "/sw.js?dev=1" : "/sw.js", { scope: "/" })
      .then((reg) => {
        const verificar = () => {
          const w = reg.waiting;
          if (!w || !navigator.serviceWorker.controller) return;
          setEspera(w);
          // Se a versão nova entrar por outro separador, o aviso deixa de fazer sentido.
          w.addEventListener("statechange", () => {
            if (w.state === "activated" || w.state === "redundant") setEspera(null);
          });
        };
        verificar();
        reg.addEventListener("updatefound", () => {
          reg.installing?.addEventListener("statechange", verificar);
        });
        // Procura versões novas quando a app volta ao primeiro plano.
        const aoVoltar = () => document.visibilityState === "visible" && reg.update().catch(() => {});
        document.addEventListener("visibilitychange", aoVoltar);
      })
      .catch(() => {});
    const aoMudar = () => {
      setEspera(null);
      if (aActualizar.current) window.location.reload();
    };
    navigator.serviceWorker.addEventListener("controllerchange", aoMudar);
    return () => navigator.serviceWorker.removeEventListener("controllerchange", aoMudar);
  }, []);

  // Internet.
  useEffect(() => {
    const actualizar = () => setSemNet(!navigator.onLine);
    actualizar();
    window.addEventListener("online", actualizar);
    window.addEventListener("offline", actualizar);
    return () => {
      window.removeEventListener("online", actualizar);
      window.removeEventListener("offline", actualizar);
    };
  }, []);

  // Convite para instalar.
  useEffect(() => {
    const aoPedir = (e: Event) => {
      e.preventDefault(); // nós decidimos quando mostrar
      setPedido(e as PedidoInstalar);
    };
    const aoInstalar = () => {
      setPedido(null);
      setMostrar(null);
    };
    window.addEventListener("beforeinstallprompt", aoPedir);
    window.addEventListener("appinstalled", aoInstalar);
    return () => {
      window.removeEventListener("beforeinstallprompt", aoPedir);
      window.removeEventListener("appinstalled", aoInstalar);
    };
  }, []);

  useEffect(() => {
    if (!pathname.startsWith("/user/") || emAtividade(pathname) || instalada()) return;
    if (ler("pe_licao_concluida") !== "1") return;
    const adiado = Number(ler(CHAVE_ADIADO) ?? 0);
    if (adiado && Date.now() < adiado) return;
    const ua = navigator.userAgent;
    // O iPad recente diz-se "Macintosh"; distingue-se por ter ecrã táctil.
    const ipad = /Macintosh/.test(ua) && navigator.maxTouchPoints > 1;
    const iphone = (/iPhone|iPad|iPod/.test(ua) || ipad) && /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
    const t = setTimeout(() => setMostrar(pedido ? "android" : iphone ? "iphone" : null), 1500);
    return () => clearTimeout(t);
  }, [pathname, pedido]);

  const adiar = () => {
    try {
      localStorage.setItem(CHAVE_ADIADO, String(Date.now() + ADIAR_DIAS * 86_400_000));
    } catch {}
    setMostrar(null);
  };

  const versaoVisivel = espera && !emAtividade(pathname);

  return (
    <div className="pe !min-h-0">
      {semNet ? (
        <div role="status" className="fixed inset-x-0 top-0 z-[60] flex items-center justify-center gap-2 bg-pe-tinta px-4 py-2 text-[14px] font-semibold text-pe-sobre-marca">
          <WifiOff aria-hidden className="size-4" /> Está sem Internet. O que fizer agora pode não ficar guardado.
        </div>
      ) : null}

      {versaoVisivel ? (
        <div role="status" className="fixed inset-x-3 bottom-[96px] z-[60] mx-auto flex max-w-[480px] items-center justify-between gap-3 rounded-pe-md bg-pe-azul-marca px-4 py-3 text-pe-sobre-marca shadow-pe-2 md:bottom-6">
          <span className="text-[15px] font-semibold leading-5">Há uma versão nova da app.</span>
          <Botao
            tipo="realce"
            tamanho="pequeno"
            onClick={() => {
              aActualizar.current = true;
              espera.postMessage({ tipo: "actualizar" });
            }}
          >
            Actualizar
          </Botao>
        </div>
      ) : null}

      {mostrar ? (
        <div role="dialog" aria-modal="false" aria-labelledby="titulo-instalar" className="fixed inset-x-0 bottom-0 z-[60] flex justify-center p-3 md:bottom-6 md:right-6 md:left-auto md:p-0">
          <div className="relative flex w-full max-w-[420px] flex-col gap-4 rounded-[24px_24px_24px_0] border border-pe-linha bg-pe-fundo p-5 shadow-pe-2">
            <button type="button" onClick={adiar} aria-label="Fechar" className="absolute right-2 top-2 flex size-11 items-center justify-center rounded-pe-sm bg-transparent text-pe-tinta-suave">
              <X aria-hidden className="size-5" />
            </button>
            {mostrar === "android" ? (
              <>
                <div className="flex items-center gap-3 pr-8">
                  {/* eslint-disable-next-line @next/next/no-img-element -- ícone da própria app */}
                  <img src="/icons/app-192.png" alt="" className="size-14 rounded-[14px]" />
                  <h2 id="titulo-instalar" className="m-0 font-pe-titulo text-[20px] font-bold leading-[26px]">
                    Instale o ProEnglish
                  </h2>
                </div>
                <ul className="m-0 flex list-none flex-col gap-2 p-0 text-[15px] leading-[22px]">
                  {["Grátis, sem passar pela loja de apps", "Abre com um toque, a partir do ecrã principal", "Ocupa muito pouco espaço no telemóvel"].map((t) => (
                    <li key={t} className="flex gap-2">
                      <Check aria-hidden className="mt-0.5 size-5 shrink-0 text-pe-certo" />
                      {t}
                    </li>
                  ))}
                </ul>
                <div className="flex flex-wrap items-center gap-3">
                  <Botao
                    onClick={async () => {
                      if (!pedido) return;
                      await pedido.prompt();
                      const r = await pedido.userChoice.catch(() => null);
                      setPedido(null);
                      if (r?.outcome === "accepted") setMostrar(null);
                      else adiar();
                    }}
                  >
                    <Download aria-hidden /> Instalar a app
                  </Botao>
                  <Botao tipo="ligacao" tamanho="pequeno" onClick={adiar}>
                    Agora não
                  </Botao>
                </div>
              </>
            ) : (
              <>
                <h2 id="titulo-instalar" className="m-0 pr-8 font-pe-titulo text-[20px] font-bold leading-[26px]">
                  Pôr o ProEnglish no ecrã principal
                </h2>
                <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">No iPhone faz-se pelo Safari, em três toques.</p>
                <ol className="m-0 flex list-none flex-col gap-3 p-0 text-[15px] leading-[22px]">
                  <li className="flex items-center gap-3">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-pe-azul-marca text-[14px] font-bold text-pe-sobre-marca">1</span>
                    <span>
                      Toque em <Share aria-label="Partilhar" className="inline size-5 align-text-bottom text-pe-azul-vivo" /> <strong>Partilhar</strong>, em baixo no Safari
                    </span>
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-pe-azul-marca text-[14px] font-bold text-pe-sobre-marca">2</span>
                    <span>
                      Escolha <SquarePlus aria-hidden className="inline size-5 align-text-bottom" /> <strong>Adicionar ao ecrã principal</strong>
                    </span>
                  </li>
                  <li className="flex items-center gap-3">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-pe-azul-marca text-[14px] font-bold text-pe-sobre-marca">3</span>
                    <span>
                      Toque em <strong>Adicionar</strong>, no canto de cima
                    </span>
                  </li>
                </ol>
                <Botao tipo="secundario" onClick={adiar}>
                  Já está
                </Botao>
              </>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
