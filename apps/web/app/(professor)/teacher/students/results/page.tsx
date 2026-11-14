"use client";

import Link from "next/link";
import { useState } from "react";
import { Download } from "lucide-react";
import { Aviso, BarraProgresso, Botao, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaAlunos } from "@/components/pe/professor/SeparadoresAlunos";
import { num, pct } from "@/src/domains/teacher/professor/api";
import { descarregarCsv, useResultadosQuery } from "@/src/domains/teacher/professor/alunos";

const PERIODOS = { "7 dias": 7, "30 dias": 30, "3 meses": 90 } as const;
const h2 = "m-0 font-pe-titulo text-[22px] font-semibold leading-7";

export default function ResultadosCursos() {
  const [periodo, setPeriodo] = useState<keyof typeof PERIODOS>("30 dias");
  const { data, isError, isFetching, refetch } = useResultadosQuery(PERIODOS[periodo]);
  const [erro, setErro] = useState<string | null>(null);
  const maxFaixa = Math.max(1, ...(data?.faixas.map((f) => f.alunos) ?? [1]));

  return (
    <Pagina className="gap-7">
      <CabecaAlunos activo="Resultados dos cursos" texto={`Últimos ${periodo === "3 meses" ? "3 meses" : periodo}, todos os cursos.`} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Pilulas rotulo="Período" opcoes={Object.keys(PERIODOS) as (keyof typeof PERIODOS)[]} valor={periodo} aoMudar={setPeriodo} />
        <Botao
          tipo="secundario"
          tamanho="pequeno"
          onClick={async () => {
            setErro(null);
            try {
              await descarregarCsv(`/teacher/resultados/exportar/?periodo=${PERIODOS[periodo]}`, "resultados.csv");
            } catch {
              setErro("Não foi possível exportar. Tente outra vez.");
            }
          }}
        >
          <Download aria-hidden className="size-[18px]" />
          Exportar relatório
        </Botao>
      </div>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}

      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os resultados.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-96 rounded-pe-md" />
      ) : (
        <div aria-busy={isFetching} className="flex flex-col gap-9">
          <div className="grid gap-9 xl:grid-cols-2">
            <section aria-labelledby="t-conclusao" className="flex flex-col gap-4">
              <h2 id="t-conclusao" className={h2}>
                Conclusão por curso
              </h2>
              {data.conclusao_por_curso.length ? (
                <ul className="m-0 flex list-none flex-col gap-3.5 p-0">
                  {data.conclusao_por_curso.map((c) => (
                    <li key={c.id} className="flex flex-col gap-1.5">
                      <span className="flex justify-between gap-3">
                        <span>
                          {c.tipo === "pratica" ? "Prática: " : ""}
                          {c.titulo}
                        </span>
                        <span className="shrink-0 font-semibold tabular-nums">{pct(c.conclusao)}</span>
                      </span>
                      <BarraProgresso valor={c.conclusao ?? 0} rotulo={`Conclusão de ${c.titulo}`} altura={10} cor="marca" />
                      <span className="text-[13px] text-pe-tinta-suave">{num(c.alunos)} {c.alunos === 1 ? "aluno" : "alunos"}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Ainda não há cursos publicados com alunos.</p>
              )}
            </section>

            <section aria-labelledby="t-faixas" className="flex flex-col gap-4">
              <div className="flex flex-col gap-1">
                <h2 id="t-faixas" className={h2}>
                  Alunos por faixa de acerto
                </h2>
                <p className="m-0 text-pe-legenda text-pe-tinta-suave">Só conta quem respondeu a 5 exercícios ou mais no período.</p>
              </div>
              <table className="w-full border-collapse tabular-nums">
                <caption className="sr-only">Alunos por faixa de acerto</caption>
                <tbody>
                  {data.faixas.map((f) => (
                    <tr key={f.nome}>
                      <th scope="row" className="w-32 py-2 pr-3 text-left font-normal">
                        {f.nome}
                      </th>
                      <td className="py-2">
                        <span className="flex items-center gap-3">
                          <span className="h-7 rounded-r-pe-sm bg-pe-azul-marca" style={{ width: `${(f.alunos / maxFaixa) * 100}%`, minWidth: f.alunos ? 4 : 0 }} />
                          <span className="font-semibold">{num(f.alunos)}</span>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>

          <section aria-labelledby="t-dificeis" className="flex max-w-[880px] flex-col gap-3">
            <div className="flex flex-col gap-1">
              <h2 id="t-dificeis" className={h2}>
                Perguntas com mais erros
              </h2>
              <p className="m-0 text-pe-tinta-suave">Com 5 respostas ou mais no período. Uma pergunta com acerto baixo pode estar confusa ou ter a resposta errada.</p>
            </div>
            {data.perguntas_dificeis.length ? (
              <ul className="m-0 flex list-none flex-col p-0">
                {data.perguntas_dificeis.map((p) => (
                  <li key={p.challenge_id} className="flex flex-wrap items-center justify-between gap-x-5 gap-y-1 border-b border-pe-fundo-forte py-3">
                    <span className="flex min-w-0 flex-[1_1_320px] flex-col">
                      <span className="font-semibold">{p.frase}</span>
                      <span className="text-pe-legenda text-pe-tinta-suave">
                        {p.curso}, {p.onde.charAt(0).toLowerCase() + p.onde.slice(1)}
                      </span>
                    </span>
                    <span className="tabular-nums">
                      Acerto <strong className={p.acerto < 50 ? "text-pe-errado" : undefined}>{Math.round(p.acerto)}%</strong>
                      <span className="text-pe-tinta-suave"> em {p.respostas}</span>
                    </span>
                    <Link href={p.licao_id ? `/teacher/practice/${p.curso_id}/lessons/${p.licao_id}?exercicio=${p.challenge_id}` : `/teacher/practice/${p.curso_id}`} className="py-2 font-semibold text-pe-azul-vivo underline-offset-[3px]">
                      Rever pergunta
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Ainda não há respostas suficientes neste período.</p>
            )}
          </section>
        </div>
      )}
    </Pagina>
  );
}
