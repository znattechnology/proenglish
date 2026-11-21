"use client";

import Link from "next/link";
import { Lock } from "lucide-react";
import { cnPe } from "@/lib/pe";

export const ROTA_PLANOS = "/user/subscription";
export const TEXTO_PLANOS_PAGOS = "Disponível nos planos pagos";

/**
 * Unidade, aula ou passo fora das unidades de amostra (a API marca-os com bloqueada/bloqueado).
 * Leva aos planos; o servidor é que decide o que abre.
 */
export function DisponivelNosPlanos({ className }: { className?: string }) {
  return (
    <Link
      href={ROTA_PLANOS}
      className={cnPe("inline-flex min-h-11 items-center gap-1.5 text-[14px] font-semibold text-pe-azul-vivo underline-offset-[3px] hover:underline", className)}
    >
      <Lock aria-hidden className="size-4 shrink-0" />
      {TEXTO_PLANOS_PAGOS}
    </Link>
  );
}
