"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ArrowLeft, Printer } from "lucide-react";
import { Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { LinhaPagamento, ReciboDoc } from "@/components/pe/subscricao/Partes";
import { kz, useHistoricoQuery, useReciboQuery } from "@/src/domains/student/subscricao/api";

export default function PaginaPagamentos() {
  return (
    <Suspense>
      <Pagamentos />
    </Suspense>
  );
}

function Pagamentos() {
  const params = useSearchParams();
  const { data: historico, isLoading, isError, refetch } = useHistoricoQuery();
  const lista = historico?.payment_history ?? [];
  const comRecibo = lista.filter((p) => p.receipt_number);
  const escolhido = params.get("recibo") ?? comRecibo[0]?.receipt_number ?? null;

  return (
    <Pagina>
      <div className="flex flex-col gap-2 print:hidden">
        <Link href="/user/subscription" className="inline-flex min-h-11 items-center gap-1.5 self-start text-[15px] font-semibold underline-offset-[3px]">
          <ArrowLeft aria-hidden className="size-5" /> Subscrição
        </Link>
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Pagamentos e recibos</h1>
      </div>

      {isError ? (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
          <p className="m-0">Não conseguimos carregar os pagamentos.</p>
          <Botao tamanho="pequeno" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : isLoading ? (
        <div aria-busy="true" aria-label="A carregar" className="grid gap-6 lg:grid-cols-[2fr_3fr]">
          <Osso className="h-[240px] rounded-pe-md" />
          <Osso className="h-[420px] rounded-pe-md" />
        </div>
      ) : !lista.length ? (
        <div className="flex max-w-[560px] flex-col items-start gap-3 rounded-pe-md bg-pe-fundo-suave p-6">
          <h2 className="m-0 text-pe-titulo-s">Ainda não fez pagamentos</h2>
          <p className="m-0 text-pe-tinta-suave">Quando pagar um plano, o recibo aparece aqui.</p>
          <Botao asChild tamanho="pequeno">
            <Link href="/user/upgrade">Ver os planos</Link>
          </Botao>
        </div>
      ) : (
        <div className="grid items-start gap-8 lg:grid-cols-[2fr_3fr]">
          <section aria-labelledby="titulo-lista" className="flex flex-col gap-2 print:hidden">
            <h2 id="titulo-lista" className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">
              Pagamentos
            </h2>
            <div className="flex flex-col">
              {lista.map((p) => (
                <LinhaPagamento
                  key={p.id}
                  p={p}
                  activo={!!p.receipt_number && p.receipt_number === escolhido}
                  href={p.receipt_number ? `/user/billing?recibo=${p.receipt_number}` : undefined}
                />
              ))}
            </div>
            <p className="m-0 pt-1 text-pe-legenda text-pe-tinta-suave">Total pago: {kz(historico?.summary.total_amount_paid)}.</p>
          </section>
          {escolhido ? <ReciboEscolhido numero={escolhido} /> : null}
        </div>
      )}
    </Pagina>
  );
}

function ReciboEscolhido({ numero }: { numero: string }) {
  const { data, isLoading, isError } = useReciboQuery(numero);
  if (isLoading) return <Osso className="h-[420px] rounded-pe-md" />;
  if (isError || !data) {
    return (
      <p role="alert" className="m-0 rounded-pe-md bg-pe-errado-suave p-5">
        Não encontrámos o recibo {numero}.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <ReciboDoc r={data} />
      <Botao tipo="secundario" tamanho="pequeno" className="self-start print:hidden" onClick={() => window.print()}>
        <Printer aria-hidden /> Imprimir ou guardar em PDF
      </Botao>
    </div>
  );
}
