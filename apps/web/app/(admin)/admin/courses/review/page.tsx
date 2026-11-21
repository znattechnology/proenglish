"use client";

import Link from "next/link";
import { CheckCircle2, XCircle } from "lucide-react";
import { Aviso, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaSeccao, SEPARADORES_CURSOS } from "@/components/pe/admin/Comum";
import { quandoEntrou, useFilaRevisaoQuery } from "@/src/domains/admin/administracao/api";
import { nivelEmFrase } from "@/src/domains/shared/niveis";

export default function FilaRevisao() {
  const { data, isError, refetch } = useFilaRevisaoQuery();
  return (
    <Pagina className="gap-7">
      <CabecaSeccao titulo="Cursos" texto="Cursos enviados pelos professores. Só entram no catálogo depois de aprovados (excepto os dos professores que publicam sem revisão)." activo="Em revisão" itens={SEPARADORES_CURSOS} />
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar a fila.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-64 rounded-pe-md" />
      ) : !data.resultados.length ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">Nenhum curso à espera de revisão.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {data.resultados.map((c) => {
            const falhas = c.verificacao.itens.filter((i) => !i.ok).length;
            return (
              <li key={c.id}>
                <Link href={`/admin/courses/review/${c.id}`} className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-pe-md border border-pe-linha p-4 text-pe-tinta no-underline hover:border-pe-azul-marca hover:bg-pe-fundo-suave">
                  <span className="flex min-w-0 flex-[1_1_320px] flex-col">
                    <span className="font-pe-titulo text-[18px] font-semibold leading-6">{c.titulo}</span>
                    <span className="text-pe-legenda text-pe-tinta-suave">
                      {c.tipo === "video" ? "Vídeo" : "Prática"}, {[c.area, nivelEmFrase(c.nivel)].filter(Boolean).join(", ")}. Por {c.professor.nome}
                      {c.estado_antes_revisao === "arquivado" ? ". Volta de arquivado" : ""}.
                    </span>
                  </span>
                  <span className="flex items-center gap-1.5 text-[15px]">
                    {falhas ? <XCircle aria-hidden className="size-5 text-pe-errado" /> : <CheckCircle2 aria-hidden className="size-5 text-pe-certo" />}
                    {falhas ? `${falhas} ${falhas === 1 ? "ponto" : "pontos"} por corrigir` : "Lista de verificação completa"}
                  </span>
                  <span className="text-[15px] text-pe-tinta-suave">Enviado {c.submetido_em ? quandoEntrou(c.submetido_em).toLowerCase() : ""}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Pagina>
  );
}
