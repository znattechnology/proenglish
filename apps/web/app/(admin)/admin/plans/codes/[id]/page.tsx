"use client";

import { useParams } from "next/navigation";
import { Aviso, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { FormCodigo } from "@/components/pe/admin/FormCodigo";
import { useCodigoQuery } from "@/src/domains/admin/administracao/negocio";

export default function EditarCodigo() {
  const { id } = useParams<{ id: string }>();
  const { data, isError } = useCodigoQuery(id);
  return <Pagina className="gap-6">{isError ? <Aviso tipo="errado">Não conseguimos abrir o código.</Aviso> : !data ? <Osso className="h-96 rounded-pe-md" /> : <FormCodigo key={data.id} inicial={data} />}</Pagina>;
}
