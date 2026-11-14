"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import { destinoPorPapel } from "@/components/pe/conta/Partes";

const nada = () => () => {};
/** Valor de um cookie no browser; null no servidor (a página é estática e igual para todos). */
function useCookie(nome: string) {
  return useSyncExternalStore(nada, () => ler(nome) ?? null, () => null);
}

function ler(nome: string) {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${nome}=`))
    ?.slice(nome.length + 1);
}

/** Botão de um plano: quem tem sessão vai direto ao pagamento; os visitantes criam a conta com o plano escolhido. */
export function LigacaoPlano({ tipo, gratis, className, children }: { tipo: string; gratis: boolean; className: string; children: React.ReactNode }) {
  const sessao = !!useCookie("auth_state");
  const href = sessao ? (gratis ? "/user/dashboard" : `/user/upgrade?plan=${tipo}`) : gratis ? "/signup" : `/signup?plan=${tipo}`;
  return (
    <Link href={href} className={className}>
      {children}
    </Link>
  );
}

/** Entrar e Criar conta; quem já tem sessão vê a ligação para a sua área (lido no browser: a página fica estática). */
export function Entrada() {
  const sessao = useCookie("auth_state");
  const role = useCookie("user_role");
  const papel = sessao ? (role ?? "student") : null;

  if (papel)
    return (
      <div className="ml-auto flex items-center lg:ml-0">
        <Link href={destinoPorPapel(papel)} className="inline-flex min-h-11 items-center rounded-pe-sm bg-pe-azul-marca px-4 font-semibold text-pe-sobre-marca no-underline hover:bg-pe-azul-vivo hover:text-pe-sobre-marca sm:px-5">
          Ir para a minha área
        </Link>
      </div>
    );
  return (
    <div className="ml-auto flex items-center gap-1 sm:gap-3 lg:ml-0">
      <Link href="/signin" className="inline-flex min-h-11 items-center px-3 font-semibold text-pe-azul-marca underline-offset-[3px]">
        Entrar
      </Link>
      <Link href="/signup" className="inline-flex min-h-11 items-center rounded-pe-sm bg-pe-azul-marca px-4 font-semibold text-pe-sobre-marca no-underline hover:bg-pe-azul-vivo hover:text-pe-sobre-marca sm:px-5">
        Criar conta
      </Link>
    </div>
  );
}
