"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { CheckCircle2, XCircle } from "lucide-react";
import { Logo, Osso } from "@/components/pe";
import { dataPt } from "@/src/domains/student/subscricao/api";
import { useVerificarCertificadoQuery } from "@/src/domains/student/progresso/api";

/** Página pública: uma empresa confirma um certificado pelo número, sem conta. */
export default function VerificarCertificado() {
  const { numero } = useParams<{ numero: string }>();
  const { data, isLoading, isError, error, refetch } = useVerificarCertificadoQuery(decodeURIComponent(numero));
  const naoExiste = isError && (error as { status?: number })?.status === 404;
  const valido = data?.valido && data.estado === "valido";

  return (
    <div className="pe min-h-dvh bg-pe-fundo-suave">
      <header className="border-b border-pe-linha bg-pe-fundo">
        <div className="mx-auto flex max-w-[720px] items-center px-5 py-4">
          <Link href="/" aria-label="ProEnglish">
            <Logo altura={36} />
          </Link>
        </div>
      </header>
      <main className="mx-auto flex max-w-[720px] flex-col gap-5 px-5 py-10">
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8">Verificação de certificado</h1>
        {isLoading ? (
          <Osso className="h-[240px] rounded-pe-md" />
        ) : isError && !naoExiste ? (
          <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-fundo p-6">
            <span className="font-pe-titulo text-[20px] font-bold">Não foi possível verificar agora</span>
            <span>O problema é da ligação ou do nosso lado, não do certificado. Tente outra vez daqui a pouco.</span>
            <button type="button" onClick={() => refetch()} className="min-h-11 rounded-pe-sm bg-pe-azul-marca px-5 font-semibold text-pe-sobre-marca">
              Tentar outra vez
            </button>
          </div>
        ) : isError || !data ? (
          <div role="alert" className="flex items-start gap-3 rounded-pe-md bg-pe-fundo p-6">
            <XCircle aria-hidden className="mt-0.5 size-7 shrink-0 text-pe-errado" />
            <div className="flex flex-col gap-1">
              <span className="font-pe-titulo text-[20px] font-bold">Não encontrámos este certificado</span>
              <span>Confirme o número {decodeURIComponent(numero)}. Tem o formato PE-C-2026-000000.</span>
            </div>
          </div>
        ) : (
          <article className="flex flex-col gap-5 rounded-pe-md bg-pe-fundo p-6 md:p-8">
            <div role="status" className="flex items-center gap-3">
              {valido ? <CheckCircle2 aria-hidden className="size-8 text-pe-certo" /> : <XCircle aria-hidden className="size-8 text-pe-errado" />}
              <span className={`font-pe-titulo text-[22px] font-bold ${valido ? "text-pe-certo" : "text-pe-errado"}`}>
                {valido ? "Certificado válido" : "Certificado revogado"}
              </span>
            </div>
            <dl className="m-0 flex flex-col">
              {(
                [
                  ["Estudante", data.nome_aluno],
                  ["Curso", data.curso],
                  ["Nota final", data.nota_final === null || data.nota_final === undefined ? "Sem nota registada" : `${Math.round(data.nota_final)}%`],
                  ...(data.nivel_fala ? [["Nível de fala", data.nivel_fala]] : []),
                  ...(data.nota_exame_oral != null ? [["Exame oral", `${data.nota_exame_oral}%`]] : []),
                  ...(data.notas_fala ?? []).map((n) => [`${n.nome} (exame oral)`, `${n.nota}`]),
                  ["Emitido em", dataPt(data.emitido_em)],
                  ["Número", data.numero],
                  ...(data.revogado_em ? [["Revogado em", dataPt(data.revogado_em)]] : []),
                ] as [string, string][]
              ).map(([dt, dd]) => (
                <div key={dt} className="flex justify-between gap-4 border-b border-pe-fundo-forte py-2.5">
                  <dt className="text-pe-tinta-suave">{dt}</dt>
                  <dd className="m-0 text-right font-semibold">{dd}</dd>
                </div>
              ))}
            </dl>
            {data.nivel_fala_texto ? <p className="m-0 font-semibold">{data.nivel_fala_texto}, avaliado num exame oral com tarefas de trabalho.</p> : null}
            <p className="m-0 text-pe-legenda text-pe-tinta-suave">Emitido pela ProEnglish, Luanda, Angola, a quem concluiu o curso com a nota indicada.</p>
          </article>
        )}
      </main>
    </div>
  );
}
