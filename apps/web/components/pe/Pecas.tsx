import * as React from "react";
import Link from "next/link";
import { Heart } from "lucide-react";
import { cnPe } from "@/lib/pe";

/* ------------------------------------------------------------------ */
/* Etiqueta: estado curto (Publicado, Pago, Por rever...).             */
/* Cor nunca sozinha: o texto diz sempre o estado.                     */
/* ------------------------------------------------------------------ */
const ETIQUETA = {
  neutra: "bg-pe-fundo-forte text-pe-tinta",
  certo: "bg-pe-certo-suave text-pe-certo",
  errado: "bg-pe-errado-suave text-pe-errado",
  realce: "bg-pe-realce text-pe-tinta",
  marca: "bg-pe-azul-marca text-pe-sobre-marca",
} as const;

export function Etiqueta({
  tipo = "neutra",
  className,
  children,
}: {
  tipo?: keyof typeof ETIQUETA;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cnPe(
        "inline-flex w-fit items-center gap-1 whitespace-nowrap rounded-pe-sm px-2.5 py-0.5 text-pe-legenda font-semibold",
        ETIQUETA[tipo],
        className
      )}
    >
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Cartão                                                              */
/* ------------------------------------------------------------------ */
export function Cartao({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cnPe("flex flex-col gap-3 rounded-pe-md border border-pe-linha bg-pe-fundo p-4", className)} {...props}>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Balão de fala: a forma do logótipo. Tutor em azul-marca, aluno em   */
/* fundo-suave. O canto recto fica do lado de quem fala.              */
/* ------------------------------------------------------------------ */
export function BalaoFala({
  quem = "tutor",
  autor,
  className,
  children,
}: {
  quem?: "tutor" | "aluno";
  autor?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  const tutor = quem === "tutor";
  return (
    <div
      className={cnPe(
        "flex max-w-[560px] flex-col gap-1.5 px-6 py-4",
        tutor
          ? "pe-sobre-marca self-start rounded-pe-fala bg-pe-azul-marca text-pe-sobre-marca"
          : "self-end rounded-pe-fala-aluno bg-pe-fundo-suave text-pe-tinta",
        className
      )}
    >
      {autor ? <span className="text-pe-legenda font-semibold">{autor}</span> : null}
      <div className="text-pe-corpo-l">{children}</div>
    </div>
  );
}

/** A palavra ou frase que o aluno está a aprender, marcada a amarelo. */
export function Realce({ children }: { children: React.ReactNode }) {
  return (
    <mark className="rounded-[2px] bg-pe-realce px-1.5 font-semibold text-pe-tinta [box-decoration-break:clone]">
      {children}
    </mark>
  );
}

/* ------------------------------------------------------------------ */
/* Barra de progresso                                                  */
/* ------------------------------------------------------------------ */
export function BarraProgresso({
  valor,
  rotulo,
  altura = 8,
  cor = "vivo",
  className,
}: {
  valor: number;
  rotulo: string;
  altura?: number;
  /** Sobre azul-marca use "realce": o azul-vivo não tem contraste suficiente aí. */
  cor?: "vivo" | "certo" | "errado" | "marca" | "realce";
  className?: string;
}) {
  const v = Math.max(0, Math.min(100, Math.round(valor)));
  const preenchimento = { vivo: "bg-pe-azul-vivo", certo: "bg-pe-certo", errado: "bg-pe-errado", marca: "bg-pe-azul-marca", realce: "bg-pe-realce" }[cor];
  return (
    <div
      role="progressbar"
      aria-valuenow={v}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={rotulo}
      className={cnPe("w-full overflow-hidden rounded-full bg-pe-fundo-forte", className)}
      style={{ height: altura }}
    >
      <div className={cnPe("h-full rounded-full", preenchimento)} style={{ width: `${v}%` }} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Vidas do laboratório                                                */
/* ------------------------------------------------------------------ */
export function Vidas({ quantas, ilimitadas = false }: { quantas: number; ilimitadas?: boolean }) {
  const texto = ilimitadas ? "Vidas ilimitadas" : `${quantas} ${quantas === 1 ? "vida" : "vidas"}`;
  return (
    <span role="img" aria-label={texto} className="inline-flex items-center gap-1 font-semibold">
      <Heart aria-hidden className="size-[22px] fill-pe-vida text-pe-vida" />
      {ilimitadas ? "∞" : quantas}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Separadores (navegação entre vistas da mesma área, com URL própria) */
/* ------------------------------------------------------------------ */
export function Separadores({
  itens,
  activo,
  rotulo,
  className,
}: {
  itens: { nome: string; href: string }[];
  activo: string;
  rotulo: string;
  className?: string;
}) {
  return (
    <nav aria-label={rotulo} className={cnPe("flex border-b border-pe-linha", className)}>
      {itens.map((i) => {
        const a = i.nome === activo;
        return (
          <Link
            key={i.href}
            href={i.href}
            aria-current={a ? "page" : undefined}
            className={cnPe(
              "flex min-h-11 items-center border-b-[3px] px-4 no-underline",
              a ? "border-pe-azul-marca font-semibold text-pe-azul-marca" : "border-transparent text-pe-tinta-suave hover:text-pe-tinta"
            )}
          >
            {i.nome}
          </Link>
        );
      })}
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/* Aviso em linha (informação, sucesso, erro)                          */
/* ------------------------------------------------------------------ */
const AVISO = {
  info: "bg-pe-realce-suave text-pe-tinta",
  certo: "bg-pe-certo-suave text-pe-tinta",
  errado: "bg-pe-errado-suave text-pe-tinta",
  neutro: "bg-pe-fundo-suave text-pe-tinta",
} as const;

export function Aviso({
  tipo = "info",
  icone,
  children,
  className,
}: {
  tipo?: keyof typeof AVISO;
  icone?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      role={tipo === "errado" ? "alert" : "status"}
      className={cnPe("flex gap-2.5 rounded-pe-md px-3.5 py-3 text-[15px] leading-[22px]", AVISO[tipo], className)}
    >
      {icone ? <span className="mt-px shrink-0 [&_svg]:size-5">{icone}</span> : null}
      <div>{children}</div>
    </div>
  );
}

/** Bloco de carregamento com a forma do conteúdo que vem a seguir. */
export function Osso({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <span aria-hidden className={cnPe("pe-osso block rounded-pe-sm", className)} style={style} />;
}

/** Marca quadrada com um canto recto e um ícone (estados vazios, permissões...). */
export function MarcaIcone({
  children,
  fundo = "marca",
  tamanho = 80,
}: {
  children: React.ReactNode;
  fundo?: "marca" | "forte" | "realce" | "errado";
  tamanho?: number;
}) {
  const cores = {
    marca: "bg-pe-azul-marca text-pe-sobre-marca",
    forte: "bg-pe-fundo-forte text-pe-tinta",
    realce: "bg-pe-realce-suave text-pe-tinta",
    errado: "bg-pe-errado-suave text-pe-errado",
  }[fundo];
  const r = Math.round(tamanho / 3);
  return (
    <span
      aria-hidden
      className={cnPe("flex shrink-0 items-center justify-center [&_svg]:size-1/2", cores)}
      style={{ width: tamanho, height: tamanho, borderRadius: `${r}px ${r}px ${r}px 0` }}
    >
      {children}
    </span>
  );
}
