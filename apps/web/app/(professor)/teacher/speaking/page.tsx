"use client";

import Link from "next/link";
import { useState } from "react";
import { Aviso, Etiqueta, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaFala } from "@/components/pe/professor/fala/Cabeca";
import { num } from "@/src/domains/teacher/professor/api";
import { useSituacoesQuery } from "@/src/domains/teacher/professor/fala";

const FILTROS = ["Todas", "As minhas", "Da plataforma"] as const;

export default function Situacoes() {
  const { data, isError, refetch } = useSituacoesQuery();
  const [filtro, setFiltro] = useState<(typeof FILTROS)[number]>("Todas");
  const lista = (data?.resultados ?? []).filter((s) => filtro === "Todas" || (filtro === "As minhas" ? s.minha : !s.minha));
  const th = "border-b border-pe-linha px-3 py-2.5 text-pe-legenda font-semibold text-pe-tinta-suave";
  const td = "border-b border-pe-fundo-forte p-3 align-middle";

  return (
    <Pagina className="gap-7">
      <CabecaFala activo="Situações" />
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar as situações.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-72 rounded-pe-md" />
      ) : (
        <>
          <Pilulas rotulo="Mostrar" opcoes={FILTROS} valor={filtro} aoMudar={setFiltro} />
          {lista.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse tabular-nums">
                <caption className="sr-only">Situações de conversa</caption>
                <thead>
                  <tr>
                    <th scope="col" className={`${th} text-left`}>Situação</th>
                    <th scope="col" className={`${th} text-left`}>Curso</th>
                    <th scope="col" className={`${th} text-left`}>Nível</th>
                    <th scope="col" className={`${th} text-left`}>Estado</th>
                    <th scope="col" className={`${th} text-right`}>Sessões</th>
                    <th scope="col" className={`${th} text-right`}>Pontuação média</th>
                    <th scope="col" className={th}>
                      <span className="sr-only">Acções</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {lista.map((s) => (
                    <tr key={s.id}>
                      <td className={`${td} font-semibold`}>{s.nome}</td>
                      <td className={td}>{s.curso?.titulo ?? "Geral"}</td>
                      <td className={td}>{s.nivel}</td>
                      <td className={td}>
                        <Etiqueta tipo={s.estado === "activo" ? "certo" : "neutra"}>{s.estado === "activo" ? "Activa" : "Rascunho"}</Etiqueta>
                      </td>
                      <td className={`${td} text-right`}>{num(s.sessoes)}</td>
                      <td className={`${td} text-right`}>{s.pontuacao_media == null ? "–" : `${Math.round(s.pontuacao_media)} em 100`}</td>
                      <td className={`${td} text-right`}>
                        {s.minha ? (
                          <Link href={`/teacher/speaking/${s.id}`} className="inline-flex min-h-11 items-center font-semibold text-pe-azul-vivo underline-offset-[3px]">
                            Editar<span className="sr-only">: {s.nome}</span>
                          </Link>
                        ) : (
                          <span className="text-pe-legenda text-pe-tinta-suave">Da plataforma</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">
              {filtro === "As minhas" ? "Ainda não criou situações. Uma situação descreve a cena que o tutor faz com o aluno, por exemplo pedir um relatório ao supervisor." : "Não há situações neste filtro."}
            </p>
          )}
        </>
      )}
    </Pagina>
  );
}
