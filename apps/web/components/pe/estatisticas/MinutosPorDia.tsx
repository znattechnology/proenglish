"use client";

import { useState } from "react";
import { cnPe } from "@/lib/pe";

export type Dia = { data: string; minutos: number; rotulo?: string };

const nomeCurto = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-PT", { weekday: "short" }).replace(".", "");
const nomeLongo = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-PT", { weekday: "long", day: "numeric", month: "long" });

/**
 * Minutos de estudo por dia: uma barra por dia (uma só cor), a linha tracejada da meta,
 * tooltip em cada barra e a mesma informação em tabela para quem não vê o gráfico.
 */
export function MinutosPorDia({ dias, meta }: { dias: Dia[]; meta: number }) {
  const [activo, setActivo] = useState<number | null>(null);
  const maximo = Math.max(meta * 1.25, ...dias.map((d) => d.minutos), 1);
  const altura = 200;
  const yMeta = (meta / maximo) * altura;
  const muitos = dias.length > 14;
  const cumpridos = dias.filter((d) => d.minutos >= meta).length;

  return (
    <div className="flex flex-col gap-3">
      <p aria-hidden className="m-0 flex items-center gap-2 text-[13px] leading-[18px] text-pe-tinta-suave">
        <span className="inline-block w-6 border-t-2 border-dashed border-pe-realce" /> meta de {meta} min
      </p>
      <div className="relative" style={{ height: altura }} onMouseLeave={() => setActivo(null)}>
        {/* Grelha discreta: base e meta */}
        <div aria-hidden className="absolute inset-x-0 bottom-0 border-b border-pe-linha" />
        <div aria-hidden className="absolute inset-x-0 border-t-2 border-dashed border-pe-realce" style={{ bottom: yMeta }} />
        <ol
          aria-label={`Minutos por dia. ${cumpridos} de ${dias.length} dias com a meta de ${meta} minutos cumprida.`}
          className="absolute inset-0 m-0 grid list-none items-end p-0"
          style={{ gridTemplateColumns: `repeat(${dias.length}, minmax(0, 1fr))`, gap: muitos ? 2 : 12 }}
        >
          {dias.map((d, i) => {
            const h = d.minutos ? Math.max(4, (d.minutos / maximo) * altura) : 0;
            const texto = `${nomeLongo(d.data)}: ${d.minutos} min${d.minutos >= meta ? ", meta cumprida" : ""}`;
            return (
              <li key={d.data} className="relative flex h-full items-end justify-center">
                {/* Alvo maior do que a barra, para o rato e o toque */}
                <button
                  type="button"
                  aria-label={texto}
                  onMouseEnter={() => setActivo(i)}
                  onFocus={() => setActivo(i)}
                  onBlur={() => setActivo(null)}
                  onClick={() => setActivo(i)}
                  className="flex h-full w-full items-end justify-center bg-transparent p-0"
                >
                  <span
                    aria-hidden
                    className={cnPe("block w-full max-w-[24px] rounded-t-[4px] motion-safe:transition-opacity", d.minutos ? "bg-pe-azul-vivo" : "bg-transparent", activo !== null && activo !== i && "opacity-50")}
                    style={{ height: h }}
                  />
                </button>
                {activo === i ? (
                  <span
                    role="tooltip"
                    className="pointer-events-none absolute z-10 whitespace-nowrap rounded-pe-sm bg-pe-tinta px-2.5 py-1.5 text-[13px] leading-[18px] text-pe-sobre-marca shadow-pe-2"
                    style={{ bottom: h + 8, left: "50%", transform: `translateX(${i < dias.length / 3 ? "-20%" : i > (2 * dias.length) / 3 ? "-80%" : "-50%"})` }}
                  >
                    {texto}
                  </span>
                ) : null}
              </li>
            );
          })}
        </ol>
      </div>
      <div aria-hidden className="grid text-center text-[13px] leading-[18px] text-pe-tinta-suave md:text-[14px]" style={{ gridTemplateColumns: `repeat(${dias.length}, minmax(0, 1fr))`, gap: muitos ? 2 : 12 }}>
        {dias.map((d, i) => (
          <span key={d.data} className={cnPe("truncate", muitos && i % 5 !== 0 && i !== dias.length - 1 && "invisible")}>
            {muitos ? new Date(`${d.data}T12:00:00`).getDate() : d.rotulo ?? nomeCurto(d.data)}
          </span>
        ))}
      </div>
      <details className="text-[15px]">
        <summary className="min-h-11 cursor-pointer py-2 font-semibold text-pe-azul-marca">Ver em tabela</summary>
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="text-pe-tinta-suave">
              <th scope="col" className="py-1.5 font-normal">
                Dia
              </th>
              <th scope="col" className="py-1.5 text-right font-normal">
                Minutos
              </th>
            </tr>
          </thead>
          <tbody>
            {dias.map((d) => (
              <tr key={d.data} className="border-t border-pe-fundo-forte">
                <td className="py-1.5 first-letter:uppercase">{nomeLongo(d.data)}</td>
                <td className="py-1.5 text-right tabular-nums">
                  {d.minutos}
                  {d.minutos >= meta ? " (meta cumprida)" : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
