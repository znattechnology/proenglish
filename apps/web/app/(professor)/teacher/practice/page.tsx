"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Plus } from "lucide-react";
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

export default function CursosPratica() {
  const { data, isError, refetch } = useCursosQuery({ tipo: "pratica" });
  const [filtro, setFiltro] = useState<(typeof FILTROS)[number]>("Todos");
  const lista = useMemo(() => {
    const e = ESTADO_DO_FILTRO[filtro];
    return (data?.resultados ?? []).filter((c) => !e || c.estado === e);
  }, [data, filtro]);
  const n = data?.numeros;

  return (
    <Pagina className="gap-7">
      <Cabeca titulo="Cursos de prática" texto="O trilho do Laboratório de prática: unidades, lições e exercícios curtos.">
        <Botao asChild tamanho="medio">
          <Link href="/teacher/courses/new?tipo=pratica">
            <Plus aria-hidden className="size-5" />
            Criar curso de prática
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
          <h2 className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">Ainda não tem cursos de prática</h2>
          <p className="m-0 text-pe-tinta-suave">Um curso de prática divide-se em unidades; cada unidade tem lições curtas com exercícios de escolher, completar, ordenar, ouvir e falar.</p>
          <Botao asChild tamanho="medio">
            <Link href="/teacher/courses/new?tipo=pratica">Criar curso de prática</Link>
          </Botao>
        </section>
      ) : (
        <>
          <Numeros
            itens={[
              {
                nome: "Cursos publicados",
                valor: num(n.publicados),
                nota: [n.em_revisao ? `${n.em_revisao} em revisão` : null, n.rascunhos ? `${n.rascunhos} em rascunho` : null].filter(Boolean).join(", ") || "nenhum por publicar",
              },
              { nome: "Alunos inscritos", valor: num(n.alunos), nota: n.alunos_novos_mes ? `+${num(n.alunos_novos_mes)} este mês` : "nenhum novo este mês" },
              { nome: "Lições", valor: num(n.licoes), nota: n.exercicios != null ? `${num(n.exercicios)} exercícios` : undefined },
              { nome: "Acerto médio", valor: pct(n.acerto_medio), nota: "nas respostas dos alunos" },
            ]}
          />
          <Pilulas rotulo="Mostrar" opcoes={FILTROS} valor={filtro} aoMudar={setFiltro} />
          {lista.length ? (
            <TabelaCursos
              cursos={lista}
              comCapa={false}
              legenda="Cursos de prática"
              colunas={[
                { nome: "Unidades", valor: (c) => num(c.unidades) },
                { nome: "Lições", valor: (c) => num(c.licoes) },
                { nome: "Exercícios", valor: (c) => num(c.exercicios) },
                COLUNA_ALUNOS,
                COLUNA_CONCLUSAO,
              ]}
            />
          ) : (
            <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Não tem cursos neste estado.</p>
          )}
        </>
      )}
    </Pagina>
  );
}
