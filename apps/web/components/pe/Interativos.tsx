"use client";

import * as React from "react";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import { cnPe } from "@/lib/pe";

/** Pílulas de filtro: escolha de uma opção entre poucas (Todos, Activos, ...). */
export function Pilulas<T extends string>({
  opcoes,
  valor,
  aoMudar,
  rotulo,
}: {
  opcoes: readonly T[];
  valor: T;
  aoMudar?: (v: T) => void;
  rotulo: string;
}) {
  return (
    <div role="group" aria-label={rotulo} className="flex flex-wrap gap-2">
      {opcoes.map((o) => {
        const a = o === valor;
        return (
          <button
            key={o}
            type="button"
            aria-pressed={a}
            onClick={() => aoMudar?.(o)}
            className={cnPe(
              "min-h-10 rounded-full px-3.5 font-pe-texto text-[15px] font-semibold",
              a
                ? "bg-pe-azul-marca text-pe-sobre-marca"
                : "border-[1.5px] border-pe-linha-forte bg-pe-fundo text-pe-tinta hover:bg-pe-fundo-suave"
            )}
          >
            {o}
          </button>
        );
      })}
    </div>
  );
}

/** Interruptor com rótulo e descrição. O rótulo inteiro é clicável. */
export function Interruptor({
  rotulo,
  descricao,
  ligado,
  aoMudar,
  disabled,
}: {
  rotulo: string;
  descricao?: string;
  ligado: boolean;
  aoMudar: (v: boolean) => void;
  disabled?: boolean;
}) {
  const id = React.useId();
  return (
    <div className="flex items-center justify-between gap-6 border-b border-pe-fundo-forte py-3.5">
      <label htmlFor={id} className="flex flex-col">
        <span className="font-semibold leading-[22px]">{rotulo}</span>
        {descricao ? <span className="text-pe-legenda text-pe-tinta-suave">{descricao}</span> : null}
      </label>
      <SwitchPrimitive.Root
        id={id}
        checked={ligado}
        onCheckedChange={aoMudar}
        disabled={disabled}
        className="relative h-[26px] w-[46px] shrink-0 rounded-full bg-pe-linha-forte transition-colors data-[state=checked]:bg-pe-azul-marca disabled:opacity-50"
      >
        <SwitchPrimitive.Thumb className="block size-[22px] translate-x-0.5 rounded-full bg-pe-fundo shadow-pe-1 transition-transform data-[state=checked]:translate-x-[22px]" />
      </SwitchPrimitive.Root>
    </div>
  );
}
