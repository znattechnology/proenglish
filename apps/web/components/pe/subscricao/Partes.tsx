"use client";

import Link from "next/link";
import { Check } from "lucide-react";
import { Etiqueta, Logo } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import {
  dataPt,
  kz,
  precoPlano,
  vantagens,
  type EntradaHistorico,
  type Orcamento,
  type Periodo,
  type Plano,
  type Recibo,
} from "@/src/domains/student/subscricao/api";

/* ------------------------------------------------------------------ */
/* Passos do pagamento (Plano, Pagamento, Concluído)                   */
/* ------------------------------------------------------------------ */
const PASSOS = ["Plano", "Pagamento", "Concluído"] as const;

export function CabecalhoCheckout({ passo }: { passo: 1 | 2 | 3 }) {
  return (
    <header className="border-b border-pe-linha print:hidden">
      <div className="mx-auto flex max-w-[1080px] flex-wrap items-center justify-between gap-x-8 gap-y-3 px-5 py-3 md:px-6 md:py-4">
        <Link href="/user/subscription" aria-label="ProEnglish: voltar à subscrição">
          <Logo altura={36} />
        </Link>
        <ol aria-label="Passos do pagamento" className="m-0 flex list-none flex-wrap gap-x-6 gap-y-2 p-0 text-[15px] leading-[22px]">
          {PASSOS.map((nome, i) => {
            const n = i + 1;
            const feito = n < passo;
            const actual = n === passo;
            return (
              <li
                key={nome}
                aria-current={actual ? "step" : undefined}
                className={cnPe("flex items-center gap-2", feito ? "font-semibold text-pe-certo" : actual ? "font-semibold" : "text-pe-tinta-suave")}
              >
                <span
                  aria-hidden
                  className={cnPe(
                    "flex size-[26px] items-center justify-center rounded-full text-[14px]",
                    feito ? "bg-pe-certo-suave" : actual ? "bg-pe-azul-marca text-pe-sobre-marca" : "bg-pe-fundo-forte"
                  )}
                >
                  {feito ? <Check className="size-4" strokeWidth={3} /> : n}
                </span>
                {nome}
                {feito ? <span className="sr-only"> (feito)</span> : null}
              </li>
            );
          })}
        </ol>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/* Resumo da compra                                                     */
/* ------------------------------------------------------------------ */
export function ResumoCompra({
  plano,
  periodo,
  orcamento,
  desconto,
  codigo,
  credito,
  aoMudarPlano,
  className,
}: {
  plano: Plano;
  periodo: Periodo;
  /** Orçamento do servidor: quando existe, é ele que manda (crédito dos dias já pagos, código, total). */
  orcamento?: Orcamento;
  desconto?: number;
  codigo?: string | null;
  credito?: { kz: number; plano?: string | null; dias?: number } | null;
  aoMudarPlano?: () => void;
  className?: string;
}) {
  const preco = precoPlano(plano, periodo);
  const linhas: { descricao: string; valor_kz: number; tipo: string }[] = orcamento
    ? orcamento.linhas
    : [
        { tipo: "plano", descricao: periodo === "anual" ? "Anuidade" : "Mensalidade", valor_kz: preco },
        ...(desconto ? [{ tipo: "codigo", descricao: `Código ${codigo ?? ""}`.trim(), valor_kz: -desconto }] : []),
        ...(credito?.kz ? [{ tipo: "credito", descricao: `Crédito do ${credito.plano ?? "plano actual"}${credito.dias ? ` (${credito.dias} dias por usar)` : ""}`, valor_kz: -credito.kz }] : []),
      ];
  const total = orcamento ? orcamento.final_kz : Math.max(0, preco - (desconto ?? 0) - (credito?.kz ?? 0));
  return (
    <aside aria-label="Resumo da compra" className={cnPe("flex flex-col gap-4", className)}>
      <section className="pe-sobre-marca flex flex-col gap-3 rounded-pe-fala bg-pe-azul-marca p-6 text-pe-sobre-marca">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="m-0 font-pe-titulo text-[22px] font-bold leading-7">{plano.name}</h2>
          {aoMudarPlano ? (
            <button type="button" onClick={aoMudarPlano} className="min-h-11 bg-transparent p-0 text-[15px] font-semibold text-pe-sobre-marca underline underline-offset-[3px]">
              Mudar de plano
            </button>
          ) : null}
        </div>
        <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5 text-[15px] leading-[22px]">
          {vantagens(plano).map((v) => (
            <li key={v}>{v}</li>
          ))}
        </ul>
      </section>
      <section className="flex flex-col gap-2 rounded-pe-md border border-pe-linha p-5">
        <dl className="m-0 flex flex-col gap-2">
          {linhas.map((l) => (
            <div key={l.tipo + l.descricao} className={cnPe("flex justify-between gap-3", l.valor_kz < 0 && "text-pe-certo")}>
              <dt>{l.descricao}</dt>
              <dd className="m-0 shrink-0 tabular-nums">{l.valor_kz < 0 ? `menos ${kz(-l.valor_kz)}` : kz(l.valor_kz)}</dd>
            </div>
          ))}
          <div className="flex justify-between gap-3 border-t border-pe-linha pt-2 font-pe-titulo text-[20px] font-bold leading-7">
            <dt>A pagar hoje</dt>
            <dd className="m-0 tabular-nums">{kz(total)}</dd>
          </div>
        </dl>
        {orcamento?.dias_extra ? (
          <p className="m-0 text-[15px] leading-[22px] text-pe-certo">
            O crédito que sobra dá mais {orcamento.dias_extra} {orcamento.dias_extra === 1 ? "dia" : "dias"} de {plano.name}.
          </p>
        ) : null}
        {orcamento?.credito_kz ? (
          <p className="m-0 text-pe-legenda text-pe-tinta-suave">
            Os dias que ainda tinha no {orcamento.credito_plano?.nome ?? "plano actual"} passam a desconto. O {plano.name} começa já e dura até {dataPt(orcamento.termina_em)}.
          </p>
        ) : (
          <p className="m-0 text-pe-legenda text-pe-tinta-suave">
            Dura {periodo === "anual" ? "um ano" : "um mês"}. Não há cobranças automáticas: avisamos antes de terminar para renovar.
          </p>
        )}
        {orcamento?.aviso_codigo ? <p className="m-0 text-pe-legenda text-pe-tinta-suave">{orcamento.aviso_codigo}</p> : null}
      </section>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/* Comparar planos                                                      */
/* ------------------------------------------------------------------ */
export function TabelaPlanos({ planos, actual }: { planos: Plano[]; actual?: string }) {
  const linhas: [string, (p: Plano) => string][] = [
    ["Preço por mês", (p) => (Number(p.monthly_price) ? kz(p.monthly_price) : "Grátis")],
    ["Lições", (p) => (p.daily_lessons_limit ? `${p.daily_lessons_limit} por dia` : "Ilimitadas")],
    ["Vidas", (p) => (p.hearts_limit > 0 ? `${p.hearts_limit}, voltam com o tempo` : "Ilimitadas")],
    ["Conversa com o tutor", (p) => (p.daily_speaking_minutes == null ? "Sem limite" : p.daily_speaking_minutes > 0 ? `${p.daily_speaking_minutes} min por dia` : "Não incluída")],
    ["Certificados", (p) => (p.certificates ? "Sim" : "Não")],
  ];
  return (
    <div className="-mx-5 overflow-x-auto px-5 md:mx-0 md:px-0">
      <table className="w-full min-w-[520px] border-collapse text-left text-[15px] leading-[22px]">
        <thead>
          <tr>
            <th scope="col" className="w-[30%] pb-3" />
            {planos.map((p) => (
              <th key={p.id} scope="col" className={cnPe("px-3 pb-3 align-bottom font-pe-titulo text-[17px] font-bold", p.id === actual && "rounded-t-pe-md bg-pe-fundo-suave pt-3")}>
                <span className="flex flex-col items-start gap-1">
                  {p.id === actual ? <Etiqueta tipo="marca">O seu plano</Etiqueta> : null}
                  {p.name}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {linhas.map(([nome, valor]) => (
            <tr key={nome} className="border-t border-pe-linha">
              <th scope="row" className="py-2.5 pr-3 font-normal text-pe-tinta-suave">
                {nome}
              </th>
              {planos.map((p) => (
                <td key={p.id} className={cnPe("px-3 py-2.5 tabular-nums", p.id === actual && "bg-pe-fundo-suave font-semibold")}>
                  {valor(p)}
                </td>
              ))}
            </tr>
          ))}
          <tr>
            <td />
            {planos.map((p) => (
              <td key={p.id} className={cnPe("px-3 pb-3 pt-2", p.id === actual && "rounded-b-pe-md bg-pe-fundo-suave")}>
                {p.id !== actual && p.plan_type !== "FREE" ? (
                  <Link href={`/user/upgrade?plan=${p.plan_type}`} className="inline-flex min-h-11 items-center font-semibold underline-offset-[3px]">
                    {p.so_renovacao ? `Renovar o ${p.name}` : `Escolher ${p.name}`}
                  </Link>
                ) : null}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Lista de pagamentos                                                  */
/* ------------------------------------------------------------------ */
const ESTADOS: Record<string, { texto: string; tipo: "certo" | "errado" | "neutra" }> = {
  pago: { texto: "Pago", tipo: "certo" },
  recusado: { texto: "Recusado", tipo: "errado" },
  expirado: { texto: "Expirou", tipo: "neutra" },
  cancelado: { texto: "Cancelado", tipo: "neutra" },
  pendente: { texto: "Por confirmar", tipo: "neutra" },
};

export function LinhaPagamento({ p, activo, href }: { p: EntradaHistorico; activo?: boolean; href?: string }) {
  const estado = ESTADOS[p.status ?? "pago"] ?? ESTADOS.pago;
  const conteudo = (
    <>
      <span className="flex min-w-0 flex-col">
        <span className="font-semibold leading-[22px]">{p.description}</span>
        <span className="text-pe-legenda text-pe-tinta-suave">{dataPt(p.date)}</span>
      </span>
      <span className="flex shrink-0 flex-col items-end gap-1">
        <span className="font-semibold tabular-nums">{kz(p.amount_kz)}</span>
        <Etiqueta tipo={estado.tipo}>{estado.texto}</Etiqueta>
      </span>
    </>
  );
  const classe = cnPe(
    "flex items-center justify-between gap-4 border-b border-pe-linha px-3 py-3 text-pe-tinta no-underline",
    activo && "rounded-pe-md border-transparent bg-pe-fundo-suave"
  );
  return href ? (
    <Link href={href} aria-current={activo ? "true" : undefined} className={cnPe(classe, "hover:bg-pe-fundo-suave hover:text-pe-tinta")}>
      {conteudo}
    </Link>
  ) : (
    <div className={classe}>{conteudo}</div>
  );
}

/* ------------------------------------------------------------------ */
/* Recibo                                                               */
/* ------------------------------------------------------------------ */
export function ReciboDoc({ r }: { r: Recibo }) {
  const linhas: [string, string][] = [
    ["Cliente", r.cliente.nome],
    ["Email", r.cliente.email],
    ["Descrição", r.descricao],
    ...(r.validade ? ([["Período", `${dataPt(r.validade.inicio, { day: "numeric", month: "long" })} a ${dataPt(r.validade.fim)}`]] as [string, string][]) : []),
    ["Quantidade", String(r.quantidade)],
    ["Pago com", r.telefone_mascarado ? `${r.metodo}, ${r.telefone_mascarado}` : r.metodo],
    ...(r.desconto_kz || r.credito_kz ? ([["Subtotal", kz(r.subtotal_kz)]] as [string, string][]) : []),
    ...(r.desconto_kz ? ([[`Código ${r.codigo_promocional ?? ""}`.trim(), `menos ${kz(r.desconto_kz)}`]] as [string, string][]) : []),
    ...(r.credito_kz ? ([[r.credito_descricao ?? "Crédito do plano anterior", `menos ${kz(r.credito_kz)}`]] as [string, string][]) : []),
  ];
  return (
    <article aria-labelledby="titulo-recibo" className="flex flex-col gap-5 rounded-pe-md border border-pe-linha p-6 md:p-8 print:border-0 print:p-0">
      <div className="flex items-start justify-between gap-4">
        <Logo altura={40} />
        <Etiqueta tipo="certo">Pago</Etiqueta>
      </div>
      <div className="flex flex-col gap-1">
        <h2 id="titulo-recibo" className="m-0 font-pe-titulo text-[24px] font-bold leading-[30px]">
          Recibo {r.numero_recibo}
        </h2>
        <span className="text-pe-legenda text-pe-tinta-suave">Emitido a {dataPt(r.data_emissao)}</span>
      </div>
      <dl className="m-0 flex flex-col">
        {linhas.map(([dt, dd]) => (
          <div key={dt} className="flex justify-between gap-4 border-b border-pe-linha py-2.5 text-[15px] leading-[22px]">
            <dt className="text-pe-tinta-suave">{dt}</dt>
            <dd className="m-0 text-right">{dd}</dd>
          </div>
        ))}
        <div className="flex justify-between gap-4 pt-3 font-pe-titulo text-[20px] font-bold leading-7">
          <dt>Total pago</dt>
          <dd className="m-0 tabular-nums">{kz(r.total_kz)}</dd>
        </div>
      </dl>
      <p className="m-0 text-pe-legenda text-pe-tinta-suave">
        ProEnglish, Luanda, Angola. {r.referencia ? `Referência Multicaixa ${r.referencia}.` : ""}
      </p>
    </article>
  );
}
