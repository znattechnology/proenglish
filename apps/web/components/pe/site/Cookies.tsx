"use client";

import Script from "next/script";
import { useEffect, useState, useSyncExternalStore } from "react";

const CHAVE = "pe-cookies";
const EVENTO = "pe-cookies-abrir";

/** Ligação do rodapé para voltar a escolher. Retirar a autorização recarrega a página, para descarregar os scripts. */
export function PreferenciasCookies() {
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new Event(EVENTO))}
      className="min-h-0 bg-transparent p-0 py-2 text-left text-[15px] text-pe-azul-vivo underline underline-offset-[3px]"
    >
      Preferências de cookies
    </button>
  );
}
type Escolha = "aceites" | "recusados";

function ler(): Escolha | null {
  try {
    const v = localStorage.getItem(CHAVE);
    return v === "aceites" || v === "recusados" ? v : null;
  } catch {
    return null;
  }
}

/**
 * Aviso de cookies. Google Analytics e o Pixel só carregam depois de a pessoa aceitar;
 * se não houver nenhum configurado no site, o aviso nem aparece (não há cookies de medição).
 */
export function Cookies({ ga, pixel }: { ga: string | null; pixel: string | null }) {
  // "por-ler" no servidor e na primeira pintura; depois, o que está guardado no browser.
  const guardada = useSyncExternalStore(
    () => () => {},
    () => ler(),
    () => "por-ler" as const
  );
  const [escolhida, setEscolhida] = useState<Escolha | null | undefined>(undefined);
  useEffect(() => {
    const abrir = () => setEscolhida(null); // mostra o aviso; a escolha guardada só muda quando escolher outra vez
    window.addEventListener(EVENTO, abrir);
    return () => window.removeEventListener(EVENTO, abrir);
  }, []);
  const escolha = escolhida !== undefined ? escolhida : guardada;
  const setEscolha = setEscolhida;
  if (!ga && !pixel) return null;

  const escolher = (e: Escolha) => {
    const antes = ler();
    try {
      localStorage.setItem(CHAVE, e);
    } catch {}
    // Já tinham carregado e agora recusou: só recarregar tira o Analytics e o Pixel da página.
    if (antes === "aceites" && e === "recusados") return window.location.reload();
    setEscolha(e);
  };

  return (
    <>
      {(escolha === "aceites" || (escolha === null && ler() === "aceites")) && ga && /^G-[A-Z0-9]+$/i.test(ga) ? (
        <>
          <Script src={`https://www.googletagmanager.com/gtag/js?id=${ga}`} strategy="afterInteractive" />
          <Script id="ga" strategy="afterInteractive">{`window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','${ga}',{anonymize_ip:true});`}</Script>
        </>
      ) : null}
      {(escolha === "aceites" || (escolha === null && ler() === "aceites")) && pixel && /^\d+$/.test(pixel) ? (
        <Script id="pixel" strategy="afterInteractive">{`!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init','${pixel}');fbq('track','PageView');`}</Script>
      ) : null}
      {escolha === null ? (
        <div role="region" aria-label="Cookies" className="fixed inset-x-3 bottom-3 z-40 mx-auto flex max-w-[720px] flex-col gap-4 rounded-[20px_20px_20px_0] bg-pe-azul-marca p-5 text-pe-sobre-marca shadow-pe-2 sm:flex-row sm:items-center">
          <p className="m-0 flex-1 text-[15px] leading-[22px]">
            Usamos cookies para medir as visitas ao site e melhorar os anúncios. Só os ligamos se aceitar.{" "}
            <a href="/privacidade#cookies" className="text-pe-sobre-marca underline">Saber mais</a>
          </p>
          <div className="flex shrink-0 gap-2">
            <button type="button" onClick={() => escolher("recusados")} className="min-h-11 rounded-pe-sm border-2 border-pe-sobre-marca bg-transparent px-4 font-semibold text-pe-sobre-marca">
              Recusar
            </button>
            <button type="button" onClick={() => escolher("aceites")} className="min-h-11 rounded-pe-sm bg-pe-realce px-4 font-semibold text-pe-tinta">
              Aceitar
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
