import Link from "next/link";

/**
 * Ecrã de estado (404, erro, sem permissão): o logótipo, um símbolo grande no balão da marca,
 * o que aconteceu, o que fazer a seguir. Funciona fora das áreas com barra lateral.
 */
export function Estado({
  simbolo,
  titulo,
  texto,
  children,
  rodape,
}: {
  simbolo: React.ReactNode;
  titulo: string;
  texto: React.ReactNode;
  children?: React.ReactNode;
  rodape?: React.ReactNode;
}) {
  return (
    <div className="pe flex min-h-dvh flex-col bg-pe-fundo text-pe-tinta">
      <header className="px-5 py-4 md:px-10">
        <Link href="/" aria-label="ProEnglish, página inicial" className="inline-block">
          {/* Imagem simples: o estado de erro não deve depender do optimizador de imagens. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo/Logo_azul.png" alt="ProEnglish" style={{ height: 36, width: "auto" }} />
        </Link>
      </header>
      <main className="mx-auto flex w-full max-w-[560px] flex-1 flex-col justify-center gap-6 px-5 pb-16">
        <div aria-hidden className="pe-sobre-marca flex h-[88px] min-w-[88px] items-center justify-center self-start rounded-[28px_28px_28px_0] bg-pe-azul-marca px-5 font-pe-titulo text-[36px] font-bold text-pe-realce">
          {simbolo}
        </div>
        <div className="flex flex-col gap-2">
          <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9 md:text-[32px] md:leading-10">{titulo}</h1>
          <div className="m-0 text-pe-tinta-suave">{texto}</div>
        </div>
        {children ? <div className="flex flex-col gap-3">{children}</div> : null}
        {rodape ? <div className="text-[14px] leading-5 text-pe-tinta-suave">{rodape}</div> : null}
      </main>
    </div>
  );
}

/** Lista de destinos para continuar (usada no 404 e no sem permissão). */
export function Destinos({ itens }: { itens: { href: string; nome: string; texto?: string }[] }) {
  return (
    <ul className="m-0 flex list-none flex-col p-0">
      {itens.map((i) => (
        <li key={i.href}>
          <Link href={i.href} className="flex min-h-14 items-center justify-between gap-3 border-b border-pe-fundo-forte py-3 text-pe-tinta no-underline hover:bg-pe-fundo-suave md:px-2">
            <span className="flex flex-col">
              <span className="font-semibold leading-[22px]">{i.nome}</span>
              {i.texto ? <span className="text-[14px] leading-5 text-pe-tinta-suave">{i.texto}</span> : null}
            </span>
            <svg aria-hidden viewBox="0 0 24 24" className="size-5 shrink-0 text-pe-tinta-suave" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m9 18 6-6-6-6" />
            </svg>
          </Link>
        </li>
      ))}
    </ul>
  );
}
