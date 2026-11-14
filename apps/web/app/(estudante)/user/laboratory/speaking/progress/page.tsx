"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { BarraProgresso, Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { useProgressoQuery, type Progresso } from "@/src/domains/student/conversa/api";
import { duracao } from "@/src/domains/student/progresso/api";
import { diaMesCurto } from "@/src/domains/student/subscricao/api";

export default function PaginaProgressoConversa() {
  const { data, isError, refetch } = useProgressoQuery();
  return (
    <Pagina>
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Progresso na conversa</h1>
        <Botao asChild tamanho="medio" className="self-start md:self-auto">
          <Link href="/user/laboratory/speaking/real-time">Começar uma conversa</Link>
        </Botao>
      </div>
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
      </div>

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
  );
}
