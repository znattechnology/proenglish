"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Plus, Search } from "lucide-react";
import { Aviso, Botao, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Cabeca, Numeros } from "@/components/pe/professor/Partes";
import { COLUNA_ALUNOS, COLUNA_CONCLUSAO, TabelaCursos } from "@/components/pe/professor/TabelaCursos";
import { num, pct, useCursosQuery, type EstadoCurso } from "@/src/domains/teacher/professor/api";

const FILTROS = ["Todos", "Publicados", "Em revisão", "Rascunhos", "Arquivados"] as const;
const ESTADO_DO_FILTRO: Record<(typeof FILTROS)[number], EstadoCurso | null> = {
  Todos: null,
  Publicados: "publicado",
  "Em revisão": "em_revisao",
  Rascunhos: "rascunho",
  Arquivados: "arquivado",
};

const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`;

export default function CursosVideo() {
  const { data, isError, refetch } = useCursosQuery({ tipo: "video" });
  const [filtro, setFiltro] = useState<(typeof FILTROS)[number]>("Todos");
  const [procura, setProcura] = useState("");

  const lista = useMemo(() => {
    const e = ESTADO_DO_FILTRO[filtro];
    const q = procura.trim().toLocaleLowerCase("pt-PT");
    return (data?.resultados ?? []).filter((c) => (!e || c.estado === e) && (!q || c.titulo.toLocaleLowerCase("pt-PT").includes(q)));
  }, [data, filtro, procura]);

  const n = data?.numeros;

  return (
    <Pagina className="gap-7">
      <Cabeca titulo="Cursos em vídeo" texto="Aulas gravadas, organizadas em secções. Os alunos vêem-nas na área Cursos.">
        <Botao asChild tamanho="medio">
          <Link href="/teacher/courses/new">
            <Plus aria-hidden className="size-5" />
            Criar curso
          </Link>
        </Botao>
      </Cabeca>

      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os seus cursos.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data || !n ? (
        <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-6">
          <Osso className="h-[104px] rounded-pe-md" />
          <Osso className="h-72 rounded-pe-md" />
        </div>
      ) : !data.resultados.length ? (
        <section className="flex max-w-[640px] flex-col items-start gap-3 rounded-pe-md bg-pe-fundo-suave p-6 md:p-8">
          <h2 className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">Ainda não tem cursos em vídeo</h2>
          <p className="m-0 text-pe-tinta-suave">Comece pelo título, a área e o nível. Depois organiza as aulas em secções e envia o curso para revisão.</p>
          <Botao asChild tamanho="medio">
            <Link href="/teacher/courses/new">Criar curso</Link>
          </Botao>
        </section>
      ) : (
        <>
          <Numeros
            itens={[
              {
                nome: "Publicados",
                valor: num(n.publicados),
                nota: [n.em_revisao ? `${n.em_revisao} em revisão` : null, n.rascunhos ? `${n.rascunhos} em rascunho` : null].filter(Boolean).join(", ") || "nenhum por publicar",
              },
              { nome: "Alunos inscritos", valor: num(n.alunos), nota: n.alunos_novos_mes ? `+${num(n.alunos_novos_mes)} este mês` : "nenhum novo este mês" },
              { nome: "Aulas publicadas", valor: num(n.aulas), nota: n.seccoes != null ? `em ${plural(n.seccoes, "secção", "secções")}` : undefined },
              { nome: "Conclusão média", valor: pct(n.conclusao_media), nota: "dos alunos inscritos" },
            ]}
          />

          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <label className="flex h-11 w-full items-center gap-2 rounded-pe-sm border-[1.5px] border-pe-linha-forte px-3 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-pe-azul-vivo lg:max-w-[420px]">
              <Search aria-hidden className="size-[18px] text-pe-tinta-suave" />
              <input
                type="search"
                value={procura}
                onChange={(e) => setProcura(e.target.value)}
                placeholder="Procurar nos seus cursos"
                aria-label="Procurar nos seus cursos"
                className="min-w-0 flex-1 border-0 bg-transparent font-pe-texto text-[16px] text-pe-tinta outline-none"
              />
            </label>
            <Pilulas rotulo="Mostrar" opcoes={FILTROS} valor={filtro} aoMudar={setFiltro} />
          </div>

          {lista.length ? (
            <TabelaCursos
              cursos={lista}
              comCapa
              legenda="Cursos em vídeo"
              colunas={[
                COLUNA_ALUNOS,
                {
                  nome: "Aulas",
                  valor: (c) =>
                    c.aulas == null ? "–" : (
                      <span className="flex flex-col items-end">
                        {plural(c.aulas, "aula", "aulas")}
                        {c.aulas_sem_video ? <span className="text-pe-legenda font-semibold text-pe-errado">{c.aulas_sem_video} sem vídeo</span> : null}
                      </span>
                    ),
                },
                COLUNA_CONCLUSAO,
              ]}
            />
          ) : (
            <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">
              {procura.trim() ? `Nenhum curso com "${procura.trim()}".` : `Não tem cursos neste estado.`}
            </p>
          )}
        </>
      )}
    </Pagina>
  );
}
