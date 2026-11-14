"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { ObrigarMudarSenha } from "@/components/pe/conta/ObrigarMudarSenha";
import { CabecalhoProfessor, LateralProfessor } from "@/components/pe/professor/Navegacao";
import { Osso } from "@/components/pe";

/**
 * Moldura das telas novas do professor (base visual `.pe`).
 * O papel é verificado no servidor (proxy.ts); aqui só esperamos pelos dados da pessoa.
 * As telas que ainda não foram refeitas continuam no grupo (dashboard).
 */
export default function LayoutProfessor({ children }: { children: React.ReactNode }) {
  const { user, isLoading, logout } = useDjangoAuth();
  const nome = user?.name ?? "";
  const router = useRouter();
  // O proxy já filtra pelo papel, mas deixa passar quem está a renovar a sessão: confirmamos aqui.
  const semPermissao = !!user && user.role !== "teacher" && user.role !== "admin";
  useEffect(() => {
    if (semPermissao) router.replace("/sem-permissao?area=teacher");
  }, [semPermissao, router]);
  return (
    <div className="pe flex min-h-dvh">
      <LateralProfessor nome={nome} aoSair={() => void logout()} />
      <div className="flex min-w-0 flex-1 flex-col">
        <CabecalhoProfessor nome={nome} aoSair={() => void logout()} />
        {(isLoading && !user) || semPermissao ? (
          <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-5 px-5 py-6 md:px-12 md:py-8">
            <Osso className="h-[38px] w-3/5 max-w-[360px]" />
            <Osso className="h-[104px] rounded-pe-md" />
            <Osso className="h-64 rounded-pe-md" />
          </div>
        ) : (
          <ObrigarMudarSenha>{children}</ObrigarMudarSenha>
        )}
      </div>
    </div>
  );
}
