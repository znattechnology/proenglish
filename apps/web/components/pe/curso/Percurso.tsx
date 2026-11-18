"use client";

import Link from "next/link";
import { BookOpen, Check, ClipboardCheck, Dumbbell, Mic } from "lucide-react";
import { cnPe } from "@/lib/pe";
import { Botao } from "@/components/pe";
import { hrefDoPasso, nomeDoPasso, type Passo, type ProximoPasso, type TipoPasso } from "@/src/domains/student/curso/api";

const ICONE: Record<TipoPasso, React.ReactNode> = {
  aula: <BookOpen />,
  questionario: <ClipboardCheck />,
  pratica: <Dumbbell />,
  conversa: <Mic />,
};

/** "8 min" ou nada, quando o servidor não sabe a duração. */
export function duracaoDoPasso(passo: Pick<Passo, "minutos">) {
  return passo.minutos ? `${passo.minutos} min` : null;
}

/**
 * Os passos que vêm depois do vídeo de uma aula (questionário, laboratório, conversas), pela ordem
 * em que o aluno os deve fazer. O passo da própria aula não aparece: é a linha da aula, por cima.
 */
export function PassosDaAula({ courseId, passos }: { courseId: string; passos: Passo[] }) {
  const depois = passos.filter((p) => p.tipo !== "aula");
  if (!depois.length) return null;
  return (
    <ol className="m-0 ml-[14px] flex list-none flex-col border-l-2 border-pe-fundo-forte p-0 pl-[26px]">
      {depois.map((p) => {
        const feito = p.estado === "feito";
        const actual = p.estado === "actual";
        const duracao = duracaoDoPasso(p);
        return (
          <li key={p.chave}>
            <Link
              href={hrefDoPasso(courseId, p)}
              aria-current={actual ? "step" : undefined}
              className={cnPe(
                "flex min-h-12 items-center gap-3 border-b border-pe-fundo-forte py-1 text-[15px] text-pe-tinta no-underline hover:bg-pe-fundo-suave hover:text-pe-tinta",
                actual && "font-semibold text-pe-azul-marca"
              )}
            >
              <span
                aria-hidden
                className={cnPe(
                  "flex size-6 shrink-0 items-center justify-center rounded-full [&>svg]:size-3.5",
                  feito ? "bg-pe-certo-suave text-pe-certo" : actual ? "bg-pe-realce text-pe-tinta" : "bg-pe-fundo-forte text-pe-tinta-suave"
                )}
              >
                {feito ? <Check strokeWidth={3} /> : ICONE[p.tipo]}
              </span>
              <span className="min-w-0 flex-1">
                {nomeDoPasso(p)}
                {p.tipo !== "questionario" ? <span className="font-normal text-pe-tinta-suave">: {p.titulo}</span> : null}
                {feito ? <span className="sr-only"> (feito)</span> : null}
              </span>
              {duracao ? <span className="shrink-0 text-[14px] font-normal text-pe-tinta-suave tabular-nums">{duracao}</span> : null}
            </Link>
          </li>
        );
      })}
    </ol>
  );
}

/** O texto do botão diz o que acontece a seguir. */
export function accaoDoPasso(passo: Pick<Passo, "tipo">) {
  if (passo.tipo === "aula") return "Ver a aula";
  if (passo.tipo === "questionario") return "Fazer o questionário";
  if (passo.tipo === "pratica") return "Praticar no laboratório";
  return "Falar com o tutor";
}

/**
 * "A seguir": o passo seguinte do percurso, mostrado no fim de uma aula, de uma lição ou de uma
 * conversa. Quem o usa decide se há passo para mostrar (o servidor é que o calcula).
 */
export function ASeguir({ proximo, className }: { proximo: ProximoPasso; className?: string }) {
  const p = proximo.passo;
  const duracao = duracaoDoPasso(p);
  return (
    <section
      aria-labelledby="titulo-a-seguir"
      className={cnPe("flex flex-col gap-3 rounded-pe-md border border-pe-linha px-5 py-4 md:flex-row md:items-center md:justify-between md:gap-6", className)}
    >
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="text-pe-legenda text-pe-tinta-suave">
          A seguir em {proximo.curso.titulo}, {p.unidade}
        </span>
        <h2 id="titulo-a-seguir" className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">
          {p.tipo === "questionario" ? "Questionário" : p.titulo}
        </h2>
        <span className="text-[15px] leading-[22px] text-pe-tinta-suave">
          {nomeDoPasso(p)}
          {duracao ? `, cerca de ${duracao}` : ""}
        </span>
      </div>
      <Botao asChild tipo="realce" className="self-stretch md:shrink-0 md:self-auto">
        <Link href={hrefDoPasso(proximo.curso.id, p)}>{accaoDoPasso(p)}</Link>
      </Botao>
    </section>
  );
}
