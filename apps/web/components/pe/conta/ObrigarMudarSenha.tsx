"use client";

import { KeyRound } from "lucide-react";
import { usePerfilQuery } from "@/src/domains/student/perfil/api";
import { MudarPalavraPasse } from "./MudarPalavraPasse";

/**
 * Quando a administração pede para mudar a palavra-passe, a API recusa tudo o resto (403 mudar_senha).
 * Em vez de páginas com erros, mostra só o pedido para escolher uma palavra-passe nova.
 */
export function ObrigarMudarSenha({ children }: { children: React.ReactNode }) {
  const { data: perfil, refetch } = usePerfilQuery();
  if (!perfil?.deve_mudar_senha) return <>{children}</>;
  return (
    <main className="mx-auto flex w-full max-w-[560px] flex-col items-start gap-4 px-5 py-12">
      <KeyRound aria-hidden className="size-10 text-pe-azul-marca" />
      <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9">Escolha uma palavra-passe nova</h1>
      <p className="m-0 text-pe-tinta-suave">Por segurança, a equipa ProEnglish pediu-lhe para mudar a palavra-passe antes de continuar.</p>
      <MudarPalavraPasse temSenha={perfil.has_password !== false} aberto aoMudar={() => {}} aoMudada={() => void refetch()} />
    </main>
  );
}
