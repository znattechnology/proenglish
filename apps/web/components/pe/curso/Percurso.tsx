"use client";

import Link from "next/link";
import { BookOpen, Check, ClipboardCheck, Dumbbell, Mic } from "lucide-react";
import { cnPe } from "@/lib/pe";
import { hrefDoPasso, nomeDoPasso, type Passo, type TipoPasso } from "@/src/domains/student/curso/api";

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
