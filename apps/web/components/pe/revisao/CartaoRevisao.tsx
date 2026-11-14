"use client";

import Link from "next/link";
import { ChevronRight, RotateCcw } from "lucide-react";
import { MarcaIcone } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import { nFrases, useResumoRevisaoQuery } from "@/src/domains/student/revisao/api";

/** Entrada para a revisão de hoje (laboratório e painel). Não aparece quando não há nada para rever. */
export function CartaoRevisao({ className }: { className?: string }) {
  const { data } = useResumoRevisaoQuery();
  if (!data?.para_rever) return null;
  const minutos = Math.max(1, data.minutos);
  return (
    <Link
      href="/user/laboratory/review"
      className={cnPe(
        "flex items-center gap-4 rounded-pe-md border-2 border-pe-realce bg-pe-realce-suave px-4 py-3.5 text-pe-tinta no-underline hover:shadow-pe-2 hover:text-pe-tinta",
        className
      )}
    >
      <MarcaIcone fundo="marca" tamanho={44}>
        <RotateCcw />
      </MarcaIcone>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="font-semibold leading-[22px]">Revisão de hoje</span>
        <span className="text-pe-legenda text-pe-tinta-suave">
          Tem {nFrases(data.para_rever)} para rever, em cerca de {minutos} {minutos === 1 ? "minuto" : "minutos"}.
        </span>
      </span>
      <ChevronRight aria-hidden className="size-5 shrink-0 text-pe-tinta-suave" />
    </Link>
  );
}
