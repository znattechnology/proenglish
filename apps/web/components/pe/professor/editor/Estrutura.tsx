"use client";

import { useState } from "react";
import { ArrowDown, ArrowUp, Pencil, Plus, Trash2, TriangleAlert } from "lucide-react";
import { Aviso, Botao } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { cnPe } from "@/lib/pe";
import { minSeg } from "@/src/domains/teacher/professor/envio";
import { useApagarSeccaoMutation, useMudarSeccaoMutation, useOrdenarSeccoesMutation, type Seccao } from "@/src/domains/teacher/professor/api";
import { erroProfessor } from "@/src/domains/teacher/professor/api";

const botaoIcone = "flex size-9 shrink-0 items-center justify-center rounded-pe-sm text-pe-tinta-suave hover:bg-pe-fundo-forte hover:text-pe-tinta disabled:opacity-40 disabled:hover:bg-transparent";

/** Coluna "Estrutura": secções com as suas aulas. Escolher uma aula abre-a ao lado. */
export function Estrutura({
  curso,
  seccoes,
  aulaActiva,
  aoEscolher,
  aoNovaAula,
  aoNovaSeccao,
  aoGuardar,
  aoErro,
  aCriar,
}: {
  aoErro: (m: string) => void;
  curso: string;
  seccoes: Seccao[];
  aulaActiva: string | null;
  aoEscolher: (id: string) => void;
  aoNovaAula: () => void;
  aoNovaSeccao: () => void;
  aoGuardar: () => void;
  aCriar: boolean;
}) {
  const [ordenar] = useOrdenarSeccoesMutation();
  const mover = async (i: number, d: -1 | 1) => {
    const ids = seccoes.map((s) => s.id);
    [ids[i], ids[i + d]] = [ids[i + d], ids[i]];
    try {
      await ordenar({ curso, ids }).unwrap();
      aoGuardar();
    } catch (e) {
      aoErro(erroProfessor(e, "Não foi possível mudar a ordem das secções."));
    }
  };

  return (
    <aside aria-labelledby="t-estrutura" className="flex w-full shrink-0 flex-col gap-2 rounded-pe-md border border-pe-linha p-4 lg:sticky lg:top-6 lg:w-[340px]">
      <h2 id="t-estrutura" className="m-0 font-pe-titulo text-[16px] font-semibold leading-6">
        Estrutura
      </h2>
      {seccoes.length ? null : <p className="m-0 text-[15px] text-pe-tinta-suave">Ainda não há secções. Crie a primeira para acrescentar aulas.</p>}
      {seccoes.map((s, i) => (
        <BlocoSeccao
          key={s.id}
          s={s}
          n={i + 1}
          aulaActiva={aulaActiva}
          aoEscolher={aoEscolher}
          aoSubir={i > 0 ? () => mover(i, -1) : undefined}
          aoDescer={i < seccoes.length - 1 ? () => mover(i, 1) : undefined}
          aoGuardar={aoGuardar}
          aoErro={aoErro}
        />
      ))}
      <div className="mt-2 flex flex-wrap gap-2">
        {seccoes.length ? (
          <Botao tipo="secundario" tamanho="pequeno" onClick={aoNovaAula} disabled={aCriar}>
            <Plus aria-hidden className="size-[18px]" />
            Nova aula
          </Botao>
        ) : null}
        <Botao tipo={seccoes.length ? "ligacao" : "secundario"} tamanho="pequeno" onClick={aoNovaSeccao} disabled={aCriar}>
          <Plus aria-hidden className="size-[18px]" />
          Nova secção
        </Botao>
      </div>
    </aside>
  );
}

function BlocoSeccao({
  s,
  n,
  aulaActiva,
  aoEscolher,
  aoSubir,
  aoDescer,
  aoGuardar,
  aoErro,
}: {
  aoErro: (m: string) => void;
  s: Seccao;
  n: number;
  aulaActiva: string | null;
  aoEscolher: (id: string) => void;
  aoSubir?: () => void;
  aoDescer?: () => void;
  aoGuardar: () => void;
}) {
  const [aEditar, setAEditar] = useState(false);
  const [titulo, setTitulo] = useState(s.titulo);
  const [apagar, setApagar] = useState(false);
  const [erroApagar, setErroApagar] = useState<string | null>(null);
  const [mudar] = useMudarSeccaoMutation();
  const [remover, { isLoading: aRemover }] = useApagarSeccaoMutation();

  const guardarTitulo = async () => {
    setAEditar(false);
    const t = titulo.trim();
    if (!t || t === s.titulo) return setTitulo(s.titulo);
    try {
      await mudar({ id: s.id, titulo: t }).unwrap();
      aoGuardar();
    } catch (e) {
      setTitulo(s.titulo);
      aoErro(erroProfessor(e, "Não foi possível mudar o nome da secção."));
    }
  };

  return (
    <section aria-label={`Secção ${n}: ${s.titulo}`} className="flex flex-col gap-1 border-t border-pe-fundo-forte pt-2 first-of-type:border-t-0 first-of-type:pt-0">
      <div className="flex items-center gap-1 py-1">
        {aEditar ? (
          <input
            autoFocus
            value={titulo}
            maxLength={80}
            aria-label={`Nome da secção ${n}`}
            onChange={(e) => setTitulo(e.target.value)}
            onBlur={guardarTitulo}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
              if (e.key === "Escape") {
                setTitulo(s.titulo);
                setAEditar(false);
              }
            }}
            className="h-10 min-w-0 flex-1 rounded-pe-sm border-[1.5px] border-pe-linha-forte px-2 font-pe-texto text-[15px] font-semibold"
          />
        ) : (
          <span className="min-w-0 flex-1 font-semibold leading-[22px]">
            Secção {n}: {s.titulo}
          </span>
        )}
        <span className="shrink-0 px-1 text-[13px] text-pe-tinta-suave">{s.aulas.length === 1 ? "1 aula" : `${s.aulas.length} aulas`}</span>
      </div>
      <div className="-mt-1 flex gap-0.5">
        <button type="button" className={botaoIcone} onClick={() => setAEditar(true)} aria-label={`Mudar o nome da secção ${n}`}>
          <Pencil aria-hidden className="size-4" />
        </button>
        <button type="button" className={botaoIcone} onClick={aoSubir} disabled={!aoSubir} aria-label={`Subir a secção ${n}`}>
          <ArrowUp aria-hidden className="size-4" />
        </button>
        <button type="button" className={botaoIcone} onClick={aoDescer} disabled={!aoDescer} aria-label={`Descer a secção ${n}`}>
          <ArrowDown aria-hidden className="size-4" />
        </button>
        <button type="button" className={botaoIcone} onClick={() => setApagar(true)} aria-label={`Apagar a secção ${n}`}>
          <Trash2 aria-hidden className="size-4" />
        </button>
      </div>
      {s.aulas.length ? (
        <ol className="m-0 flex list-none flex-col gap-0.5 p-0 pl-2">
          {s.aulas.map((a) => {
            const act = a.id === aulaActiva;
            return (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => aoEscolher(a.id)}
                  aria-current={act ? "true" : undefined}
                  className={cnPe(
                    "flex min-h-11 w-full items-center gap-2.5 rounded-pe-sm px-2.5 py-2 text-left text-[15px] leading-5",
                    act ? "bg-pe-azul-marca text-pe-sobre-marca" : "text-pe-tinta hover:bg-pe-fundo-suave"
                  )}
                >
                  <span className="min-w-0 flex-1">{a.titulo}</span>
                  {a.video || (a.tipo && a.tipo !== "Video") ? (
                    <span className={cnPe("shrink-0 text-[13px] tabular-nums", act ? "text-pe-sobre-marca" : "text-pe-tinta-suave")}>
                      {a.video ? (minSeg(a.duracao_s) ?? "") : a.tipo === "Quiz" ? "questionário" : "texto"}
                    </span>
                  ) : (
                    <span className={cnPe("flex shrink-0 items-center gap-1 text-[13px] font-semibold", act ? "text-pe-realce" : "text-pe-errado")}>
                      <TriangleAlert aria-hidden className="size-3.5" />
                      sem vídeo<span className="sr-only">, os alunos ainda não a vêem</span>
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="m-0 pl-2 text-[14px] text-pe-tinta-suave">Sem aulas.</p>
      )}

      <Dialogo
        aberto={apagar}
        aoMudar={setApagar}
        titulo={`Apagar "${s.titulo}"?`}
        descricao={
          s.aulas.length
            ? `A secção tem ${s.aulas.length === 1 ? "1 aula" : `${s.aulas.length} aulas`}, com os vídeos, materiais e questionários. Tudo é apagado e não pode ser recuperado.`
            : "A secção está vazia."
        }
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
                await remover(s.id).unwrap();
                setApagar(false);
                aoGuardar();
              } catch (e) {
                setErroApagar(erroProfessor(e, "Não foi possível apagar a secção."));
              }
            }}
          >
            Apagar secção
          </Botao>
        </div>
      </Dialogo>
    </section>
  );
}
