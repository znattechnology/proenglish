"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Check, Dumbbell, ExternalLink, FileText } from "lucide-react";
import { Aviso, Botao, Etiqueta, Osso } from "@/components/pe";
import { Questionario } from "@/components/pe/curso/Questionario";
import { TextoRico } from "@/components/pe/curso/TextoRico";
import { cnPe } from "@/lib/pe";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import {
  capitulosPorOrdem,
  concluidos,
  TIPO_PT,
  useCapituloQuery,
  useCursoQuery,
  useInscricaoQuery,
  useMarcarCapituloMutation,
  useProgressoQuery,
  useRecursosQuery,
  type CapituloNoCurso,
} from "@/src/domains/student/curso/api";

type Linha = { start: number; end: number; text: string };

export default function PaginaAula() {
  const { courseId, chapterId } = useParams<{ courseId: string; chapterId: string }>();
  const { user } = useDjangoAuth();
  const { data: dados, isError: erroCurso } = useCursoQuery(courseId);
  const { data: inscricao } = useInscricaoQuery(courseId);
  const podeVer = !!inscricao?.is_enrolled && !!dados?.temAcesso;
  const { data: cap, isError: erroCap, refetch } = useCapituloQuery(chapterId, { skip: !podeVer });
  const { data: progresso } = useProgressoQuery({ userId: user?.id ?? "", courseId }, { skip: !user || !podeVer });

  const lista = useMemo(() => (dados ? capitulosPorOrdem(dados.curso) : []), [dados]);
  const i = lista.findIndex((c) => c.chapterId === chapterId);
  const aqui = lista[i];
  const anterior = i > 0 ? lista[i - 1] : null;
  const seguinte = i >= 0 && i < lista.length - 1 ? lista[i + 1] : null;
  const feitos = concluidos(progresso);

  if (erroCurso) return <Problema titulo="Não encontrámos este curso" courseId={courseId} />;
  if (!dados || !inscricao) return <EsqueletoAula />;
  if (!podeVer) {
    return (
      <main className="mx-auto flex w-full max-w-[720px] flex-col items-start gap-4 px-5 py-10">
        <h1 className="m-0 text-pe-titulo-m">{inscricao.is_enrolled ? "Esta aula precisa de outro plano" : "Comece o curso para ver as aulas"}</h1>
        <p className="m-0 text-pe-tinta-suave">{dados.curso.title}</p>
        <Botao asChild>
          <Link href={`/user/courses/${courseId}`}>Ver o curso</Link>
        </Botao>
      </main>
    );
  }
  if (!aqui) return <Problema titulo="Esta aula já não existe" courseId={courseId} />;
  if (erroCap) return <Problema titulo="Não conseguimos abrir esta aula" courseId={courseId} aoTentar={refetch} />;

  const daSeccao = lista.filter((c) => c.sectionId === aqui.sectionId);

  return (
    <main className="mx-auto flex w-full max-w-[1280px] flex-col gap-5 px-5 pb-10 pt-4 md:px-10 md:pt-6 xl:px-12">
      <nav aria-label="Caminho" className="flex flex-wrap items-center gap-x-1.5 text-[15px] leading-[22px] text-pe-tinta-suave">
        <Link href="/user/courses" className="underline-offset-[3px]">
          Cursos
        </Link>
        <span aria-hidden>/</span>
        <Link href={`/user/courses/${courseId}`} className="underline-offset-[3px]">
          {dados.curso.title}
        </Link>
        <span aria-hidden className="hidden md:inline">
          /
        </span>
        <span className="hidden md:inline">{aqui.seccao}</span>
      </nav>

      <div className="flex flex-col gap-8 lg:flex-row lg:items-start">
        <div className="flex min-w-0 flex-col gap-6 lg:flex-[3_1_560px]">
          {cap ? (
            <Conteudo
              key={chapterId}
              cap={{ ...aqui, ...cap }}
              courseId={courseId}
              userId={user?.id ?? ""}
              feito={feitos.has(chapterId)}
              seguinte={seguinte}
            />
          ) : (
            <Osso className="aspect-video rounded-pe-md" />
          )}

          <div className="flex flex-wrap justify-between gap-3 border-t border-pe-linha pt-5">
            {anterior ? (
              <Link href={`/user/courses/${courseId}/chapters/${anterior.chapterId}`} className="inline-flex min-h-11 items-center gap-1.5 font-semibold underline-offset-[3px]">
                <ArrowLeft aria-hidden className="size-5" /> <span className="sr-only">Aula anterior: </span>
                <span className="max-w-[40vw] truncate md:max-w-none">{anterior.title}</span>
              </Link>
            ) : (
              <span />
            )}
            {seguinte ? (
              <Link href={`/user/courses/${courseId}/chapters/${seguinte.chapterId}`} className="inline-flex min-h-11 items-center gap-1.5 text-right font-semibold underline-offset-[3px]">
                <span className="sr-only">Aula seguinte: </span>
                <span className="max-w-[40vw] truncate md:max-w-none">{seguinte.title}</span> <ArrowRight aria-hidden className="size-5" />
              </Link>
            ) : (
              <Link href={`/user/courses/${courseId}/grades`} className="inline-flex min-h-11 items-center gap-1.5 font-semibold underline-offset-[3px]">
                Ver as notas do curso <ArrowRight aria-hidden className="size-5" />
              </Link>
            )}
          </div>
        </div>

        <aside aria-label={`Aulas de ${aqui.seccao}`} className="flex min-w-0 flex-col gap-3 rounded-pe-md border border-pe-linha p-5 lg:sticky lg:top-6 lg:max-w-[380px] lg:flex-[1_1_300px]">
          <h2 className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">{aqui.seccao}</h2>
          <ol className="m-0 flex list-none flex-col gap-1 p-0">
            {daSeccao.map((c) => {
              const actual = c.chapterId === chapterId;
              const visto = feitos.has(c.chapterId);
              return (
                <li key={c.chapterId}>
                  <Link
                    href={`/user/courses/${courseId}/chapters/${c.chapterId}`}
                    aria-current={actual ? "page" : undefined}
                    className={cnPe(
                      "flex min-h-12 items-center gap-3 rounded-pe-sm px-3 py-1 text-[15px] leading-[22px] text-pe-tinta no-underline hover:bg-pe-fundo-suave hover:text-pe-tinta",
                      actual && "bg-pe-fundo-suave font-semibold",
                      visto && !actual && "text-pe-tinta-suave"
                    )}
                  >
                    <span className="min-w-0 flex-1">
                      {c.numero}. {c.title}
                    </span>
                    <span className="shrink-0 text-[14px] font-normal leading-5">{actual ? "Aqui" : visto ? "Vista" : TIPO_PT[c.type]}</span>
                  </Link>
                </li>
              );
            })}
          </ol>
        </aside>
      </div>
    </main>
  );
}

/* ------------------------------------------------------------------ */
/* Conteúdo da aula: vídeo, leitura, questionário ou prática           */
/* ------------------------------------------------------------------ */
function Conteudo({
  cap,
  courseId,
  userId,
  feito,
  seguinte,
}: {
  cap: CapituloNoCurso & { resources_data?: unknown[] };
  courseId: string;
  userId: string;
  feito: boolean;
  seguinte: CapituloNoCurso | null;
}) {
  const [marcar, { isLoading }] = useMarcarCapituloMutation();
  const [erro, setErro] = useState<string | null>(null);
  // O progresso pode chegar depois de a aula abrir: conta o que vem do servidor e o que se marcou agora.
  const [vistoAgora, setVisto] = useState(false);
  const visto = feito || vistoAgora;
  const segundos = useRef(0);
  const { data: recursos } = useRecursosQuery(cap.chapterId);
  const linhas = useMemo(() => lerTranscricao(cap.transcript), [cap.transcript]);

  const concluir = async () => {
    setErro(null);
    const r = await marcar({ userId, courseId, sectionId: cap.sectionId, chapterId: cap.chapterId, concluido: true, segundos: segundos.current });
    segundos.current = 0;
    if ("error" in r && r.error) {
      setErro(mensagemErro(r.error, "Não foi possível guardar. Tente outra vez."));
      return;
    }
    setVisto(true);
  };

  const accao =
    cap.type === "Quiz" ? null : visto ? (
      <div className="flex flex-wrap items-center gap-3">
        <Etiqueta tipo="certo">
          <Check aria-hidden className="size-4" strokeWidth={3} /> {cap.type === "Text" ? "Lida" : "Vista"}
        </Etiqueta>
        {seguinte ? (
          <Botao asChild tamanho="medio">
            <Link href={`/user/courses/${courseId}/chapters/${seguinte.chapterId}`}>Aula seguinte</Link>
          </Botao>
        ) : null}
      </div>
    ) : (
      <Botao tamanho="medio" disabled={isLoading} onClick={() => void concluir()}>
        {isLoading ? "A guardar…" : cap.type === "Text" ? "Marcar como lida" : "Marcar como vista"}
      </Botao>
    );

  return (
    <>
      {cap.type === "Video" && cap.video ? (
        <Video src={cap.video} titulo={cap.title} linhas={linhas} aoAvancar={(s) => (segundos.current += s)} aoTerminar={() => !visto && void concluir()} />
      ) : null}

      <div className="flex flex-col gap-4 md:flex-row md:flex-wrap md:items-start md:justify-between">
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="m-0 font-pe-titulo text-[24px] font-bold leading-[30px] tracking-[-0.01em] md:text-pe-titulo-m">{cap.title}</h1>
          <p className="m-0 text-pe-tinta-suave">
            {cap.seccao}, aula {cap.numeroNaSeccao} de {cap.totalNaSeccao}
          </p>
        </div>
        {accao}
      </div>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}

      {cap.type === "Quiz" && cap.content ? <p className="m-0 text-pe-corpo-l">{cap.content}</p> : null}

      {cap.type === "Quiz" ? (
        cap.quiz_data ? (
          <Questionario chapterId={cap.chapterId} courseId={courseId} quiz={cap.quiz_data} aoPassar={() => !visto && void concluir()} />
        ) : (
          <Aviso tipo="neutro">O professor ainda não pôs perguntas neste questionário.</Aviso>
        )
      ) : null}

      {cap.content && cap.type !== "Quiz" ? <TextoRico texto={cap.content} /> : null}

      {cap.type === "Exercise" && cap.practice_lesson ? (
        <div className="flex flex-col items-start gap-3 rounded-pe-fala bg-pe-azul-marca p-6 text-pe-sobre-marca pe-sobre-marca">
          <span className="font-pe-titulo text-[20px] font-bold leading-[26px]">Praticar no laboratório</span>
          <span className="text-[15px] leading-[22px]">Esta aula é uma lição de prática: responde, ganha pontos e volta aqui quando terminar.</span>
          <Botao asChild tipo="realce" tamanho="medio">
            <Link href={`/user/laboratory/learn/lesson/${cap.practice_lesson}`}>
              <Dumbbell aria-hidden /> Começar a prática
            </Link>
          </Botao>
        </div>
      ) : null}

      {recursos?.length ? (
        <section aria-labelledby="titulo-recursos" className="flex flex-col gap-2">
          <h2 id="titulo-recursos" className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">
            Materiais da aula
          </h2>
          <ul className="m-0 flex list-none flex-col p-0">
            {recursos.map((r) => {
              const url = r.file_url || r.external_url;
              const pdf = r.resource_type === "PDF";
              return (
                <li key={r.id} className="border-b border-pe-fundo-forte">
                  <a href={url ?? "#"} target="_blank" rel="noopener noreferrer" className="flex min-h-14 items-center gap-3 py-2 text-pe-tinta no-underline hover:bg-pe-fundo-suave hover:text-pe-tinta">
                    <span aria-hidden className="flex size-9 shrink-0 items-center justify-center rounded-[12px_12px_12px_0] bg-pe-fundo-forte">
                      {pdf ? <FileText className="size-5" /> : <ExternalLink className="size-5" />}
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="font-semibold leading-[22px]">{r.title}</span>
                      {r.description ? <span className="text-pe-legenda text-pe-tinta-suave">{r.description}</span> : null}
                    </span>
                    <span className="shrink-0 text-[14px] text-pe-azul-vivo">{pdf ? "Abrir PDF" : "Abrir"}</span>
                    <span className="sr-only">(abre noutro separador)</span>
                  </a>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Vídeo com transcrição sincronizada                                   */
/* ------------------------------------------------------------------ */
function Video({ src, titulo, linhas, aoAvancar, aoTerminar }: { src: string; titulo: string; linhas: Linha[]; aoAvancar: (s: number) => void; aoTerminar: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const ultimo = useRef(0);
  const [tempo, setTempo] = useState(0);
  const actual = linhas.findIndex((l) => tempo >= l.start && tempo < l.end);

  useEffect(() => {
    const v = video.current;
    if (!v) return;
    const aoTempo = () => {
      const t = v.currentTime;
      const delta = t - ultimo.current;
      // Só conta o tempo visto a reproduzir (saltos para a frente não contam).
      if (!v.paused && delta > 0 && delta < 2) aoAvancar(delta);
      ultimo.current = t;
      setTempo(t);
    };
    v.addEventListener("timeupdate", aoTempo);
    v.addEventListener("ended", aoTerminar);
    return () => {
      v.removeEventListener("timeupdate", aoTempo);
      v.removeEventListener("ended", aoTerminar);
    };
  }, [aoAvancar, aoTerminar]);

  return (
    <div className="flex flex-col gap-3">
      <video ref={video} src={src} controls preload="metadata" playsInline aria-label={`Vídeo: ${titulo}`} className="aspect-video w-full rounded-pe-md bg-pe-azul-marca" />
      {linhas.length ? (
        <details className="group rounded-pe-md bg-pe-fundo-suave" open>
          <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 font-semibold">
            Transcrição em inglês
            <span className="text-[14px] font-normal text-pe-tinta-suave group-open:hidden">Mostrar</span>
            <span className="hidden text-[14px] font-normal text-pe-tinta-suave group-open:inline">Esconder</span>
          </summary>
          <ol className="m-0 flex max-h-[280px] list-none flex-col gap-1 overflow-y-auto p-0 px-2 pb-3">
            {linhas.map((l, n) => (
              <li key={`${l.start}-${n}`}>
                <button
                  type="button"
                  onClick={() => {
                    if (video.current) {
                      video.current.currentTime = l.start;
                      void video.current.play();
                    }
                  }}
                  aria-current={n === actual ? "true" : undefined}
                  className={cnPe(
                    "flex w-full gap-3 rounded-pe-sm px-2 py-1.5 text-left font-pe-titulo text-[18px] font-light leading-7",
                    n === actual ? "bg-pe-azul-marca text-pe-sobre-marca" : "text-pe-tinta hover:bg-pe-fundo-forte"
                  )}
                >
                  <span className={cnPe("w-11 shrink-0 pt-0.5 font-pe-texto text-[14px] font-normal tabular-nums", n === actual ? "text-pe-sobre-marca" : "text-pe-tinta-suave")}>
                    {Math.floor(l.start / 60)}:{String(Math.floor(l.start % 60)).padStart(2, "0")}
                  </span>
                  <span>{l.text}</span>
                </button>
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </div>
  );
}

function lerTranscricao(t?: string): Linha[] {
  if (!t) return [];
  try {
    const d = JSON.parse(t);
    return Array.isArray(d) ? d.filter((l) => typeof l?.text === "string").map((l) => ({ start: Number(l.start) || 0, end: Number(l.end) || 0, text: l.text })) : [];
  } catch {
    return [];
  }
}

function Problema({ titulo, courseId, aoTentar }: { titulo: string; courseId: string; aoTentar?: () => void }) {
  return (
    <main className="mx-auto flex w-full max-w-[720px] flex-col items-start gap-4 px-5 py-10">
      <h1 className="m-0 text-pe-titulo-m">{titulo}</h1>
      <div className="flex flex-wrap gap-3">
        {aoTentar ? <Botao onClick={aoTentar}>Tentar outra vez</Botao> : null}
        <Botao asChild tipo="secundario">
          <Link href={`/user/courses/${courseId}`}>Voltar ao curso</Link>
        </Botao>
      </div>
    </main>
  );
}

function EsqueletoAula() {
  return (
    <div aria-busy="true" aria-label="A carregar a aula" className="mx-auto flex w-full max-w-[1280px] flex-col gap-5 px-5 py-6 md:px-10">
      <Osso className="h-5 w-72" />
      <div className="flex gap-8">
        <div className="flex flex-1 flex-col gap-4">
          <Osso className="aspect-video rounded-pe-md" />
          <Osso className="h-8 w-2/3" />
        </div>
        <Osso className="hidden h-[360px] w-[320px] rounded-pe-md lg:block" />
      </div>
    </div>
  );
}
