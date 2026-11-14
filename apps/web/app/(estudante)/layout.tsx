"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { ObrigarMudarSenha } from "@/components/pe/conta/ObrigarMudarSenha";
import { useMinhaSubscricaoQuery } from "@/src/domains/student/subscricao/api";
import { BarraNavMovel, LateralEstudante } from "@/components/pe/estudante/Navegacao";
import { Osso } from "@/components/pe";

/**
 * Moldura das telas novas do estudante (base visual `.pe`).
 * A sessão é verificada no servidor (proxy.ts); aqui só esperamos pelos dados da pessoa.
 * As páginas que ainda não foram refeitas continuam no grupo (dashboard).
 */
export default function LayoutEstudante({ children }: { children: React.ReactNode }) {
  const { user, isLoading, logout } = useDjangoAuth();
  const { data: subscricao } = useMinhaSubscricaoQuery(undefined, { skip: !user });
  const plano = subscricao?.plan?.name ? `Plano ${subscricao.plan.name}` : undefined;
  const router = useRouter();
  // O proxy já filtra pelo papel, mas deixa passar quem está a renovar a sessão: confirmamos aqui.
  const semPermissao = !!user && user.role !== "student";
  useEffect(() => {
    if (semPermissao) router.replace("/sem-permissao?area=student");
  }, [semPermissao, router]);

  return (
    <div className="pe flex min-h-dvh">
      <LateralEstudante nome={user?.name ?? ""} plano={plano} aoSair={() => void logout()} />
      <div className="flex min-w-0 flex-1 flex-col pb-[84px] md:pb-0">
        {(isLoading && !user) || semPermissao ? <EsqueletoPagina /> : <ObrigarMudarSenha>{children}</ObrigarMudarSenha>}
      </div>
      <BarraNavMovel />
    </div>
  );
}

function EsqueletoPagina() {
  return (
    <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-5 px-5 py-6 md:px-12 md:py-8">
      <Osso className="h-[30px] w-3/5 max-w-[360px]" />
      <Osso className="h-[170px] max-w-[760px] rounded-pe-fala" />
      <Osso className="h-16 max-w-[760px] rounded-pe-md" />
      <Osso className="h-16 max-w-[760px] rounded-pe-md" />
    </div>
  );
}
