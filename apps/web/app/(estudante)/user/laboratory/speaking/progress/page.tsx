"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { BarraProgresso, Botao, Etiqueta, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { ProgressoDaFala } from "@/components/pe/fala/Fala";
import { useProgressoQuery, type Progresso } from "@/src/domains/student/conversa/api";
import { duracao } from "@/src/domains/student/progresso/api";
import { diaMesCurto } from "@/src/domains/student/subscricao/api";

export default function PaginaProgressoConversa() {
  const { data, isError, refetch } = useProgressoQuery();
  return (
    <Pagina>
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Progresso a falar</h1>
        <Botao asChild tamanho="medio" className="self-start md:self-auto">
          <Link href="/user/laboratory/speaking/real-time">Começar uma conversa</Link>
        </Botao>
      </div>
      {/* Fase 3: quanto e como fala (todas as gravações e conversas). */}
      <ProgressoDaFala />
      <h2 className="m-0 mt-4 font-pe-titulo text-[22px] font-bold leading-7 md:text-pe-titulo-m">Conversas com o tutor</h2>
      {isError ? (
        <div role="alert" className="flex max-w-[640px] flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
          <p className="m-0">Não conseguimos carregar o progresso.</p>
          <Botao tamanho="pequeno" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : !data ? (
        <div aria-busy="true" aria-label="A carregar" className="grid gap-6 lg:grid-cols-[2fr_3fr]">
          <Osso className="h-[300px] rounded-pe-md" />
          <Osso className="h-[300px] rounded-pe-md" />
        </div>
      ) : !data.sessoes ? (
        <div className="flex max-w-[760px] flex-col gap-1 rounded-pe-md bg-pe-fundo-suave p-6">
          <h2 className="m-0 text-pe-titulo-s">Ainda não conversou com o tutor</h2>
          <p className="m-0 text-pe-tinta-suave">Depois da primeira conversa vê aqui a sua pontuação, o que melhorou e as conversas para rever.</p>
        </div>
      ) : (
        <Conteudo p={data} />
      )}
    </Pagina>
  );
}

function Conteudo({ p }: { p: Progresso }) {
  const variacao =
    p.variacao_mes === null ? null : p.variacao_mes === 0 ? "igual ao mês passado" : `${p.variacao_mes > 0 ? "mais" : "menos"} ${Math.abs(p.variacao_mes)} que no mês passado`;
  return (
    <div className="grid items-start gap-8 lg:grid-cols-[2fr_3fr]">
      <div className="flex min-w-0 flex-col gap-6">
        <section aria-labelledby="titulo-media" className="pe-sobre-marca flex flex-col gap-1 rounded-[28px_28px_28px_0] bg-pe-azul-marca p-6 text-pe-sobre-marca md:p-7">
          <h2 id="titulo-media" className="m-0 text-[15px] font-semibold leading-5">
            Pontuação média
          </h2>
          <p className="m-0 flex items-baseline gap-2">
            <span className="font-pe-titulo text-[56px] font-bold leading-[60px] tabular-nums">{p.media ?? "–"}</span>
            <span>de 100{variacao ? `, ${variacao}` : ""}</span>
          </p>
          <p className="m-0 text-[15px] leading-[22px]">
            {p.sessoes} {p.sessoes === 1 ? "conversa" : "conversas"}, {duracao(p.minutos)} a falar.
          </p>
        </section>

        <section aria-labelledby="titulo-competencias" className="flex flex-col gap-4">
          <h2 id="titulo-competencias" className="m-0 font-pe-titulo text-pe-titulo-s">
            Por competência
          </h2>
          <ul className="m-0 flex list-none flex-col gap-4 p-0">
            {p.por_competencia
              .filter((a) => a.valor !== null)
              .map((a) => (
                <li key={a.chave} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1">
                  <span className="font-semibold">{a.nome}</span>
                  <span className="font-pe-titulo text-[18px] font-bold tabular-nums">{a.valor}</span>
                  <BarraProgresso valor={a.valor ?? 0} rotulo={`${a.nome}: ${a.valor} de 100`} className="col-span-2" />
                  {a.nota ? <span className="col-span-2 text-[14px] leading-5 text-pe-tinta-suave">{a.nota}</span> : null}
                </li>
              ))}
          </ul>
        </section>

        <Padroes p={p} />
      </div>

      <div className="flex min-w-0 flex-col gap-8">
        <FrasesSozinho p={p} />

        <section aria-labelledby="titulo-ultimas" className="flex min-w-0 flex-col gap-3">
          <h2 id="titulo-ultimas" className="m-0 font-pe-titulo text-pe-titulo-s">
            Últimas conversas
          </h2>
          <ul className="m-0 flex list-none flex-col p-0">
            {p.ultimas.map((s) => (
              <li key={s.id}>
                <Link
                  href={`/user/laboratory/speaking/summary/${s.id}`}
                  className="flex min-h-[64px] items-center gap-4 border-b border-pe-fundo-forte py-3 text-pe-tinta no-underline hover:bg-pe-fundo-suave md:px-2"
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate font-semibold leading-[22px]">{s.titulo}</span>
                    <span className="text-[14px] leading-5 text-pe-tinta-suave">
                      {diaMesCurto(new Date(s.iniciada_em))}, {Math.max(1, Math.round(s.minutos))} min
                    </span>
                  </span>
                  <span className="font-pe-titulo text-[22px] font-bold tabular-nums">
                    {s.geral ?? <span className="text-[14px] font-normal text-pe-tinta-suave">sem nota</span>}
                  </span>
                  <ChevronRight aria-hidden className="size-5 shrink-0 text-pe-tinta-suave" />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

/** Os erros que se repetem (perfil de fala): primeiro os que ainda aparecem, depois os já superados. */
function Padroes({ p }: { p: Progresso }) {
  const lista = p.padroes ?? [];
  return (
    <section aria-labelledby="titulo-padroes" className="flex flex-col gap-3">
      <h2 id="titulo-padroes" className="m-0 font-pe-titulo text-pe-titulo-s">
        Erros a trabalhar
      </h2>
      {lista.length ? (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {lista.map((e) => (
            <li key={e.chave} className="flex flex-col gap-1.5 rounded-pe-md bg-pe-fundo-suave p-4">
              <span className="flex flex-wrap items-center gap-2">
                {e.superado ? <Etiqueta tipo="certo">Já superado</Etiqueta> : <Etiqueta tipo="realce">{e.ocorrencias === 1 ? "1 conversa" : `${e.ocorrencias} conversas`}</Etiqueta>}
                {e.ultima_ocorrencia ? <span className="text-[14px] leading-5 text-pe-tinta-suave">Última vez a {diaMesCurto(new Date(e.ultima_ocorrencia))}</span> : null}
              </span>
              <span className="leading-[22px]">{e.descricao}</span>
              {e.errado && e.certo ? (
                <span lang="en" className="text-[15px] leading-[22px]">
                  <span className="sr-only">Disse: </span>
                  <span className="text-pe-tinta-suave line-through decoration-pe-errado decoration-2">{e.errado}</span>
                  <span aria-hidden> → </span>
                  <span className="sr-only">. Forma certa: </span>
                  <span className="font-semibold">{e.certo}</span>
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="m-0 text-pe-tinta-suave">Ainda não encontrámos erros que se repitam.</p>
      )}
    </section>
  );
}

/** Frases que o aluno diz sozinho numa conversa: contam como aprendidas (voltam a 'com ajuda' se as falhar em dias seguidos). */
function FrasesSozinho({ p }: { p: Progresso }) {
  const f = p.frases_sozinho ?? { total: 0, recentes: [] };
  return (
    <section aria-labelledby="titulo-sozinho" className="flex flex-col gap-3">
      <h2 id="titulo-sozinho" className="m-0 font-pe-titulo text-pe-titulo-s">
        Frases que já diz sozinho
      </h2>
      <p className="m-0 flex items-baseline gap-2">
        <span className="font-pe-titulo text-[40px] font-bold leading-[44px] tabular-nums">{f.total}</span>
        <span className="text-pe-tinta-suave">{f.total === 1 ? "frase dita sem ajuda numa conversa" : "frases ditas sem ajuda numa conversa"}</span>
      </p>
      {f.recentes.length ? (
        <ul className="m-0 flex list-none flex-col p-0">
          {f.recentes.map((r) => (
            <li key={r.texto} className="flex flex-col border-b border-pe-fundo-forte py-2.5 last:border-b-0">
              <span lang="en" className="font-semibold leading-[22px]">
                {r.texto}
              </span>
              <span className="text-[14px] leading-5 text-pe-tinta-suave">
                {[r.traducao, r.dias > 1 ? `Disse em ${r.dias} dias diferentes` : r.ultima_vez ? `Disse a ${diaMesCurto(new Date(r.ultima_vez))}` : ""].filter(Boolean).join(". ")}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="m-0 text-pe-tinta-suave">Quando disser sozinho uma das frases-objectivo numa conversa, ela aparece aqui.</p>
      )}
      {f.a_recuperar ? (
        <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">
          {f.a_recuperar === 1 ? "1 frase voltou" : `${f.a_recuperar} frases voltaram`} a «disse com ajuda» depois de falhar em dois dias seguidos na revisão. Diga-as outra vez sozinho numa conversa para voltarem a contar.
        </p>
      ) : null}
    </section>
  );
}
