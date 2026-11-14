import Link from "next/link";
import { Logo } from "@/components/pe";
import { EM_VIGOR, porPreencher } from "@/src/domains/legal/empresa";

export type Seccao = { id: string; titulo: string; corpo: React.ReactNode };

const data = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-PT", { day: "numeric", month: "long", year: "numeric" });

/**
 * Documento legal: resumo em linguagem simples no topo, índice das cláusulas
 * (fixo ao lado no desktop) e o texto completo, numerado porque as cláusulas são citadas pelo número.
 */
export function Documento({
  titulo,
  tipo,
  resumo,
  seccoes,
  outro,
}: {
  titulo: string;
  tipo: keyof typeof EM_VIGOR;
  resumo: React.ReactNode[];
  seccoes: Seccao[];
  outro: { href: string; nome: string };
}) {
  return (
    <div className="pe min-h-dvh bg-pe-fundo text-pe-tinta">
      <header className="border-b border-pe-linha">
        <div className="mx-auto flex max-w-[1120px] items-center justify-between gap-4 px-5 py-4 md:px-10">
          <Link href="/" aria-label="ProEnglish, página inicial">
            <Logo altura={36} />
          </Link>
          <Link href={outro.href} className="text-[15px] font-semibold text-pe-azul-marca underline-offset-[3px]">
            {outro.nome}
          </Link>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1120px] gap-10 px-5 pb-20 pt-8 md:px-10 md:pt-12 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-16">
        <div className="flex flex-col gap-3 lg:col-span-2">
          <h1 className="m-0 font-pe-titulo text-[30px] font-bold leading-9 tracking-[-0.01em] md:text-[40px] md:leading-[48px]">{titulo}</h1>
          <p className="m-0 text-pe-tinta-suave">Em vigor desde {data(EM_VIGOR[tipo])}.</p>
          {porPreencher() ? (
            <p role="note" className="m-0 max-w-[68ch] rounded-pe-md bg-pe-errado-suave px-4 py-3 text-[15px] leading-[22px]">
              Versão de trabalho: faltam os dados da empresa e a revisão jurídica. Não publicar assim.
            </p>
          ) : null}
        </div>

        <nav aria-label="Índice" className="hidden lg:block">
          <ol className="sticky top-8 m-0 flex list-none flex-col gap-0.5 p-0 text-[15px] leading-[22px]">
            {seccoes.map((s, i) => (
              <li key={s.id}>
                <a href={`#${s.id}`} className="flex gap-2 rounded-pe-sm px-2 py-1.5 text-pe-tinta no-underline hover:bg-pe-fundo-suave">
                  <span className="w-5 shrink-0 tabular-nums text-pe-tinta-suave">{i + 1}.</span>
                  {s.titulo}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <article className="flex min-w-0 max-w-[68ch] flex-col gap-10">
          <section aria-labelledby="titulo-resumo" className="pe-sobre-marca flex flex-col gap-3 rounded-[28px_28px_28px_0] bg-pe-azul-marca p-6 text-pe-sobre-marca md:p-8">
            <h2 id="titulo-resumo" className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">
              Em resumo
            </h2>
            <ul className="m-0 flex list-disc flex-col gap-2 pl-5 text-[16px] leading-[25px] marker:text-pe-realce">
              {resumo.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
            <p className="m-0 text-[14px] leading-5 opacity-90">O resumo ajuda a ler, mas o que vale é o texto completo abaixo.</p>
          </section>

          <details className="rounded-pe-md border border-pe-linha lg:hidden">
            <summary className="min-h-12 cursor-pointer px-4 py-3 font-semibold">Índice</summary>
            <ol className="m-0 flex list-decimal flex-col gap-1 px-4 pb-4 pl-9 text-[15px] leading-[22px]">
              {seccoes.map((s) => (
                <li key={s.id}>
                  <a href={`#${s.id}`} className="text-pe-azul-marca underline-offset-[3px]">
                    {s.titulo}
                  </a>
                </li>
              ))}
            </ol>
          </details>

          {seccoes.map((s, i) => (
            <section key={s.id} id={s.id} aria-labelledby={`t-${s.id}`} className="flex scroll-mt-8 flex-col gap-3">
              <h2 id={`t-${s.id}`} className="m-0 flex gap-3 font-pe-titulo text-[22px] font-semibold leading-7">
                <span className="tabular-nums text-pe-tinta-suave">{i + 1}.</span>
                {s.titulo}
              </h2>
              <div className="pe-legal flex flex-col gap-3 text-[16px] leading-[26px]">{s.corpo}</div>
            </section>
          ))}
        </article>
      </main>
    </div>
  );
}
