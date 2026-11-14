"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { Destinos, Estado } from "@/components/pe/estados/Estado";

const AREAS: Record<string, string> = { teacher: "professores", admin: "a administração", student: "estudantes" };
const PAPEIS: Record<string, string> = { teacher: "professor", admin: "administrador", student: "estudante" };
const INICIO: Record<string, string> = { teacher: "/teacher/dashboard", admin: "/admin/dashboard", student: "/user/dashboard" };

function SemPermissao() {
  const area = useSearchParams().get("area") ?? "";
  const { user } = useDjangoAuth();
  const papel = user?.role ?? "student";
  return (
    <Estado
      simbolo={
        <svg viewBox="0 0 24 24" className="size-10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="4" y="11" width="16" height="10" rx="2" />
          <path d="M8 11V7a4 4 0 0 1 8 0v4" />
        </svg>
      }
      titulo={AREAS[area] ? `Esta área é só para ${AREAS[area]}` : "Não tem acesso a esta área"}
      texto={
        <>
          {user?.name ? `Está a usar a conta de ${PAPEIS[papel] ?? papel} de ${user.name}. ` : ""}
          Se devia ter este acesso, peça à administração para mudar o seu papel.
        </>
      }
    >
      <Destinos itens={[{ href: INICIO[papel] ?? "/", nome: "Voltar ao início" }]} />
    </Estado>
  );
}

export default function Pagina() {
  return (
    <Suspense>
      <SemPermissao />
    </Suspense>
  );
}
