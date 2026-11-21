"use client";

import Link from "next/link";
import { useState, useSyncExternalStore } from "react";
import { Dumbbell } from "lucide-react";
import { Botao } from "@/components/pe";
import { fechar, foiFechado, type PraticaAnterior } from "./praticaAnterior";

function armazenamento(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

const semAvisos = () => () => {};

/**
 * «Pratique primeiro»: o laboratório da aula anterior ainda está por fazer. Não bloqueia a aula:
 * o vídeo continua por baixo, e «Continuar esta aula» fecha o aviso nesta aula.
 */
export function AvisoPraticaAnterior({ aulaId, pratica }: { aulaId: string; pratica: PraticaAnterior }) {
  // No servidor fica escondido (não há armazenamento), para não piscar num aviso já fechado.
  const fechadoAntes = useSyncExternalStore(
    semAvisos,
    () => foiFechado(armazenamento(), aulaId, pratica.licao_id),
    () => true,
  );
  const [fechadoAgora, setFechadoAgora] = useState(false);
  if (fechadoAntes || fechadoAgora) return null;

  const continuar = () => {
    fechar(armazenamento(), aulaId, pratica.licao_id);
    setFechadoAgora(true);
  };

  return (
    <section
      aria-labelledby="titulo-pratica-anterior"
      className="flex flex-col gap-4 rounded-pe-fala border-2 border-pe-realce bg-pe-realce-suave p-5 md:flex-row md:items-center md:justify-between md:gap-6 md:p-6"
    >
      <div className="flex min-w-0 gap-3.5">
        <span aria-hidden className="mt-0.5 grid size-11 shrink-0 place-items-center rounded-full bg-pe-azul-marca text-pe-realce [&_svg]:size-5">
          <Dumbbell />
        </span>
        <div className="flex min-w-0 flex-col gap-1">
          <h2 id="titulo-pratica-anterior" className="m-0 font-pe-titulo text-[19px] font-bold leading-[25px] text-pe-tinta">
            Ainda não praticou a aula anterior
          </h2>
          <p className="m-0 max-w-[60ch] text-[15px] leading-[22px] text-pe-tinta">
            O laboratório de «{pratica.aula_titulo}» está por fazer. Recomendamos que pratique primeiro: é a praticar que o
            que aprendeu fica consolidado{pratica.minutos ? ` (cerca de ${pratica.minutos} minutos)` : ""}.
          </p>
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2.5 md:flex-col md:items-stretch">
        <Botao asChild tipo="principal" tamanho="medio">
          <Link href={`/user/laboratory/learn/lesson/${pratica.licao_id}`}>Praticar a aula anterior</Link>
        </Botao>
        <Botao tipo="secundario" tamanho="medio" onClick={continuar}>
          Continuar esta aula
        </Botao>
      </div>
    </section>
  );
}
