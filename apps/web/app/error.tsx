"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Estado } from "@/components/pe/estados/Estado";

/** Erro inesperado numa página: diz que o progresso está guardado e dá um código para o apoio. */
export default function Erro({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Erro na página:", error);
  }, [error]);
  const codigo = error.digest ? `ERR-${error.digest.slice(0, 8).toUpperCase()}` : null;

  return (
    <Estado
      simbolo="!"
      titulo="Não conseguimos abrir esta página"
      texto="O problema é do nosso lado, não da sua ligação. O seu progresso está guardado."
      rodape={codigo ? <>Se continuar, fale com o apoio e indique o código {codigo}.</> : null}
    >
      <button
        type="button"
        onClick={reset}
        className="flex min-h-[52px] items-center justify-center rounded-pe-sm bg-pe-azul-marca px-6 font-semibold text-pe-sobre-marca hover:bg-pe-azul-vivo"
      >
        Tentar outra vez
      </button>
      <Link href="/user/dashboard" className="flex min-h-12 items-center justify-center rounded-pe-sm border-2 border-pe-azul-marca px-6 font-semibold text-pe-azul-marca no-underline">
        Ir para o início
      </Link>
    </Estado>
  );
}
