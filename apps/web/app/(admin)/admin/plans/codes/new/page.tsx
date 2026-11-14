"use client";

import { Pagina } from "@/components/pe/estudante/Pagina";
import { FormCodigo } from "@/components/pe/admin/FormCodigo";

export default function NovoCodigo() {
  return (
    <Pagina className="gap-6">
      <FormCodigo />
    </Pagina>
  );
}
