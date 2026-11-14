"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { CheckCircle2, ChevronLeft, Circle, Mic } from "lucide-react";
import { BalaoFala, Botao, Etiqueta, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { cnPe } from "@/lib/pe";
import { COMPETENCIAS, useResumoQuery, type Ajuste, type PadraoConversa, type Resumo } from "@/src/domains/student/conversa/api";

export default function PaginaResumoConversa() {
  const { sessionId } = useParams<{ sessionId: string }>();
  // Enquanto o Claude avalia a conversa, a página volta a perguntar de 4 em 4 segundos.
  const { data, isError, refetch } = useResumoQuery(sessionId);
  const aAvaliar = data?.estado === "a_avaliar";
  useEffect(() => {
    if (!aAvaliar) return;
    const t = setInterval(() => void refetch(), 4000);
    return () => clearInterval(t);
  }, [aAvaliar, refetch]);

  return (
    <Pagina>
      <Link href="/user/laboratory/speaking/progress" className="-ml-1 flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-marca no-underline">
        <ChevronLeft aria-hidden className="size-5" /> Progresso a falar
      </Link>
      {isError ? (
        <div role="alert" className="flex max-w-[640px] flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
          <p className="m-0">Não encontrámos esta conversa.</p>
          <Botao tamanho="pequeno" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : !data ? (
        <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-5">
          <Osso className="h-[34px] w-2/3 max-w-[420px]" />
          <Osso className="h-[96px] rounded-pe-md" />
          <Osso className="h-[320px] rounded-pe-md" />
        </div>
      ) : (
        <Conteudo r={data} />
      )}
    </Pagina>
  );
}

function quando(iso: string) {
  const d = new Date(iso);
  const hoje = new Date();
  const ontem = new Date(Date.now() - 86_400_000);
  const hora = d.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === hoje.toDateString()) return `Hoje às ${hora}`;
  if (d.toDateString() === ontem.toDateString()) return `Ontem às ${hora}`;
  return `${d.toLocaleDateString("pt-PT", { day: "numeric", month: "long" })} às ${hora}`;
}

function Conteudo({ r }: { r: Resumo }) {
  const minutos = r.minutos_cobrados;
  const notas = r.notas
    ? (["geral", "fluencia", "gramatica", "pronuncia", "vocabulario"] as const).filter((k) => r.notas![k] !== null).map((k) => ({ k, nome: COMPETENCIAS[k], valor: r.notas![k] as number }))
    : [];

  return (
    <>
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">{r.situacao.titulo}</h1>
          <p className="m-0 text-pe-tinta-suave">
            {quando(r.iniciada_em)}, {minutos ? `${minutos} ${minutos === 1 ? "minuto" : "minutos"} com o tutor` : "sem minutos contados"}
          </p>
        </div>
        <Botao asChild tipo="secundario" tamanho="medio" className="self-start md:self-auto">
          <Link href={r.situacao.id ? `/user/laboratory/speaking/real-time?situacao=${encodeURIComponent(r.situacao.id)}` : "/user/laboratory/speaking/real-time"}>
            {r.situacao.id ? "Repetir esta conversa" : "Nova conversa"}
          </Link>
        </Botao>
      </div>

      {r.fala ? (
        <p className="m-0 flex max-w-[760px] items-start gap-3 rounded-pe-md border border-pe-linha px-4 py-3 text-[17px] leading-[26px]">
          <Mic aria-hidden className="mt-0.5 size-5 shrink-0 text-pe-azul-marca" />
          <span>
            {r.fala.frase}
            {r.fala.fonte === "estimado" ? <span className="block text-pe-legenda text-pe-tinta-suave">Tempo estimado pelas palavras que disse.</span> : null}
          </span>
        </p>
      ) : null}

      {notas.length ? (
        <dl className={cnPe("m-0 grid grid-cols-2 gap-3", notas.length === 5 ? "sm:grid-cols-3 lg:grid-cols-5" : "sm:grid-cols-4")}>
          {notas.map((n) => (
            <div
              key={n.k}
              className={cnPe(
                "flex min-w-0 flex-col px-5 py-4",
                n.k === "geral" ? "pe-sobre-marca rounded-[24px_24px_24px_0] bg-pe-azul-marca text-pe-sobre-marca" : "rounded-pe-md bg-pe-fundo-suave"
              )}
            >
              <dt className={cnPe("text-pe-legenda", n.k === "geral" ? "" : "text-pe-tinta-suave")}>{n.nome}</dt>
              <dd className="m-0 font-pe-titulo text-[32px] font-bold leading-[38px] tabular-nums">{Math.round(n.valor)}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <div className="flex max-w-[760px] flex-col gap-1 rounded-pe-md bg-pe-fundo-suave p-5">
          <h2 className="m-0 text-[17px] font-semibold leading-6">
            {r.estado === "em_curso"
              ? "Esta conversa ainda não terminou"
              : r.estado === "a_avaliar"
                ? "A avaliar a conversa…"
                : r.estado === "nao_ligou"
                  ? "A chamada não chegou a ligar"
                  : "Conversa curta demais para dar notas"}
          </h2>
          <p className="m-0 text-pe-tinta-suave" aria-live="polite">
            {r.estado === "em_curso"
              ? "Volte daqui a pouco para ver o resumo."
              : r.estado === "a_avaliar"
                ? "Demora uns segundos. Esta página actualiza-se sozinha."
                : r.estado === "nao_ligou"
                  ? "Não gastou minutos. Pode tentar outra vez quando quiser."
                  : "Responda pelo menos a algumas perguntas do tutor para receber notas e correcções. Os minutos contam na mesma para o seu dia."}
          </p>
        </div>
      )}

      {r.resumo ? <p className="m-0 max-w-[72ch] text-[17px] leading-[26px]">{r.resumo}</p> : null}

      <div className="grid items-start gap-8 lg:grid-cols-[3fr_2fr]">
        <section aria-labelledby="titulo-transcricao" className="flex min-w-0 flex-col gap-3">
          <h2 id="titulo-transcricao" className="m-0 font-pe-titulo text-pe-titulo-s">
            A conversa
          </h2>
          {r.transcricao.length ? (
            <div className="flex flex-col gap-3">
              {r.transcricao.map((f, i) => (
                <BalaoFala key={i} quem={f.quem} autor={f.quem === "tutor" ? "Tutor" : "Você"} className={cnPe("max-w-[85%] md:max-w-[560px] [&_.text-pe-corpo-l]:text-[17px] [&_.text-pe-corpo-l]:leading-[26px]", f.quem === "aluno" && "[&>span]:text-pe-tinta-suave")}>
                  <p lang="en" className="m-0">
                    {f.quem === "aluno" ? <ComErros texto={f.texto} correccoes={r.correccoes} /> : f.texto}
                  </p>
                </BalaoFala>
              ))}
            </div>
          ) : (
            <p className="m-0 text-pe-tinta-suave">Não ficou registada nenhuma fala nesta conversa.</p>
          )}
        </section>

        <div className="flex min-w-0 flex-col gap-8 lg:sticky lg:top-8">
          <Objectivos r={r} />

          <section aria-labelledby="titulo-correccoes" className="flex flex-col gap-3">
            <h2 id="titulo-correccoes" className="m-0 font-pe-titulo text-pe-titulo-s">
              Correcções
            </h2>
            {r.correccoes.length ? (
              <ul className="m-0 flex list-none flex-col gap-3 p-0">
                {r.correccoes.map((c, i) => (
                  <li key={i} className="flex flex-col gap-1 rounded-pe-md border border-pe-linha p-4">
                    <span lang="en" className="text-[15px] leading-[22px] text-pe-tinta-suave line-through decoration-pe-errado decoration-2">
                      <span className="sr-only">Disse: </span>
                      {c.disse}
                    </span>
                    <span lang="en" className="font-semibold leading-[22px]">
                      <span className="sr-only">Forma certa: </span>
                      {c.certo}
                    </span>
                    <span className="text-[14px] leading-5 text-pe-tinta-suave">{c.porque}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="m-0 text-pe-tinta-suave">{notas.length ? "Nenhuma correcção nesta conversa." : "Sem correcções."}</p>
            )}
          </section>

          {r.padroes?.length ? (
            <section aria-labelledby="titulo-padroes" className="flex flex-col gap-3">
              <h2 id="titulo-padroes" className="m-0 font-pe-titulo text-pe-titulo-s">
                Erros a trabalhar
              </h2>
              <ul className="m-0 flex list-none flex-col gap-3 p-0">
                {r.padroes.map((p) => (
                  <li key={p.chave} className="flex flex-col gap-1.5 rounded-pe-md bg-pe-fundo-suave p-4">
                    <EstadoPadrao estado={p.estado} />
                    <span className="leading-[22px]">{p.descricao}</span>
                    <Exemplo errado={p.errado} certo={p.certo} />
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {r.palavras_bem_usadas.length ? (
            <section aria-labelledby="titulo-palavras" className="flex flex-col gap-3">
              <h2 id="titulo-palavras" className="m-0 font-pe-titulo text-pe-titulo-s">
                Palavras novas que usou bem
              </h2>
              <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
                {r.palavras_bem_usadas.map((p) => (
                  <li key={p} lang="en" className="rounded-pe-sm bg-pe-certo-suave px-3 py-1.5 text-[15px] font-semibold leading-5">
                    {p}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      </div>
    </>
  );
}

/** Marca, na fala do aluno, o trecho que foi corrigido. */
function ComErros({ texto, correccoes }: { texto: string; correccoes: Ajuste[] }) {
  const baixo = texto.toLowerCase();
  const c = correccoes.find((x) => x.disse && baixo.includes(x.disse.toLowerCase().replace(/[.!?]+$/, "")));
  if (!c) return <>{texto}</>;
  const alvo = c.disse.replace(/[.!?]+$/, "");
  const i = baixo.indexOf(alvo.toLowerCase());
  return (
    <>
      {texto.slice(0, i)}
      <mark className="rounded-[2px] bg-pe-errado-suave px-0.5 text-pe-tinta underline decoration-pe-errado decoration-wavy underline-offset-4">{texto.slice(i, i + alvo.length)}</mark>
      {texto.slice(i + alvo.length)}
    </>
  );
}

/** As frases-alvo: ditas sozinho (contam como aprendidas) ou ainda não. */
function Objectivos({ r }: { r: Resumo }) {
  const lista = r.objectivos ?? [];
  if (!lista.length) return null;
  const avaliada = r.estado === "avaliada";
  const ditas = lista.filter((o) => o.usado).length;
  return (
    <section aria-labelledby="titulo-objectivos" className="flex flex-col gap-3">
      <h2 id="titulo-objectivos" className="m-0 font-pe-titulo text-pe-titulo-s">
        Objectivos
      </h2>
      <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">
        {!avaliada
          ? "Vemos que frases disse quando a conversa for avaliada."
          : ditas === lista.length
            ? "Disse todas as frases sozinho. Ficam como aprendidas."
            : ditas
              ? `Disse ${ditas} de ${lista.length} frases sozinho. Essas ficam como aprendidas.`
              : "Ainda não disse estas frases sozinho. Tente na próxima conversa."}
      </p>
      <ul className="m-0 flex list-none flex-col p-0">
        {lista.map((o) => (
          <li key={o.en} className="flex items-start gap-2.5 border-b border-pe-fundo-forte py-2.5 last:border-b-0">
            {o.usado ? <CheckCircle2 aria-hidden className="mt-0.5 size-5 shrink-0 text-pe-certo" /> : <Circle aria-hidden className="mt-0.5 size-5 shrink-0 text-pe-tinta-suave" />}
            <span className="flex min-w-0 flex-col">
              <span lang="en" className="font-semibold leading-[22px]">
                {o.en}
              </span>
              {o.pt ? <span className="text-[14px] leading-5 text-pe-tinta-suave">{o.pt}</span> : null}
              {avaliada ? (
                <span className={cnPe("text-[14px] leading-5", o.usado ? "font-semibold text-pe-certo" : "text-pe-tinta-suave")}>
                  {o.usado ? "Disse sozinho" : o.com_ajuda ? "Disse logo a seguir ao tutor: ainda não conta" : "Ainda não disse"}
                </span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function EstadoPadrao({ estado }: { estado: PadraoConversa["estado"] }) {
  if (estado === "superado") return <Etiqueta tipo="certo">Já superado</Etiqueta>;
  if (estado === "recorrente") return <Etiqueta tipo="realce">Repete-se</Etiqueta>;
  return <Etiqueta>Novo</Etiqueta>;
}

function Exemplo({ errado, certo }: { errado: string; certo: string }) {
  if (!errado || !certo) return null;
  return (
    <span lang="en" className="text-[15px] leading-[22px]">
      <span className="sr-only">Disse: </span>
      <span className="text-pe-tinta-suave line-through decoration-pe-errado decoration-2">{errado}</span>
      <span aria-hidden> → </span>
      <span className="sr-only">. Forma certa: </span>
      <span className="font-semibold">{certo}</span>
    </span>
  );
}
