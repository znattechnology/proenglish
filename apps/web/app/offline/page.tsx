
export const metadata = { title: "Sem ligação | ProEnglish" };
export const dynamic = "force-static";

/**
 * Mostrada pelo service worker quando não há Internet.
 * Funciona sem JavaScript: o botão só volta a pedir o mesmo endereço.
 */
export default function SemLigacao() {
  return (
    <div className="pe flex min-h-dvh flex-col bg-pe-fundo text-pe-tinta">
      <header className="px-5 py-4">
        {/* Imagem simples (não passa pelo optimizador do Next), para estar guardada sem ligação. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo/Logo_azul.png" alt="ProEnglish" height={32} style={{ height: 32, width: "auto" }} />
      </header>
      <main className="mx-auto flex w-full max-w-[520px] flex-1 flex-col justify-center gap-6 px-5 pb-16">
        <div aria-hidden className="flex size-16 items-center justify-center rounded-[22px_22px_22px_0] bg-pe-fundo-suave">
          <svg viewBox="0 0 24 24" className="size-8 text-pe-azul-marca" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h.01M8.5 16.4a5 5 0 0 1 7 0M5 12.9a10 10 0 0 1 5.2-2.7M19 12.9a10 10 0 0 0-2-1.5M2 8.8a15 15 0 0 1 4.2-2.6M22 8.8A15 15 0 0 0 11 5M2 2l20 20" />
          </svg>
        </div>
        <div className="flex flex-col gap-2">
          <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9">Está sem Internet</h1>
          <p className="m-0 text-pe-tinta-suave">
            As lições, as aulas e a conversa com o tutor precisam de ligação. O que já fez está guardado na sua conta e continua onde parou quando a Internet voltar.
          </p>
        </div>
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4 text-[15px] leading-[22px]">
          Experimente desligar e voltar a ligar os dados móveis ou o Wi-Fi. Em muitos telemóveis, o modo de poupança de dados também bloqueia as apps.
        </p>
        <a
          href=""
          className="flex min-h-[52px] items-center justify-center rounded-pe-sm bg-pe-azul-marca px-6 font-semibold text-pe-sobre-marca no-underline hover:bg-pe-azul-vivo"
        >
          Tentar ligar outra vez
        </a>
      </main>
    </div>
  );
}
