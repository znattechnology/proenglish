import Link from "next/link";
import { cnPe } from "@/lib/pe";
import { Etiqueta } from "@/components/pe";
import { ESTADO, type EstadoCurso } from "@/src/domains/teacher/professor/api";

/** Título da página com a explicação curta e as acções à direita (por baixo no telemóvel). */
export function Cabeca({ titulo, texto, children }: { titulo: string; texto?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex min-w-0 flex-col gap-1">
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 tracking-[-0.015em] md:text-[32px] md:leading-[38px]">{titulo}</h1>
        {texto ? <p className="m-0 text-pe-tinta-suave">{texto}</p> : null}
      </div>
      {children ? <div className="flex shrink-0 flex-wrap gap-3">{children}</div> : null}
    </div>
  );
}

/** Números do topo: rótulo, valor grande, nota curta. */
export function Numeros({ itens }: { itens: { nome: string; valor: string; nota?: string }[] }) {
  return (
    <dl className="m-0 grid grid-cols-2 gap-3 md:gap-4 xl:grid-cols-4">
      {itens.map((n) => (
        <div key={n.nome} className="flex min-w-0 flex-col gap-0.5 rounded-pe-md bg-pe-fundo-suave px-[18px] py-4">
          <dt className="text-pe-legenda text-pe-tinta-suave">{n.nome}</dt>
          <dd className="m-0 font-pe-titulo text-[24px] font-bold leading-8 tabular-nums md:text-[26px]">{n.valor}</dd>
          {n.nota ? <dd className="m-0 text-pe-legenda">{n.nota}</dd> : null}
        </div>
      ))}
    </dl>
  );
}

export function EtiquetaEstado({ estado }: { estado: EstadoCurso }) {
  const e = ESTADO[estado] ?? ESTADO.rascunho;
  return <Etiqueta tipo={e.tipo}>{e.nome}</Etiqueta>;
}

/** Miniatura da capa; sem imagem mostra as iniciais do título. */
export function Capa({ imagem, titulo, className }: { imagem: string | null; titulo: string; className?: string }) {
  return imagem ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={imagem} alt="" className={cnPe("h-10 w-14 shrink-0 rounded-pe-sm bg-pe-fundo-forte object-cover", className)} />
  ) : (
    <span aria-hidden className={cnPe("flex h-10 w-14 shrink-0 items-center justify-center rounded-pe-sm bg-pe-fundo-forte font-pe-titulo text-[14px] font-bold text-pe-tinta-suave", className)}>
      {titulo
        .replace(/\[[^\]]*\]/g, "")
        .split(/\s+/)
        .filter((p) => p.length > 2 && /^\p{L}/u.test(p))
        .slice(0, 2)
        .map((p) => p[0]?.toUpperCase())
        .join("")}
    </span>
  );
}

export function LigacaoEditar({ href, nome }: { href: string; nome: string }) {
  return (
    <Link href={href} className="inline-flex min-h-11 items-center font-semibold text-pe-azul-vivo underline-offset-[3px]">
      Editar<span className="sr-only">: {nome}</span>
    </Link>
  );
}
