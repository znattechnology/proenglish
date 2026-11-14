"use client";

import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { Aviso, BarraProgresso, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Numeros } from "@/components/pe/professor/Partes";
import { Avatar, CabecaSeccao, SEPARADORES_SUBSCRICOES, detalhePlano } from "@/components/pe/admin/Comum";
import { diaMesCurto, kz } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import { quandoEntrou } from "@/src/domains/admin/administracao/api";
import { useResumoSubscricoesQuery } from "@/src/domains/admin/administracao/negocio";

const h2 = "m-0 font-pe-titulo text-[20px] font-semibold leading-7";
const pctTxt = (v: number | null) => (v == null ? "–" : `${v.toLocaleString("pt-PT", { maximumFractionDigits: 1 })}%`);

export default function ResumoSubscricoes() {
  const { data: r, isError, refetch } = useResumoSubscricoesQuery();
  const max = Math.max(1, ...(r?.por_plano.map((p) => p.utilizadores) ?? [1]));
  return (
    <Pagina className="gap-7">
      <CabecaSeccao titulo="Subscrições e pagamentos" activo="Resumo" itens={SEPARADORES_SUBSCRICOES} />
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar o resumo.{" "}
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
              { nome: "Assinantes pagos", valor: num(r.assinantes_pagos), nota: `${num(r.premium)} Premium, ${num(r.premium_plus)} Premium Plus` },
              { nome: "Receita do mês", valor: kz(r.receita_mes_kz), nota: `até ${diaMesCurto(new Date(`${r.receita_ate}T12:00:00`))}` },
              { nome: "Passam a pagar", valor: pctTxt(r.passam_a_pagar_pct), nota: "do Gratuito, em 30 dias" },
              { nome: "Cancelam", valor: pctTxt(r.cancelam_pct), nota: r.em_teste ? `por mês; ${num(r.em_teste)} em teste agora` : "por mês" },
            ]}
          />
          {r.atencao.falhados_semana || r.atencao.terminam_3_dias ? (
            <section aria-labelledby="t-atencao" className="flex flex-col gap-2">
              <h2 id="t-atencao" className={h2}>
                A precisar de atenção
              </h2>
              {r.atencao.falhados_semana ? (
                <p className="m-0 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-pe-md bg-pe-realce-suave px-4 py-3">
                  <AlertCircle aria-hidden className="size-5" />
                  <span className="flex-1">
                    {r.atencao.falhados_semana} {r.atencao.falhados_semana === 1 ? "pagamento falhou" : "pagamentos falharam"} esta semana ({kz(r.atencao.falhados_semana_kz)}).
                  </span>
                  <Link href="/admin/subscriptions/failed" className="font-semibold">
                    Ver pagamentos
                  </Link>
                </p>
              ) : null}
              {r.atencao.terminam_3_dias ? (
                <p className="m-0 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-pe-md bg-pe-realce-suave px-4 py-3">
                  <AlertCircle aria-hidden className="size-5" />
                  <span className="flex-1">
                    {r.atencao.terminam_3_dias} {r.atencao.terminam_3_dias === 1 ? "subscrição termina" : "subscrições terminam"} nos próximos 3 dias sem renovação.
                  </span>
                  <Link href="/admin/subscriptions/subscribers?estado=a_expirar&dias=3" className="font-semibold">
                    Ver lista
                  </Link>
                </p>
              ) : null}
            </section>
          ) : null}
          <div className="grid gap-9 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <section aria-labelledby="t-planos" className="flex flex-col gap-4">
              <h2 id="t-planos" className={h2}>
                Utilizadores por plano
              </h2>
              <ul className="m-0 flex list-none flex-col gap-3.5 p-0">
                {r.por_plano.map((p) => (
                  <li key={p.plano} className="flex flex-col gap-1.5">
                    <span className="flex justify-between">
                      <span>{p.nome}</span>
                      <span className="font-semibold tabular-nums">{num(p.utilizadores)}</span>
                    </span>
                    <BarraProgresso valor={(p.utilizadores / max) * 100} rotulo={`${p.nome}: ${p.utilizadores}`} altura={10} cor={p.plano === "FREE" ? "vivo" : "marca"} />
                    {detalhePlano(p) ? <span className="text-pe-legenda text-pe-tinta-suave">{detalhePlano(p)}</span> : null}
                  </li>
                ))}
              </ul>
            </section>
            <section aria-labelledby="t-recentes" className="flex flex-col gap-3">
              <h2 id="t-recentes" className={h2}>
                Pagamentos recentes
              </h2>
              {r.recentes.length ? (
                <ul className="m-0 flex list-none flex-col p-0">
                  {r.recentes.map((p) => (
                    <li key={p.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-pe-fundo-forte py-3">
                      <Avatar iniciais={p.utilizador.iniciais} />
                      <Link href={`/admin/users/${p.utilizador.id}`} className="flex min-w-0 flex-1 flex-col text-pe-tinta no-underline hover:underline">
                        <span className="font-semibold">{p.utilizador.nome}</span>
                        <span className="text-pe-legenda text-pe-tinta-suave">{p.descricao}</span>
                      </Link>
                      <span className="font-semibold tabular-nums">{kz(p.valor_kz)}</span>
                      <span className="w-24 text-right text-[15px] text-pe-tinta-suave">{quandoEntrou(p.data).replace(/, \d\d:\d\d$/, "")}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Ainda sem pagamentos.</p>
              )}
            </section>
          </div>
        </>
      )}
    </Pagina>
  );
}
