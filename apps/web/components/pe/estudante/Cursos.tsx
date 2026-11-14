"use client";

import Link from "next/link";
import { useEffect } from "react";
import { BookOpen, ChevronRight } from "lucide-react";
import { BarraProgresso, Etiqueta, MarcaIcone, Osso } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import { categoriaPt, nivelPt, useProgressoCursoQuery, type CursoVideo } from "@/src/domains/student/inicio/api";

/** Separadores da área Cursos: os cursos da pessoa e o catálogo. */
export const SEPARADORES_CURSOS = [
  { nome: "Os meus", href: "/user/courses" },
  { nome: "Explorar", href: "/user/courses/explore" },
];

/** Linha de contexto do curso: área e nível, em português. */
export function contextoCurso(c: CursoVideo) {
  return [categoriaPt(c.category), nivelPt(c.level)?.toLowerCase()].filter(Boolean).join(", ");
}

/** Miniatura do curso. A imagem é decorativa: o título já diz o que é. */
export function Capa({ curso, tamanho = 56 }: { curso: CursoVideo; tamanho?: number }) {
  if (!curso.image) {
    return (
      <MarcaIcone fundo="forte" tamanho={tamanho}>
        <BookOpen />
      </MarcaIcone>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- a origem da imagem é configurada pelo professor (local ou externa)
    <img
      src={curso.image}
      alt=""
      loading="lazy"
      className="shrink-0 rounded-pe-sm bg-pe-fundo-forte object-cover"
      style={{ width: tamanho, height: tamanho }}
    />
  );
}

/**
 * Curso em que o estudante está inscrito, com o progresso real.
 * `aoSaberProgresso` deixa a lista saber o progresso para filtrar Em progresso / Concluídos.
 */
export function LinhaCursoInscrito({
  curso,
  userId,
  aoSaberProgresso,
  escondido = false,
}: {
  curso: CursoVideo;
  userId: string;
  aoSaberProgresso?: (courseId: string, pct: number) => void;
  escondido?: boolean;
}) {
  const { data: progresso, isLoading } = useProgressoCursoQuery({ userId, courseId: curso.courseId });
  const pct = Math.round(progresso?.overallProgress ?? 0);

  useEffect(() => {
    if (!isLoading) aoSaberProgresso?.(curso.courseId, pct);
  }, [isLoading, pct, curso.courseId, aoSaberProgresso]);

  if (escondido) return null;

  return (
    <li>
      <Link
        href={`/user/courses/${curso.courseId}`}
        className="group flex items-center gap-4 border-b border-pe-linha py-4 text-pe-tinta no-underline hover:text-pe-tinta"
      >
        <Capa curso={curso} />
        <span className="flex min-w-0 flex-1 flex-col gap-1.5">
          <span className="text-pe-legenda text-pe-tinta-suave">{contextoCurso(curso)}</span>
          <span className="font-pe-titulo text-[17px] font-semibold leading-[22px] group-hover:text-pe-azul-marca">{curso.title}</span>
          {isLoading ? (
            <Osso className="h-2 w-full" />
          ) : (
            <span className="flex items-center gap-3">
              <BarraProgresso valor={pct} rotulo={`Progresso em ${curso.title}`} cor={pct === 100 ? "certo" : "vivo"} className="flex-1" />
              <span className="w-12 text-right text-pe-legenda font-semibold">{pct === 100 ? "Feito" : `${pct}%`}</span>
            </span>
          )}
        </span>
        <ChevronRight aria-hidden className="size-5 shrink-0 text-pe-tinta-suave" />
      </Link>
    </li>
  );
}

/** Curso do catálogo (Explorar). */
export function LinhaCursoCatalogo({ curso, inscrito }: { curso: CursoVideo; inscrito?: boolean }) {
  const acesso = curso.is_free ? "Gratuito" : curso.is_premium ? "Premium" : curso.access_level_display;
  return (
    <li>
      <Link
        href={`/user/courses/${curso.courseId}`}
        className="group flex items-center gap-4 border-b border-pe-linha py-4 text-pe-tinta no-underline hover:text-pe-tinta"
      >
        <Capa curso={curso} tamanho={64} />
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="text-pe-legenda text-pe-tinta-suave">{contextoCurso(curso)}</span>
          <span className="font-pe-titulo text-[17px] font-semibold leading-[22px] group-hover:text-pe-azul-marca">{curso.title}</span>
          <span className="flex flex-wrap items-center gap-2 text-pe-legenda text-pe-tinta-suave">
            {inscrito ? <Etiqueta tipo="certo">Inscrito</Etiqueta> : acesso ? <Etiqueta tipo={curso.is_premium ? "marca" : "neutra"}>{acesso}</Etiqueta> : null}
            {curso.teacherName ? <span>{curso.teacherName}</span> : null}
          </span>
        </span>
        <ChevronRight aria-hidden className="size-5 shrink-0 text-pe-tinta-suave" />
      </Link>
    </li>
  );
}

export function ListaCursos({ children, className }: { children: React.ReactNode; className?: string }) {
  return <ul className={cnPe("m-0 flex list-none flex-col p-0 [&>li:last-child>a]:border-b-0", className)}>{children}</ul>;
}

export function EsqueletoLista({ linhas = 3 }: { linhas?: number }) {
  return (
    <div aria-busy="true" aria-label="A carregar cursos" className="flex flex-col">
      {Array.from({ length: linhas }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 border-b border-pe-linha py-4">
          <Osso className="size-14 shrink-0" />
          <div className="flex flex-1 flex-col gap-2">
            <Osso className="h-3.5 w-1/3" />
            <Osso className="h-[18px] w-4/5" />
            <Osso className="h-2 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}
