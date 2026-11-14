"use client";

import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { Aviso, Separadores } from "@/components/pe";
import { ESTADO, type DetalheCurso } from "@/src/domains/teacher/professor/api";

/** Cabeçalho comum ao editor, às definições e à revisão de um curso. */
export function CabecaCurso({
  curso,
  separador,
  nota,
  voltar,
  semAviso,
  children,
}: {
  semAviso?: boolean;
  curso: DetalheCurso;
  separador?: "Aulas" | "Unidades e lições" | "Definições";
  nota?: React.ReactNode;
  voltar?: { href: string; nome: string };
  children?: React.ReactNode;
}) {
  const video = curso.tipo === "video";
  const base = video ? `/teacher/courses/${curso.id}` : `/teacher/practice/${curso.id}`;
  const v = voltar ?? (video ? { href: "/teacher/courses", nome: "Cursos em vídeo" } : { href: "/teacher/practice", nome: "Cursos de prática" });
  const estado = ESTADO[curso.estado]?.nome ?? curso.estado;
  const alunos = curso.alunos ? `, ${curso.alunos.toLocaleString("pt-PT")} ${curso.alunos === 1 ? "aluno" : "alunos"}` : "";
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Link href={v.href} className="inline-flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-vivo no-underline">
          <ChevronLeft aria-hidden className="size-[18px]" />
          {v.nome}
        </Link>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex min-w-0 flex-col gap-1">
            <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 tracking-[-0.015em] md:text-[32px] md:leading-[38px]">{curso.titulo}</h1>
            <p className="m-0 text-pe-tinta-suave" aria-live="polite">
              {estado}
              {alunos}.{nota ? <> {nota}</> : null}
            </p>
          </div>
          {children ? <div className="flex shrink-0 flex-wrap gap-3">{children}</div> : null}
        </div>
      </div>

      {semAviso ? null : curso.estado === "em_revisao" ? (
        <Aviso tipo="info">
          A equipa ProEnglish está a rever o curso. Pode continuar a editar: a revisão vê sempre a versão mais recente. Recebe uma notificação quando houver resposta.
        </Aviso>
      ) : curso.estado === "rascunho" && curso.motivo_recusa ? (
        <Aviso tipo="errado">
          <strong>O curso não foi aprovado.</strong> {curso.motivo_recusa} Corrija e envie outra vez para revisão.
        </Aviso>
      ) : curso.estado === "arquivado" ? (
        <Aviso tipo="neutro">
          {curso.modo_arquivo === "fechar"
            ? "Curso arquivado e fechado: os alunos inscritos já não vêem as aulas. Os certificados emitidos continuam válidos."
            : "Curso arquivado: não aparece no catálogo nem aceita alunos novos. Quem já estava inscrito pode terminá-lo."}
          {curso.moderacao?.motivo ? (
            <>
              {" "}
              <strong>{curso.moderacao.accao === "recusar" ? "A equipa ProEnglish recusou a última revisão:" : "Arquivado pela equipa ProEnglish:"}</strong> {curso.moderacao.motivo}
            </>
          ) : null}
        </Aviso>
      ) : curso.estado === "publicado" ? (
        <Aviso tipo="neutro">O curso está publicado: as alterações que fizer aparecem logo aos alunos.</Aviso>
      ) : null}

      {separador ? (
        <Separadores
          rotulo="Partes do curso"
          activo={separador}
          itens={
            video
              ? [
                  { nome: "Aulas", href: base },
                  { nome: "Definições", href: `${base}/settings` },
                ]
              : [
                  { nome: "Unidades e lições", href: base },
                  { nome: "Definições", href: `${base}/settings` },
                ]
          }
        />
      ) : null}
    </div>
  );
}
