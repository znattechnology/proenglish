"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, BookOpen, House, LogOut, Mic, Star, User } from "lucide-react";
import { cnPe } from "@/lib/pe";
import { Logo } from "@/components/pe";
import { usePorLerQuery } from "@/src/domains/student/avisos/api";

/** Os destinos da área do estudante. `prefixos` decide quando um item está activo. */
const MOVEL = [
  { nome: "Início", href: "/user/dashboard", icone: House, prefixos: ["/user/dashboard"] },
  { nome: "Cursos", href: "/user/courses", icone: BookOpen, prefixos: ["/user/courses", "/user/grades", "/user/certificates"] },
  {
    nome: "Praticar",
    href: "/user/laboratory",
    icone: Star,
    prefixos: ["/user/laboratory/learn", "/user/laboratory/achievements", "/user/laboratory/leaderboard"],
  },
  { nome: "Conversa", href: "/user/laboratory/speaking/real-time", icone: Mic, prefixos: ["/user/laboratory/speaking"] },
  { nome: "Perfil", href: "/user/profile", icone: User, prefixos: ["/user/profile", "/user/settings", "/user/subscription", "/user/analytics", "/user/billing"] },
] as const;

const DESKTOP = [
  { nome: "Painel", href: "/user/dashboard", prefixos: ["/user/dashboard"] },
  { nome: "Cursos", href: "/user/courses", prefixos: ["/user/courses"] },
  { nome: "Laboratório de prática", href: "/user/laboratory", prefixos: ["/user/laboratory/learn"] },
  { nome: "Conversa com o tutor", href: "/user/laboratory/speaking/real-time", prefixos: ["/user/laboratory/speaking"] },
  { nome: "Conquistas", href: "/user/laboratory/achievements", prefixos: ["/user/laboratory/achievements", "/user/laboratory/leaderboard"] },
  { nome: "Certificados", href: "/user/certificates", prefixos: ["/user/certificates"] },
  { nome: "Estatísticas", href: "/user/analytics", prefixos: ["/user/analytics", "/user/grades"] },
  { nome: "Subscrição", href: "/user/subscription", prefixos: ["/user/subscription", "/user/billing", "/user/upgrade"] },
  { nome: "Perfil e definições", href: "/user/settings", prefixos: ["/user/settings", "/user/profile"] },
  { nome: "Notificações", href: "/user/notifications", prefixos: ["/user/notifications"] },
] as const;

function activo(pathname: string, prefixos: readonly string[]) {
  return prefixos.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/** Barra de baixo do telemóvel: 5 destinos, sempre visível. */
export function BarraNavMovel() {
  const pathname = usePathname() ?? "";
  return (
    <nav
      aria-label="Navegação principal"
      className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-pe-linha bg-pe-fundo px-1 pb-[max(10px,env(safe-area-inset-bottom))] pt-1.5 md:hidden print:hidden"
    >
      {MOVEL.map(({ nome, href, icone: Icone, prefixos }) => {
        const a = activo(pathname, prefixos);
        return (
          <Link
            key={href}
            href={href}
            aria-current={a ? "page" : undefined}
            className={cnPe(
              "flex min-h-[52px] flex-col items-center justify-center gap-0.5 text-[12px] leading-4 no-underline",
              a ? "font-semibold text-pe-azul-marca" : "text-pe-tinta-suave"
            )}
          >
            <Icone aria-hidden className={cnPe("size-[22px]", a && (Icone === House || Icone === Star || Icone === User) && "fill-pe-azul-marca")} />
            {nome}
          </Link>
        );
      })}
    </nav>
  );
}

/** Barra lateral do desktop: 9 destinos e a pessoa com sessão iniciada. */
/** Número de notificações por ler (actualiza a cada minuto e ao voltar à app). */
export function usePorLer() {
  const { data } = usePorLerQuery(undefined, { pollingInterval: 60_000, refetchOnFocus: true });
  return data?.unread ?? 0;
}

/** Sino com o número por ler, para o cabeçalho do telemóvel. */
export function SinoNotificacoes() {
  const n = usePorLer();
  return (
    <Link
      href="/user/notifications"
      aria-label={n ? `Notificações, ${n} por ler` : "Notificações"}
      className="relative flex size-11 items-center justify-center rounded-pe-sm text-pe-tinta no-underline hover:bg-pe-fundo-suave"
    >
      <Bell aria-hidden className="size-6" />
      {n ? (
        <span aria-hidden className="absolute right-1 top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-pe-azul-vivo px-1 text-[12px] font-bold text-pe-sobre-marca tabular-nums">
          {n > 9 ? "9+" : n}
        </span>
      ) : null}
    </Link>
  );
}

export function LateralEstudante({ nome, plano, aoSair }: { nome: string; plano?: string; aoSair: () => void }) {
  const pathname = usePathname() ?? "";
  const porLer = usePorLer();
  const iniciais = nome
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
  return (
    <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col gap-7 bg-pe-fundo-suave px-4 py-6 md:flex print:hidden">
      <Link href="/user/dashboard" className="ml-3 self-start" aria-label="ProEnglish, ir para o painel">
        <Logo altura={44} />
      </Link>
      <nav aria-label="Área do estudante" className="flex flex-col gap-1">
        {DESKTOP.map((i) => {
          const a = activo(pathname, i.prefixos);
          return (
            <Link
              key={i.href}
              href={i.href}
              aria-current={a ? "page" : undefined}
              className={cnPe(
                "flex min-h-11 items-center rounded-pe-sm px-3 no-underline",
                a ? "bg-pe-azul-marca font-semibold text-pe-sobre-marca hover:text-pe-sobre-marca" : "text-pe-tinta hover:bg-pe-fundo-forte hover:text-pe-tinta"
              )}
            >
              <span className="flex-1">{i.nome}</span>
              {i.href === "/user/notifications" && porLer ? (
                <span className={cnPe("ml-2 flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-[13px] font-bold tabular-nums", a ? "bg-pe-realce text-pe-tinta" : "bg-pe-azul-vivo text-pe-sobre-marca")}>
                  <span className="sr-only">, por ler: </span>
                  {porLer > 99 ? "99+" : porLer}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto flex flex-col gap-2 px-3">
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="flex size-10 shrink-0 items-center justify-center rounded-pe-fala-s bg-pe-azul-marca font-semibold text-pe-sobre-marca"
          >
            {iniciais || "?"}
          </span>
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="truncate font-semibold leading-[22px]">{nome}</span>
            {plano ? <span className="truncate text-pe-legenda text-pe-tinta-suave">{plano}</span> : null}
          </span>
        </div>
        <button
          type="button"
          onClick={aoSair}
          className="flex min-h-11 items-center gap-2 self-start rounded-pe-sm px-1 text-[15px] font-semibold text-pe-tinta-suave hover:text-pe-tinta"
        >
          <LogOut aria-hidden className="size-[18px]" />
          Sair da conta
        </button>
      </div>
    </aside>
  );
}
