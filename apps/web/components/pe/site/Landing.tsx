import Link from "next/link";
import { Award, BookOpen, Bot, FlaskConical, MessageCircle, Mic } from "lucide-react";
import { cnPe } from "@/lib/pe";
import { FRASES_AREA, type Site } from "@/src/domains/site/conteudo";
import { Convite, Moldura } from "./Moldura";
import { LigacaoPlano } from "./Entrada";

export const kz = (n: number) => `${String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ")} Kz`;

const h2 = "m-0 font-pe-titulo text-[30px] font-bold leading-[1.15] tracking-[-0.015em] md:text-[2.5rem]";
const caixa = "mx-auto flex max-w-[1200px] flex-col gap-8 px-4 py-14 md:gap-10 md:px-6 md:py-20";

const PASSOS = [
  { titulo: "Escolha a sua área", texto: "Diga-nos onde trabalha e o nível em que está. O curso começa pelas situações do seu dia." },
  { titulo: "Pratique 15 minutos", texto: "Lições curtas com exercícios de vocabulário, escuta e pronúncia, no telemóvel ou no computador." },
  { titulo: "Converse com o tutor", texto: "Fale em voz alta com o tutor de IA. Ele responde, corrige e explica em português." },
  { titulo: "Receba o certificado", texto: "Ao concluir um curso nos planos pagos, fica com o certificado para juntar ao currículo." },
];

const ICONES = { livro: BookOpen, laboratorio: FlaskConical, bot: Bot, microfone: Mic, balao: MessageCircle, certificado: Award } as const;

export function Landing({ site }: { site: Site }) {
  const t = site.topo;
  const numerosTopo = site.numeros.filter((n) => n.onde === "topo");
  const faixa = site.empresas.filter((e) => e.na_faixa);
  // Só áreas com cursos publicados; sem resposta da API, a secção fica sem cartões (nada inventado).
  const gratis = site.precos.planos.some((p) => p.preco_mensal_kz <= 0);
  const areas = site.areas.filter((a) => a.cursos > 0).map((a) => a.nome).map((nome) => ({
    nome,
    ...(FRASES_AREA[nome] ?? { frase: null, texto: null }),
  }));

  return (
    <Moldura site={site} actual="inicio">
      {/* Topo */}
      <section>
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-16 gap-y-10 px-4 pb-14 pt-10 md:px-6 md:pb-20 md:pt-[72px]">
          <div className="flex min-w-0 flex-[1_1_440px] flex-col gap-6">
            {t.etiqueta ? <p className="m-0 text-[15px] font-semibold text-pe-azul-marca">{t.etiqueta}</p> : null}
            <h1 className="m-0 text-balance font-pe-titulo text-[40px] font-bold leading-[1.07] tracking-[-0.02em] md:text-[3.5rem]">{t.titulo}</h1>
            <p className="m-0 max-w-[520px] text-[18px] leading-[1.6] text-pe-tinta-suave md:text-[1.25rem]">{t.texto}</p>
            <div className="flex flex-wrap gap-4">
              <Link href={t.botao_principal.href} className="inline-flex min-h-[52px] items-center rounded-pe-sm bg-pe-realce px-7 text-[17px] font-semibold text-pe-tinta no-underline hover:text-pe-tinta hover:shadow-pe-2">
                {t.botao_principal.texto}
              </Link>
              {t.botao_secundario ? (
                <Link href={t.botao_secundario.href} className="inline-flex min-h-[52px] items-center rounded-pe-sm border-2 border-pe-azul-marca bg-pe-fundo px-7 text-[17px] font-semibold text-pe-azul-marca no-underline hover:bg-pe-fundo-suave">
                  {t.botao_secundario.texto}
                </Link>
              ) : null}
            </div>
            <p className="m-0 text-[14px] leading-5 text-pe-tinta-suave">
              {gratis ? "Plano gratuito para sempre, sem pagar nada para começar." : null}
              {t.mostrar_nota && t.nota && t.nota.total > 0 ? ` Nota média de ${t.nota.media.toLocaleString("pt-PT", { maximumFractionDigits: 1 })} em 5, de ${t.nota.total} ${t.nota.total === 1 ? "opinião" : "opiniões"} de alunos.` : ""}
            </p>
            {numerosTopo.length ? (
              <dl className="m-0 flex flex-wrap gap-x-10 gap-y-4 border-t border-pe-linha pt-5">
                {numerosTopo.map((n) => (
                  <div key={n.id} className="flex flex-col-reverse">
                    <dt className="text-[14px] leading-5 text-pe-tinta-suave">{n.texto}</dt>
                    <dd className="m-0 font-pe-titulo text-[26px] font-bold leading-8 tabular-nums">{n.valor}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </div>

          <figure aria-label="Exemplo de uma conversa com o tutor" className="m-0 flex min-w-0 flex-[1_1_440px] flex-col gap-4 rounded-[28px_28px_28px_0] bg-pe-fundo-suave p-5 md:p-8">
            <Fala quem="Tutor" lado="tutor">
              Could you send me the <mark className="rounded-[2px] bg-pe-realce px-1 text-pe-tinta">drilling report</mark> by Friday?
            </Fala>
            <Fala quem="Você" lado="aluno">Sure. I will send it in Thursday afternoon.</Fala>
            <div className="flex max-w-[380px] flex-col gap-0.5 self-end rounded-[12px] bg-pe-realce-suave px-4 py-3">
              <span className="text-[14px] font-semibold leading-5">Um ajuste</span>
              <span className="text-[15px] leading-[22px]">
                Os dias da semana levam &quot;on&quot;:{" "}
                <span lang="en" className="font-semibold">
                  on Thursday afternoon
                </span>
                .
              </span>
            </div>
            <Fala quem="Tutor" lado="tutor">Perfect. Does it include the safety incidents?</Fala>
          </figure>
        </div>
      </section>

      {faixa.length ? (
        <section aria-label="Empresas" className="border-y border-pe-linha">
          <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-10 gap-y-4 px-4 py-6 md:px-6">
            <p className="m-0 text-[15px] text-pe-tinta-suave">Estudam connosco profissionais de</p>
            <ul className="m-0 flex list-none flex-wrap items-center gap-x-10 gap-y-4 p-0">
              {faixa.map((e) => (
                <li key={e.id}>
                  {e.logo_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={e.logo_url} alt={e.nome} className="h-8 w-auto max-w-[140px] object-contain grayscale" />
                  ) : (
                    <span className="font-semibold">{e.nome}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      {/* Áreas */}
      <section id="areas" className="scroll-mt-4 bg-pe-fundo-suave">
        <div className={caixa}>
          <div className="flex max-w-[640px] flex-col gap-3">
            <h2 className={h2}>O inglês da sua profissão</h2>
            <p className="m-0 text-pe-corpo-l text-pe-tinta-suave">Cada curso parte das frases que vai mesmo usar. Escolha a área e comece pela primeira reunião, pelo primeiro email ou pelo primeiro cliente.</p>
          </div>
          {areas.length ? (
          <div className="grid gap-4 sm:grid-cols-2 md:gap-6 lg:grid-cols-3">
            {areas.map((a) => (
              <article key={a.nome} className="flex min-w-0 flex-col gap-3 rounded-[12px] bg-pe-fundo p-6 md:p-7">
                <h3 className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">{a.nome}</h3>
                {a.frase ? (
                  <p lang="en" className="m-0 font-pe-titulo text-[19px] font-light italic leading-[29px] text-pe-azul-marca">
                    {a.frase}
                  </p>
                ) : null}
                {a.texto ? <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">{a.texto}</p> : null}
                <p className="m-0 mt-auto text-[14px] leading-5 text-pe-tinta-suave">{site.areas.find((x) => x.nome === a.nome)?.cursos ?? 0} {(site.areas.find((x) => x.nome === a.nome)?.cursos ?? 0) === 1 ? "curso" : "cursos"}</p>
              </article>
            ))}
          </div>
          ) : (
            <p className="m-0">
              <Link href="/signup" className="font-semibold">Crie uma conta grátis</Link> para ver os cursos de cada área.
            </p>
          )}
        </div>
      </section>

      {/* Como funciona */}
      <section id="como-funciona" className="scroll-mt-4">
        <div className={caixa}>
          <h2 className={h2}>Como funciona</h2>
          <ol className="m-0 grid list-none gap-8 p-0 sm:grid-cols-2 lg:grid-cols-4">
            {PASSOS.map((p, i) => (
              <li key={p.titulo} className="flex min-w-0 flex-col gap-3">
                <span aria-hidden className="flex size-12 items-center justify-center rounded-[16px_16px_16px_0] bg-pe-azul-marca font-pe-titulo text-[20px] font-bold text-pe-sobre-marca">
                  {i + 1}
                </span>
                <h3 className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">{p.titulo}</h3>
                <p className="m-0 text-pe-tinta-suave">{p.texto}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {site.servicos.length ? (
        <section className="border-t border-pe-linha">
          <div className={caixa}>
            <h2 className={h2}>O que encontra no ProEnglish</h2>
            <div className="grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
              {site.servicos.map((s) => {
                const Icone = ICONES[s.icone as keyof typeof ICONES] ?? BookOpen;
                return (
                <div key={s.id} className="flex min-w-0 flex-col gap-2">
                  <span aria-hidden className="mb-1 flex size-11 items-center justify-center rounded-[14px_14px_14px_0] bg-pe-realce-suave text-pe-azul-marca">
                    <Icone className="size-5" />
                  </span>
                  <h3 className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">{s.titulo}</h3>
                  <p className="m-0 text-pe-tinta-suave">{s.texto}</p>
                  {s.leva_a ? (
                    <Link href={s.leva_a} className="self-start py-1 font-semibold">
                      Ver mais
                    </Link>
                  ) : null}
                </div>
                );
              })}
            </div>
          </div>
        </section>
      ) : null}

      {/* Planos */}
      <section id="planos" className="scroll-mt-4 bg-pe-fundo-suave">
        <div className={caixa}>
          <div className="flex max-w-[640px] flex-col gap-3">
            <h2 className={h2}>Planos em kwanzas</h2>
            <p className="m-0 text-pe-corpo-l text-pe-tinta-suave">Comece grátis e mude de plano quando quiser. Paga com Multicaixa Express.</p>
          </div>
          {site.precos.planos.length ? (
            <div className="grid items-start gap-6 md:grid-cols-2 lg:grid-cols-3">
              {site.precos.planos.map((p) => (
                <Plano key={p.tipo} p={p} anual={site.precos.mostrar_anual} />
              ))}
            </div>
          ) : (
            <p className="m-0">
              <Link href="/signup" className="font-semibold">Crie uma conta grátis</Link> para ver os planos e os preços.
            </p>
          )}
        </div>
      </section>

      {site.testemunhos.length ? (
        <section>
          <div className={caixa}>
            <h2 className={h2}>O que dizem os alunos</h2>
            <div className="grid gap-6 md:grid-cols-3">
              {site.testemunhos.map((t) => (
                <figure key={t.id} className="m-0 flex min-w-0 flex-col gap-4">
                  <blockquote className="m-0 rounded-[24px_24px_24px_0] bg-pe-fundo-suave p-6 text-[17px] leading-7">
                    <span className="sr-only">Nota {t.nota} de 5. </span>
                    {t.texto}
                  </blockquote>
                  <figcaption className="flex flex-col pl-1">
                    <span className="font-semibold">{t.nome}</span>
                    {t.area ? <span className="text-[14px] leading-5 text-pe-tinta-suave">{t.area}</span> : null}
                  </figcaption>
                </figure>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {site.perguntas.length ? (
        <section className={cnPe(site.testemunhos.length && "border-t border-pe-linha")}>
          <div className="mx-auto grid max-w-[1200px] gap-8 px-4 py-14 md:px-6 md:py-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] lg:gap-16">
            <h2 className={h2}>Perguntas frequentes</h2>
            <div className="flex flex-col">
              {site.perguntas.map((q) => (
                <details key={q.id} className="group border-b border-pe-linha">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-5 font-pe-titulo text-[18px] font-semibold leading-[26px] [&::-webkit-details-marker]:hidden">
                    {q.pergunta}
                    <span aria-hidden className="text-[24px] font-normal text-pe-azul-marca transition-transform group-open:rotate-45 motion-reduce:transition-none">+</span>
                  </summary>
                  <p className="m-0 max-w-[68ch] whitespace-pre-line pb-5 text-pe-tinta-suave">{q.resposta}</p>
                </details>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      <Convite />
    </Moldura>
  );
}

function Fala({ quem, lado, children }: { quem: string; lado: "tutor" | "aluno"; children: React.ReactNode }) {
  const tutor = lado === "tutor";
  return (
    <div className={cnPe("flex max-w-[380px] flex-col gap-0.5 px-5 py-4", tutor ? "self-start rounded-[28px_28px_28px_0] bg-pe-azul-marca text-pe-sobre-marca" : "self-end rounded-[28px_28px_0_28px] bg-pe-fundo")}>
      <span className={cnPe("text-[14px] font-semibold leading-5", !tutor && "text-pe-tinta-suave")}>{quem}</span>
      <p lang="en" className="m-0 text-[17px] leading-[27px] md:text-[19px] md:leading-[29px]">
        {children}
      </p>
    </div>
  );
}

function Plano({ p, anual }: { p: Site["precos"]["planos"][number]; anual: boolean }) {
  const gratis = p.preco_mensal_kz <= 0;
  const escuro = p.destaque;
  return (
    <article className={cnPe("flex min-w-0 flex-col gap-5 p-7 md:p-8", escuro ? "pe-sobre-marca rounded-[28px_28px_28px_0] bg-pe-azul-marca text-pe-sobre-marca" : "rounded-[12px] border border-pe-linha bg-pe-fundo")}>
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">{p.nome}</h3>
          {p.etiqueta ? <span className={cnPe("rounded-full px-3 py-0.5 text-[13px] font-semibold leading-5", escuro ? "bg-pe-realce text-pe-tinta" : "bg-pe-fundo-suave")}>{p.etiqueta}</span> : null}
        </div>
        <p className="m-0 font-pe-titulo text-[34px] font-bold leading-[42px] tabular-nums">
          {kz(p.preco_mensal_kz)}
          {gratis ? null : <span className={cnPe("ml-1 font-pe-texto text-[16px] font-normal", !escuro && "text-pe-tinta-suave")}>por mês</span>}
        </p>
        <p className={cnPe("m-0 text-[15px] leading-[22px]", !escuro && "text-pe-tinta-suave")}>
          {p.subtitulo}
        </p>
        {anual && p.preco_anual_kz ? <p className={cnPe("m-0 text-[15px] leading-[22px]", !escuro && "text-pe-tinta-suave")}>Ou {kz(p.preco_anual_kz)} por ano.</p> : null}
        {p.dias_teste > 0 ? <p className={cnPe("m-0 text-[15px] font-semibold leading-[22px]", escuro ? "text-pe-realce" : "text-pe-azul-marca")}>{p.dias_teste} dias grátis para experimentar</p> : null}
      </div>
      {p.caracteristicas.length ? (
        <ul className="m-0 flex flex-col gap-2 pl-5 text-[15px] leading-[22px]">
          {p.caracteristicas.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      ) : null}
      {p.nota_angola ? <p className={cnPe("m-0 text-[14px] leading-5", !escuro && "text-pe-tinta-suave")}>{p.nota_angola}</p> : null}
      <LigacaoPlano
        tipo={p.tipo}
        gratis={gratis}
        className={cnPe(
          "flex min-h-12 items-center justify-center rounded-pe-sm font-semibold no-underline",
          escuro ? "bg-pe-realce text-pe-tinta hover:text-pe-tinta hover:shadow-pe-2" : "border-2 border-pe-azul-marca bg-pe-fundo text-pe-azul-marca hover:bg-pe-fundo-suave"
        )}
      >
        {p.botao}
      </LigacaoPlano>
    </article>
  );
}
