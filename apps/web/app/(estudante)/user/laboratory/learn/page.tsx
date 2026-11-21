"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { BarraProgresso, Botao } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CartaoRevisao } from "@/components/pe/revisao/CartaoRevisao";
import { CartaoVidas, Contadores, EsqueletoTrilho, MetaDeHoje, TrilhoLicoes } from "@/components/pe/laboratorio/Trilho";
import {
  idCursoActivo,
  useEstadoVidasQuery,
  useProgressoPraticaQuery,
  useSequenciaQuery,
  useTrilhoQuery,
} from "@/src/domains/student/laboratorio/api";

export default function PaginaTrilho() {
  const router = useRouter();
  const { data: progresso, isFetching: aCarregarProgresso } = useProgressoPraticaQuery();
  const cursoId = idCursoActivo(progresso?.active_course);
  const { data: trilho, isError, refetch } = useTrilhoQuery(cursoId ?? "", { skip: !cursoId });
  const { data: sequencia } = useSequenciaQuery();
  const { data: vidas } = useEstadoVidasQuery();

  // Sem curso escolhido, o primeiro passo é escolher um.
  useEffect(() => {
    if (!aCarregarProgresso && progresso && !cursoId) router.replace("/user/laboratory/learn/courses");
  }, [aCarregarProgresso, progresso, cursoId, router]);

  return (
    <Pagina className="lg:flex-row lg:items-start lg:gap-12">
      <h1 className="sr-only">Laboratório de prática{trilho ? `: ${trilho.curso.titulo}` : ""}</h1>

      <div className="mx-auto flex w-full min-w-0 max-w-[640px] flex-col gap-4 lg:mx-0 lg:flex-[1_1_560px]">
        <Contadores curso={trilho?.curso.titulo} sequencia={sequencia} vidas={vidas} className="-mx-1 border-b border-pe-linha pb-2 lg:hidden" />
        <CartaoRevisao />
        {isError ? (
          <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
            <p className="m-0">Não conseguimos carregar o trilho deste curso.</p>
            <div className="flex flex-wrap gap-3">
              <Botao tamanho="pequeno" onClick={() => refetch()}>
                Tentar outra vez
              </Botao>
              <Botao asChild tipo="ligacao" tamanho="pequeno">
                <Link href="/user/laboratory/learn/courses">Escolher outro curso</Link>
              </Botao>
            </div>
          </div>
        ) : trilho ? (
          trilho.unidades.length ? (
            <TrilhoLicoes trilho={trilho} />
          ) : (
            <div className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-fundo-suave p-6">
              <h2 className="m-0 text-pe-titulo-s">Este curso ainda não tem lições</h2>
              <p className="m-0 text-pe-tinta-suave">O professor está a prepará-las. Entretanto pode praticar noutro curso.</p>
              <Botao asChild tipo="secundario" tamanho="pequeno">
                <Link href="/user/laboratory/learn/courses">Escolher outro curso</Link>
              </Botao>
            </div>
          )
        ) : (
          <EsqueletoTrilho />
        )}
      </div>

      <aside aria-label="O seu progresso" className="hidden min-w-0 max-w-[400px] flex-col gap-5 lg:sticky lg:top-8 lg:flex lg:flex-[1_1_320px]">
        <Contadores curso={trilho?.curso.titulo} sequencia={sequencia} vidas={vidas} />
        {trilho ? (
          <section className="flex flex-col gap-3 rounded-pe-md border border-pe-linha p-6">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">Curso</h2>
              <span className="text-pe-legenda tabular-nums text-pe-tinta-suave">
                {trilho.licoes_feitas} de {trilho.licoes_total} lições
              </span>
            </div>
            <BarraProgresso valor={trilho.percentagem} rotulo="Progresso no curso" altura={12} />
          </section>
        ) : null}
        <MetaDeHoje sequencia={sequencia} />
        <CartaoVidas vidas={vidas} />
      </aside>
    </Pagina>
  );
}
