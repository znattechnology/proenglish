"use client";

import { useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { Aviso, Botao, Escolha, Interruptor, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { cnPe } from "@/lib/pe";
import { useGuardarQuestionarioMutation, useQuestionarioQuery, type Pergunta, type Questionario } from "@/src/domains/teacher/professor/api";
import { erroProfessor } from "@/src/domains/teacher/professor/api";

const nova = (): Pergunta => ({ enunciado: "", opcoes: ["", "", ""], correcta: 0, explicacao: "" });

/** Perguntas de escolha múltipla da aula. Guarda tudo de uma vez. */
export function EditorQuestionario({ aula, titulo, aoFechar, aoGuardar }: { aula: string; titulo: string; aoFechar: () => void; aoGuardar: () => void }) {
  const { data, isError } = useQuestionarioQuery(aula, { refetchOnMountOrArgChange: true });
  return (
    <Dialogo aberto aoMudar={(v) => !v && aoFechar()} titulo="Questionário da aula" descricao={titulo} largura={720}>
      {isError ? (
        <Aviso tipo="errado">Não conseguimos carregar as perguntas.</Aviso>
      ) : !data ? (
        <Osso className="h-64 rounded-pe-md" />
      ) : (
        <Formulario aula={aula} inicial={data} aoFechar={aoFechar} aoGuardar={aoGuardar} />
      )}
    </Dialogo>
  );
}

function Formulario({ aula, inicial, aoFechar, aoGuardar }: { aula: string; inicial: Questionario; aoFechar: () => void; aoGuardar: () => void }) {
  const [guardar, { isLoading }] = useGuardarQuestionarioMutation();
  const [activo, setActivo] = useState(inicial.activo || !inicial.perguntas.length);
  const [nota, setNota] = useState(inicial.nota_minima || 70);
  const [perguntas, setPerguntas] = useState<Pergunta[] | null>(inicial.perguntas.length ? inicial.perguntas : [nova(), nova(), nova()]);
  const [erro, setErro] = useState<string | null>(null);

  const mudar = (i: number, p: Partial<Pergunta>) => setPerguntas((v) => v!.map((x, j) => (j === i ? { ...x, ...p } : x)));

  async function aoGuardarTudo() {
    setErro(null);
    const lista = perguntas!
      .map((p) => ({ ...p, enunciado: p.enunciado.trim(), explicacao: p.explicacao.trim(), opcoes: p.opcoes.map((o) => o.trim()) }))
      .filter((p) => p.enunciado || p.opcoes.some(Boolean));
    for (const [k, p] of lista.entries()) {
      if (!p.enunciado) return setErro(`A pergunta ${k + 1} não tem enunciado.`);
      const cheias = p.opcoes.filter(Boolean);
      if (cheias.length < 2) return setErro(`A pergunta ${k + 1} precisa de pelo menos 2 respostas.`);
      if (!p.opcoes[p.correcta]) return setErro(`Na pergunta ${k + 1}, a resposta certa está em branco.`);
    }
    if (activo && lista.length < 3) return setErro("Um questionário activo precisa de pelo menos 3 perguntas.");
    // Tira as respostas em branco e acerta o índice da certa.
    const limpas = lista.map((p) => {
      const certa = p.opcoes[p.correcta];
      const opcoes = p.opcoes.filter(Boolean);
      return { ...p, opcoes, correcta: opcoes.indexOf(certa) };
    });
    try {
      await guardar({ aula, activo, nota_minima: nota, perguntas: limpas }).unwrap();
      aoGuardar();
      aoFechar();
    } catch (e) {
      setErro(erroProfessor(e, "Não foi possível guardar as perguntas. Tente outra vez."));
    }
  }

  return (
    <>
      <div className="-mx-1 flex max-h-[min(60vh,640px)] flex-col gap-5 overflow-y-auto px-1 pb-1">
        {!perguntas ? null : (
          <>
            <Interruptor rotulo="Os alunos fazem este questionário" descricao="Aparece no fim da aula. Precisa de pelo menos 3 perguntas." ligado={activo} aoMudar={setActivo} />
            <Escolha rotulo="Nota para passar" className="max-w-[240px]" value={nota} onChange={(e) => setNota(Number(e.target.value))}>
              {[50, 60, 70, 80, 90, 100].map((n) => (
                <option key={n} value={n}>
                  {n}% ou mais
                </option>
              ))}
            </Escolha>
            <ol className="m-0 flex list-none flex-col gap-4 p-0">
              {perguntas.map((p, i) => (
                <li key={i} className="flex flex-col gap-3 rounded-pe-md border border-pe-linha p-4">
                  <div className="flex items-start gap-2">
                    <label className="flex flex-1 flex-col gap-1.5">
                      <span className="text-pe-rotulo">Pergunta {i + 1}</span>
                      <input
                        value={p.enunciado}
                        maxLength={300}
                        onChange={(e) => mudar(i, { enunciado: e.target.value })}
                        placeholder={i === 0 ? "Could you send me the report ___ Friday?" : ""}
                        className="h-12 w-full rounded-pe-sm border-[1.5px] border-pe-linha-forte px-3 font-pe-texto text-[16px]"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => setPerguntas((v) => v!.filter((_, j) => j !== i))}
                      aria-label={`Apagar a pergunta ${i + 1}`}
                      className="mt-7 flex size-11 shrink-0 items-center justify-center rounded-pe-sm text-pe-tinta-suave hover:bg-pe-fundo-suave hover:text-pe-errado"
                    >
                      <Trash2 aria-hidden className="size-[18px]" />
                    </button>
                  </div>
                  <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
                    <legend className="mb-1 p-0 text-[15px] text-pe-tinta-suave">Respostas: marque a certa</legend>
                    {p.opcoes.map((o, k) => (
                      <div key={k} className={cnPe("flex items-center gap-2 rounded-pe-sm px-2", p.correcta === k && "bg-pe-certo-suave")}>
                        <input
                          type="radio"
                          name={`certa-${i}`}
                          checked={p.correcta === k}
                          onChange={() => mudar(i, { correcta: k })}
                          aria-label={`Resposta ${k + 1} é a certa`}
                          className="size-5 shrink-0 accent-pe-certo"
                        />
                        <input
                          value={o}
                          maxLength={160}
                          aria-label={`Resposta ${k + 1} da pergunta ${i + 1}`}
                          onChange={(e) => mudar(i, { opcoes: p.opcoes.map((x, j) => (j === k ? e.target.value : x)) })}
                          className="h-11 min-w-0 flex-1 rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo px-3 font-pe-texto text-[16px]"
                        />
                        {p.opcoes.length > 2 ? (
                          <button
                            type="button"
                            aria-label={`Tirar a resposta ${k + 1}`}
                            onClick={() =>
                              mudar(i, {
                                opcoes: p.opcoes.filter((_, j) => j !== k),
                                correcta: p.correcta === k ? 0 : p.correcta > k ? p.correcta - 1 : p.correcta,
                              })
                            }
                            className="flex size-10 shrink-0 items-center justify-center rounded-pe-sm text-pe-tinta-suave hover:text-pe-tinta"
                          >
                            <X aria-hidden className="size-4" />
                          </button>
                        ) : null}
                      </div>
                    ))}
                    {p.opcoes.length < 5 ? (
                      <Botao tipo="ligacao" tamanho="pequeno" className="self-start" onClick={() => mudar(i, { opcoes: [...p.opcoes, ""] })}>
                        <Plus aria-hidden className="size-4" />
                        Acrescentar resposta
                      </Botao>
                    ) : null}
                  </fieldset>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-[15px] text-pe-tinta-suave">Explicação depois de responder (opcional)</span>
                    <input
                      value={p.explicacao}
                      maxLength={300}
                      onChange={(e) => mudar(i, { explicacao: e.target.value })}
                      className="h-11 w-full rounded-pe-sm border-[1.5px] border-pe-linha-forte px-3 font-pe-texto text-[16px]"
                    />
                  </label>
                </li>
              ))}
            </ol>
            <Botao tipo="secundario" tamanho="pequeno" className="self-start" onClick={() => setPerguntas((v) => [...v!, nova()])}>
              <Plus aria-hidden className="size-[18px]" />
              Nova pergunta
            </Botao>
          </>
        )}
      </div>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="flex flex-wrap justify-end gap-3">
        <Botao tipo="secundario" tamanho="medio" onClick={aoFechar}>
          Cancelar
        </Botao>
        <Botao tamanho="medio" onClick={aoGuardarTudo} disabled={isLoading || !perguntas}>
          {isLoading ? "A guardar…" : "Guardar perguntas"}
        </Botao>
      </div>
    </>
  );
}
