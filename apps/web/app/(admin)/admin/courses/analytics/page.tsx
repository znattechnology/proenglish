"use client";

import Link from "next/link";
import { useState } from "react";
import { Download } from "lucide-react";
import { Aviso, Botao, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Numeros } from "@/components/pe/professor/Partes";
import { Barras, BarrasHorizontais } from "@/components/pe/admin/Barras";
import { CabecaSeccao, SEPARADORES_CURSOS } from "@/components/pe/admin/Comum";
import { diaMesCurto } from "@/src/domains/student/subscricao/api";
import { num, pct } from "@/src/domains/teacher/professor/api";
import { descarregarCsv } from "@/src/domains/teacher/professor/alunos";
import { useAnaliseCursosQuery } from "@/src/domains/admin/administracao/api";

const PERIODOS = { "7 dias": 7, "30 dias": 30, "90 dias": 90 } as const;
const h2 = "m-0 font-pe-titulo text-[20px] font-semibold leading-7";
/** Médias com uma casa decimal ("0,9"), sem arredondar para inteiros. */
const dec = (v: number) => v.toLocaleString("pt-PT", { maximumFractionDigits: 1 });

export default function AnaliseCursos() {
  const [periodo, setPeriodo] = useState<keyof typeof PERIODOS>("30 dias");
  const { data: a, isError, refetch } = useAnaliseCursosQuery(PERIODOS[periodo]);
  const [erro, setErro] = useState<string | null>(null);

  return (
    <Pagina className="gap-7">
      <CabecaSeccao titulo="Cursos" activo="Análise" itens={SEPARADORES_CURSOS} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Pilulas rotulo="Período" opcoes={Object.keys(PERIODOS) as (keyof typeof PERIODOS)[]} valor={periodo} aoMudar={setPeriodo} />
        <Botao
          tipo="secundario"
          tamanho="pequeno"
          onClick={async () => {
            setErro(null);
            try {
              await descarregarCsv(`/admin/cursos/analise/exportar/?periodo=${PERIODOS[periodo]}`, "analise-cursos.csv");
            } catch {
              setErro("Não foi possível exportar. Tente outra vez.");
            }
          }}
        >
          <Download aria-hidden className="size-[18px]" />
          Exportar
        </Botao>
      </div>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar a análise.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !a ? (
        <Osso className="h-96 rounded-pe-md" />
      ) : (
        <>
          {a.gerado_em ? (
            <p className="-mt-4 m-0 text-pe-legenda text-pe-tinta-suave">
              Calculado às {new Date(a.gerado_em).toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" })}
              {a.cache_segundos ? `; actualiza de ${Math.round(a.cache_segundos / 60)} em ${Math.round(a.cache_segundos / 60)} minutos` : ""}.
            </p>
          ) : null}
          <Numeros
            itens={[
              { nome: "Activos por dia", valor: dec(a.activos_dia_media), nota: `média de ${a.periodo} dias` },
              { nome: "Activos por semana", valor: num(a.activos_semana), nota: a.pct_activos_semana == null ? undefined : `${Math.round(a.pct_activos_semana)}% dos alunos` },
              {
                nome: "Inscrições novas",
                valor: num(a.inscricoes_novas),
                nota: a.inscricoes_variacao_pct == null ? "no período" : `${a.inscricoes_variacao_pct >= 0 ? "+" : "−"}${Math.abs(Math.round(a.inscricoes_variacao_pct))}% que no período anterior`,
              },
              { nome: "Lições concluídas", valor: num(a.licoes_concluidas), nota: `${dec(a.licoes_por_dia)} por dia` },
            ]}
          />
          <section aria-labelledby="t-activos" className="flex flex-col gap-3">
            <h2 id="t-activos" className={h2}>
              Alunos activos por dia
            </h2>
            <Barras
              titulo="Alunos activos por dia"
              dados={a.activos_dia.map((d) => ({ rotulo: diaMesCurto(new Date(`${d.dia}T12:00:00`)), valor: d.n }))}
              rotuloA={(r) => `a ${r}`}
              vazio="Nenhum aluno activo no período."
            />
          </section>
          <div className="grid gap-9 xl:grid-cols-2">
            <section aria-labelledby="t-area" className="flex flex-col gap-3">
              <h2 id="t-area" className={h2}>
                Inscrições por área
              </h2>
              {a.por_area.length ? <BarrasHorizontais titulo="Inscrições por área" dados={a.por_area.map((x) => ({ nome: x.area, valor: x.inscricoes }))} /> : <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Sem inscrições.</p>}
            </section>
            <section aria-labelledby="t-baixa" className="flex flex-col gap-3">
              <h2 id="t-baixa" className={h2}>
                Cursos com conclusão mais baixa
              </h2>
              {a.conclusao_baixa.length ? (
                <>
                  <table className="w-full border-collapse tabular-nums">
                    <caption className="sr-only">Cursos com conclusão mais baixa</caption>
                    <thead>
                      <tr>
                        {["Curso", "Alunos", "Conclusão"].map((t, i) => (
                          <th key={t} scope="col" className={`border-b border-pe-linha px-3 py-2.5 text-pe-legenda font-semibold text-pe-tinta-suave ${i ? "text-right" : "text-left"}`}>
                            {t}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {a.conclusao_baixa.map((c) => (
                        <tr key={c.id}>
                          <td className="border-b border-pe-fundo-forte p-3">
                            <Link href={`/admin/courses/review/${c.id}`}>{c.titulo}</Link>
                            {c.desistencia ? (
                              <span className="block text-pe-legenda text-pe-tinta-suave">
                                {Math.round(c.desistencia.pct)}% dos que não acabaram param {c.desistencia.texto}.
                              </span>
                            ) : null}
                          </td>
                          <td className="border-b border-pe-fundo-forte p-3 text-right">{num(c.alunos)}</td>
                          <td className="border-b border-pe-fundo-forte p-3 text-right font-semibold">{pct(c.conclusao)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="m-0 text-pe-legenda text-pe-tinta-suave">Só cursos publicados com 5 alunos ou mais. Vale a pena falar com os professores destes cursos.</p>
                </>
              ) : (
                <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Ainda não há cursos com alunos suficientes para comparar.</p>
              )}
            </section>
          </div>
        </>
      )}
    </Pagina>
  );
}
