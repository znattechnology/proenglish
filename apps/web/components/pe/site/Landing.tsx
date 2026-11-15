import Link from "next/link";
import { Award, BookOpen, Bot, FlaskConical, MessageCircle, Mic, Plane } from "lucide-react";
import { cnPe } from "@/lib/pe";
import type { Site } from "@/src/domains/site/conteudo";
import { Convite, Moldura } from "./Moldura";
import { LigacaoPlano } from "./Entrada";

export const kz = (n: number) => `${String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ")} Kz`;

const h2 = "m-0 font-pe-titulo text-[30px] font-bold leading-[1.15] tracking-[-0.015em] md:text-[2.5rem]";
const caixa = "mx-auto flex max-w-[1200px] flex-col gap-8 px-4 py-14 md:gap-10 md:px-6 md:py-20";

const PASSOS = [
  { titulo: "Ouve a frase", texto: "Cada lição começa por uma situação do seu trabalho: uma reunião, uma chamada, um pedido a um colega." },
  { titulo: "Repete em voz alta", texto: "Diz a frase ao microfone. O sistema avalia a pronúncia e mostra-lhe as palavras a melhorar." },
  { titulo: "Conversa com o tutor", texto: "Fala por voz com o tutor de inteligência artificial sobre a mesma situação. Ele responde, corrige e explica em português." },
  { titulo: "Faz o exame oral", texto: "No fim do curso, o exame é falado e vale 40% da nota. É ele que dá acesso ao certificado." },
];

const SITUACOES = [
  { foto: "reuniao", alt: "Colegas a conversar numa reunião à volta de uma mesa", onde: "Na reunião", frase: "Let me share the figures for this quarter." },
  { foto: "chamada-escritorio", alt: "Profissional ao telefone no escritório, com o computador à frente", onde: "Ao telefone", frase: "Could you repeat that, please?" },
  { foto: "escuta", alt: "Profissional com auscultadores ao pescoço, atento ao ecrã", onde: "Na videochamada", frase: "Sorry, the line is bad. Can you hear me now?" },
];

/** Sectores da página inicial, pela ordem em que aparecem. `areas` são os nomes que a API usa para contar os cursos. */
const SECTORES = [
  { nome: "Petróleo e Gás", areas: ["Petróleo e Gás"], foto: "petroleo", alt: "Plataforma petrolífera no mar ao pôr do sol", frase: "Could you send me the drilling report by Friday?", texto: "Reuniões de segurança, relatórios de turno e instruções em plataforma." },
  { nome: "Banca", areas: ["Banca"], foto: "banca", alt: "Cliente a marcar o código numa caixa multibanco", frase: "Your transfer will arrive within two business days.", texto: "Atendimento, contas, taxas e reclamações explicadas com clareza." },
  { nome: "Tecnologia", areas: ["Tecnologia"], foto: "tecnologia", alt: "Dois programadores a rever código no mesmo ecrã", frase: "The deploy failed, so we rolled back.", texto: "Reuniões diárias, documentação e conversas com equipas remotas." },
  { nome: "Minas", areas: ["Minas"], foto: "minas", alt: "Camião de minério a subir a rampa de uma mina a céu aberto", frase: "The haul road is closed until the blast is cleared.", texto: "Segurança na mina, passagem de turno e relatórios de produção." },
  { nome: "Aviação", areas: ["Aviação"], foto: "cockpit", alt: "Piloto na cabine de um avião comercial, a preparar o voo", frase: "Luanda Tower, ready for departure, runway 23.", texto: "Fraseologia de rádio, tripulação de cabine, manutenção e assistência em terra.", novo: true },
  { nome: "Saúde", areas: ["Saúde"], foto: "saude", alt: "Dois profissionais de saúde a consultar um tablet", frase: "Where exactly does it hurt?", texto: "Consulta, triagem e passagem de turno com doentes e colegas estrangeiros." },
  { nome: "Direito", areas: ["Direito"], foto: "direito", alt: "Mão a assinar um contrato sobre a mesa", frase: "The contract takes effect on the first of March.", texto: "Contratos, prazos e correspondência formal." },
  { nome: "Negócios e Gestão", areas: ["Negócios", "Gestão"], foto: "negocios", alt: "Dois profissionais a conversar, sentados frente a frente", frase: "Please find the revised proposal attached.", texto: "Propostas, negociação e reuniões com clientes e parceiros." },
];

const ICONES = { livro: BookOpen, laboratorio: FlaskConical, bot: Bot, microfone: Mic, balao: MessageCircle, certificado: Award } as const;

/** Fotografia do site (public/site), em duas larguras. `forma` recorta-a no balão da marca. */
function Foto({ nome, alt, className, prioridade, sizes = "(min-width: 1024px) 560px, 100vw" }: { nome: string; alt: string; className?: string; prioridade?: boolean; sizes?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`/site/${nome}-1400.webp`}
      srcSet={`/site/${nome}-720.webp 720w, /site/${nome}-1400.webp 1400w`}
      sizes={sizes}
      alt={alt}
      loading={prioridade ? "eager" : "lazy"}
      fetchPriority={prioridade ? "high" : undefined}
      decoding="async"
      className={cnPe("block size-full object-cover", className)}
    />
  );
}

/** Onda da voz: mostra que ali se fala. Parada para quem pede menos movimento. */
function Onda({ className }: { className?: string }) {
  const barras = [10, 18, 28, 16, 24, 34, 20, 12, 26, 32, 18, 10, 22, 30, 14];
  return (
    <span aria-hidden className={cnPe("flex h-9 items-center gap-[3px]", className)}>
      {barras.map((h, i) => (
        <span key={i} className="pe-onda w-[3px] rounded-full bg-current" style={{ height: h, animationDelay: `${(i % 5) * 120}ms` }} />
      ))}
    </span>
  );
}

export function Landing({ site }: { site: Site }) {
  const t = site.topo;
  // Um número automático a zero (p.ex. "0 áreas") não se mostra.
  const numerosTopo = site.numeros.filter((n) => n.onde === "topo" && n.valor.trim() !== "0");
  const faixa = site.empresas.filter((e) => e.na_faixa);
  const gratis = site.precos.planos.some((p) => p.preco_mensal_kz <= 0);
  // Os cursos publicados de cada sector vêm da API; sem cursos, o cartão não mostra contagem.
  const sectores = SECTORES.map((x) => ({ novo: false, ...x, cursos: site.areas.filter((a) => x.areas.includes(a.nome)).reduce((n, a) => n + a.cursos, 0) }));

  return (
    <Moldura site={site} actual="inicio">
      {/* Topo */}
      <section className="overflow-hidden">
        <div className="mx-auto grid max-w-[1200px] items-center gap-x-14 gap-y-10 px-4 pb-14 pt-10 md:px-6 md:pb-24 md:pt-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
          <div className="flex min-w-0 flex-col gap-6">
            {t.etiqueta ? (
              <p className="m-0 flex items-center gap-2 self-start rounded-full bg-pe-realce-suave px-4 py-1.5 text-[15px] font-semibold text-pe-azul-marca">
                <Mic aria-hidden className="size-4" />
                {t.etiqueta}
              </p>
            ) : null}
            <h1 className="m-0 text-balance font-pe-titulo text-[40px] font-bold leading-[1.05] tracking-[-0.025em] md:text-[4rem]">{t.titulo}</h1>
            <p className="m-0 max-w-[520px] text-[18px] leading-[1.6] text-pe-tinta-suave md:text-[1.25rem]">{t.texto}</p>
            <div className="flex flex-wrap gap-4">
              <Link href={t.botao_principal.href} className="inline-flex min-h-[56px] items-center rounded-pe-sm bg-pe-realce px-8 text-[17px] font-semibold text-pe-tinta no-underline hover:text-pe-tinta hover:shadow-pe-2">
                {t.botao_principal.texto}
              </Link>
              {t.botao_secundario ? (
                <Link href={t.botao_secundario.href} className="inline-flex min-h-[56px] items-center rounded-pe-sm border-2 border-pe-azul-marca bg-pe-fundo px-7 text-[17px] font-semibold text-pe-azul-marca no-underline hover:bg-pe-fundo-suave">
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

          {/* A fotografia tem a forma do balão da marca; a conversa com o tutor assenta sobre ela. */}
          <figure aria-label="Exemplo de uma conversa com o tutor" className="relative m-0 min-w-0 pb-28 sm:pb-24 lg:pb-20">
            <div className="aspect-[4/3] overflow-hidden rounded-[56px_56px_56px_0] bg-pe-fundo-forte md:rounded-[88px_88px_88px_0]">
              <Foto nome="conversa" alt="Duas profissionais a conversar à mesa, a sorrir" prioridade />
            </div>
            <span aria-hidden className="absolute -right-3 -top-3 hidden size-24 rounded-[28px_28px_0_28px] bg-pe-realce md:block" />
            <div className="absolute inset-x-0 bottom-0 flex flex-col gap-2 sm:left-6 sm:right-auto sm:w-[400px] lg:-left-10">
              <div className="self-start rounded-pe-fala bg-pe-azul-marca px-5 py-3.5 text-pe-sobre-marca shadow-pe-2">
                <span className="block text-[13px] font-semibold leading-5 opacity-80">Tutor</span>
                <p lang="en" className="m-0 text-[17px] leading-[25px]">
                  Could you send me the <mark className="rounded-[2px] bg-pe-realce px-1 text-pe-tinta">drilling report</mark> by Friday?
                </p>
              </div>
              <div className="flex items-center gap-3 self-end rounded-pe-fala-aluno bg-pe-fundo px-5 py-3 shadow-pe-2">
                <Onda className="text-pe-azul-vivo" />
                <div className="flex flex-col">
                  <span className="text-[13px] font-semibold leading-5 text-pe-tinta-suave">Você, a falar</span>
                  <p lang="en" className="m-0 text-[16px] leading-6">Sure. I will send it on Thursday.</p>
                </div>
              </div>
            </div>
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

      {/* Como funciona: o método, centrado na fala */}
      <section id="como-funciona" className="scroll-mt-4 bg-pe-fundo-suave">
        <div className="mx-auto grid max-w-[1200px] items-center gap-x-16 gap-y-10 px-4 py-14 md:px-6 md:py-24 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1fr)]">
          <figure className="relative m-0 min-w-0">
            <div className="aspect-[4/5] max-h-[560px] w-full overflow-hidden rounded-[56px_56px_0_56px] bg-pe-fundo-forte md:rounded-[88px_88px_0_88px]">
              <Foto nome="chamada" alt="Jovem profissional ao telefone, a acenar a alguém com um sorriso" className="object-[70%_center]" />
            </div>
            <figcaption className="absolute bottom-6 left-0 max-w-[300px] rounded-pe-fala bg-pe-realce px-5 py-4 shadow-pe-2 md:-left-6">
              <span className="block text-[13px] font-semibold leading-5">O que ela diz</span>
              <span lang="en" className="font-pe-titulo text-[19px] font-light italic leading-[27px]">Good morning, this is Ana from the finance team.</span>
            </figcaption>
          </figure>
          <div className="flex min-w-0 flex-col gap-8">
            <div className="flex flex-col gap-3">
              <h2 className={h2}>Aqui, o inglês aprende-se a falar</h2>
              <p className="m-0 max-w-[560px] text-pe-corpo-l text-pe-tinta-suave">
                Saber a gramática não chega quando o telefone toca. No ProEnglish fala em voz alta desde a primeira lição, 15 minutos por dia, no telemóvel ou no computador.
              </p>
            </div>
            <ol className="m-0 flex list-none flex-col p-0">
              {PASSOS.map((p, i) => (
                <li key={p.titulo} className="flex gap-5 border-t border-pe-linha py-5 last:pb-0">
                  <span aria-hidden className="flex size-11 shrink-0 items-center justify-center rounded-pe-fala-s bg-pe-azul-marca font-pe-titulo text-[18px] font-bold text-pe-sobre-marca">
                    {i + 1}
                  </span>
                  <div className="flex min-w-0 flex-col gap-1">
                    <h3 className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">{p.titulo}</h3>
                    <p className="m-0 text-pe-tinta-suave">{p.texto}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      {/* Situações: cada fotografia diz a sua frase */}
      <section>
        <div className={caixa}>
          <div className="flex max-w-[640px] flex-col gap-3">
            <h2 className={h2}>Treina as frases que vai mesmo dizer</h2>
            <p className="m-0 text-pe-corpo-l text-pe-tinta-suave">Nada de diálogos de manual. Cada lição parte de um momento real do dia de trabalho.</p>
          </div>
          <ul className="m-0 grid list-none gap-6 p-0 md:grid-cols-3">
            {SITUACOES.map((s, i) => (
              <li key={s.foto} className={cnPe("flex min-w-0 flex-col gap-4", i === 1 && "md:mt-12")}>
                <div className={cnPe("aspect-[4/3] overflow-hidden bg-pe-fundo-forte", i === 1 ? "rounded-pe-fala-aluno" : "rounded-pe-fala")}>
                  <Foto nome={s.foto} alt={s.alt} sizes="(min-width: 768px) 380px, 100vw" />
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[15px] font-semibold leading-5 text-pe-tinta-suave">{s.onde}</span>
                  <span lang="en" className="font-pe-titulo text-[21px] font-light italic leading-[30px] text-pe-azul-marca">{s.frase}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Sectores: todos com o mesmo peso; a aviação é o mais recente */}
      <section id="areas" className="pe-sobre-marca scroll-mt-4 bg-pe-azul-marca text-pe-sobre-marca">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-10 px-4 py-14 md:gap-12 md:px-6 md:py-24">
          <div className="grid items-end gap-x-16 gap-y-5 lg:grid-cols-2">
            <h2 className="m-0 text-balance font-pe-titulo text-[34px] font-bold leading-[1.08] tracking-[-0.02em] md:text-[3.25rem]">O inglês do seu sector</h2>
            <p className="m-0 max-w-[520px] text-pe-corpo-l opacity-90">
              Cada sector tem as suas frases. Treina em voz alta as que vai usar no seu posto de trabalho, do poço de petróleo à torre de controlo.
            </p>
          </div>
          <ul className="m-0 grid list-none gap-x-6 gap-y-10 p-0 sm:grid-cols-2 lg:grid-cols-4">
            {sectores.map((a, i) => (
              <li key={a.nome} className="flex min-w-0 flex-col gap-4">
                <div className={cnPe("relative aspect-[4/3] overflow-hidden bg-white/10", i % 2 ? "rounded-pe-fala-aluno" : "rounded-pe-fala")}>
                  <Foto nome={a.foto} alt={a.alt} sizes="(min-width: 1024px) 280px, (min-width: 640px) 50vw, 100vw" />
                  {a.novo ? (
                    <span className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-pe-realce px-3 py-1 text-[13px] font-semibold leading-5 text-pe-tinta">
                      <Plane aria-hidden className="size-3.5" />
                      Novo
                    </span>
                  ) : null}
                </div>
                <div className="flex flex-col gap-1.5">
                  <h3 className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">{a.nome}</h3>
                  <p lang="en" className="m-0 font-pe-titulo text-[17px] font-light italic leading-[25px] text-pe-realce">{a.frase}</p>
                  <p className="m-0 text-[15px] leading-[22px] opacity-85">{a.texto}</p>
                  {a.cursos > 0 ? (
                    <p className="m-0 text-[14px] leading-5 opacity-75">{a.cursos} {a.cursos === 1 ? "curso" : "cursos"}</p>
                  ) : a.novo ? (
                    <p className="m-0 text-[14px] leading-5 opacity-75">Cursos em preparação</p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap items-center gap-x-8 gap-y-4 border-t border-white/20 pt-8">
            <p className="m-0 min-w-0 flex-[1_1_420px] text-pe-corpo-l">Não encontra o seu sector? O curso de inglês geral serve qualquer profissão e começa hoje.</p>
            <Link href="/signup" className="inline-flex min-h-[52px] items-center rounded-pe-sm bg-pe-realce px-7 text-[17px] font-semibold text-pe-tinta no-underline hover:text-pe-tinta hover:shadow-pe-2">
              Criar conta grátis
            </Link>
          </div>
        </div>
      </section>

      {site.servicos.length ? (
        <section>
          <div className={caixa}>
            <h2 className={h2}>O que encontra no ProEnglish</h2>
            <div className="grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
              {site.servicos.map((s) => {
                const Icone = ICONES[s.icone as keyof typeof ICONES] ?? BookOpen;
                return (
                <div key={s.id} className="flex min-w-0 flex-col gap-2">
                  <span aria-hidden className="mb-1 flex size-12 items-center justify-center rounded-pe-fala-s bg-pe-realce-suave text-pe-azul-marca">
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
