"use client";

import Link from "next/link";
import { useState } from "react";
import { Pilulas, BarraProgresso, Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { MinutosPorDia } from "@/components/pe/estatisticas/MinutosPorDia";
import { duracao, useEstatisticasQuery, type Estatisticas, type Periodo } from "@/src/domains/student/progresso/api";

const PERIODOS: Record<string, Periodo> = { "7 dias": "7", "30 dias": "30", Tudo: "tudo" };
const NOMES = Object.keys(PERIODOS) as (keyof typeof PERIODOS)[];

const CRITERIOS: Record<string, string> = { fluencia: "Fluência", pronuncia: "Pronúncia", gramatica: "Gramática", vocabulario: "Vocabulário" };

export default function PaginaEstatisticas() {
  const [nome, setNome] = useState<(typeof NOMES)[number]>("7 dias");
  const periodo = PERIODOS[nome];
  const { data, isFetching, isError, refetch } = useEstatisticasQuery(periodo);

  return (
    <Pagina>
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Estatísticas</h1>
          <Link href="/user/grades" className="self-start text-[15px] font-semibold text-pe-azul-marca underline-offset-[3px]">
            Ver as notas dos cursos
          </Link>
        </div>
        <Pilulas opcoes={NOMES} valor={nome} aoMudar={setNome} rotulo="Período" />
      </div>

      {isError ? (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
          <p className="m-0">Não conseguimos calcular as estatísticas.</p>
          <Botao tamanho="pequeno" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : !data ? (
        <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-5">
          <Osso className="h-[110px] rounded-pe-md" />
          <Osso className="h-[300px] rounded-pe-md" />
        </div>
      ) : (
        <div className={isFetching ? "opacity-60 motion-safe:transition-opacity" : undefined} aria-busy={isFetching}>
          <Conteudo e={data} periodoNome={nome} />
        </div>
      )}
    </Pagina>
  );
}

function comparacao(variacao: number | null, unidade: (n: number) => string, periodoNome: string) {
  if (variacao === null || periodoNome === "Tudo") return null;
  if (variacao === 0) return "igual ao período anterior";
  return `${variacao > 0 ? "mais" : "menos"} ${unidade(Math.abs(variacao))} que no período anterior`;
}

function Conteudo({ e, periodoNome }: { e: Estatisticas; periodoNome: string }) {
  const numeros = [
    { nome: "Tempo de estudo", valor: duracao(e.tempo_estudo.minutos), nota: `${e.dias_meta_cumprida} de ${e.dias} dias com a meta cumprida` },
    {
      nome: "Lições concluídas",
      valor: String(e.licoes_concluidas.total),
      nota: comparacao(e.licoes_concluidas.variacao, (n) => String(n), periodoNome) ?? "lições do laboratório",
    },
    { nome: "Dias seguidos", valor: String(e.sequencia.atual), nota: `o seu recorde é ${e.sequencia.maior}` },
    {
      nome: "Respostas certas",
      valor: e.respostas.percentagem === null ? "–" : `${e.respostas.percentagem}%`,
      nota: e.respostas.total ? `${e.respostas.certas} de ${e.respostas.total} perguntas` : "ainda sem respostas neste período",
    },
  ];
  const tipos = e.por_tipo_exercicio.filter((t) => t.total > 0).sort((a, b) => (b.percentagem ?? 0) - (a.percentagem ?? 0));
  const conv = e.conversacao;

  return (
    <div className="flex flex-col gap-6">
      <dl className="m-0 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {numeros.map((n) => (
          <div key={n.nome} className="flex flex-col gap-0.5 rounded-pe-md bg-pe-fundo-suave p-4 md:p-5">
            <dt className="text-pe-legenda text-pe-tinta-suave">{n.nome}</dt>
            <dd className="m-0 font-pe-titulo text-[28px] font-bold leading-[34px] tabular-nums md:text-[32px] md:leading-[38px]">{n.valor}</dd>
            <dd className="m-0 text-[14px] leading-5 text-pe-tinta-suave">{n.nota}</dd>
          </div>
        ))}
      </dl>

      <div className="grid items-start gap-5 lg:grid-cols-[3fr_2fr]">
        <section aria-labelledby="titulo-minutos" className="flex min-w-0 flex-col gap-4 rounded-pe-md border border-pe-linha p-5 md:p-6">
          <h2 id="titulo-minutos" className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">
            Minutos de estudo por dia
          </h2>
          {e.minutos_por_dia.length ? (
            <MinutosPorDia dias={e.minutos_por_dia.map((d) => ({ data: d.data, minutos: d.minutos, rotulo: d.dia_semana }))} meta={e.meta_diaria_minutos} />
          ) : (
            <p className="m-0 text-pe-tinta-suave">Ainda não estudou neste período.</p>
          )}
          <p className="m-0 text-pe-legenda text-pe-tinta-suave">
            {duracao(e.tempo_estudo.por_tipo.licoes)} no laboratório, {duracao(e.tempo_estudo.por_tipo.videos)} a ver aulas e {duracao(e.tempo_estudo.por_tipo.conversacao)} a conversar com o tutor.{" "}
            <Link href="/user/settings" className="underline-offset-[3px]">
              Mudar a meta diária
            </Link>
          </p>
        </section>

        <section aria-labelledby="titulo-tipos" className="flex min-w-0 flex-col gap-3.5 rounded-pe-md border border-pe-linha p-5 md:p-6">
          <h2 id="titulo-tipos" className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">
            Respostas certas por tipo
          </h2>
          {tipos.length ? (
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {tipos.map((t) => (
                <li key={t.tipo} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1">
                  <span className="truncate text-[15px] leading-[22px]">{t.rotulo}</span>
                  <span className="text-[15px] font-semibold tabular-nums">{t.percentagem}%</span>
                  <BarraProgresso valor={t.percentagem ?? 0} rotulo={`${t.rotulo}: ${t.certas} de ${t.total} certas`} className="col-span-2" />
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-pe-tinta-suave">Faça lições no laboratório para ver aqui onde acerta mais.</p>
          )}
        </section>
      </div>

      <section aria-labelledby="titulo-conversa" className="flex flex-col gap-4 rounded-pe-md border border-pe-linha p-5 md:p-6">
        <h2 id="titulo-conversa" className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">
          Conversa com o tutor
        </h2>
        {conv.sessoes ? (
          <div className="flex flex-col gap-5 md:flex-row md:items-start md:gap-10">
            <div className="flex flex-col gap-1 md:w-[260px] md:shrink-0">
              <p className="m-0 flex items-baseline gap-1">
                <span className="font-pe-titulo text-[44px] font-bold leading-[48px] tabular-nums">{conv.pontuacao_media}</span>
                <span className="text-pe-tinta-suave">de 100, em média</span>
              </p>
              <p className="m-0 text-[15px] leading-[22px]">
                {conv.sessoes} {conv.sessoes === 1 ? "conversa" : "conversas"}, {duracao(conv.minutos)} a falar. Melhor nota: {conv.melhor_pontuacao}.
              </p>
            </div>
            {conv.criterios ? (
              <ul className="m-0 grid flex-1 list-none gap-3 p-0 sm:grid-cols-2">
                {Object.entries(conv.criterios)
                  .filter(([, v]) => v !== null)
                  .map(([k, v]) => (
                    <li key={k} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1">
                      <span className="text-[15px]">{CRITERIOS[k] ?? k}</span>
                      <span className="text-[15px] font-semibold tabular-nums">{v}</span>
                      <BarraProgresso valor={v ?? 0} rotulo={`${CRITERIOS[k] ?? k}: ${v} de 100`} className="col-span-2" />
                    </li>
                  ))}
              </ul>
            ) : null}
          </div>
        ) : (
          <div className="flex flex-col items-start gap-3">
            <p className="m-0 text-pe-tinta-suave">Ainda não conversou com o tutor neste período.</p>
            <Botao asChild tipo="secundario" tamanho="pequeno">
              <Link href="/user/laboratory/speaking/real-time">Conversar com o tutor</Link>
            </Botao>
          </div>
        )}
        {conv.ultima_sessao?.resumo ? (
          <div className="rounded-pe-md bg-pe-fundo-suave p-4">
            <p className="m-0 text-pe-legenda text-pe-tinta-suave">Última conversa, {new Date(conv.ultima_sessao.data).toLocaleDateString("pt-PT", { day: "numeric", month: "long" })}</p>
            <p className="m-0 mt-1 text-[15px] leading-[22px]">{conv.ultima_sessao.resumo}</p>
          </div>
        ) : null}
      </section>
    </div>
  );
}
