"use client";

import Link from "next/link";
import { SobreProfessor } from "@/components/pe/curso/SobreProfessor";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Check, Lock } from "lucide-react";
import { Aviso, Botao, Osso } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { nivelEmFrase, nomeCompletoNivel } from "@/src/domains/shared/niveis";
import { categoriaPt } from "@/src/domains/student/inicio/api";
import { mensagemErro, useMinhaSubscricaoQuery } from "@/src/domains/student/subscricao/api";
import {
  capitulosPorOrdem,
  concluidos,
  PLANO_DO_CURSO,
  TIPO_PT,
  useCursoQuery,
  useInscreverMutation,
  useInscricaoQuery,
  useNotasQuery,
  useProgressoQuery,
  type Curso,
} from "@/src/domains/student/curso/api";

export default function PaginaCurso() {
  const { courseId } = useParams<{ courseId: string }>();
  const { data, isLoading, isError, refetch } = useCursoQuery(courseId);
  const { data: inscricao } = useInscricaoQuery(courseId);

  if (isError) {
    return (
      <main className="mx-auto flex w-full max-w-[1280px] flex-col items-start gap-4 px-5 py-10 md:px-10">
        <h1 className="m-0 text-pe-titulo-m">Não encontrámos este curso</h1>
        <p className="m-0 text-pe-tinta-suave">Pode ter deixado de estar publicado.</p>
        <div className="flex gap-3">
          <Botao onClick={() => refetch()}>Tentar outra vez</Botao>
          <Botao asChild tipo="secundario">
            <Link href="/user/courses/explore">Explorar cursos</Link>
          </Botao>
        </div>
      </main>
    );
  }
  if (isLoading || !data || !inscricao) return <EsqueletoCurso />;

  return inscricao.is_enrolled && data.temAcesso ? <CursoInscrito curso={data.curso} /> : <CursoPorComecar curso={data.curso} temAcesso={data.temAcesso} />;
}

/* ------------------------------------------------------------------ */
/* Inscrito: progresso, continuar, secções                              */
/* ------------------------------------------------------------------ */
function CursoInscrito({ curso }: { curso: Curso }) {
  const { user } = useDjangoAuth();
  const { data: progresso } = useProgressoQuery({ userId: user?.id ?? "", courseId: curso.courseId }, { skip: !user });
  const { data: notas } = useNotasQuery(curso.courseId);
  const lista = capitulosPorOrdem(curso);
  const feitos = concluidos(progresso);
  const seguinte = lista.find((c) => !feitos.has(c.chapterId));
  const nFeitos = lista.filter((c) => feitos.has(c.chapterId)).length;
  const pct = lista.length ? (100 * nFeitos) / lista.length : 0;
  const contexto = [categoriaPt(curso.category), nivelEmFrase(curso.level), curso.teacherName || null, `${lista.length} aulas`].filter(Boolean).join(", ");

  return (
    <div className="flex flex-col">
      <section className="pe-sobre-marca rounded-br-pe-fala bg-pe-azul-marca text-pe-sobre-marca md:rounded-br-[28px]">
        <div className="mx-auto flex max-w-[1280px] flex-col gap-6 px-5 pb-8 pt-5 md:flex-row md:flex-wrap md:items-end md:justify-between md:px-10 md:pb-9 md:pt-8 xl:px-12">
          <div className="flex min-w-0 flex-col gap-3 md:flex-[1_1_420px]">
            <Link href="/user/courses" className="inline-flex min-h-11 items-center gap-1.5 self-start text-[15px] font-semibold text-pe-sobre-marca underline-offset-[3px] hover:text-pe-realce">
              <ArrowLeft aria-hidden className="size-5" /> Os meus cursos
            </Link>
            <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-[34px] tracking-[-0.01em] md:text-[34px] md:leading-10">{curso.title}</h1>
            <span className="text-[15px] leading-6 md:text-[16px]">{contexto}</span>
            <div className="flex max-w-[460px] items-center gap-3">
              <div role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label="Progresso do curso" className="h-2.5 flex-1 overflow-hidden rounded-full bg-white/25">
                <div className="h-full rounded-full bg-pe-sobre-marca" style={{ width: `${pct}%` }} />
              </div>
              <span className="shrink-0 text-[15px] tabular-nums">
                {nFeitos} de {lista.length}
              </span>
            </div>
          </div>
          {seguinte ? (
            <Botao asChild tipo="realce" className="md:shrink-0">
              <Link href={`/user/courses/${curso.courseId}/chapters/${seguinte.chapterId}`}>
                {nFeitos ? `Continuar: aula ${seguinte.numero}` : "Começar a primeira aula"}
              </Link>
            </Botao>
          ) : (
            <span className="inline-flex items-center gap-2 font-semibold">
              <Check aria-hidden className="size-5" /> Todas as aulas vistas
            </span>
          )}
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-10 px-5 pb-10 pt-7 lg:flex-row lg:items-start lg:px-10 xl:px-12">
        <div className="flex min-w-0 flex-col gap-7 lg:flex-[3_1_560px]">
          {curso.sections.map((s) => {
            const caps = lista.filter((c) => c.sectionId === s.sectionId);
            const feitosS = caps.filter((c) => feitos.has(c.chapterId)).length;
            return (
              <section key={s.sectionId} aria-labelledby={`sec-${s.sectionId}`} className="flex flex-col gap-1.5">
                <div className="flex items-baseline justify-between gap-3">
                  <h2 id={`sec-${s.sectionId}`} className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">
                    {s.sectionTitle}
                  </h2>
                  <span className="shrink-0 text-[15px] text-pe-tinta-suave tabular-nums">
                    {feitosS} de {caps.length}
                  </span>
                </div>
                <ol className="m-0 flex list-none flex-col p-0">
                  {caps.map((c) => {
                    const feita = feitos.has(c.chapterId);
                    const actual = seguinte?.chapterId === c.chapterId;
                    return (
                      <li key={c.chapterId}>
                        <Link
                          href={`/user/courses/${curso.courseId}/chapters/${c.chapterId}`}
                          aria-current={actual ? "step" : undefined}
                          className={cnPe(
                            "flex min-h-14 items-center gap-3.5 border-b border-pe-fundo-forte py-1 text-pe-tinta no-underline hover:bg-pe-fundo-suave hover:text-pe-tinta",
                            actual && "font-semibold text-pe-azul-marca"
                          )}
                        >
                          <span
                            aria-hidden
                            className={cnPe(
                              "flex size-[30px] shrink-0 items-center justify-center rounded-full text-[13px] font-semibold tabular-nums",
                              feita ? "bg-pe-certo-suave text-pe-certo" : actual ? "bg-pe-realce text-pe-tinta" : "bg-pe-fundo-forte text-pe-tinta-suave"
                            )}
                          >
                            {feita ? <Check className="size-4" strokeWidth={3} /> : c.type === "Quiz" ? "Q" : c.numero}
                          </span>
                          <span className="min-w-0 flex-1">
                            {c.title}
                            {feita ? <span className="sr-only"> (vista)</span> : null}
                          </span>
                          <span className="shrink-0 text-[14px] font-normal text-pe-tinta-suave">{TIPO_PT[c.type] ?? c.type}</span>
                        </Link>
                      </li>
                    );
                  })}
                </ol>
              </section>
            );
          })}
        </div>

        <aside aria-label="Notas e certificado" className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-8 lg:max-w-[400px] lg:flex-[1_1_300px]">
          <Link href={`/user/courses/${curso.courseId}/grades`} className="flex flex-col gap-1.5 rounded-pe-md bg-pe-fundo-suave p-[22px] text-pe-tinta no-underline hover:bg-pe-fundo-forte hover:text-pe-tinta">
            <span className="text-[15px] text-pe-tinta-suave">Nota até agora</span>
            {notas ? (
              <span className="font-pe-titulo text-[34px] font-bold leading-10 tabular-nums">{Math.round(notas.final_grade.percentage)}%</span>
            ) : (
              <Osso className="h-10 w-24" />
            )}
            <span className="text-[15px] leading-[22px]">
              {notas
                ? notas.plano_inclui_certificados === false
                  ? "Os certificados fazem parte do Premium e do Premium Plus."
                  : notas.certificate_eligibility.is_eligible
                  ? "Já cumpre tudo o que o certificado pede."
                  : `Certificado a partir de ${notas.nota_minima ?? notas.certificate_eligibility.nota_minima ?? 70}%. ${Object.values(notas.certificate_eligibility.details).filter((d) => !d.met && !d.info_only).length} ${Object.values(notas.certificate_eligibility.details).filter((d) => !d.met && !d.info_only).length === 1 ? "requisito por cumprir" : "requisitos por cumprir"}.`
                : " "}
            </span>
            <span className="font-semibold text-pe-azul-vivo underline underline-offset-[3px]">Ver as notas</span>
          </Link>
          {curso.description ? (
            <section className="flex flex-col gap-2 rounded-pe-md border border-pe-linha p-[22px]">
              <h2 className="m-0 font-pe-titulo text-[18px] font-semibold leading-6">Sobre o curso</h2>
              <p className="m-0 text-[15px] leading-[22px]">{curso.description}</p>
            </section>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Ainda não inscrito: programa e começar (ou plano necessário)        */
/* ------------------------------------------------------------------ */
function CursoPorComecar({ curso, temAcesso }: { curso: Curso; temAcesso: boolean }) {
  const { data: sub } = useMinhaSubscricaoQuery();
  const [inscrever, { isLoading }] = useInscreverMutation();
  const [erro, setErro] = useState<string | null>(null);
  const plano = PLANO_DO_CURSO[curso.access_level] ?? PLANO_DO_CURSO.free;
  const lista = capitulosPorOrdem(curso);
  const total = curso.total_chapters || lista.length;

  const comecar = async () => {
    setErro(null);
    const r = await inscrever(curso.courseId);
    if ("error" in r && r.error) {
      setErro(mensagemErro(r.error, "Não foi possível começar o curso. Tente outra vez."));
      return;
    }
    // A inscrição invalida o curso e o estado: a página passa sozinha para a vista de inscrito.
  };

  return (
    <main className="mx-auto flex w-full max-w-[1280px] flex-col gap-8 px-5 pb-10 pt-4 md:px-10 md:pt-8 lg:flex-row lg:items-start xl:px-12">
      <div className="flex min-w-0 flex-col gap-7 lg:flex-[3_1_560px]">
        <div className="flex flex-col gap-2">
          <Link href="/user/courses/explore" className="inline-flex min-h-11 items-center gap-1.5 self-start text-[15px] font-semibold underline-offset-[3px]">
            <ArrowLeft aria-hidden className="size-5" /> Explorar cursos
          </Link>
          <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-[34px] tracking-[-0.01em] md:text-pe-titulo-l">{curso.title}</h1>
          <p className="m-0 text-pe-tinta-suave">{[categoriaPt(curso.category), nivelEmFrase(curso.level)].filter(Boolean).join(", ")}</p>
          {curso.description ? <p className="m-0 max-w-[68ch] text-pe-corpo-l">{curso.description}</p> : null}
        </div>
        <section aria-labelledby="titulo-programa" className="flex flex-col gap-3">
          <h2 id="titulo-programa" className="m-0 font-pe-titulo text-pe-titulo-s">
            Programa
          </h2>
          <ol className="m-0 flex list-none flex-col p-0">
            {curso.sections.map((s, i) => {
              const caps = s.chapters;
              const questionarios = caps.filter((c) => c.type === "Quiz").length;
              return (
                <li key={s.sectionId} className="flex items-start gap-3.5 border-b border-pe-fundo-forte py-3">
                  <span aria-hidden className="pe-sobre-marca flex size-8 shrink-0 items-center justify-center rounded-[11px_11px_11px_0] bg-pe-azul-marca font-pe-titulo text-[14px] font-bold text-pe-sobre-marca">
                    {i + 1}
                  </span>
                  <span className="flex flex-col">
                    <span className="font-semibold leading-[22px]">{s.sectionTitle}</span>
                    <span className="text-pe-legenda text-pe-tinta-suave">
                      {caps.length
                        ? `${caps.length - questionarios} ${caps.length - questionarios === 1 ? "aula" : "aulas"}${questionarios ? `, ${questionarios} ${questionarios === 1 ? "questionário" : "questionários"}` : ""}`
                        : s.sectionDescription || "Conteúdo disponível com o plano certo"}
                    </span>
                  </span>
                </li>
              );
            })}
          </ol>
        </section>
        <SobreProfessor id={curso.teacherId} />
      </div>

      <aside aria-label="Começar o curso" className="flex min-w-0 flex-col gap-4 rounded-pe-md border border-pe-linha p-6 lg:sticky lg:top-8 lg:max-w-[400px] lg:flex-[1_1_320px]">
        <dl className="m-0 flex flex-col">
          {(
            [
              ["Professor", curso.teacherName],
              ["Nível", nomeCompletoNivel(curso.level) ?? "—"],
              ["Aulas", total ? `${total}` : "—"],
              ["Incluído no plano", plano.nome],
            ] as [string, string][]
          ).map(([dt, dd]) => (
            <div key={dt} className="flex justify-between gap-4 border-b border-pe-fundo-forte py-2.5 text-[15px] leading-[22px] last:border-0">
              <dt className="text-pe-tinta-suave">{dt}</dt>
              <dd className="m-0 text-right font-semibold">{dd}</dd>
            </div>
          ))}
        </dl>
        {temAcesso ? (
          <>
            <p className="m-0 text-[15px] leading-[22px]">
              {curso.access_level === "free" ? "Este curso é gratuito para todos." : `Incluído no seu plano ${sub?.plan.name ?? plano.nome}.`}
            </p>
            {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
            <Botao larguraTotal disabled={isLoading} onClick={() => void comecar()}>
              {isLoading ? "A preparar o curso…" : "Começar o curso"}
            </Botao>
          </>
        ) : (
          <>
            <div className="flex items-start gap-2.5 rounded-pe-md bg-pe-realce-suave p-3.5 text-[15px] leading-[22px]">
              <Lock aria-hidden className="mt-0.5 size-5 shrink-0" />
              <span>
                Este curso faz parte do {plano.nome}. O seu plano é o {sub?.plan.name ?? "Gratuito"}.
              </span>
            </div>
            <Botao asChild tipo="realce" larguraTotal>
              <Link href={`/user/upgrade?plan=${plano.tipo}`}>Passar para {plano.nome}</Link>
            </Botao>
            <Link href="/user/subscription#planos" className="self-center text-[15px] font-semibold underline-offset-[3px]">
              Comparar planos
            </Link>
          </>
        )}
      </aside>
    </main>
  );
}

function EsqueletoCurso() {
  return (
    <div aria-busy="true" aria-label="A carregar o curso" className="flex flex-col">
      <div className="h-[220px] bg-pe-fundo-suave" />
      <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-3 px-5 py-8 md:px-10">
        <Osso className="h-7 w-64" />
        {[0, 1, 2, 3, 4].map((i) => (
          <Osso key={i} className="h-14" />
        ))}
      </div>
    </div>
  );
}
