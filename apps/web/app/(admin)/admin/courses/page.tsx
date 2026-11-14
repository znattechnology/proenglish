"use client";

import { useEffect, useState } from "react";
import { Aviso, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { EtiquetaEstado, Numeros } from "@/components/pe/professor/Partes";
import { CabecaSeccao, LigacaoAbrir, Paginacao, Procura, SEPARADORES_CURSOS } from "@/components/pe/admin/Comum";
import { cnPe } from "@/lib/pe";
import { num, pct } from "@/src/domains/teacher/professor/api";
import { useCursosAdminQuery } from "@/src/domains/admin/administracao/api";

const TIPOS = { Todos: "", Vídeo: "video", Prática: "pratica" } as const;
const ESTADOS = { Todos: "", Publicados: "publicado", "Em revisão": "em_revisao", Rascunhos: "rascunho", Arquivados: "arquivado" } as const;

export default function CursosAdmin() {
  const [tipo, setTipo] = useState<keyof typeof TIPOS>("Todos");
  const [estado, setEstado] = useState<keyof typeof ESTADOS>("Todos");
  const [q, setQ] = useState("");
  const [qAtrasado, setQAtrasado] = useState("");
  const [pagina, setPagina] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => {
      setQAtrasado(q.trim());
      setPagina(1);
    }, 300);
    return () => clearTimeout(t);
  }, [q]);
  const { data, isError, isFetching, refetch } = useCursosAdminQuery({ tipo: TIPOS[tipo], estado: ESTADOS[estado], q: qAtrasado, pagina });
  const n = data?.numeros;

  return (
    <Pagina className="gap-7">
      <CabecaSeccao titulo="Cursos" activo="Todos os cursos" itens={SEPARADORES_CURSOS} />
      {n ? (
        <Numeros
          itens={[
            { nome: "Publicados", valor: num(n.publicados), nota: `${n.publicados_video} vídeo, ${n.publicados_pratica} prática` },
            { nome: "Rascunhos", valor: num(n.rascunhos), nota: n.rascunhos_parados_30d ? `${n.rascunhos_parados_30d} sem mexer há 30 dias` : "todos com actividade recente" },
            { nome: "Inscrições", valor: num(n.inscricoes), nota: n.inscricoes_mes ? `+${num(n.inscricoes_mes)} este mês` : "nenhuma nova este mês" },
            { nome: "Conclusão média", valor: pct(n.conclusao_media), nota: "dos alunos inscritos" },
          ]}
        />
      ) : isError ? null : (
        <Osso className="h-[104px] rounded-pe-md" />
      )}
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
        <Procura valor={q} aoMudar={setQ} rotulo="Procurar pelo título ou professor" className="xl:max-w-[360px]" />
        <Pilulas rotulo="Tipo" opcoes={Object.keys(TIPOS) as (keyof typeof TIPOS)[]} valor={tipo} aoMudar={(v) => (setTipo(v), setPagina(1))} />
        <Pilulas rotulo="Estado" opcoes={Object.keys(ESTADOS) as (keyof typeof ESTADOS)[]} valor={estado} aoMudar={(v) => (setEstado(v), setPagina(1))} />
      </div>
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os cursos.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-80 rounded-pe-md" />
      ) : !data.resultados.length ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">Nenhum curso com estes filtros.</p>
      ) : (
        <div aria-busy={isFetching} className={cnPe("flex flex-col gap-4", isFetching && "opacity-70")}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] border-collapse tabular-nums">
              <caption className="sr-only">Cursos</caption>
              <thead>
                <tr>
                  {["Curso", "Tipo", "Professor", "Área", "Estado", "Alunos", "Conclusão", ""].map((t, i) => (
                    <th key={i} scope="col" className={`border-b border-pe-linha px-3 py-2.5 text-pe-legenda font-semibold text-pe-tinta-suave ${i === 5 || i === 6 ? "text-right" : "text-left"}`}>
                      {t || <span className="sr-only">Acções</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.resultados.map((c) => (
                  <tr key={c.id}>
                    <td className="border-b border-pe-fundo-forte p-3 font-semibold">{c.titulo}</td>
                    <td className="border-b border-pe-fundo-forte p-3">{c.tipo === "video" ? "Vídeo" : "Prática"}</td>
                    <td className="border-b border-pe-fundo-forte p-3">{c.professor.nome}</td>
                    <td className="border-b border-pe-fundo-forte p-3">{c.area ?? "–"}</td>
                    <td className="border-b border-pe-fundo-forte p-3">
                      <EtiquetaEstado estado={c.estado} />
                    </td>
                    <td className="border-b border-pe-fundo-forte p-3 text-right">{c.estado === "rascunho" && !c.alunos ? "–" : num(c.alunos)}</td>
                    <td className="border-b border-pe-fundo-forte p-3 text-right">{pct(c.conclusao)}</td>
                    <td className="border-b border-pe-fundo-forte px-3 text-right">
                      <LigacaoAbrir href={`/admin/courses/review/${c.id}`} nome={c.titulo} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacao pagina={pagina} paginas={data.paginas} total={data.total} nome="cursos" aoMudar={setPagina} />
        </div>
      )}
    </Pagina>
  );
}
