"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Aviso, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { FormConquista } from "@/components/pe/professor/fala/FormConquista";
import { useConquistasQuery } from "@/src/domains/teacher/professor/fala";

export default function EditarConquista() {
  const { id } = useParams<{ id: string }>();
  const { data, isError } = useConquistasQuery("todas");
  const c = data?.resultados.find((x) => x.id === id);
  return (
    <Pagina className="gap-6">
      {isError ? (
        <Aviso tipo="errado">Não conseguimos carregar a conquista.</Aviso>
      ) : !data ? (
        <Osso className="h-96 rounded-pe-md" />
      ) : !c || !c.minha ? (
        <Aviso tipo="info">
          Esta conquista não existe ou não é sua. <Link href="/teacher/achievements">Ver as conquistas</Link>
        </Aviso>
      ) : (
        <FormConquista key={c.id} inicial={c} />
      )}
    </Pagina>
  );
}
