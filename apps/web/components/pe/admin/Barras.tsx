"use client";

import { useId, useState } from "react";

/**
 * Barras verticais de uma só série (ex.: activos por dia, receita por mês).
 * Uma cor, cantos de 4px só em cima, 2px entre barras, grelha discreta, valor ao passar o rato
 * ou com o teclado, e a mesma informação numa tabela para leitores de ecrã.
 */
export function Barras({
  titulo,
  dados,
  formatar = (v) => v.toLocaleString("pt-PT"),
  altura = 200,
  rotuloA = (r) => r,
  inteiros = true,
  vazio = "Sem dados no período.",
}: {
  titulo: string;
  dados: { rotulo: string; valor: number; detalhe?: string }[];
  formatar?: (v: number) => string;
  altura?: number;
  rotuloA?: (r: string) => string;
  /** Contagens (alunos, lições): o eixo só usa números inteiros. */
  inteiros?: boolean;
  vazio?: string;
}) {
  const id = useId();
  const [activa, setActiva] = useState<number | null>(null);
  if (!dados.length || dados.every((d) => !d.valor)) return <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">{vazio}</p>;

  const max = Math.max(...dados.map((d) => d.valor));
  // Topo redondo; nas contagens, par (para o meio do eixo ser inteiro) e pelo menos 2.
  const passo = Math.pow(10, Math.floor(Math.log10(max)));
  let topo = Math.ceil(max / passo) * passo;
  if (inteiros) topo = Math.max(2, topo % 2 ? topo + 1 : topo);
  const linhas = [topo, topo / 2, 0];
  // Até 7 rótulos no eixo X, posicionados por cima da barra a que pertencem.
  const cadaN = Math.max(1, Math.ceil(dados.length / 7));
  const pos = (i: number) => ((i + 0.5) / dados.length) * 100;
  const ancora = (i: number) => (pos(i) < 12 ? "translate-x-0" : pos(i) > 88 ? "-translate-x-full" : "-translate-x-1/2");

  return (
    <figure className="m-0 flex flex-col gap-2" aria-labelledby={`${id}-t`}>
      <figcaption id={`${id}-t`} className="sr-only">
        {titulo}
      </figcaption>
      <div aria-hidden className="relative flex gap-2">
        <div className="flex w-12 shrink-0 flex-col justify-between text-right text-[12px] leading-4 text-pe-tinta-suave" style={{ height: altura }}>
          {linhas.map((l) => (
            <span key={l}>{formatar(l)}</span>
          ))}
        </div>
        <div className="relative min-w-0 flex-1" style={{ height: altura }}>
          {linhas.map((l, i) => (
            <span key={l} className="absolute inset-x-0 border-t border-pe-fundo-forte" style={{ top: `${(i / (linhas.length - 1)) * 100}%` }} />
          ))}
          <div className="absolute inset-0 flex items-end gap-[2px]" onMouseLeave={() => setActiva(null)}>
            {dados.map((d, i) => (
              <div key={d.rotulo + i} onMouseEnter={() => setActiva(i)} className="group relative flex h-full min-w-0 flex-1 items-end">
                <span className="block w-full rounded-t-[4px] bg-pe-azul-marca group-hover:bg-pe-azul-vivo" style={{ height: `${(d.valor / topo) * 100}%`, minHeight: d.valor ? 2 : 0 }} />
              </div>
            ))}
          </div>
          {activa != null ? (
            <div
              className={`pointer-events-none absolute z-10 whitespace-nowrap rounded-pe-sm bg-pe-tinta px-2.5 py-1.5 text-[13px] leading-[18px] text-pe-fundo shadow-pe-2 ${ancora(activa)}`}
              style={{ left: `${pos(activa)}%`, bottom: `calc(${(dados[activa].valor / topo) * 100}% + 8px)` }}
            >
              <span className="font-semibold">{formatar(dados[activa].valor)}</span> {rotuloA(dados[activa].rotulo)}
              {dados[activa].detalhe ? <span className="block text-[12px] opacity-80">{dados[activa].detalhe}</span> : null}
            </div>
          ) : null}
        </div>
      </div>
      <div aria-hidden className="relative ml-14 h-4 text-[12px] leading-4 text-pe-tinta-suave">
        {dados.map((d, i) =>
          i % cadaN === 0 ? (
            <span key={d.rotulo + i} className={`absolute top-0 whitespace-nowrap ${ancora(i)}`} style={{ left: `${pos(i)}%` }}>
              {d.rotulo}
            </span>
          ) : null
        )}
      </div>
      <table className="sr-only">
        <caption>{titulo}</caption>
        <tbody>
          {dados.map((d, i) => (
            <tr key={i}>
              <th scope="row">{rotuloA(d.rotulo)}</th>
              <td>{formatar(d.valor)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

/** Barras horizontais com o valor escrito ao lado (listas curtas: por área, por província). */
export function BarrasHorizontais({ titulo, dados, formatar = (v) => v.toLocaleString("pt-PT") }: { titulo: string; dados: { nome: string; valor: number }[]; formatar?: (v: number) => string }) {
  const max = Math.max(1, ...dados.map((d) => d.valor));
  return (
    <table className="w-full border-collapse tabular-nums">
      <caption className="sr-only">{titulo}</caption>
      <tbody>
        {dados.map((d) => (
          <tr key={d.nome}>
            <th scope="row" className="w-36 py-1.5 pr-3 text-left text-[15px] font-normal">
              {d.nome}
            </th>
            <td className="py-1.5">
              <span className="flex items-center gap-3">
                <span aria-hidden className="h-6 rounded-r-[4px] bg-pe-azul-marca" style={{ width: `${(d.valor / max) * 100}%`, minWidth: d.valor ? 4 : 0 }} />
                <span className="font-semibold">{formatar(d.valor)}</span>
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
