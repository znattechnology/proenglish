"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { Aviso, Botao, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Cabeca, Numeros } from "@/components/pe/professor/Partes";
import { Barras, BarrasHorizontais } from "@/components/pe/admin/Barras";
import { kz } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import { descarregarCsv } from "@/src/domains/teacher/professor/alunos";
import { useRelatorioQuery } from "@/src/domains/admin/administracao/negocio";

const PERIODOS = { "30 dias": 30, "90 dias": 90, "6 meses": 180, "1 ano": 365 } as const;
const h2 = "m-0 font-pe-titulo text-[20px] font-semibold leading-7";
const pct = (v: number | null) => (v == null ? "–" : `${Math.round(v)}%`);
/** "5,2 M Kz", "480 mil Kz" para os eixos. */
const kzCurto = (v: number) => (v >= 1e6 ? `${(v / 1e6).toLocaleString("pt-PT", { maximumFractionDigits: 1 })} M` : v >= 1e3 ? `${Math.round(v / 1e3)} mil` : String(v));

export default function Relatorios() {
  const [periodo, setPeriodo] = useState<keyof typeof PERIODOS>("6 meses");
  const { data: r, isError, refetch } = useRelatorioQuery(PERIODOS[periodo]);
  const [erro, setErro] = useState<string | null>(null);
  return (
    <Pagina className="gap-7">
      <Cabeca titulo="Relatórios" texto="Receita, assinantes e retenção." />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Pilulas rotulo="Período" opcoes={Object.keys(PERIODOS) as (keyof typeof PERIODOS)[]} valor={periodo} aoMudar={setPeriodo} />
        <Botao
          tipo="secundario"
          tamanho="pequeno"
          onClick={async () => {
            setErro(null);
            try {
              await descarregarCsv(`/admin/relatorios/exportar/?periodo=${PERIODOS[periodo]}`, "relatorio.csv");
            } catch {
              setErro("Não foi possível exportar. Tente outra vez.");
            }
          }}
        >
          <Download aria-hidden className="size-[18px]" />
          Exportar folha de cálculo
        </Botao>
      </div>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar o relatório.{" "}
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
                nome: periodo === "1 ano" ? "Receita no último ano" : `Receita nos últimos ${periodo}`,
                valor: kz(r.periodo_receita_kz ?? r.receita_mes_kz),
                nota: r.receita_variacao_pct == null ? "sem período anterior para comparar" : `${r.receita_variacao_pct >= 0 ? "+" : "−"}${Math.abs(Math.round(r.receita_variacao_pct))}% que o período anterior`,
              },
              {
                nome: "Receita mensal por assinante",
                valor: r.receita_por_assinante_kz == null || !r.assinantes_total ? "–" : kz(r.receita_por_assinante_kz),
                nota: r.assinantes_total ? "recorrente; o anual conta 1/12 por mês" : "ainda sem assinantes pagos",
              },
              { nome: "Ficam 3 meses", valor: pct(r.retencao_3_meses_pct), nota: "dos que pagam o 1.º mês" },
              { nome: "Teste passa a pago", valor: pct(r.teste_para_pago_pct), nota: "dos testes grátis terminados" },
            ]}
          />
          <section aria-labelledby="t-receita" className="flex flex-col gap-3">
            <h2 id="t-receita" className={h2}>
              Receita por mês, em kwanzas
            </h2>
            <Barras titulo="Receita por mês, em kwanzas" dados={r.receita_por_mes.map((m) => ({ rotulo: m.nome_curto, valor: m.valor_kz }))} formatar={kzCurto} rotuloA={(x) => `em ${x}`} altura={220} inteiros={false} vazio="Ainda sem receita no período." />
          </section>
          <section aria-labelledby="t-provincia" className="flex max-w-[720px] flex-col gap-3">
            <h2 id="t-provincia" className={h2}>
              Assinantes por província
            </h2>
            {r.por_provincia.length ? (
              <BarrasHorizontais titulo="Assinantes por província" dados={r.por_provincia.map((p) => ({ nome: p.nome, valor: p.assinantes }))} />
            ) : (
              <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Ainda nenhum assinante indicou a província.</p>
            )}
            <p className="m-0 text-pe-legenda text-pe-tinta-suave">
              Pela província que cada pessoa indicou no perfil. {num(r.assinantes_total)} assinantes
              {r.sem_provincia ? `, ${num(r.sem_provincia)} sem província indicada` : ""}.
            </p>
          </section>
        </>
      )}
    </Pagina>
  );
}
