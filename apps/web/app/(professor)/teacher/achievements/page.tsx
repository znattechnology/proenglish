"use client";

import Link from "next/link";
import { useState } from "react";
import { Plus } from "lucide-react";
import { Aviso, Botao, Etiqueta, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaConquistas } from "@/components/pe/professor/fala/CabecaConquistas";
import { Medalha } from "@/components/pe/professor/fala/Medalha";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import { RARIDADE, useConquistasQuery, useMudarConquistaMutation } from "@/src/domains/teacher/professor/fala";

const FILTROS = { Todas: "todas", Activas: "activas", Desligadas: "desligadas" } as const;

export default function Conquistas() {
  const [filtro, setFiltro] = useState<keyof typeof FILTROS>("Todas");
  const { data, isError, refetch } = useConquistasQuery(FILTROS[filtro]);
  const [mudar] = useMudarConquistaMutation();
  const [erro, setErro] = useState<string | null>(null);
  const th = "border-b border-pe-linha px-3 py-2.5 text-pe-legenda font-semibold text-pe-tinta-suave";
  const td = "border-b border-pe-fundo-forte p-3 align-middle";

  return (
    <Pagina className="gap-7">
      <CabecaConquistas activo="Conquistas" texto="Medalhas que os alunos dos seus cursos ganham ao praticar. Aparecem em Conquistas, na área do aluno.">
        <Botao asChild tamanho="medio">
          <Link href="/teacher/achievements/new">
            <Plus aria-hidden className="size-5" />
            Nova conquista
          </Link>
        </Botao>
      </CabecaConquistas>
      <Pilulas rotulo="Mostrar" opcoes={Object.keys(FILTROS) as (keyof typeof FILTROS)[]} valor={filtro} aoMudar={setFiltro} />
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar as conquistas.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-72 rounded-pe-md" />
      ) : !data.resultados.length ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">Não há conquistas neste filtro.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse tabular-nums">
            <caption className="sr-only">Conquistas</caption>
            <thead>
              <tr>
                <th scope="col" className={`${th} text-left`}>Conquista</th>
                <th scope="col" className={`${th} text-left`}>Como se ganha</th>
                <th scope="col" className={`${th} text-left`}>Raridade</th>
                <th scope="col" className={`${th} text-right`}>Pontos</th>
                <th scope="col" className={`${th} text-right`}>Alunos que têm</th>
                <th scope="col" className={`${th} text-left`}>Activa</th>
                <th scope="col" className={th}>
                  <span className="sr-only">Acções</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.resultados.map((c) => (
                <tr key={c.id}>
                  <td className={td}>
                    <span className="flex items-center gap-3">
                      <Medalha icone={c.icone} raridade={c.raridade} />
                      <span className="flex flex-col">
                        <span className="font-semibold">{c.nome}</span>
                        {!c.minha ? <span className="text-pe-legenda text-pe-tinta-suave">Da plataforma</span> : c.regra.curso ? <span className="text-pe-legenda text-pe-tinta-suave">{c.regra.curso.titulo}</span> : null}
                      </span>
                    </span>
                  </td>
                  <td className={td}>{c.como_se_ganha}</td>
                  <td className={td}>
                    <Etiqueta>{RARIDADE[c.raridade]}</Etiqueta>
                  </td>
                  <td className={`${td} text-right`}>{num(c.pontos)}</td>
                  <td className={`${td} text-right`}>{num(c.alunos_que_tem)}</td>
                  <td className={td}>
                    {c.minha ? (
                      <label className="inline-flex min-h-11 cursor-pointer items-center gap-2">
                        <input
                          type="checkbox"
                          checked={c.activa}
                          onChange={(e) => {
                            setErro(null);
                            mudar({ id: c.id, activa: e.target.checked })
                              .unwrap()
                              .catch((x) => setErro(mensagemErro(x, "Não foi possível mudar a conquista.")));
                          }}
                          className="size-5 accent-pe-azul-marca"
                        />
                        <span className="sr-only">Activa: {c.nome}</span>
                        {c.activa ? "Sim" : "Não"}
                      </label>
                    ) : c.activa ? (
                      "Sim"
                    ) : (
                      "Não"
                    )}
                  </td>
                  <td className={`${td} text-right`}>
                    {c.minha ? (
                      <Link href={`/teacher/achievements/${c.id}`} className="inline-flex min-h-11 items-center font-semibold text-pe-azul-vivo underline-offset-[3px]">
                        Editar<span className="sr-only">: {c.nome}</span>
                      </Link>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Pagina>
  );
}
