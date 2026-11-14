"use client";

import { useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { Aviso, Botao, Etiqueta, Osso } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { useResponderQuizMutation, useResumoQuizQuery, type QuizData, type ResultadoQuiz } from "@/src/domains/student/curso/api";

/**
 * Questionário de um capítulo. O estudante escolhe uma opção por pergunta e envia;
 * a correcção (nota, respostas certas e explicações) vem do servidor.
 */
export function Questionario({ chapterId, courseId, quiz, aoPassar }: { chapterId: string; courseId: string; quiz: QuizData; aoPassar?: () => void }) {
  const { data: resumo, isLoading } = useResumoQuizQuery(chapterId);
  const [responder, { isLoading: aEnviar }] = useResponderQuizMutation();
  const [respostas, setRespostas] = useState<Record<string, string>>({});
  const [resultado, setResultado] = useState<ResultadoQuiz | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [inicio, setInicio] = useState(() => Date.now());

  const perguntas = quiz.questions ?? [];
  const minimo = resumo?.quiz_info?.passing_score ?? quiz.settings?.passingScore ?? 70;
  const restantes = resultado ? resultado.tentativas_restantes : resumo?.attempts_remaining ?? quiz.settings?.maxAttempts ?? 1;
  const faltam = perguntas.filter((q) => !respostas[q.id]).length;

  if (isLoading) return <Osso className="h-[320px] rounded-pe-md" />;
  if (!perguntas.length) return <Aviso tipo="neutro">Este questionário ainda não tem perguntas.</Aviso>;

  const enviar = async () => {
    setErro(null);
    const r = await responder({ chapterId, courseId, respostas, segundos: (Date.now() - inicio) / 1000 });
    if ("error" in r && r.error) {
      setErro(mensagemErro(r.error, "Não foi possível enviar as respostas. Tente outra vez."));
      return;
    }
    setResultado(r.data!);
    if (r.data!.is_passed) aoPassar?.();
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const recomecar = () => {
    setResultado(null);
    setRespostas({});
    setInicio(Date.now());
  };

  const porPergunta = new Map(resultado?.correccao.map((c) => [c.pergunta, c]));

  return (
    <div className="flex flex-col gap-6">
      {resultado ? (
        <div
          role="status"
          className={cnPe("flex flex-col gap-2 rounded-pe-md p-5", resultado.is_passed ? "bg-pe-certo-suave" : "bg-pe-errado-suave")}
        >
          <div className="flex flex-wrap items-baseline gap-x-3">
            <span className="font-pe-titulo text-[32px] font-bold leading-[38px] tabular-nums">{Math.round(resultado.score_percentage)}%</span>
            <span className={cnPe("font-pe-titulo text-[19px] font-semibold", resultado.is_passed ? "text-pe-certo" : "text-pe-errado")}>
              {resultado.is_passed ? "Passou" : "Ainda não passou"}
            </span>
          </div>
          <p className="m-0">
            Acertou {resultado.correccao.filter((c) => c.certa).length} de {resultado.correccao.length}. Precisa de {minimo}% para passar.
            {!resultado.is_passed ? (restantes ? ` Tem mais ${restantes} ${restantes === 1 ? "tentativa" : "tentativas"}.` : " Já não tem mais tentativas.") : ""}
            {!resultado.revela_respostas && !resultado.is_passed && restantes ? " As respostas certas aparecem quando passar ou quando acabarem as tentativas." : ""}
          </p>
        </div>
      ) : resumo && resumo.attempts_count > 0 ? (
        <Aviso tipo={resumo.is_passed ? "certo" : "neutro"}>
          {resumo.is_passed ? `Já passou neste questionário (melhor nota: ${Math.round(resumo.best_score)}%). ` : `Melhor nota até agora: ${Math.round(resumo.best_score)}%. `}
          {restantes ? `Tem ${restantes} ${restantes === 1 ? "tentativa" : "tentativas"}.` : "Já não tem mais tentativas."}
        </Aviso>
      ) : (
        <p className="m-0 text-pe-tinta-suave">
          {perguntas.length} perguntas. Precisa de {minimo}% para passar e tem {restantes} {restantes === 1 ? "tentativa" : "tentativas"}.
        </p>
      )}

      <ol className="m-0 flex list-none flex-col gap-7 p-0">
        {perguntas.map((q, i) => {
          const c = porPergunta.get(q.id);
          return (
            <li key={q.id}>
              <fieldset className="m-0 flex flex-col gap-2.5 border-0 p-0">
                <legend className="mb-2.5 flex gap-3 p-0 text-[18px] font-semibold leading-7">
                  <span aria-hidden className="pe-sobre-marca flex size-7 shrink-0 items-center justify-center rounded-[10px_10px_10px_0] bg-pe-azul-marca font-pe-titulo text-[14px] font-bold text-pe-sobre-marca">
                    {i + 1}
                  </span>
                  <span>
                    <span className="sr-only">Pergunta {i + 1}: </span>
                    {q.question}
                  </span>
                </legend>
                {q.options.map((o) => {
                  const escolhida = respostas[q.id] === o.id;
                  // Antes de passar (ou de acabarem as tentativas) só se diz se a escolha estava certa, não qual era a certa.
                  const certa = c ? (c.opcoes_certas ? c.opcoes_certas.includes(o.id) : escolhida && c.certa) : false;
                  return (
                    <label
                      key={o.id}
                      className={cnPe(
                        "flex min-h-[52px] cursor-pointer items-center gap-3 rounded-pe-sm border-[1.5px] px-4 py-2.5",
                        c
                          ? certa
                            ? "border-pe-certo bg-pe-certo-suave"
                            : escolhida
                              ? "border-pe-errado bg-pe-errado-suave"
                              : "border-pe-linha text-pe-tinta-suave"
                          : escolhida
                            ? "border-pe-azul-marca bg-pe-fundo-suave font-semibold"
                            : "border-pe-linha-forte hover:bg-pe-fundo-suave",
                        c && "cursor-default"
                      )}
                    >
                      <input
                        type="radio"
                        name={`pergunta-${q.id}`}
                        value={o.id}
                        checked={escolhida}
                        disabled={!!resultado}
                        onChange={() => setRespostas((r) => ({ ...r, [q.id]: o.id }))}
                        className="size-5 shrink-0 accent-pe-azul-marca"
                      />
                      <span className="flex-1">{o.text}</span>
                      {c && certa ? <CheckCircle2 aria-label="Resposta certa" className="size-5 shrink-0 text-pe-certo" /> : null}
                      {c && escolhida && !certa ? <XCircle aria-label="A sua resposta" className="size-5 shrink-0 text-pe-errado" /> : null}
                    </label>
                  );
                })}
                {c ? (
                  <p className={cnPe("m-0 mt-1 flex flex-col gap-0.5 text-[15px] leading-[22px]")}>
                    <Etiqueta tipo={c.certa ? "certo" : "errado"}>{c.certa ? "Certo" : c.respondida ? "Errado" : "Sem resposta"}</Etiqueta>
                    {c.explicacao ? <span className="mt-1">{c.explicacao}</span> : null}
                  </p>
                ) : null}
              </fieldset>
            </li>
          );
        })}
      </ol>

      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}

      {resultado ? (
        !resultado.is_passed && restantes > 0 ? (
          <Botao tipo="secundario" className="self-start" onClick={recomecar}>
            Tentar outra vez
          </Botao>
        ) : null
      ) : restantes > 0 ? (
        <div className="flex flex-wrap items-center gap-4">
          <Botao disabled={aEnviar || faltam > 0} onClick={() => void enviar()}>
            {aEnviar ? "A corrigir…" : "Enviar respostas"}
          </Botao>
          {faltam ? (
            <span className="text-pe-legenda text-pe-tinta-suave">
              Falta{faltam === 1 ? "" : "m"} {faltam} {faltam === 1 ? "pergunta" : "perguntas"}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
