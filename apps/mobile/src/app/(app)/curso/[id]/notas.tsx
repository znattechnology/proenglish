/**
 * Notas de um curso (canvas Notas e EstadoSemNotas; web user/courses/[courseId]/grades/page.tsx):
 * a nota final no balão azul, como é calculada, os questionários e os requisitos do certificado.
 */
import { router, useLocalSearchParams } from "expo-router";
import { ListChecks } from "lucide-react-native";
import { useState } from "react";
import { View } from "react-native";
import { Anel } from "@/componentes/cursos/Pecas";
import { capitulosPorOrdem, concluidos, useCursoDetalheQuery, useNotasCursoQuery, useProgressoCursoQuery, type Notas } from "@/dominios/cursos/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { BalaoFala, BarraProgresso, Botao, Cabecalho, Ecra, EstadoErro, EstadoVazio, Osso, Texto } from "@/ui";
import { balao, cor, fonte, raio } from "@/tema";

const NOMES_REQUISITOS: Record<string, string> = {
  quiz_average: "Média dos questionários",
  all_quizzes_passed: "Passar em todos os questionários",
  practice_completion: "Prática no laboratório concluída",
  conversation_score: "Conversa com o tutor",
  oral_exam: "Passar no exame oral",
  final_grade: "Nota final",
};

export default function EcraNotasCurso() {
  const { id: courseId } = useLocalSearchParams<{ id: string }>();
  const { utilizador } = useSessao();
  const curso = useCursoDetalheQuery(courseId);
  const notas = useNotasCursoQuery(courseId);
  const progresso = useProgressoCursoQuery({ userId: utilizador?.id ?? "", courseId }, { skip: !utilizador });
  const [aActualizar, setAActualizar] = useState(false);

  const lista = curso.data ? capitulosPorOrdem(curso.data.curso) : [];
  const feitos = concluidos(progresso.data);
  const seguinte = lista.find((c) => !feitos.has(c.chapterId));

  return (
    <Ecra
      cabecalho={<Cabecalho titulo="As suas notas" subtitulo={curso.data?.curso.title} />}
      aoActualizar={async () => {
        setAActualizar(true);
        await Promise.allSettled([notas.refetch(), progresso.refetch()]);
        setAActualizar(false);
      }}
      aActualizar={aActualizar}
      style={{ gap: 20 }}
    >
      {notas.isError ? (
        <EstadoErro titulo="Não conseguimos calcular as notas deste curso" erro={notas.error} aoTentar={notas.refetch} />
      ) : !notas.data ? (
        <View accessible accessibilityLabel="A carregar" accessibilityState={{ busy: true }} style={{ gap: 16 }}>
          <Osso altura={136} style={balao.grande} />
          <Osso altura={90} />
          <Osso altura={90} />
        </View>
      ) : semNotaAinda(notas.data) ? (
        <EstadoVazio
          icone={<ListChecks size={30} color={cor.azulMarca} />}
          titulo="Ainda não há notas"
          texto="A nota aparece depois do primeiro questionário ou lição de prática."
          accao={
            seguinte ? (
              <Botao larguraTotal href={`/curso/${courseId}/aula/${seguinte.chapterId}`}>
                {`Continuar a aula ${seguinte.numero}`}
              </Botao>
            ) : (
              <Botao larguraTotal href={`/curso/${courseId}`}>
                Voltar ao curso
              </Botao>
            )
          }
          nota={`Para o certificado precisa de ${notas.data.nota_minima ?? notas.data.certificate_eligibility.nota_minima ?? 70}% ou mais na nota final.`}
        />
      ) : (
        <Conteudo notas={notas.data} courseId={courseId} />
      )}
    </Ecra>
  );
}

function semNotaAinda(n: Notas) {
  const g = n.grades;
  return (
    !g.quizzes.details.some((q) => q.attempts_used) &&
    !g.practice.completed &&
    !g.conversation.sessions &&
    !n.exame_oral?.attempts &&
    !n.frases_curso?.mastered &&
    Math.round(n.final_grade.percentage) === 0
  );
}

function Conteudo({ notas, courseId }: { notas: Notas; courseId: string }) {
  const g = notas.grades;
  const final = Math.round(notas.final_grade.percentage);
  const elegivel = notas.certificate_eligibility.is_eligible;
  const minimo = notas.nota_minima ?? notas.certificate_eligibility.nota_minima ?? 70;
  const semCertificados = notas.plano_inclui_certificados === false;
  // Sem peso, a conversa não entra na nota, mas um requisito de conversa por cumprir continua a impedir o certificado.
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
  const partes = [
    {
      chave: "exam",
      nome: "Exame oral",
      nota: exame?.score ?? 0,
      peso: w.exam_weight ?? 0,
      texto: !exame?.attempts ? "Ainda por fazer" : exame.passed ? "Aprovado" : `Ainda não aprovado (mínimo ${Math.round(exame.min_score ?? 60)}%)`,
      href: `/curso/${courseId}/exame`,
    },
    { chave: "phrases", nome: "Frases do curso ditas sozinho", nota: frases?.score ?? 0, peso: w.phrases_weight ?? 0, texto: `${frases?.mastered ?? 0} de ${frases?.total ?? 0} frases` },
    { chave: "conversation", nome: "Conversas do curso", nota: g.conversation.score, peso: w.conversation_weight, texto: `${g.conversation.sessions} conversas, ${g.conversation.minutes} min` },
    { chave: "study", nome: "Questionários e prática", nota: w.study_score ?? 0, peso: w.study_weight ?? 0, texto: estudo.join(", ") || "Sem questionários nem prática" },
  ].filter((p) => p.peso > 0);

  return (
    <>
      <BalaoFala style={{ flexDirection: "row", alignItems: "center", gap: 20, paddingVertical: 22 }}>
        <Anel valor={final} cheio={cor.realce} vazio={cor.sobreMarcaFraco} fundo={cor.azulMarca} corTexto={cor.sobreMarca} rotulo={`Nota final de ${final} por cento`} />
        <View style={{ flex: 1, gap: 2 }}>
          <Texto v="legenda" forte cor={cor.sobreMarca}>
            Nota final até agora
          </Texto>
          <Texto v="legenda" cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
            {semCertificados
              ? "O seu plano não inclui certificados. A nota fica guardada."
              : elegivel
                ? "Cumpre tudo o que o certificado pede."
                : final >= minimo
                  ? "Já tem a nota para o certificado. Falta cumprir os requisitos abaixo."
                  : `O certificado pede ${minimo}% ou mais e os requisitos abaixo.`}
          </Texto>
        </View>
      </BalaoFala>

      {partes.length ? (
        <View style={{ gap: 12 }}>
          <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
            Como a nota é calculada
          </Texto>
          {partes.map((p) => (
            <View key={p.chave} style={{ gap: 6, paddingVertical: 14, paddingHorizontal: 16, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, opacity: activos.has(p.chave) ? 1 : 0.7 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
                <Texto forte style={{ flex: 1 }}>
                  {p.nome}
                </Texto>
                <Texto numeros style={{ fontFamily: fonte.numero, fontSize: 18 }}>
                  {Math.round(p.nota)}%
                </Texto>
              </View>
              <BarraProgresso valor={p.nota} rotulo={p.nome} corBarra={p.nota >= 70 ? cor.certo : undefined} />
              <Texto v="legenda" suave>
                {p.texto}. Vale {Math.round(p.peso)}% da nota.
              </Texto>
              {"href" in p && p.href ? (
                <Botao tipo="ligacao" tamanho="pequeno" onPress={() => router.push(p.href!)}>
                  {exame?.passed ? "Ver o resultado" : "Ir para o exame"}
                </Botao>
              ) : null}
            </View>
          ))}
        </View>
      ) : null}

      <View style={{ gap: 8 }}>
        <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
          Questionários
        </Texto>
        {g.quizzes.details.length ? (
          g.quizzes.details.map((q) => (
            <View key={q.quiz_id} style={{ flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 10, borderTopWidth: 1, borderColor: cor.linha }}>
              <View style={{ flex: 1 }}>
                <Texto forte style={{ fontSize: 15, lineHeight: 22 }}>
                  {q.quiz_title}
                </Texto>
                <Texto v="legenda" suave>
                  {q.section_title}, {q.attempts_used} de {q.max_attempts} tentativas
                </Texto>
              </View>
              <View
                style={{
                  paddingHorizontal: 10,
                  paddingVertical: 2,
                  borderRadius: raio.sm,
                  backgroundColor: !q.attempts_used ? cor.fundoForte : q.is_passed ? cor.certoSuave : cor.erradoSuave,
                }}
              >
                <Texto v="legenda" forte numeros cor={!q.attempts_used ? cor.tintaSuave : q.is_passed ? cor.certo : cor.errado}>
                  {q.attempts_used ? `${Math.round(q.score)}%` : "Por fazer"}
                </Texto>
              </View>
            </View>
          ))
        ) : (
          <Texto suave>Este curso não tem questionários.</Texto>
        )}
      </View>

      <View style={{ gap: 10 }}>
        <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
          Para o certificado
        </Texto>
        {requisitos.map(([chave, r]) => (
          <View key={chave} accessible accessibilityLabel={`${NOMES_REQUISITOS[chave] ?? chave}: ${r.met ? "cumprido" : "por cumprir"}. ${r.message}`} style={{ flexDirection: "row", alignItems: "flex-start", gap: 10 }}>
            <View style={{ width: 22, height: 22, marginTop: 1, borderRadius: 11, alignItems: "center", justifyContent: "center", backgroundColor: r.met ? cor.certoSuave : cor.realceSuave }}>
              <Texto v="mini" forte cor={r.met ? cor.certo : cor.tinta} style={{ fontSize: 13 }}>
                {r.met ? "✓" : "!"}
              </Texto>
            </View>
            <Texto style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>
              <Texto forte style={{ fontSize: 15, lineHeight: 22 }}>
                {r.met ? "Feito." : "Falta."}
              </Texto>{" "}
              {NOMES_REQUISITOS[chave] ?? chave}: {r.message}
            </Texto>
          </View>
        ))}
        {elegivel ? (
          <Botao tipo="secundario" href="/certificados">
            Ver os certificados
          </Botao>
        ) : (
          <Botao tipo="secundario" href={`/curso/${courseId}`}>
            Continuar o curso
          </Botao>
        )}
      </View>
    </>
  );
}
