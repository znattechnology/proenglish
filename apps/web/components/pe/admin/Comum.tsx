"use client";

import Link from "next/link";
import { Search } from "lucide-react";
import { Botao, Escolha, Separadores } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import { Cabeca } from "@/components/pe/professor/Partes";

export function Procura({ valor, aoMudar, rotulo, className }: { valor: string; aoMudar: (v: string) => void; rotulo: string; className?: string }) {
  return (
    <label className={cnPe("flex h-11 w-full items-center gap-2 rounded-pe-sm border-[1.5px] border-pe-linha-forte px-3 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-pe-azul-vivo", className)}>
      <Search aria-hidden className="size-[18px] text-pe-tinta-suave" />
      <input type="search" value={valor} onChange={(e) => aoMudar(e.target.value)} placeholder={rotulo} aria-label={rotulo} className="min-w-0 flex-1 border-0 bg-transparent font-pe-texto text-[16px] text-pe-tinta outline-none" />
    </label>
  );
}

export function Filtro({ rotulo, valor, aoMudar, opcoes }: { rotulo: string; valor: string; aoMudar: (v: string) => void; opcoes: { valor: string; nome: string }[] }) {
  return (
    <Escolha rotulo={rotulo} className="[&_select]:h-11" value={valor} onChange={(e) => aoMudar(e.target.value)}>
      {opcoes.map((o) => (
        <option key={o.valor} value={o.valor}>
          {o.nome}
        </option>
      ))}
    </Escolha>
  );
}

export function Paginacao({ pagina, paginas, total, nome, aoMudar }: { pagina: number; paginas: number; total: number; nome: string; aoMudar: (p: number) => void }) {
  if (paginas <= 1) return <p className="m-0 text-pe-legenda text-pe-tinta-suave">{total.toLocaleString("pt-PT")} {nome}</p>;
  return (
    <nav aria-label="Páginas" className="flex flex-wrap items-center justify-between gap-3">
      <span className="text-pe-tinta-suave">
        Página {pagina} de {paginas}, {total.toLocaleString("pt-PT")} {nome}
      </span>
      <span className="flex gap-2">
        <Botao tipo="secundario" tamanho="pequeno" disabled={pagina <= 1} onClick={() => aoMudar(pagina - 1)}>
          Anterior
        </Botao>
        <Botao tipo="secundario" tamanho="pequeno" disabled={pagina >= paginas} onClick={() => aoMudar(pagina + 1)}>
          Seguinte
        </Botao>
      </span>
    </nav>
  );
}

/** Cabeçalho de uma secção com separadores (Utilizadores / Convites, etc.). */
export function CabecaSeccao({ titulo, texto, activo, itens, children }: { titulo: string; texto?: string; activo: string; itens: { nome: string; href: string }[]; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4">
      <Cabeca titulo={titulo} texto={texto}>
        {children}
      </Cabeca>
      <Separadores rotulo={titulo} activo={activo} itens={itens} />
    </div>
  );
}

export function Avatar({ iniciais, className }: { iniciais: string; className?: string }) {
  return (
    <span aria-hidden className={cnPe("flex size-9 shrink-0 items-center justify-center rounded-pe-fala-s bg-pe-fundo-forte text-[14px] font-semibold", className)}>
      {iniciais}
    </span>
  );
}

export function LigacaoAbrir({ href, nome }: { href: string; nome: string }) {
  return (
    <Link href={href} className="inline-flex min-h-11 items-center font-semibold text-pe-azul-vivo underline-offset-[3px]">
      Abrir<span className="sr-only">: {nome}</span>
    </Link>
  );
}

export const SEPARADORES_UTILIZADORES = [
  { nome: "Utilizadores", href: "/admin/users" },
  { nome: "Convites de professor", href: "/admin/users/invites" },
];

export const SEPARADORES_CURSOS = [
  { nome: "Todos os cursos", href: "/admin/courses" },
  { nome: "Em revisão", href: "/admin/courses/review" },
  { nome: "Análise", href: "/admin/courses/analytics" },
];

export const SEPARADORES_SUBSCRICOES = [
  { nome: "Resumo", href: "/admin/subscriptions" },
  { nome: "Assinantes", href: "/admin/subscriptions/subscribers" },
  { nome: "Pagamentos falhados", href: "/admin/subscriptions/failed" },
];

export const SEPARADORES_PLANOS = [
  { nome: "Planos", href: "/admin/plans" },
  { nome: "Códigos promocionais", href: "/admin/plans/codes" },
];

export const SEPARADORES_OPINIOES = [
  { nome: "Opiniões", href: "/admin/feedback" },
  { nome: "Testemunhos no site", href: "/admin/feedback/testimonials" },
];

/** "3 pagos, 1 em teste, 1 atribuído" para os planos pagos. */
export function detalhePlano(p: { pagos?: number; em_teste?: number; atribuidos?: number }) {
  const partes = [
    p.pagos ? `${p.pagos} ${p.pagos === 1 ? "pago" : "pagos"}` : null,
    p.em_teste ? `${p.em_teste} em teste` : null,
    p.atribuidos ? `${p.atribuidos} ${p.atribuidos === 1 ? "atribuído" : "atribuídos"} sem pagamento` : null,
  ].filter(Boolean);
  return partes.join(", ");
}
