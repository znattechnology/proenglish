import Link from "next/link";
import { Logo } from "@/components/pe";
import type { Site } from "@/src/domains/site/conteudo";
import { Cookies, PreferenciasCookies } from "./Cookies";
import { Entrada } from "./Entrada";
import { MenuMovel } from "./MenuMovel";

const ligacaoNav = "py-2.5 font-semibold text-pe-tinta no-underline hover:text-pe-azul-marca";

/** Cabeçalho, rodapé e aviso de cookies das páginas públicas. */
export function Moldura({ site, actual, children }: { site: Site; actual: "inicio" | "sobre"; children: React.ReactNode }) {
  const d = site.definicoes;
  const redes = [
    d.instagram ? { nome: "Instagram", href: d.instagram } : null,
    d.linkedin ? { nome: "LinkedIn", href: d.linkedin } : null,
    d.facebook ? { nome: "Facebook", href: d.facebook } : null,
  ].filter(Boolean) as { nome: string; href: string }[];
  const contacto = d.email ? `mailto:${d.email}` : null;
  const rodape = site.numeros.filter((n) => n.onde === "rodape");

  return (
    <div className="pe bg-pe-fundo text-pe-tinta">
      <a href="#conteudo" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-pe-sm focus:bg-pe-fundo focus:px-4 focus:py-2">
        Saltar para o conteúdo
      </a>
      <header className="relative border-b border-pe-linha">
        <div className="mx-auto flex max-w-[1200px] items-center gap-2 px-4 py-3 sm:gap-4 md:gap-8 md:px-6 md:py-4">
          <Link href="/" aria-label="ProEnglish, página inicial" className="shrink-0">
            <Logo altura={40} className="h-9 w-auto md:h-11" />
          </Link>
          <nav aria-label="Secções" className="hidden flex-1 flex-wrap gap-x-7 lg:flex">
            {actual === "inicio" ? (
              <>
                <a href="#como-funciona" className={ligacaoNav}>Como funciona</a>
                <a href="#areas" className={ligacaoNav}>Sectores</a>
                <a href="#planos" className={ligacaoNav}>Planos</a>
                <Link href="/about" className={ligacaoNav}>Sobre</Link>
              </>
            ) : (
              <>
                <Link href="/" className={ligacaoNav}>Início</Link>
                <Link href="/about" aria-current="page" className={ligacaoNav}>Sobre</Link>
                <Link href="/#planos" className={ligacaoNav}>Planos</Link>
              </>
            )}
          </nav>
          <Entrada />
          <MenuMovel
            ligacoes={
              actual === "inicio"
                ? [
                    { nome: "Como funciona", href: "#como-funciona" },
                    { nome: "Sectores", href: "#areas" },
                    { nome: "Planos", href: "#planos" },
                    { nome: "Sobre", href: "/about" },
                  ]
                : [
                    { nome: "Início", href: "/" },
                    { nome: "Sobre", href: "/about", actual: true },
                    { nome: "Planos", href: "/#planos" },
                  ]
            }
          />
        </div>
      </header>

      <main id="conteudo">{children}</main>

      <footer className="border-t border-pe-linha">
        {rodape.length ? (
          <dl className="mx-auto m-0 flex max-w-[1200px] flex-wrap gap-x-10 gap-y-3 border-b border-pe-linha px-4 py-6 md:px-6">
            {rodape.map((n) => (
              <div key={n.id} className="flex items-baseline gap-2">
                <dd className="m-0 font-pe-titulo text-[22px] font-bold tabular-nums">{n.valor}</dd>
                <dt className="text-[15px] text-pe-tinta-suave">{n.texto}</dt>
              </div>
            ))}
          </dl>
        ) : null}
        <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 py-10 md:flex-row md:flex-wrap md:items-center md:gap-x-10 md:px-6">
          <Logo versao="azul-assinatura" altura={44} className="h-11 w-auto" />
          <nav aria-label="Rodapé" className="flex flex-1 flex-wrap gap-x-6 gap-y-1 text-[15px]">
            <Link href="/termos" className="py-2">Termos de utilização</Link>
            <Link href="/privacidade" className="py-2">Privacidade</Link>
            <Link href="/about" className="py-2">Sobre</Link>
            <Link href="/#planos" className="py-2">Planos</Link>
            <Link href="/verify" className="py-2">Verificar certificado</Link>
            {contacto ? <a href={contacto} className="py-2">Contacto</a> : null}
            {redes.map((r) => (
              <a key={r.nome} href={r.href} rel="noopener" className="py-2">
                {r.nome}
              </a>
            ))}
            {d.ga_id || d.pixel_id ? <PreferenciasCookies /> : null}
          </nav>
          <div className="flex flex-col gap-1 text-[14px] leading-5 text-pe-tinta-suave md:items-end">
            {d.telefone ? <a href={`tel:${d.telefone.replace(/\s/g, "")}`} className="text-pe-tinta-suave">{d.telefone}</a> : null}
            <span>{new Date().getFullYear()} ProEnglish, Luanda</span>
          </div>
        </div>
      </footer>
      <Cookies ga={d.ga_id} pixel={d.pixel_id} />
    </div>
  );
}

/** Faixa final com o convite para começar. */
export function Convite({ titulo = "A primeira lição leva 15 minutos", botao = "Começar agora" }: { titulo?: string; botao?: string }) {
  return (
    <section className="bg-pe-fundo-suave">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-x-12 gap-y-6 px-4 py-14 md:px-6 md:py-16">
        <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-2">
          <h2 className="m-0 font-pe-titulo text-[28px] font-bold leading-[1.2] md:text-[2rem]">{titulo}</h2>
          <p className="m-0 font-pe-titulo text-[19px] font-light italic leading-7 text-pe-azul-marca">Fluência ao alcance de todos</p>
        </div>
        <Link href="/signup" className="inline-flex min-h-[52px] items-center rounded-pe-sm bg-pe-realce px-7 text-[17px] font-semibold text-pe-tinta no-underline hover:text-pe-tinta hover:shadow-pe-2">
          {botao}
        </Link>
      </div>
    </section>
  );
}
