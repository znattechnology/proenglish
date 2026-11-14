"use client";

import { useState } from "react";
import { Aviso, BarraProgresso, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaFala } from "@/components/pe/professor/fala/Cabeca";
import { Numeros } from "@/components/pe/professor/Partes";
import { num, pct } from "@/src/domains/teacher/professor/api";
import { useResultadosFalaQuery } from "@/src/domains/teacher/professor/fala";

const PERIODOS = { "7 dias": 7, "30 dias": 30, "90 dias": 90, "1 ano": 365 } as const;
const h2 = "m-0 font-pe-titulo text-[22px] font-semibold leading-7";

export default function ResultadosFala() {
  const [periodo, setPeriodo] = useState<keyof typeof PERIODOS>("30 dias");
  const { data: r, isError, refetch } = useResultadosFalaQuery(PERIODOS[periodo]);
  return (
    <Pagina className="gap-7">
      <CabecaFala activo="Resultados" />
      <Pilulas rotulo="Período" opcoes={Object.keys(PERIODOS) as (keyof typeof PERIODOS)[]} valor={periodo} aoMudar={setPeriodo} />
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os resultados.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !r ? (
        <Osso className="h-96 rounded-pe-md" />
      ) : (
        <>
          <Numeros
            itens={[
              {
                nome: "Minutos a falar",
                valor: num(r.minutos),
                nota: r.minutos_variacao_pct == null ? "no período" : `${r.minutos_variacao_pct >= 0 ? "+" : "−"}${Math.abs(Math.round(r.minutos_variacao_pct))}% que no período anterior`,
              },
              { nome: "Sessões", valor: num(r.sessoes), nota: `${r.sessoes_por_dia.toLocaleString("pt-PT", { maximumFractionDigits: 1 })} por dia` },
              { nome: "Pontuação média", valor: r.pontuacao_media == null ? "–" : String(Math.round(r.pontuacao_media)), nota: "em 100" },
              { nome: "Terminam a sessão", valor: pct(r.terminam_pct), nota: r.terminam_pct == null ? "sem sessões" : `${100 - Math.round(r.terminam_pct)}% saem a meio` },
            ]}
          />
          <div className="grid gap-9 xl:grid-cols-2">
            <section aria-labelledby="t-comp" className="flex flex-col gap-4">
              <h2 id="t-comp" className={h2}>
                Pontuação por competência
              </h2>
              {r.competencias.some((c) => c.media != null) ? (
                <ul className="m-0 flex list-none flex-col gap-3.5 p-0">
                  {r.competencias
                    .filter((c) => c.media != null)
                    .map((c) => (
                      <li key={c.nome} className="flex flex-col gap-1.5">
                        <span className="flex justify-between">
                          <span>{c.nome}</span>
                          <span className="font-semibold tabular-nums">{Math.round(c.media!)} em 100</span>
                        </span>
                        <BarraProgresso valor={c.media!} rotulo={`${c.nome}: ${Math.round(c.media!)} em 100`} altura={10} cor="marca" />
                      </li>
                    ))}
                </ul>
              ) : (
                <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Ainda sem conversas avaliadas neste período.</p>
              )}
            </section>
            <section aria-labelledby="t-sit" className="flex flex-col gap-3">
              <h2 id="t-sit" className={h2}>
                Situações mais usadas
              </h2>
              {r.situacoes.length ? (
                <table className="w-full border-collapse tabular-nums">
                  <caption className="sr-only">Situações mais usadas</caption>
                  <thead>
                    <tr>
                      <th scope="col" className="border-b border-pe-linha px-3 py-2.5 text-left text-pe-legenda font-semibold text-pe-tinta-suave">Situação</th>
                      <th scope="col" className="border-b border-pe-linha px-3 py-2.5 text-right text-pe-legenda font-semibold text-pe-tinta-suave">Sessões</th>
                      <th scope="col" className="border-b border-pe-linha px-3 py-2.5 text-right text-pe-legenda font-semibold text-pe-tinta-suave">Média</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.situacoes.map((s) => (
                      <tr key={s.id}>
                        <td className="border-b border-pe-fundo-forte p-3">{s.nome}</td>
                        <td className="border-b border-pe-fundo-forte p-3 text-right">{num(s.sessoes)}</td>
                        <td className="border-b border-pe-fundo-forte p-3 text-right">{s.media == null ? "–" : Math.round(s.media)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Ainda sem conversas neste período.</p>
              )}
            </section>
          </div>
          <p className="m-0 max-w-[68ch] text-pe-legenda text-pe-tinta-suave">
            Conta as conversas nas suas situações e as dos alunos dos seus cursos nas situações da plataforma. As conversas em si são privadas: só se mostram números.
          </p>
        </>
      )}
    </Pagina>
  );
}
