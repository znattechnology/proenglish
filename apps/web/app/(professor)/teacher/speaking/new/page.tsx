"use client";

import { Pagina } from "@/components/pe/estudante/Pagina";
import { FormSituacao } from "@/components/pe/professor/fala/FormSituacao";

export default function NovaSituacao() {
  return (
    <Pagina className="gap-6">
      <FormSituacao />
    </Pagina>
  );
}
