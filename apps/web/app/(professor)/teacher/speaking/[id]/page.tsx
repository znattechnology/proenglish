"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Aviso, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { FormSituacao } from "@/components/pe/professor/fala/FormSituacao";
import { useSituacaoQuery } from "@/src/domains/teacher/professor/fala";

export default function EditarSituacao() {
  const { id } = useParams<{ id: string }>();
  const { data, isError } = useSituacaoQuery(id);
  return (
    <Pagina className="gap-6">
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos abrir a situação. <Link href="/teacher/speaking">Ver as situações</Link>
        </Aviso>
      ) : !data ? (
        <Osso className="h-96 max-w-[760px] rounded-pe-md" />
      ) : data.minha === false ? (
        <Aviso tipo="info">
          Esta situação é da plataforma e não pode ser editada. <Link href="/teacher/speaking">Ver as situações</Link>
        </Aviso>
      ) : (
        <FormSituacao key={data.id} inicial={data} />
      )}
    </Pagina>
  );
}
