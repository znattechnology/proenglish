"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { LogOut, Menu, X } from "lucide-react";
import { cnPe } from "@/lib/pe";
import { Logo } from "@/components/pe";
import { usePorLer } from "@/components/pe/estudante/Navegacao";

/**
 * Destinos da área do professor. Enquanto uma tela não é refeita, o item aponta para a página antiga
 * (`href`); `prefixos` decide quando fica activo.
 */
const DESTINOS = [
  { nome: "Painel", href: "/teacher/dashboard", prefixos: ["/teacher/dashboard"] },
  { nome: "Cursos em vídeo", href: "/teacher/courses", prefixos: ["/teacher/courses"] },
  { nome: "Cursos de prática", href: "/teacher/practice", prefixos: ["/teacher/practice", "/teacher/laboratory/courses", "/teacher/laboratory/manage-courses"] },
  { nome: "Conversa e escuta", href: "/teacher/speaking", prefixos: ["/teacher/speaking", "/teacher/laboratory/speaking", "/teacher/laboratory/listening"] },
  { nome: "Alunos e resultados", href: "/teacher/students", prefixos: ["/teacher/students", "/teacher/laboratory/analytics"] },
  { nome: "Conquistas e competições", href: "/teacher/achievements", prefixos: ["/teacher/achievements", "/teacher/laboratory/achievements", "/teacher/laboratory/leaderboard"] },
  { nome: "Ganhos", href: "/teacher/billing", prefixos: ["/teacher/billing"] },
  { nome: "Perfil e definições", href: "/teacher/profile", prefixos: ["/teacher/profile", "/teacher/settings"] },
  { nome: "Notificações", href: "/teacher/notifications", prefixos: ["/teacher/notifications"] },
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
  const porLer = usePorLer();
  return (
    <nav aria-label="Área do professor" className="flex flex-col gap-1">
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
            {d.href === "/teacher/notifications" && porLer ? (
              <span className={cnPe("ml-2 flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-[13px] font-bold tabular-nums", a ? "bg-pe-realce text-pe-tinta" : "bg-pe-azul-vivo text-pe-sobre-marca")}>
                <span className="sr-only">, por ler: </span>
                {porLer > 99 ? "99+" : porLer}
              </span>
            ) : null}
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
          <span className="text-pe-legenda text-pe-tinta-suave">Professor</span>
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
export function LateralProfessor({ nome, aoSair }: { nome: string; aoSair: () => void }) {
  const pathname = usePathname() ?? "";
  return (
    <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col gap-7 overflow-y-auto bg-pe-fundo-suave px-4 py-6 lg:flex print:hidden">
      <Link href="/teacher/dashboard" className="ml-3 self-start" aria-label="ProEnglish, ir para o painel">
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
export function CabecalhoProfessor({ nome, aoSair }: { nome: string; aoSair: () => void }) {
  const pathname = usePathname() ?? "";
  // O menu fica aberto só na página em que foi aberto: mudar de página fecha-o.
  const [abertoEm, setAbertoEm] = useState<string | null>(null);
  const aberto = abertoEm === pathname;
  const porLer = usePorLer();
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
        <Link href="/teacher/dashboard" aria-label="ProEnglish, ir para o painel">
          <Logo altura={36} />
        </Link>
        <button
          type="button"
          onClick={() => setAberto((v) => !v)}
          aria-expanded={aberto}
          aria-controls={aberto ? "menu-professor" : undefined}
          aria-label={!aberto && porLer ? `Menu, ${porLer} notificações por ler` : undefined}
          className="relative flex min-h-11 items-center gap-2 rounded-pe-sm px-3 font-semibold text-pe-tinta hover:bg-pe-fundo-suave"
        >
          {aberto ? <X aria-hidden className="size-5" /> : <Menu aria-hidden className="size-5" />}
          {aberto ? "Fechar" : "Menu"}
          {!aberto && porLer ? <span aria-hidden className="absolute right-1 top-1.5 size-2.5 rounded-full bg-pe-azul-vivo" /> : null}
        </button>
      </div>
      {aberto ? (
        <div id="menu-professor" ref={menu} tabIndex={-1} className="fixed inset-x-0 bottom-0 top-16 flex flex-col gap-6 overflow-y-auto bg-pe-fundo-suave px-4 pb-[max(24px,env(safe-area-inset-bottom))] pt-4">
          <Destinos pathname={pathname} aoEscolher={() => setAberto(false)} />
          <div className="mt-auto border-t border-pe-linha pt-4">
            <Pessoa nome={nome} aoSair={aoSair} />
          </div>
        </div>
      ) : null}
    </header>
  );
}
