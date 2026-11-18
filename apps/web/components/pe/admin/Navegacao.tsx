"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { LogOut, Menu, X } from "lucide-react";
import { cnPe } from "@/lib/pe";
import { Logo } from "@/components/pe";

/** Destinos da área da administração; `prefixos` decide quando um item fica activo. */
const DESTINOS = [
  { nome: "Painel", href: "/admin/dashboard", prefixos: ["/admin/dashboard"] },
  { nome: "Utilizadores", href: "/admin/users", prefixos: ["/admin/users"] },
  { nome: "Cursos", href: "/admin/courses", prefixos: ["/admin/courses"] },
  { nome: "Subscrições e pagamentos", href: "/admin/subscriptions", prefixos: ["/admin/subscriptions"] },
  { nome: "Planos e códigos", href: "/admin/plans", prefixos: ["/admin/plans"] },
  { nome: "Tutor de conversa", href: "/admin/tutor", prefixos: ["/admin/tutor"] },
  { nome: "Opiniões e testemunhos", href: "/admin/feedback", prefixos: ["/admin/feedback"] },
  { nome: "Conteúdo do site", href: "/admin/site", prefixos: ["/admin/site"] },
  { nome: "Ganhos dos professores", href: "/admin/earnings", prefixos: ["/admin/earnings"] },
  { nome: "Relatórios", href: "/admin/reports", prefixos: ["/admin/reports"] },
] as const;

function activo(pathname: string, prefixos: readonly string[]) {
  return prefixos.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export function iniciais(nome: string) {
  return (
    nome
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase())
      .join("") || "?"
  );
}

function Destinos({ pathname, aoEscolher }: { pathname: string; aoEscolher?: () => void }) {
  return (
    <nav aria-label="Área da administração" className="flex flex-col gap-1">
      {DESTINOS.map((d) => {
        const a = activo(pathname, d.prefixos);
        return (
          <Link
            key={d.nome}
            href={d.href}
            onClick={aoEscolher}
            aria-current={a ? "page" : undefined}
            className={cnPe(
              "flex min-h-11 items-center rounded-pe-sm px-3 no-underline",
              a ? "bg-pe-azul-marca font-semibold text-pe-sobre-marca hover:text-pe-sobre-marca" : "text-pe-tinta hover:bg-pe-fundo-forte hover:text-pe-tinta"
            )}
          >
            <span className="flex-1">{d.nome}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function Pessoa({ nome, aoSair }: { nome: string; aoSair: () => void }) {
  return (
    <div className="flex flex-col gap-2 px-3">
      <div className="flex items-center gap-3">
        <span aria-hidden className="flex size-10 shrink-0 items-center justify-center rounded-pe-fala-s bg-pe-azul-marca font-semibold text-pe-sobre-marca">
          {iniciais(nome)}
        </span>
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate font-semibold leading-[22px]">{nome}</span>
          <span className="text-pe-legenda text-pe-tinta-suave">Administração</span>
        </span>
      </div>
      <button type="button" onClick={aoSair} className="flex min-h-11 items-center gap-2 self-start rounded-pe-sm px-1 text-[15px] font-semibold text-pe-tinta-suave hover:text-pe-tinta">
        <LogOut aria-hidden className="size-[18px]" />
        Sair da conta
      </button>
    </div>
  );
}

/** Barra lateral do desktop: os destinos e a pessoa com sessão iniciada. */
export function LateralAdmin({ nome, aoSair }: { nome: string; aoSair: () => void }) {
  const pathname = usePathname() ?? "";
  return (
    <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col gap-7 overflow-y-auto bg-pe-fundo-suave px-4 py-6 lg:flex print:hidden">
      <Link href="/admin/dashboard" className="ml-3 self-start" aria-label="ProEnglish, ir para o painel">
        <Logo altura={44} />
      </Link>
      <Destinos pathname={pathname} />
      <div className="mt-auto">
        <Pessoa nome={nome} aoSair={aoSair} />
      </div>
    </aside>
  );
}

/**
 * Telemóvel e tablet: cabeçalho com o logótipo e um botão Menu que abre os destinos por cima da página.
 * São 8 destinos, demasiados para uma barra de baixo.
 */
export function CabecalhoAdmin({ nome, aoSair }: { nome: string; aoSair: () => void }) {
  const pathname = usePathname() ?? "";
  // O menu fica aberto só na página em que foi aberto: mudar de página fecha-o.
  const [abertoEm, setAbertoEm] = useState<string | null>(null);
  const aberto = abertoEm === pathname;
  const menu = useRef<HTMLDivElement>(null);
  const setAberto = (v: boolean | ((x: boolean) => boolean)) => setAbertoEm((typeof v === "function" ? v(aberto) : v) ? pathname : null);
  useEffect(() => {
    if (!aberto) return;
    const fechar = (e: KeyboardEvent) => e.key === "Escape" && setAbertoEm(null);
    document.addEventListener("keydown", fechar);
    document.body.style.overflow = "hidden";
    // Leva o foco para dentro do menu aberto, para quem navega com o teclado ou leitor de ecrã.
    menu.current?.querySelector<HTMLElement>("a, button")?.focus();
    return () => {
      document.removeEventListener("keydown", fechar);
      document.body.style.overflow = "";
    };
  }, [aberto]);
  return (
    <header className="sticky top-0 z-40 border-b border-pe-linha bg-pe-fundo lg:hidden print:hidden">
      <div className="flex h-16 items-center justify-between px-4">
        <Link href="/admin/dashboard" aria-label="ProEnglish, ir para o painel">
          <Logo altura={36} />
        </Link>
        <button
          type="button"
          onClick={() => setAberto((v) => !v)}
          aria-expanded={aberto}
          aria-controls={aberto ? "menu-admin" : undefined}
          className="relative flex min-h-11 items-center gap-2 rounded-pe-sm px-3 font-semibold text-pe-tinta hover:bg-pe-fundo-suave"
        >
          {aberto ? <X aria-hidden className="size-5" /> : <Menu aria-hidden className="size-5" />}
          {aberto ? "Fechar" : "Menu"}
        </button>
      </div>
      {aberto ? (
        <div id="menu-admin" ref={menu} tabIndex={-1} className="fixed inset-x-0 bottom-0 top-16 flex flex-col gap-6 overflow-y-auto bg-pe-fundo-suave px-4 pb-[max(24px,env(safe-area-inset-bottom))] pt-4">
          <Destinos pathname={pathname} aoEscolher={() => setAberto(false)} />
          <div className="mt-auto border-t border-pe-linha pt-4">
            <Pessoa nome={nome} aoSair={aoSair} />
          </div>
        </div>
      ) : null}
    </header>
  );
}
