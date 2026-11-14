"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Check, Minus, X } from "lucide-react";
import { BarraProgresso, Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { cnPe } from "@/lib/pe";
import { useCursoQuery, useNotasQuery, type Notas } from "@/src/domains/student/curso/api";

const NOMES_REQUISITOS: Record<string, string> = {
  quiz_average: "Média dos questionários",
  all_quizzes_passed: "Passar em todos os questionários",
  practice_completion: "Prática no laboratório concluída",
  conversation_score: "Conversa com o tutor",
  oral_exam: "Passar no exame oral",
  final_grade: "Nota final",
};

export default function PaginaNotas() {
  const { courseId } = useParams<{ courseId: string }>();
  const { data: curso } = useCursoQuery(courseId);
  const { data: notas, isLoading, isError, refetch } = useNotasQuery(courseId);

  return (
    <Pagina className="max-w-[1040px]">
      <div className="flex flex-col gap-2">
        <Link href={`/user/courses/${courseId}`} className="inline-flex min-h-11 items-center gap-1.5 self-start text-[15px] font-semibold underline-offset-[3px]">
          <ArrowLeft aria-hidden className="size-5" /> {curso?.curso.title ?? "Voltar ao curso"}
        </Link>
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">As suas notas</h1>
      </div>

      {isError ? (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
          <p className="m-0">Não conseguimos calcular as notas deste curso.</p>
          <Botao tamanho="pequeno" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : isLoading || !notas ? (
        <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-4">
          <Osso className="h-[150px] rounded-pe-fala" />
          <Osso className="h-[220px] rounded-pe-md" />
        </div>
      ) : (
        <Conteudo notas={notas} courseId={courseId} />
      )}
    </Pagina>
  );
}

function Conteudo({ notas, courseId }: { notas: Notas; courseId: string }) {
  const g = notas.grades;
  const final = Math.round(notas.final_grade.percentage);
  const elegivel = notas.certificate_eligibility.is_eligible;
  const minimo = notas.nota_minima ?? notas.certificate_eligibility.nota_minima ?? 70;
  const semCertificados = notas.plano_inclui_certificados === false;
  // Sem peso, a conversa não entra na nota, mas um requisito de conversa por cumprir continua a
  // impedir o certificado: só se esconde quando está cumprido.
  const requisitos = Object.entries(notas.certificate_eligibility.details).filter(
    ([chave, r]) => !r.info_only && !(chave === "conversation_score" && !notas.weight_info.conversation_weight && r.met)
  );
  const w = notas.weight_info;
  const activos = new Set(w.active_components);
  const exame = notas.exame_oral;
  const frases = notas.frases_curso;
  const estudo: string[] = [];
  if (g.quizzes.count) estudo.push(`${g.quizzes.passed} de ${g.quizzes.count} questionários aprovados`);
  if (g.practice.count) estudo.push(`${g.practice.completed} de ${g.practice.count} exercícios feitos`);
  // Fase 6: exame oral 40, frases do curso 25, conversas 20, estudo 15 (renormalizados quando falta algum).
  const partes = [
    {
      chave: "exam",
      nome: "Exame oral",
      nota: exame?.score ?? 0,
      peso: w.exam_weight ?? 0,
      texto: !exame?.attempts ? "Ainda por fazer" : exame.passed ? "Aprovado" : `Ainda não aprovado (mínimo ${Math.round(exame.min_score ?? 60)}%)`,
      href: `/user/courses/${courseId}/exame`,
    },
    { chave: "phrases", nome: "Frases do curso ditas sozinho", nota: frases?.score ?? 0, peso: w.phrases_weight ?? 0, texto: `${frases?.mastered ?? 0} de ${frases?.total ?? 0} frases` },
    { chave: "conversation", nome: "Conversas do curso", nota: g.conversation.score, peso: w.conversation_weight, texto: `${g.conversation.sessions} conversas, ${g.conversation.minutes} min` },
    { chave: "study", nome: "Questionários e prática", nota: w.study_score ?? 0, peso: w.study_weight ?? 0, texto: estudo.join(", ") || "Sem questionários nem prática" },
  ].filter((p) => p.peso > 0);

  return (
    <>
      <section aria-label="Nota final" className="pe-sobre-marca flex flex-col gap-2 rounded-pe-fala bg-pe-azul-marca p-6 text-pe-sobre-marca md:flex-row md:items-center md:gap-8 md:p-8">
        <span className="font-pe-titulo text-[56px] font-bold leading-[60px] tracking-[-0.02em] tabular-nums">{final}%</span>
        <span className="flex flex-col gap-1">
          <span className="font-pe-titulo text-[19px] font-semibold leading-[26px]">Nota final até agora</span>
          <span className="text-[15px] leading-[22px]">
            {semCertificados
              ? "Os certificados fazem parte do Premium e do Premium Plus. A nota fica guardada."
              : elegivel
                ? "Cumpre tudo o que o certificado pede."
                : final >= minimo
                  ? "Já tem a nota para o certificado. Falta cumprir os requisitos abaixo."
                  : `O certificado pede ${minimo}% ou mais e os requisitos abaixo.`}
          </span>
        </span>
      </section>

      <section aria-label="Como a nota é feita" className={cnPe("grid gap-3", partes.length >= 4 ? "md:grid-cols-2 xl:grid-cols-4" : partes.length === 3 ? "md:grid-cols-3" : "md:grid-cols-2")}>
        {partes.map((p) => (
          <div key={p.chave} className={cnPe("flex flex-col gap-2 rounded-pe-md border border-pe-linha p-5", !activos.has(p.chave) && "opacity-70")}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="font-semibold">{p.nome}</span>
              <span className="font-pe-titulo text-[22px] font-bold tabular-nums">{Math.round(p.nota)}%</span>
            </div>
            <BarraProgresso valor={p.nota} rotulo={p.nome} cor={p.nota >= 70 ? "certo" : undefined} />
            <span className="text-pe-legenda text-pe-tinta-suave">
              {p.texto}. Vale {Math.round(p.peso)}% da nota.
            </span>
            {"href" in p && p.href ? (
              <Link href={p.href} className="self-start text-[15px] font-semibold text-pe-azul-marca underline-offset-[3px]">
                {exame?.passed ? "Ver o resultado" : "Ir para o exame"}
              </Link>
            ) : null}
          </div>
        ))}
      </section>

      <section aria-labelledby="titulo-quizzes" className="flex flex-col gap-2">
        <h2 id="titulo-quizzes" className="m-0 font-pe-titulo text-pe-titulo-s">
          Questionários
        </h2>
        {g.quizzes.details.length ? (
          <div className="-mx-5 overflow-x-auto px-5 md:mx-0 md:px-0">
            <table className="w-full min-w-[480px] border-collapse text-left text-[15px] leading-[22px]">
              <thead>
                <tr className="text-pe-tinta-suave">
                  <th scope="col" className="py-2 pr-3 font-normal">
                    Questionário
                  </th>
                  <th scope="col" className="px-3 py-2 font-normal">
                    Tentativas
                  </th>
                  <th scope="col" className="py-2 pl-3 text-right font-normal">
                    Nota
                  </th>
                </tr>
              </thead>
              <tbody>
                {g.quizzes.details.map((q) => (
                  <tr key={q.quiz_id} className="border-t border-pe-linha">
                    <td className="py-3 pr-3">
                      <span className="flex flex-col">
                        <span className="font-semibold">{q.quiz_title}</span>
                        <span className="text-pe-legenda text-pe-tinta-suave">{q.section_title}</span>
                      </span>
                    </td>
                    <td className="px-3 py-3 tabular-nums">
                      {q.attempts_used} de {q.max_attempts}
                    </td>
                    <td className="py-3 pl-3 text-right">
                      <span
                        className={cnPe(
                          "inline-block rounded-pe-sm px-2.5 py-0.5 font-semibold tabular-nums",
                          !q.attempts_used ? "bg-pe-fundo-forte text-pe-tinta-suave" : q.is_passed ? "bg-pe-certo-suave text-pe-certo" : "bg-pe-errado-suave text-pe-errado"
                        )}
                      >
                        {q.attempts_used ? `${Math.round(q.score)}%` : "Por fazer"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="m-0 text-pe-tinta-suave">Este curso não tem questionários.</p>
        )}
      </section>

      <section aria-labelledby="titulo-certificado" className="flex flex-col gap-3">
        <h2 id="titulo-certificado" className="m-0 font-pe-titulo text-pe-titulo-s">
          Para o certificado
        </h2>
        <ul className="m-0 flex list-none flex-col p-0">
          {requisitos.map(([chave, r]) => (
            <li key={chave} className="flex items-start gap-3 border-b border-pe-fundo-forte py-3">
              <span
                aria-hidden
                className={cnPe("mt-0.5 flex size-[22px] shrink-0 items-center justify-center rounded-full", r.met ? "bg-pe-certo-suave text-pe-certo" : "bg-pe-fundo-forte text-pe-tinta-suave")}
              >
                {r.met ? <Check className="size-3.5" strokeWidth={3} /> : r.actual ? <Minus className="size-3.5" strokeWidth={3} /> : <X className="size-3.5" strokeWidth={3} />}
              </span>
              <span className="flex flex-col">
                <span className="font-semibold leading-[22px]">
                  {NOMES_REQUISITOS[chave] ?? chave}
                  <span className="sr-only">{r.met ? ": cumprido" : ": por cumprir"}</span>
                </span>
                <span className="text-pe-legenda text-pe-tinta-suave">{r.message}</span>
              </span>
            </li>
          ))}
        </ul>
        {!elegivel ? (
          <Botao asChild tipo="secundario" className="self-start">
            <Link href={`/user/courses/${courseId}`}>Continuar o curso</Link>
          </Botao>
        ) : null}
      </section>
    </>
  );
}
