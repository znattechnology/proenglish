"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { ChevronLeft } from "lucide-react";
import { BalaoFala, Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { cnPe } from "@/lib/pe";
import { COMPETENCIAS, useResumoQuery, type Ajuste, type Resumo } from "@/src/domains/student/conversa/api";

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
        <ChevronLeft aria-hidden className="size-5" /> Progresso na conversa
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
