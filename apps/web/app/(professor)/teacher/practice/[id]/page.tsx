"use client";

import { erroProfessor } from "@/src/domains/teacher/professor/api";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowDown, ArrowUp, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { Aviso, Botao, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaCurso } from "@/components/pe/professor/editor/CabecaCurso";
import { cnPe } from "@/lib/pe";
import {
  useApagarUnidadeMutation,
  useEstruturaPraticaQuery,
  useMudarUnidadeMutation,
  useNovaLicaoMutation,
  useNovaUnidadeMutation,
  useOrdenarLicoesMutation,
  useOrdenarUnidadesMutation,
  type UnidadePratica,
} from "@/src/domains/teacher/professor/pratica";

const botaoIcone = "flex size-9 shrink-0 items-center justify-center rounded-pe-sm text-pe-tinta-suave hover:bg-pe-fundo-forte hover:text-pe-tinta disabled:opacity-40 disabled:hover:bg-transparent";

export default function UnidadesLicoes() {
  const { id } = useParams<{ id: string }>();
  const { data, isError, error, refetch } = useEstruturaPraticaQuery(id);
  const [novaUnidade, { isLoading: aCriar }] = useNovaUnidadeMutation();
  const [ordenar] = useOrdenarUnidadesMutation();
  const [erro, setErro] = useState<string | null>(null);

  if (isError && !data)
    return (
      <Pagina>
        <Aviso tipo="errado">
          {(error as { status?: number })?.status === 404 ? (
            <>
              Este curso não existe ou não é seu. <Link href="/teacher/practice">Ver os seus cursos</Link>
            </>
          ) : (
            <>
              Não conseguimos abrir o curso.{" "}
              <button type="button" onClick={() => refetch()} className="font-semibold underline">
                Tentar outra vez
              </button>
            </>
          )}
        </Aviso>
      </Pagina>
    );
  if (!data)
    return (
      <Pagina>
        <Osso className="h-[76px] w-3/4 max-w-[560px]" />
        <Osso className="h-96 max-w-[960px] rounded-pe-md" />
      </Pagina>
    );

  const { curso, unidades } = data;
  return (
    <Pagina className="gap-6">
      <CabecaCurso curso={curso} separador="Unidades e lições">
        {unidades.length ? (
          <Botao asChild tipo="secundario" tamanho="medio">
            <Link href={`/teacher/practice/${id}/generate`}>
              <Sparkles aria-hidden className="size-[18px]" />
              Gerar lição com IA
            </Link>
          </Botao>
        ) : null}
        <Botao asChild tamanho="medio">
          <Link href={`/teacher/practice/${id}/publish`}>{curso.estado === "rascunho" || curso.estado === "arquivado" ? "Rever e enviar" : "Rever o curso"}</Link>
        </Botao>
      </CabecaCurso>

      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}

      <div className="flex max-w-[960px] flex-col gap-3">
        {unidades.length ? null : (
          <div className="flex flex-col items-start gap-2 rounded-pe-md bg-pe-fundo-suave p-6">
            <h2 className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">Comece pela primeira unidade</h2>
            <p className="m-0 text-pe-tinta-suave">Uma unidade junta lições sobre o mesmo tema, por exemplo &ldquo;Segurança no estaleiro&rdquo;. Cada lição tem pelo menos 3 exercícios curtos; 8 a 12 funcionam bem.</p>
          </div>
        )}
        {unidades.map((u, i) => (
          <BlocoUnidade
            key={u.id}
            curso={id}
            u={u}
            n={i + 1}
            aoErro={setErro}
            aoSubir={
              i > 0
                ? async () => {
                    const ids = unidades.map((x) => x.id);
                    [ids[i - 1], ids[i]] = [ids[i], ids[i - 1]];
                    await ordenar({ curso: id, ids }).unwrap().catch((e) => setErro(erroProfessor(e, "Não foi possível mudar a ordem.")));
                  }
                : undefined
            }
            aoDescer={
              i < unidades.length - 1
                ? async () => {
                    const ids = unidades.map((x) => x.id);
                    [ids[i + 1], ids[i]] = [ids[i], ids[i + 1]];
                    await ordenar({ curso: id, ids }).unwrap().catch((e) => setErro(erroProfessor(e, "Não foi possível mudar a ordem.")));
                  }
                : undefined
            }
          />
        ))}
        <Botao
          tipo="secundario"
          tamanho="medio"
          className="self-start"
          disabled={aCriar}
          onClick={async () => {
            setErro(null);
            try {
              await novaUnidade({ curso: id, titulo: `Unidade ${unidades.length + 1}` }).unwrap();
            } catch (e) {
              setErro(erroProfessor(e, "Não foi possível criar a unidade."));
            }
          }}
        >
          <Plus aria-hidden className="size-[18px]" />
          Nova unidade
        </Botao>
      </div>
    </Pagina>
  );
}

function BlocoUnidade({ curso, u, n, aoSubir, aoDescer, aoErro }: { curso: string; u: UnidadePratica; n: number; aoSubir?: () => void; aoDescer?: () => void; aoErro: (m: string) => void }) {
  const router = useRouter();
  const [aEditar, setAEditar] = useState(false);
  const [titulo, setTitulo] = useState(u.titulo);
  const [apagar, setApagar] = useState(false);
  const [erroApagar, setErroApagar] = useState<string | null>(null);
  const [mudar] = useMudarUnidadeMutation();
  const [remover, { isLoading: aRemover }] = useApagarUnidadeMutation();
  const [novaLicao, { isLoading: aCriar }] = useNovaLicaoMutation();
  const [ordenar] = useOrdenarLicoesMutation();
  const exercicios = u.licoes.reduce((s, l) => s + l.exercicios, 0);

  const moverLicao = (i: number, d: -1 | 1) => {
    const ids = u.licoes.map((l) => l.id);
    [ids[i], ids[i + d]] = [ids[i + d], ids[i]];
    ordenar({ unidade: u.id, ids })
      .unwrap()
      .catch((e) => aoErro(erroProfessor(e, "Não foi possível mudar a ordem.")));
  };

  return (
    <section aria-label={`Unidade ${n}: ${u.titulo}`} className="overflow-hidden rounded-pe-md border border-pe-linha">
      <div className="flex flex-wrap items-center gap-3 bg-pe-fundo-suave px-4 py-3">
        <span aria-hidden className="flex size-9 shrink-0 items-center justify-center rounded-pe-fala-s bg-pe-azul-marca font-pe-titulo font-bold text-pe-sobre-marca">
          {n}
        </span>
        {aEditar ? (
          <input
            autoFocus
            value={titulo}
            maxLength={80}
            aria-label={`Nome da unidade ${n}`}
            onChange={(e) => setTitulo(e.target.value)}
            onBlur={async () => {
              setAEditar(false);
              const t = titulo.trim();
              if (!t || t === u.titulo) return setTitulo(u.titulo);
              try {
                await mudar({ id: u.id, titulo: t }).unwrap();
              } catch (e) {
                setTitulo(u.titulo);
                aoErro(erroProfessor(e, "Não foi possível mudar o nome da unidade."));
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
              if (e.key === "Escape") {
                setTitulo(u.titulo);
                setAEditar(false);
              }
            }}
            className="h-10 min-w-0 flex-1 rounded-pe-sm border-[1.5px] border-pe-linha-forte px-2 font-pe-texto font-semibold"
          />
        ) : (
          <h2 className="m-0 min-w-0 flex-1 font-pe-texto text-[17px] font-semibold leading-6">{u.titulo}</h2>
        )}
        <span className="text-pe-legenda text-pe-tinta-suave">
          {u.licoes.length === 1 ? "1 lição" : `${u.licoes.length} lições`}, {exercicios} {exercicios === 1 ? "exercício" : "exercícios"}
        </span>
        <span className="flex gap-0.5">
          <button type="button" className={botaoIcone} onClick={() => setAEditar(true)} aria-label={`Mudar o nome da unidade ${n}`}>
            <Pencil aria-hidden className="size-4" />
          </button>
          <button type="button" className={botaoIcone} onClick={aoSubir} disabled={!aoSubir} aria-label={`Subir a unidade ${n}`}>
            <ArrowUp aria-hidden className="size-4" />
          </button>
          <button type="button" className={botaoIcone} onClick={aoDescer} disabled={!aoDescer} aria-label={`Descer a unidade ${n}`}>
            <ArrowDown aria-hidden className="size-4" />
          </button>
          <button type="button" className={botaoIcone} onClick={() => setApagar(true)} aria-label={`Apagar a unidade ${n}`}>
            <Trash2 aria-hidden className="size-4" />
          </button>
        </span>
      </div>

      {u.licoes.length ? (
        <ol className="m-0 flex list-none flex-col p-0">
          {u.licoes.map((l, i) => (
            <li key={l.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-pe-fundo-forte px-4 py-3 md:grid md:grid-cols-[minmax(0,1fr)_170px_110px_100px_auto]">
              <span className="min-w-0 basis-full font-semibold md:basis-auto">
                {i + 1}. {l.titulo}
              </span>
              <span className="text-pe-legenda text-pe-tinta-suave">{l.tipos.join(", ") || "Sem exercícios"}</span>
              <span className={cnPe("text-pe-legenda tabular-nums", l.exercicios < 3 && "font-semibold text-pe-errado")}>
                {l.exercicios} {l.exercicios === 1 ? "exercício" : "exercícios"}
              </span>
              <span className="text-pe-legenda tabular-nums">{l.acerto == null ? "Sem respostas" : `Acerto ${l.acerto}%`}</span>
              <span className="ml-auto flex items-center gap-0.5">
                <button type="button" className={botaoIcone} onClick={() => moverLicao(i, -1)} disabled={i === 0} aria-label={`Subir a lição ${l.titulo}`}>
                  <ArrowUp aria-hidden className="size-4" />
                </button>
                <button type="button" className={botaoIcone} onClick={() => moverLicao(i, 1)} disabled={i === u.licoes.length - 1} aria-label={`Descer a lição ${l.titulo}`}>
                  <ArrowDown aria-hidden className="size-4" />
                </button>
                <Link href={`/teacher/practice/${curso}/lessons/${l.id}`} className="ml-2 inline-flex min-h-11 items-center font-semibold text-pe-azul-vivo underline-offset-[3px]">
                  Editar<span className="sr-only">: {l.titulo}</span>
                </Link>
              </span>
            </li>
          ))}
        </ol>
      ) : null}
      <div className="flex flex-wrap gap-2 border-t border-pe-fundo-forte px-4 py-3">
        <Botao
          tipo="ligacao"
          tamanho="pequeno"
          disabled={aCriar}
          onClick={async () => {
            try {
              const l = await novaLicao({ unidade: u.id, titulo: "Nova lição" }).unwrap();
              router.push(`/teacher/practice/${curso}/lessons/${l.id}`);
            } catch (e) {
              aoErro(erroProfessor(e, "Não foi possível criar a lição."));
            }
          }}
        >
          <Plus aria-hidden className="size-4" />
          Nova lição na unidade {n}
        </Botao>
        <Botao asChild tipo="ligacao" tamanho="pequeno">
          <Link href={`/teacher/practice/${curso}/generate?unidade=${u.id}`}>
            <Sparkles aria-hidden className="size-4" />
            Gerar com IA
          </Link>
        </Botao>
      </div>

      <Dialogo
        aberto={apagar}
        aoMudar={setApagar}
        titulo={`Apagar "${u.titulo}"?`}
        descricao={u.licoes.length ? `A unidade tem ${u.licoes.length === 1 ? "1 lição" : `${u.licoes.length} lições`} com ${exercicios} exercícios. Tudo é apagado, incluindo o progresso dos alunos.` : "A unidade está vazia."}
      >
        {erroApagar ? <Aviso tipo="errado">{erroApagar}</Aviso> : null}
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={() => setApagar(false)}>
            Cancelar
          </Botao>
          <Botao
            tipo="perigo"
            tamanho="medio"
            disabled={aRemover}
            onClick={async () => {
              setErroApagar(null);
              try {
                await remover(u.id).unwrap();
                setApagar(false);
              } catch (e) {
                setErroApagar(erroProfessor(e, "Não foi possível apagar a unidade."));
              }
            }}
          >
            Apagar unidade
          </Botao>
        </div>
      </Dialogo>
    </section>
  );
}
