"use client";

import { useState } from "react";
import { Aviso, Botao, Etiqueta, Osso } from "@/components/pe";
import { NotasDoExame } from "@/components/pe/curso/Exame";
import { dataCurta } from "@/src/domains/shared/exameOral";
import { MinutosPorDia } from "@/components/pe/estatisticas/MinutosPorDia";
import { useFalaAlunoQuery, useProcurarGravacaoExameMutation, useReverExameMutation, type ExameDoAluno, type FalaDoAluno as DadosFala } from "@/src/domains/teacher/professor/alunos";

const COMPETENCIAS = [
  ["falar", "Falar"],
  ["ouvir", "Perceber"],
  ["vocabulario", "Vocabulário"],
  ["gramatica", "Gramática"],
] as const;

/** Ficha do aluno (professor): perfil de fala e exames orais nos cursos do professor. */
export function FalaDoAluno({ alunoId }: { alunoId: string }) {
  const { data, isLoading, isError } = useFalaAlunoQuery(alunoId);
  if (isLoading) return <Osso className="h-[220px] rounded-pe-md" />;
  if (isError || !data) return null;
  const p = data.perfil;
  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <section aria-labelledby="t-fala" className="flex flex-col gap-3">
        <h2 id="t-fala" className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">
          Perfil de fala
        </h2>
        <ul aria-label="Nível por competência" className="m-0 grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-4 xl:grid-cols-2">
          {COMPETENCIAS.map(([chave, nome]) => (
            <li key={chave} className="flex flex-col rounded-pe-md bg-pe-fundo-suave px-4 py-3">
              <span className="text-pe-legenda text-pe-tinta-suave">{nome}</span>
              <span className="font-pe-titulo text-[24px] font-bold">{p.niveis[chave] ?? "—"}</span>
            </li>
          ))}
        </ul>
        <p className="m-0 text-[15px] leading-[22px]">
          Disse sozinho {p.frases_sozinho} {p.frases_sozinho === 1 ? "frase" : "frases"} numa conversa ({p.frases_sozinho_cursos} dos seus cursos). {p.conversas_avaliadas} {p.conversas_avaliadas === 1 ? "conversa avaliada" : "conversas avaliadas"}.
        </p>
        <h3 className="m-0 mt-2 text-[17px] font-semibold leading-6">Erros que ainda repete</h3>
        {p.padroes.length ? (
          <ul className="m-0 flex list-none flex-col p-0">
            {p.padroes.map((x) => (
              <li key={x.chave} className="flex flex-col border-b border-pe-fundo-forte py-2.5">
                <span className="flex justify-between gap-3">
                  <span className="font-semibold">{x.descricao}</span>
                  <span className="shrink-0 tabular-nums text-pe-tinta-suave">{x.ocorrencias}×</span>
                </span>
                {x.errado && x.certo ? (
                  <span lang="en" className="text-[15px] text-pe-tinta-suave">
                    <s>{x.errado}</s> {x.certo}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Sem erros repetidos em aberto.</p>
        )}
      </section>

      <section aria-labelledby="t-exames" className="flex flex-col gap-3">
        <h2 id="t-exames" className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">
          Exames orais
        </h2>
        {data.exames.length ? (
          <ul className="m-0 flex list-none flex-col gap-4 p-0">
            {data.exames.map((e) => (
              <CartaoExame key={e.id} e={e} alunoId={alunoId} />
            ))}
          </ul>
        ) : (
          <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Ainda não fez o exame oral de nenhum curso seu.</p>
        )}
      </section>

      {data.fala ? <FalaPorSemana f={data.fala} /> : null}
    </div>
  );
}

function CartaoExame({ e, alunoId }: { e: ExameDoAluno; alunoId: string }) {
  const [rever, { isLoading }] = useReverExameMutation();
  const [procurar, { isLoading: aProcurar, data: procurado }] = useProcurarGravacaoExameMutation();
  const [aRever, setARever] = useState(false);
  const [nota, setNota] = useState(String(Math.round(e.nota ?? e.nota_ia ?? 0)));
  const [comentario, setComentario] = useState(e.revisao?.comentario ?? "");
  const [erro, setErro] = useState<string | null>(null);
  const avaliado = e.estado === "avaliado";

  const enviar = async (corpo: { confirmar: true } | { nota: number; comentario: string }) => {
    setErro(null);
    try {
      await rever({ id: e.id, alunoId, ...corpo }).unwrap();
      setARever(false);
    } catch (x) {
      const d = (x as { data?: { error?: string; message?: string } }).data;
      setErro(d?.error ?? d?.message ?? "Não foi possível guardar a nota. Tente outra vez.");
    }
  };

  return (
    <li className="flex flex-col gap-3 rounded-pe-md border border-pe-linha p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <span className="flex flex-col">
          <span className="font-semibold">{e.curso.titulo}</span>
          <span className="text-pe-legenda text-pe-tinta-suave">
            {dataCurta(e.criado_em)}
            {e.nivel_cefr ? `. Nível de fala ${e.nivel_cefr}` : ""}
          </span>
        </span>
        {avaliado ? (
          <span className="flex flex-col items-end gap-1">
            <span className="font-pe-titulo text-[24px] font-bold tabular-nums">{Math.round(e.nota ?? 0)}%</span>
            <Etiqueta tipo={e.aprovado ? "certo" : "errado"}>{e.aprovado ? "Passou" : `Abaixo de ${Math.round(e.nota_minima)}%`}</Etiqueta>
          </span>
        ) : (
          <Etiqueta>{e.estado === "a_avaliar" ? "A avaliar" : "Sem nota"}</Etiqueta>
        )}
      </div>

      {avaliado ? (
        <>
          {e.revisao_recomendada ? (
            <p className="m-0 flex flex-wrap items-center gap-2 text-[15px] leading-[22px]">
              <Etiqueta tipo="realce">Por confirmar</Etiqueta>
              {e.revisao_recomendada} Ouça a gravação e confirme ou reveja a nota.
            </p>
          ) : null}
          <NotasDoExame exame={e} compacto />
          <p className="m-0 text-[15px] leading-[22px]">
            {e.revisao ? `Nota revista por si${e.revisao.por ? ` (${e.revisao.por})` : ""}; a da IA era ${Math.round(e.nota_ia ?? 0)}%.` : `Nota da IA: ${Math.round(e.nota_ia ?? 0)}%, ainda não confirmada.`} Disse sozinho {e.frases_usadas.length} de {e.frases_total} frases do curso.
          </p>
          {e.relatorio ? <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">{e.relatorio}</p> : null}
        </>
      ) : null}

      {e.gravacao_url ? (
        <audio controls preload="none" src={e.gravacao_url} className="w-full">
          O seu browser não toca áudio.
        </audio>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <p className="m-0 text-pe-legenda text-pe-tinta-suave">
            {e.consentimento_gravacao
              ? e.gravacao_apagada
                ? "A gravação foi apagada."
                : procurado && !procurado.gravacao_url
                  ? "A gravação ainda não chegou do serviço de voz. Tente daqui a alguns minutos."
                  : "A gravação ainda não está disponível."
              : "O aluno não autorizou a gravação deste exame."}
          </p>
          {e.consentimento_gravacao && !e.gravacao_apagada ? (
            <Botao tipo="ligacao" tamanho="pequeno" disabled={aProcurar} onClick={() => void procurar({ id: e.id, alunoId })}>
              {aProcurar ? "A procurar…" : "Procurar a gravação"}
            </Botao>
          ) : null}
        </div>
      )}

      {avaliado ? (
        aRever ? (
          <form
            className="flex flex-col gap-3 rounded-pe-md bg-pe-fundo-suave p-4"
            onSubmit={(x) => {
              x.preventDefault();
              const n = Number(nota.replace(",", "."));
              if (!Number.isFinite(n) || n < 0 || n > 100) return setErro("A nota tem de ser um número de 0 a 100.");
              void enviar({ nota: n, comentario });
            }}
          >
            <label className="flex flex-col gap-1.5">
              <span className="font-semibold">Nova nota (0 a 100)</span>
              <input value={nota} onChange={(x) => setNota(x.target.value)} inputMode="decimal" className="h-12 w-32 rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo px-3 text-[16px] tabular-nums" />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="font-semibold">Comentário para o aluno</span>
              <textarea value={comentario} onChange={(x) => setComentario(x.target.value)} rows={3} maxLength={1000} className="rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo px-3 py-2 text-[16px]" />
            </label>
            {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
            <div className="flex flex-wrap gap-3">
              <Botao type="submit" tamanho="medio" disabled={isLoading}>
                Guardar a nota
              </Botao>
              <Botao tipo="ligacao" tamanho="medio" onClick={() => setARever(false)}>
                Cancelar
              </Botao>
            </div>
          </form>
        ) : (
          <div className="flex flex-col gap-2">
            {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
            <div className="flex flex-wrap gap-3">
              {!e.revisao ? (
                <Botao tamanho="pequeno" disabled={isLoading} onClick={() => void enviar({ confirmar: true })}>
                  Confirmar nota
                </Botao>
              ) : null}
              <Botao tipo="secundario" tamanho="pequeno" onClick={() => setARever(true)}>
                Rever nota
              </Botao>
            </div>
          </div>
        )
      ) : null}
    </li>
  );
}

const semanaCurta = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-PT", { day: "numeric", month: "short" }).replace(".", "");

/** Quanto o aluno fala por semana, o ritmo (palavras por minuto) e as palavras que ainda não saem bem. */
function FalaPorSemana({ f }: { f: NonNullable<DadosFala["fala"]> }) {
  const total = f.semanas.reduce((a, s) => a + s.segundos, 0);
  const ppm = f.semanas.filter((s) => s.ppm !== null);
  return (
    <section aria-labelledby="t-minutos" className="flex flex-col gap-3 xl:col-span-2">
      <h2 id="t-minutos" className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">
        Quanto fala
      </h2>
      <div className="grid gap-8 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex min-w-0 flex-col gap-3">
          <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">
            {total ? `${Math.round(total / 60)} min a falar nas últimas 8 semanas (conversas e gravações). Meta do aluno: ${f.meta_min} min por dia.` : "Ainda não falou nas últimas 8 semanas."}
          </p>
          {total ? (
            <MinutosPorDia
              dias={f.semanas.map((s) => ({ data: s.inicio, minutos: Math.round(s.segundos / 60), rotulo: s.actual ? "esta" : semanaCurta(s.inicio) }))}
              meta={f.meta_min * 7}
              legendaMeta={`meta da semana: ${f.meta_min} min por dia`}
              rotuloLongo={(iso) => `Semana de ${semanaCurta(iso)}`}
              descricao="Minutos a falar por semana"
              cabecalho="Semana"
            />
          ) : null}
          {ppm.length ? (
            <p className="m-0 text-[15px] leading-[22px]">
              Palavras por minuto (mediana):{" "}
              {ppm.map((s) => `${s.actual ? "esta semana" : semanaCurta(s.inicio)} ${Math.round(s.ppm!)}`).join(", ")}.
            </p>
          ) : null}
        </div>
        <div className="flex min-w-0 flex-col gap-2">
          <h3 className="m-0 text-[17px] font-semibold leading-6">Palavras a treinar</h3>
          {f.palavras_treinar.length ? (
            <ul className="m-0 flex list-none flex-col p-0">
              {f.palavras_treinar.map((w) => (
                <li key={w.palavra} className="flex justify-between gap-3 border-b border-pe-fundo-forte py-2">
                  <span lang="en" className="font-semibold">
                    {w.palavra}
                    {w.fonema ? <span className="font-normal text-pe-tinta-suave"> /{w.fonema}/</span> : null}
                  </span>
                  <span className="shrink-0 tabular-nums text-pe-tinta-suave">
                    {w.falhas} de {w.tentativas}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Sem palavras difíceis nas gravações.</p>
          )}
        </div>
      </div>
    </section>
  );
}
