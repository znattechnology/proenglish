"use client";

import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { Aviso, BarraProgresso, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Cabeca, Numeros } from "@/components/pe/professor/Partes";
import { detalhePlano } from "@/components/pe/admin/Comum";
import { kz } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import { PAPEL, quandoEntrou, usePainelAdminQuery, type Painel } from "@/src/domains/admin/administracao/api";

const MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const h2 = "m-0 font-pe-titulo text-[22px] font-semibold leading-7";

export default function PainelAdmin() {
  const { data, isError, refetch } = usePainelAdminQuery();
  return (
    <Pagina className="gap-8">
      <Cabeca titulo="Painel" texto={`${MESES[new Date().getMonth()]}, até hoje.`} />
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar o painel.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <>
          <Osso className="h-[104px] rounded-pe-md" />
          <Osso className="h-72 rounded-pe-md" />
        </>
      ) : (
        <Conteudo p={data} />
      )}
    </Pagina>
  );
}

function Conteudo({ p }: { p: Painel }) {
  const n = p.numeros;
  const a = p.atencao;
  const avisos = [
    a.pagamentos_falhados_semana ? { texto: `${a.pagamentos_falhados_semana} ${a.pagamentos_falhados_semana === 1 ? "pagamento falhou" : "pagamentos falharam"} esta semana.`, href: "/admin/subscriptions/failed", accao: "Ver pagamentos" } : null,
    a.terminam_3_dias ? { texto: `${a.terminam_3_dias} ${a.terminam_3_dias === 1 ? "subscrição termina" : "subscrições terminam"} nos próximos 3 dias.`, href: "/admin/subscriptions/subscribers?estado=a_expirar&dias=3", accao: "Ver lista" } : null,
    a.cursos_em_revisao ? { texto: `${a.cursos_em_revisao} ${a.cursos_em_revisao === 1 ? "curso espera" : "cursos esperam"} pela sua revisão.`, href: "/admin/courses/review", accao: "Rever cursos" } : null,
    a.opinioes_por_rever ? { texto: `${a.opinioes_por_rever} ${a.opinioes_por_rever === 1 ? "opinião de aluno por rever" : "opiniões de alunos por rever"}.`, href: "/admin/feedback", accao: "Rever opiniões" } : null,
  ].filter(Boolean) as { texto: string; href: string; accao: string }[];
  const maxPlano = Math.max(1, ...p.por_plano.map((x) => x.utilizadores));

  return (
    <>
      <Numeros
        itens={[
          { nome: "Utilizadores", valor: num(n.utilizadores), nota: n.novos_mes ? `+${num(n.novos_mes)} este mês` : "nenhum novo este mês" },
          { nome: "Assinantes pagos", valor: num(n.assinantes_pagos), nota: `${num(n.estudantes)} estudantes no total` },
          { nome: "Receita do mês", valor: kz(n.receita_mes_kz), nota: "pagamentos confirmados" },
          { nome: "Professores", valor: num(n.professores), nota: n.professores_por_activar ? `${n.professores_por_activar} convites por aceitar` : "nenhum convite pendente" },
        ]}
      />

      <div className="grid gap-9 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section aria-labelledby="t-atencao" className="flex flex-col gap-3">
          <h2 id="t-atencao" className={h2}>
            A precisar de atenção
          </h2>
          {avisos.length ? (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {avisos.map((v) => (
                <li key={v.href} className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-pe-md bg-pe-realce-suave px-4 py-3">
                  <AlertCircle aria-hidden className="size-5 shrink-0" />
                  <span className="min-w-0 flex-1">{v.texto}</span>
                  <Link href={v.href} className="font-semibold text-pe-azul-marca underline-offset-[3px]">
                    {v.accao}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Nada pendente: pagamentos, cursos e opiniões estão em dia.</p>
          )}
          {n.email_por_verificar ? (
            <p className="m-0 text-pe-legenda text-pe-tinta-suave">
              {num(n.email_por_verificar)} contas com o email por verificar{n.email_por_verificar_3d ? `, ${num(n.email_por_verificar_3d)} há mais de 3 dias` : ""}.{" "}
              <Link href="/admin/users?estado=email_por_verificar">Ver</Link>
            </p>
          ) : null}
        </section>

        <section aria-labelledby="t-planos" className="flex flex-col gap-4">
          <h2 id="t-planos" className={h2}>
            Utilizadores por plano
          </h2>
          <ul className="m-0 flex list-none flex-col gap-3.5 p-0">
            {p.por_plano.map((x) => (
              <li key={x.plano} className="flex flex-col gap-1.5">
                <span className="flex justify-between">
                  <span>{x.nome}</span>
                  <span className="font-semibold tabular-nums">{num(x.utilizadores)}</span>
                </span>
                <BarraProgresso valor={(x.utilizadores / maxPlano) * 100} rotulo={`${x.nome}: ${x.utilizadores}`} altura={10} cor={x.plano === "FREE" ? "vivo" : "marca"} />
                {detalhePlano(x) ? <span className="text-pe-legenda text-pe-tinta-suave">{detalhePlano(x)}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section aria-labelledby="t-recentes" className="flex flex-col gap-3">
        <div className="flex items-end justify-between gap-3">
          <h2 id="t-recentes" className={h2}>
            Contas novas
          </h2>
          <Link href="/admin/users" className="font-semibold">
            Ver todos os utilizadores
          </Link>
        </div>
        <ul className="m-0 flex list-none flex-col p-0">
          {p.recentes.map((u) => (
            <li key={u.id} className="flex flex-wrap items-center justify-between gap-x-4 border-b border-pe-fundo-forte py-3">
              <Link href={`/admin/users/${u.id}`} className="flex min-w-0 flex-col text-pe-tinta no-underline hover:underline">
                <span className="font-semibold">{u.nome}</span>
                <span className="truncate text-pe-legenda text-pe-tinta-suave">{u.email}</span>
              </Link>
              <span className="text-[15px] text-pe-tinta-suave">
                {PAPEL[u.papel]}, {quandoEntrou(u.criado_em).toLowerCase()}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
