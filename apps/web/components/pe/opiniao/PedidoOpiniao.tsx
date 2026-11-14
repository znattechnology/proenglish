"use client";

import Link from "next/link";
import { MessageSquareHeart, X } from "lucide-react";
import { Botao } from "@/components/pe";
import { useAdiarOpiniaoMutation, useEstadoOpiniaoQuery } from "@/src/domains/student/opiniao/api";

/** Cartão discreto no Painel quando chega um momento de pedir opinião (primeira lição, 5 lições, ...). */
export function PedidoOpiniao() {
  const { data } = useEstadoOpiniaoQuery();
  const [adiar, { isLoading }] = useAdiarOpiniaoMutation();
  if (!data?.should_show_prompt || !data.chave || !data.trigger) return null;
  const params = new URLSearchParams({ chave: data.chave, trigger: data.trigger });
  return (
    <section aria-labelledby="titulo-opiniao" className="relative flex flex-col gap-3 rounded-pe-md border border-pe-linha p-5">
      <button
        type="button"
        aria-label="Agora não"
        disabled={isLoading}
        onClick={() => adiar({ trigger: data.trigger!, chave: data.chave! })}
        className="absolute right-2 top-2 flex size-11 items-center justify-center rounded-pe-sm bg-transparent text-pe-tinta-suave"
      >
        <X aria-hidden className="size-5" />
      </button>
      <span className="flex items-center gap-2 pr-10">
        <MessageSquareHeart aria-hidden className="size-5 shrink-0 text-pe-azul-marca" />
        <h2 id="titulo-opiniao" className="m-0 text-[17px] font-semibold leading-6">
          {data.frase}
        </h2>
      </span>
      <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">Demora um minuto: uma nota de 1 a 5 e, se quiser, um comentário.</p>
      <div className="flex flex-wrap items-center gap-3">
        <Botao asChild tamanho="pequeno">
          <Link href={`/user/feedback?${params}`}>Dar a opinião</Link>
        </Botao>
        <Botao tipo="ligacao" tamanho="pequeno" disabled={isLoading} onClick={() => adiar({ trigger: data.trigger!, chave: data.chave! })}>
          Agora não
        </Botao>
      </div>
    </section>
  );
}
