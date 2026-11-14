"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Aviso, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaCurso } from "@/components/pe/professor/editor/CabecaCurso";
import { FormDefinicoes } from "@/components/pe/professor/editor/DefinicoesCurso";
import { useCursoQuery } from "@/src/domains/teacher/professor/api";

export default function DefinicoesCursoVideo() {
  const { id } = useParams<{ id: string }>();
  const { data: curso, isError } = useCursoQuery(id);
  return (
    <Pagina className="gap-6">
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos abrir o curso. <Link href="/teacher/courses">Ver os seus cursos</Link>
        </Aviso>
      ) : !curso ? (
        <>
          <Osso className="h-[76px] w-3/4 max-w-[560px]" />
          <Osso className="h-96 max-w-[760px] rounded-pe-md" />
        </>
      ) : (
        <>
          <CabecaCurso curso={curso} separador="Definições" />
          <FormDefinicoes key={curso.id} curso={curso} />
        </>
      )}
    </Pagina>
  );
}
