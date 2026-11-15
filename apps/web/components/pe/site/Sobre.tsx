import Link from "next/link";
import type { Site } from "@/src/domains/site/conteudo";
import { Convite, Moldura } from "./Moldura";

const PRINCIPIOS = [
  { titulo: "O inglês da sua profissão", texto: "Cada curso parte das situações reais de uma área: a reunião de segurança, o balcão do banco, a triagem no hospital." },
  { titulo: "Pouco e todos os dias", texto: "Lições de 15 minutos, pensadas para o intervalo do almoço ou a viagem de táxi para o trabalho." },
  { titulo: "Falar desde o primeiro dia", texto: "O tutor de inteligência artificial conversa consigo em inglês e explica as correcções em português." },
];

const h2 = "m-0 font-pe-titulo text-[28px] font-bold leading-[1.2] tracking-[-0.015em] md:text-[2.25rem]";

export function Sobre({ site }: { site: Site }) {
  const areas = site.areas.filter((a) => a.cursos > 0);
  const numeros = site.numeros.filter((n) => n.onde === "sobre");
  return (
    <Moldura site={site} actual="sobre">
      <section>
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-16 gap-y-8 px-4 pb-14 pt-10 md:px-6 md:pb-[72px] md:pt-[72px]">
          <div className="flex min-w-0 flex-[3_1_480px] flex-col gap-5">
            <h1 className="m-0 text-balance font-pe-titulo text-[36px] font-bold leading-[1.1] tracking-[-0.02em] md:text-[3rem]">Feito em Angola, para quem trabalha em Angola</h1>
            <p className="m-0 max-w-[620px] text-[18px] leading-[1.6] text-pe-tinta-suave md:text-[1.25rem]">
              Muitos profissionais angolanos lidam todos os dias com colegas, clientes e documentos em inglês. O ProEnglish ensina o inglês dessas situações, a partir das frases que se usam no trabalho.
            </p>
          </div>
          <div className="m-0 flex min-w-0 flex-[2_1_320px] flex-col gap-2.5 rounded-[28px_28px_28px_0] bg-pe-azul-marca p-7 text-pe-sobre-marca md:p-8">
            <p className="m-0 font-pe-titulo text-[24px] font-light italic leading-[34px] md:text-[28px] md:leading-[38px]">Fluência ao alcance de todos</p>
            <span>{site.precos.planos.some((p) => p.preco_mensal_kz <= 0) ? "Plano gratuito para sempre, e preços em kwanzas para quem quer ir mais longe." : "Preços em kwanzas, pagos por Multicaixa Express."}</span>
          </div>
        </div>
      </section>

      <section className="bg-pe-fundo-suave">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-8 px-4 py-14 md:px-6 md:py-[72px]">
          <h2 className={h2}>Como ensinamos</h2>
          <div className="grid gap-4 md:grid-cols-3 md:gap-6">
            {PRINCIPIOS.map((p) => (
              <article key={p.titulo} className="flex min-w-0 flex-col gap-2.5 rounded-[12px] bg-pe-fundo p-6 md:p-7">
                <h3 className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">{p.titulo}</h3>
                <p className="m-0 text-pe-tinta-suave">{p.texto}</p>
              </article>
            ))}
          </div>
          {numeros.length ? (
            <dl className="m-0 flex flex-wrap gap-x-12 gap-y-4">
              {numeros.map((n) => (
                <div key={n.id} className="flex flex-col-reverse">
                  <dt className="text-[15px] text-pe-tinta-suave">{n.texto}</dt>
                  <dd className="m-0 font-pe-titulo text-[30px] font-bold leading-9 tabular-nums">{n.valor}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </div>
      </section>

      {areas.length ? (
        <section>
          <div className="mx-auto flex max-w-[1200px] flex-col gap-8 px-4 py-14 md:px-6 md:py-[72px]">
            <h2 className={h2}>As áreas que ensinamos</h2>
            <ul className="m-0 grid list-none grid-cols-2 gap-3 p-0 sm:grid-cols-3 md:gap-4 lg:grid-cols-6">
              {areas.map((a) => (
                <li key={a.valor} className="flex min-w-0 flex-col gap-1 rounded-[12px] border border-pe-linha p-4 md:p-5">
                  <span className="font-semibold">{a.nome}</span>
                  <span className="text-[14px] leading-5 text-pe-tinta-suave">
                    {a.cursos} {a.cursos === 1 ? "curso" : "cursos"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      {site.definicoes.email || site.definicoes.telefone ? (
        <section className="border-t border-pe-linha">
          <div className="mx-auto flex max-w-[1200px] flex-col gap-3 px-4 py-12 md:px-6">
            <h2 className="m-0 font-pe-titulo text-[24px] font-bold leading-8">Fale connosco</h2>
            <p className="m-0 text-pe-tinta-suave">
              {site.definicoes.email ? (
                <>
                  Escreva para <a href={`mailto:${site.definicoes.email}`}>{site.definicoes.email}</a>
                </>
              ) : null}
              {site.definicoes.email && site.definicoes.telefone ? " ou ligue para " : site.definicoes.telefone ? "Ligue para " : ""}
              {site.definicoes.telefone ? <a href={`tel:${site.definicoes.telefone.replace(/\s/g, "")}`}>{site.definicoes.telefone}</a> : null}.
            </p>
          </div>
        </section>
      ) : null}

      <Convite botao="Experimentar grátis" />
    </Moldura>
  );
}

/** Página mostrada enquanto o site está em manutenção. */
export function Manutencao({ mensagem, voltaEm }: { mensagem: string; voltaEm: string | null }) {
  const volta = voltaEm ? new Date(voltaEm) : null;
  return (
    <main className="pe flex min-h-dvh flex-col items-center justify-center bg-pe-fundo-suave px-4 py-12 text-pe-tinta">
      <div className="flex w-full max-w-[560px] flex-col gap-5 rounded-[28px_28px_28px_0] bg-pe-azul-marca p-7 text-pe-sobre-marca md:p-10">
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9 md:text-[34px] md:leading-[42px]">Estamos a melhorar o ProEnglish</h1>
        <p className="m-0 whitespace-pre-line text-[17px] leading-7">{mensagem || "O site está em manutenção por alguns minutos. O seu progresso está guardado."}</p>
        {volta && !Number.isNaN(volta.getTime()) ? (
          <p className="m-0 font-semibold text-pe-realce">
            Voltamos {volta.toLocaleString("pt-PT", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit", timeZone: "Africa/Luanda" })}.
          </p>
        ) : null}
      </div>
      <Link href="/signin" className="mt-6 text-[15px] text-pe-tinta-suave">
        Já tem conta? Entrar
      </Link>
    </main>
  );
}
