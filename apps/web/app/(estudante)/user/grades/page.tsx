"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { cnPe } from "@/lib/pe";
import { useNotasDeTodosQuery, type NotasDeTodos } from "@/src/domains/student/curso/api";
import { categoriaPt } from "@/src/domains/student/inicio/api";
import { useCertificadosQuery } from "@/src/domains/student/progresso/api";

type LinhaCurso = NotasDeTodos["courses"][number];

const minimo = (c: LinhaCurso) => c.nota_minima ?? c.missing_requirements?.find((r) => r.requirement === "final_grade")?.required ?? 70;
const semNota = (c: LinhaCurso) => c.grading_mode === "no_content" || c.active_components.length === 0;

/** Notas de todos os cursos: uma linha por curso, com a régua até aos 70% do certificado. */
export default function PaginaNotas() {
  const { data, isError, refetch } = useNotasDeTodosQuery();
  const { data: certs } = useCertificadosQuery();
  const emitidos = new Set((certs?.certificados ?? []).filter((c) => c.estado === "valido").map((c) => c.curso.id));

  return (
    <Pagina className="max-w-[1040px]">
      <div className="flex flex-col gap-1">
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">As suas notas</h1>
        <p className="m-0 text-pe-tinta-suave">Abra um curso para ver como a nota foi calculada.</p>
      </div>

      {isError ? (
        <div role="alert" className="flex max-w-[640px] flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
          <p className="m-0">Não conseguimos carregar as notas.</p>
          <Botao tamanho="pequeno" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : !data ? (
        <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-4">
          <Osso className="h-[120px] max-w-[420px] rounded-pe-md" />
          {[0, 1, 2].map((i) => (
            <Osso key={i} className="h-[88px] rounded-pe-md" />
          ))}
        </div>
      ) : !data.courses.length ? (
        <div className="flex max-w-[760px] flex-col items-start gap-3 rounded-pe-md bg-pe-fundo-suave p-6">
          <h2 className="m-0 text-pe-titulo-s">Ainda não há notas</h2>
          <p className="m-0 text-pe-tinta-suave">A nota aparece depois do primeiro questionário de um curso. Para o certificado precisa de 70% ou mais na nota final.</p>
          <Botao asChild tamanho="medio">
            <Link href="/user/courses">Ver os cursos</Link>
          </Botao>
        </div>
      ) : (
        <Conteudo d={data} emitidos={emitidos} />
      )}
    </Pagina>
  );
}

function Conteudo({ d, emitidos }: { d: NotasDeTodos; emitidos: Set<string> }) {
  const comNota = d.courses.filter((c) => !semNota(c));
  const semNotaAinda = d.courses.filter(semNota);
  const media = typeof d.summary.average_grade === "number" ? d.summary.average_grade : d.summary.average_grade.percentage;

  return (
    <>
      {comNota.length ? (
        <section aria-labelledby="titulo-media" className="pe-sobre-marca flex max-w-[460px] flex-col gap-1 rounded-[28px_28px_28px_0] bg-pe-azul-marca p-6 text-pe-sobre-marca">
          <h2 id="titulo-media" className="m-0 text-[15px] font-semibold leading-5">
            {comNota.length === 1 ? "Nota do seu curso" : `Média dos ${comNota.length} cursos`}
          </h2>
          <p className="m-0 font-pe-titulo text-[56px] font-bold leading-[60px] tabular-nums">{Math.round(media)}%</p>
          <p className="m-0 text-[15px] leading-[22px]">
            Cada curso pede 70% para dar certificado.
            {d.summary.certificates_earned ? ` Já tem ${d.summary.certificates_earned} ${d.summary.certificates_earned === 1 ? "certificado" : "certificados"}.` : ""}
          </p>
        </section>
      ) : null}

      {comNota.length ? (
        <ul aria-label="Cursos com nota" className="m-0 flex list-none flex-col p-0">
          {comNota.map((c) => (
            <Linha key={c.course.id} c={c} emitido={emitidos.has(c.course.id)} />
          ))}
        </ul>
      ) : null}

      {semNotaAinda.length ? (
        <section aria-labelledby="titulo-sem-nota" className="flex flex-col gap-2 pt-2">
          <h2 id="titulo-sem-nota" className="m-0 font-pe-titulo text-pe-titulo-s">
            Ainda sem nota
          </h2>
          <p className="m-0 text-[15px] text-pe-tinta-suave">A nota aparece depois do primeiro questionário ou lição de prática.</p>
          <ul className="m-0 flex list-none flex-col p-0">
            {semNotaAinda.map((c) => (
              <li key={c.course.id}>
                <Link href={`/user/courses/${c.course.id}`} className="flex min-h-14 items-center gap-3 border-b border-pe-fundo-forte py-2 text-pe-tinta no-underline hover:bg-pe-fundo-suave md:px-2">
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="text-[14px] leading-5 text-pe-tinta-suave">{categoriaPt(c.course.category)}</span>
                    <span className="truncate font-semibold leading-[22px]">{c.course.title}</span>
                  </span>
                  <span className="text-[15px] font-semibold text-pe-azul-marca">Continuar</span>
                  <ChevronRight aria-hidden className="size-5 shrink-0 text-pe-tinta-suave" />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

function estado(c: LinhaCurso, emitido: boolean) {
  const pct = c.final_grade.percentage;
  const min = minimo(c);
  if (emitido) return { texto: "Aprovado, certificado emitido", ok: true };
  if (c.is_eligible_for_certificate) return { texto: "Aprovado. Já pode receber o certificado.", ok: true };
  if (pct >= min) {
    const outro = c.missing_requirements?.find((r) => r.requirement !== "final_grade");
    return { texto: outro ? `Já acima de ${min}%. Falta: ${outro.message.replace(/\.0%/g, "%")}` : `Em curso, já acima de ${min}%`, ok: false };
  }
  const faltam = Math.ceil(min - pct);
  return { texto: `Em curso, ${faltam === 1 ? "falta 1 ponto" : `faltam ${faltam} pontos`} para ${min}%`, ok: false };
}

function Linha({ c, emitido }: { c: LinhaCurso; emitido: boolean }) {
  const pct = Math.round(c.final_grade.percentage);
  const min = minimo(c);
  const e = estado(c, emitido);
  return (
    <li>
      <Link
        href={`/user/courses/${c.course.id}/grades`}
        className="grid grid-cols-[72px_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 border-b border-pe-fundo-forte py-4 text-pe-tinta no-underline hover:bg-pe-fundo-suave md:grid-cols-[96px_minmax(0,1fr)_minmax(200px,280px)_auto] md:px-2"
      >
        <span className="font-pe-titulo text-[30px] font-bold leading-9 tabular-nums md:text-[36px] md:leading-[42px]">{pct}%</span>
        <span className="flex min-w-0 flex-col">
          <span className="text-[14px] leading-5 text-pe-tinta-suave">{categoriaPt(c.course.category)}</span>
          <span className="font-semibold leading-[22px] md:truncate">{c.course.title}</span>
          <span className={cnPe("text-[14px] leading-5", e.ok ? "font-semibold text-pe-certo" : "text-pe-tinta-suave")}>{e.texto}</span>
        </span>
        <ChevronRight aria-hidden className="size-5 shrink-0 text-pe-tinta-suave md:order-last" />
        <Regua pct={pct} min={min} titulo={c.course.title} />
      </Link>
    </li>
  );
}

/** Barra da nota com um traço nos 70%: mostra de uma vez quanto falta (ou sobra) para o certificado. */
function Regua({ pct, min, titulo }: { pct: number; min: number; titulo: string }) {
  return (
    <span className="col-span-3 flex flex-col gap-1 md:col-span-1">
      <span
        role="img"
        aria-label={`${titulo}: ${pct}% de 100. O certificado pede ${min}%.`}
        className="relative block h-2.5 w-full rounded-full bg-pe-fundo-forte"
      >
        <span className={cnPe("absolute inset-y-0 left-0 rounded-full", pct >= min ? "bg-pe-certo" : "bg-pe-azul-vivo")} style={{ width: `${Math.min(100, Math.max(pct, 2))}%` }} />
        <span aria-hidden className="absolute -inset-y-1.5 w-0.5 rounded-full bg-pe-tinta" style={{ left: `${min}%` }} />
      </span>
      <span aria-hidden className="relative block h-4 text-[12px] leading-4 text-pe-tinta-suave">
        <span className="absolute -translate-x-1/2" style={{ left: `${min}%` }}>
          {min}%
        </span>
      </span>
    </span>
  );
}
