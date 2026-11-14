"use client";

import { useState } from "react";
import { Aviso, Botao, Etiqueta } from "@/components/pe";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { useDarTentativasMutation, useQuestionariosAlunoQuery, type QuestionarioDoAluno } from "@/src/domains/teacher/professor/questionarios";

/**
 * Ficha do aluno (professor): questionários das aulas que o aluno tentou e ainda não passou.
 * Quem gastou as tentativas conclui a aula na mesma, mas o questionário falhado pesa na nota e
 * pode impedir o certificado: aqui o professor dá-lhe mais uma tentativa.
 */
export function QuestionariosDoAluno({ alunoId }: { alunoId: string }) {
  const { data } = useQuestionariosAlunoQuery(alunoId);
  if (!data?.length) return null;
  return (
    <section aria-labelledby="t-questionarios" className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 id="t-questionarios" className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">
          Questionários por passar
        </h2>
        <p className="m-0 max-w-[68ch] text-pe-tinta-suave">
          Sem tentativas, a aula conta como concluída depois de ver o vídeo, mas a nota do questionário fica na nota do curso. Dê mais uma tentativa para o aluno a poder melhorar.
        </p>
      </div>
      <ul className="m-0 flex list-none flex-col p-0">
        {data.map((q) => (
          <Linha key={q.id} q={q} alunoId={alunoId} />
        ))}
      </ul>
    </section>
  );
}

function Linha({ q, alunoId }: { q: QuestionarioDoAluno; alunoId: string }) {
  const [dar, { isLoading }] = useDarTentativasMutation();
  const [erro, setErro] = useState<string | null>(null);
  const [feito, setFeito] = useState(false);
  const esgotado = q.restantes === 0;

  async function darUma() {
    setErro(null);
    setFeito(false);
    try {
      await dar({ alunoId, quizId: q.id, extra: 1 }).unwrap();
      setFeito(true);
    } catch (x) {
      setErro(mensagemErro(x, "Não foi possível dar a tentativa. Tente outra vez."));
    }
  }

  return (
    <li className="flex flex-col gap-2 border-b border-pe-fundo-forte py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <span className="flex min-w-0 flex-col">
          <span className="font-semibold">{q.aula.titulo}</span>
          <span className="text-pe-legenda text-pe-tinta-suave">
            {q.curso.titulo}. Melhor nota {q.melhor_nota ?? 0}% (precisa de {q.nota_minima}%), {q.tentativas} de {q.limite} tentativas.
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-3">
          {esgotado ? <Etiqueta tipo="errado">Sem tentativas</Etiqueta> : <Etiqueta tipo="neutra">{q.restantes === 1 ? "Falta 1 tentativa" : `Faltam ${q.restantes} tentativas`}</Etiqueta>}
          <Botao tamanho="pequeno" tipo="secundario" disabled={isLoading} onClick={() => void darUma()}>
            {isLoading ? "A guardar…" : "Dar mais uma tentativa"}
          </Botao>
        </span>
      </div>
      {feito ? <span role="status" className="text-pe-legenda text-pe-certo">Tentativa dada. O aluno já pode responder outra vez.</span> : null}
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
    </li>
  );
}
