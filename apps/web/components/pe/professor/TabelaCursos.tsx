"use client";

import { Capa, EtiquetaEstado, LigacaoEditar } from "./Partes";
import { areaNivel, num, pct, type CursoProfessor } from "@/src/domains/teacher/professor/api";

/** Para onde vai o "Editar" de cada curso. */
export function hrefEditar(c: Pick<CursoProfessor, "id" | "tipo">) {
  return c.tipo === "video" ? `/teacher/courses/${c.id}` : `/teacher/practice/${c.id}`;
}

type Coluna = { nome: string; direita?: boolean; valor: (c: CursoProfessor) => React.ReactNode };

/**
 * Tabela de cursos no desktop; no telemóvel cada curso é um bloco com os mesmos dados,
 * para não obrigar a deslizar para o lado.
 */
export function TabelaCursos({ cursos, colunas, comCapa, legenda }: { cursos: CursoProfessor[]; colunas: Coluna[]; comCapa?: boolean; legenda: string }) {
  return (
    <>
      <table className="hidden w-full border-collapse tabular-nums md:table">
        <caption className="sr-only">{legenda}</caption>
        <thead>
          <tr>
            <th scope="col" className="border-b border-pe-linha px-3 py-2.5 text-left text-pe-legenda font-semibold text-pe-tinta-suave">
              Curso
            </th>
            <th scope="col" className="border-b border-pe-linha px-3 py-2.5 text-left text-pe-legenda font-semibold text-pe-tinta-suave">
              Estado
            </th>
            {colunas.map((k) => (
              <th key={k.nome} scope="col" className="border-b border-pe-linha px-3 py-2.5 text-right text-pe-legenda font-semibold text-pe-tinta-suave">
                {k.nome}
              </th>
            ))}
            <th scope="col" className="border-b border-pe-linha px-3 py-2.5">
              <span className="sr-only">Acções</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {cursos.map((c) => (
            <tr key={c.id}>
              <td className="border-b border-pe-fundo-forte p-3 align-middle">
                <span className="flex items-center gap-3">
                  {comCapa ? <Capa imagem={c.imagem} titulo={c.titulo} /> : null}
                  <span className="flex min-w-0 flex-col">
                    <span className="font-semibold leading-[22px]">{c.titulo}</span>
                    <span className="text-pe-legenda text-pe-tinta-suave">{c.tipo === "pratica" && comCapa === undefined ? `Prática: ${areaNivel(c)}` : areaNivel(c)}</span>
                  </span>
                </span>
              </td>
              <td className="border-b border-pe-fundo-forte p-3 align-middle">
                <EtiquetaEstado estado={c.estado} />
              </td>
              {colunas.map((k) => (
                <td key={k.nome} className="border-b border-pe-fundo-forte p-3 text-right align-middle">
                  {k.valor(c)}
                </td>
              ))}
              <td className="border-b border-pe-fundo-forte px-3 text-right align-middle">
                <LigacaoEditar href={hrefEditar(c)} nome={c.titulo} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul aria-label={legenda} className="m-0 flex list-none flex-col p-0 md:hidden">
        {cursos.map((c) => (
          <li key={c.id} className="flex flex-col gap-2 border-b border-pe-fundo-forte py-4">
            <div className="flex items-start gap-3">
              {comCapa ? <Capa imagem={c.imagem} titulo={c.titulo} /> : null}
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="font-semibold leading-[22px]">{c.titulo}</span>
                <span className="text-pe-legenda text-pe-tinta-suave">{areaNivel(c)}</span>
              </span>
              <EtiquetaEstado estado={c.estado} />
            </div>
            <dl className="m-0 flex flex-wrap gap-x-5 gap-y-1 text-[15px] tabular-nums">
              {colunas.map((k) => (
                <div key={k.nome} className="flex gap-1.5">
                  <dt className="text-pe-tinta-suave">{k.nome}</dt>
                  <dd className="m-0 font-semibold">{k.valor(c)}</dd>
                </div>
              ))}
            </dl>
            <LigacaoEditar href={hrefEditar(c)} nome={c.titulo} />
          </li>
        ))}
      </ul>
    </>
  );
}

export const COLUNA_ALUNOS: Coluna = { nome: "Alunos", direita: true, valor: (c) => (c.estado === "publicado" || c.alunos ? num(c.alunos) : "–") };
export const COLUNA_CONCLUSAO: Coluna = { nome: "Conclusão", direita: true, valor: (c) => pct(c.conclusao) };
