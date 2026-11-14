"use client";

import { Pagina } from "@/components/pe/estudante/Pagina";
import { FormConquista } from "@/components/pe/professor/fala/FormConquista";

export default function NovaConquista() {
  return (
    <Pagina className="gap-6">
      <FormConquista />
    </Pagina>
  );
}
