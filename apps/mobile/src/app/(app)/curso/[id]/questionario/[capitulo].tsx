/**
 * Questionário de uma aula (canvas Questionario e QuestionarioResultado; web components/pe/curso/Questionario.tsx).
 * Uma pergunta de cada vez; no fim envia todas as respostas e mostra a correcção que vem do servidor.
 */
import { router, useLocalSearchParams } from "expo-router";
import { CheckCircle2, X, XCircle } from "lucide-react-native";
import { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, View } from "react-native";
import { mensagemErro } from "@/api/erros";
import { Anel } from "@/componentes/cursos/Pecas";
import { agora } from "@/componentes/cursos/leitor";
import {
  capitulosPorOrdem,
  useCapituloCursoQuery,
  useCursoDetalheQuery,
  useResponderQuizMutation,
  useResumoQuizQuery,
  type PerguntaQuiz,
  type ResultadoQuiz,
} from "@/dominios/cursos/api";
import { Aviso, BarraProgresso, Botao, BotaoIcone, Cabecalho, Dialogo, Ecra, EstadoErro, Etiqueta, Osso, Texto, Titulo } from "@/ui";
import { cor, raio } from "@/tema";

// Sem tentativas e sem passar, a aula conclui-se na mesma (com o vídeo visto); a nota fica.
const SEM_TENTATIVAS = "Já não tem mais tentativas. A aula conta como concluída depois de ver o vídeo, mas esta nota fica na nota do curso. O professor pode dar-lhe outra tentativa.";

export default function EcraQuestionario() {
  const { id: courseId, capitulo: chapterId } = useLocalSearchParams<{ id: string; capitulo: string }>();
  const curso = useCursoDetalheQuery(courseId);
  const cap = useCapituloCursoQuery(chapterId);
  const resumo = useResumoQuizQuery(chapterId);
  const numero = useMemo(() => (curso.data ? capitulosPorOrdem(curso.data.curso).find((c) => c.chapterId === chapterId)?.numero : undefined), [curso.data, chapterId]);

  if (cap.isError || resumo.isError)
    return (
      <Ecra cabecalho={<Cabecalho titulo="Questionário" fechar />}>
        <EstadoErro
          titulo="Não conseguimos abrir o questionário"
          erro={cap.error ?? resumo.error}
          aoTentar={() => {
            cap.refetch();
            resumo.refetch();
          }}
        />
      </Ecra>
    );
  if (!cap.data || resumo.isLoading)
    return (
      <Ecra cabecalho={<Cabecalho titulo="Questionário" fechar />}>
        <View accessible accessibilityLabel="A carregar o questionário" accessibilityState={{ busy: true }} style={{ gap: 12 }}>
          <Osso altura={20} largura="50%" />
          <Osso altura={56} />
          {[0, 1, 2, 3].map((i) => (
            <Osso key={i} altura={60} raio={6} />
          ))}
        </View>
      </Ecra>
    );
  const quiz = cap.data.quiz_data;
  if (!quiz?.questions?.length)
    return (
      <Ecra cabecalho={<Cabecalho titulo="Questionário" fechar />}>
        <Aviso>O professor ainda não pôs perguntas neste questionário.</Aviso>
      </Ecra>
    );
  return (
    <Questionario
      chapterId={chapterId}
      courseId={courseId}
      perguntas={quiz.questions}
      minimo={resumo.data?.quiz_info?.passing_score ?? quiz.settings?.passingScore ?? 70}
      maxTentativas={resumo.data?.quiz_info?.max_attempts ?? quiz.settings?.maxAttempts ?? 1}
      restantesInicio={resumo.data?.attempts_remaining ?? quiz.settings?.maxAttempts ?? 1}
      resumo={resumo.data ?? null}
      numeroAula={numero}
    />
  );
}

function Questionario({
  chapterId,
  courseId,
  perguntas,
  minimo,
  maxTentativas,
  restantesInicio,
  resumo,
  numeroAula,
}: {
  chapterId: string;
  courseId: string;
  perguntas: PerguntaQuiz[];
  minimo: number;
  maxTentativas: number;
  restantesInicio: number;
  resumo: { attempts_count: number; best_score: number; is_passed: boolean } | null;
  numeroAula?: number;
}) {
  const [responder, { isLoading: aEnviar }] = useResponderQuizMutation();
  const [respostas, setRespostas] = useState<Record<string, string>>({});
  const [n, setN] = useState(0);
  const [resultado, setResultado] = useState<ResultadoQuiz | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [sair, setSair] = useState(false);
  const inicio = useRef(0);
  useEffect(() => {
    inicio.current = agora();
  }, []);
  const restantes = resultado ? resultado.tentativas_restantes : restantesInicio;
  const tentativa = (resumo?.attempts_count ?? 0) + 1;
  const fechar = () => (router.canGoBack() ? router.back() : router.replace(`/curso/${courseId}/aula/${chapterId}`));

  // Já não há tentativas: mostra o que ficou registado.
  if (!resultado && restantes <= 0) {
    return (
      <Ecra cabecalho={<Cabecalho titulo="Questionário" fechar />} rodape={<Botao tipo="secundario" onPress={fechar}>Voltar à aula</Botao>}>
        <Aviso tom={resumo?.is_passed ? "certo" : "info"} titulo={resumo?.is_passed ? "Já passou neste questionário" : "Sem tentativas"}>
          {resumo ? `${resumo.is_passed ? "" : `Melhor nota até agora: ${Math.round(resumo.best_score)}%. `}${resumo.is_passed ? `Melhor nota: ${Math.round(resumo.best_score)}%. Já não tem mais tentativas.` : SEM_TENTATIVAS}` : SEM_TENTATIVAS}
        </Aviso>
      </Ecra>
    );
  }

  if (resultado) return <Resultado r={resultado} perguntas={perguntas} respostas={respostas} minimo={minimo} restantes={restantes} numeroAula={numeroAula} aoRepetir={() => { setResultado(null); setRespostas({}); setN(0); inicio.current = agora(); }} aoVoltar={fechar} />;

  const q = perguntas[n];
  const ultima = n === perguntas.length - 1;
  const escolhida = respostas[q.id];
  const faltam = perguntas.filter((p) => !respostas[p.id]).length;

  const enviar = async () => {
    setErro(null);
    const r = await responder({ chapterId, courseId, respostas, segundos: (agora() - inicio.current) / 1000 });
    if ("error" in r && r.error) {
      setErro(mensagemErro(r.error, "Não foi possível enviar as respostas. Tente outra vez."));
      return;
    }
    setResultado(r.data!);
  };

  return (
    <Ecra
      cabecalho={
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12, paddingVertical: 8, minHeight: 60 }}>
          <BotaoIcone rotulo="Sair do questionário" onPress={() => (Object.keys(respostas).length ? setSair(true) : fechar())}>
            <X size={24} color={cor.tinta} />
          </BotaoIcone>
          <View style={{ flex: 1 }}>
            <BarraProgresso valor={(100 * (n + 1)) / perguntas.length} rotulo={`Pergunta ${n + 1} de ${perguntas.length}`} altura={12} />
          </View>
        </View>
      }
      rodape={
        <>
          {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
          <View style={{ flexDirection: "row", gap: 10 }}>
            {n > 0 ? (
              <Botao tipo="secundario" style={{ flex: 1 }} onPress={() => setN(n - 1)}>
                Anterior
              </Botao>
            ) : null}
            {ultima ? (
              <Botao style={{ flex: 1 }} disabled={faltam > 0} carregando={aEnviar} onPress={() => void enviar()}>
                {aEnviar ? "A corrigir…" : "Enviar respostas"}
              </Botao>
            ) : (
              <Botao style={{ flex: 1 }} disabled={!escolhida} onPress={() => setN(n + 1)}>
                Seguinte
              </Botao>
            )}
          </View>
          {ultima && faltam > 0 ? (
            <Texto v="legenda" suave centro>
              {faltam === 1 ? "Falta 1 pergunta." : `Faltam ${faltam} perguntas.`} Volte atrás para responder.
            </Texto>
          ) : null}
        </>
      }
      style={{ gap: 22 }}
    >
      {n === 0 && resumo && resumo.attempts_count > 0 ? (
        <Aviso tom={resumo.is_passed ? "certo" : "info"}>
          {`${resumo.is_passed ? `Já passou neste questionário (melhor nota: ${Math.round(resumo.best_score)}%).` : `Melhor nota até agora: ${Math.round(resumo.best_score)}%.`} Tem ${restantes} ${restantes === 1 ? "tentativa" : "tentativas"}.`}
        </Aviso>
      ) : n === 0 && !resumo?.attempts_count ? (
        <Texto suave>
          {perguntas.length} perguntas. Precisa de {minimo}% para passar e tem {restantes} {restantes === 1 ? "tentativa" : "tentativas"}.
        </Texto>
      ) : null}
      <View style={{ gap: 6 }}>
        <Texto v="legenda" suave style={{ fontSize: 15 }}>
          Pergunta {n + 1} de {perguntas.length}. Tentativa {Math.min(tentativa, maxTentativas)} de {maxTentativas}.
        </Texto>
        <Titulo v="tituloM">{q.question}</Titulo>
      </View>
      <View accessibilityRole="radiogroup" accessibilityLabel="Opções de resposta" style={{ gap: 12 }}>
        {q.options.map((o, i) => {
          const a = escolhida === o.id;
          return (
            <Pressable
              key={o.id}
              accessibilityRole="radio"
              accessibilityState={{ selected: a, checked: a }}
              onPress={() => setRespostas((r) => ({ ...r, [q.id]: o.id }))}
              style={({ pressed }) => ({
                flexDirection: "row",
                alignItems: "center",
                gap: 12,
                minHeight: 60,
                paddingVertical: 8,
                paddingHorizontal: 16,
                borderWidth: 2,
                borderColor: a ? cor.azulMarca : cor.linhaForte,
                borderRadius: raio.sm,
                backgroundColor: a || pressed ? cor.fundoSuave : cor.fundo,
              })}
            >
              <View style={{ width: 28, height: 28, alignItems: "center", justifyContent: "center", borderWidth: 1.5, borderColor: cor.linhaForte, borderRadius: raio.sm, backgroundColor: cor.fundo }}>
                <Texto v="legenda" forte suave>
                  {i + 1}
                </Texto>
              </View>
              <Texto forte={a} style={{ flex: 1, fontSize: 17, lineHeight: 24 }}>
                {o.text}
              </Texto>
            </Pressable>
          );
        })}
      </View>
      <Dialogo
        aberto={sair}
        titulo="Sair do questionário?"
        texto="As respostas que já escolheu perdem-se. Não gasta nenhuma tentativa."
        aoFechar={() => setSair(false)}
      >
        <Botao larguraTotal onPress={() => setSair(false)}>
          Continuar a responder
        </Botao>
        <Botao
          tipo="secundario"
          larguraTotal
          onPress={() => {
            setSair(false);
            fechar();
          }}
        >
          Sair
        </Botao>
      </Dialogo>
    </Ecra>
  );
}

function Resultado({
  r,
  perguntas,
  respostas,
  minimo,
  restantes,
  numeroAula,
  aoRepetir,
  aoVoltar,
}: {
  r: ResultadoQuiz;
  perguntas: PerguntaQuiz[];
  respostas: Record<string, string>;
  minimo: number;
  restantes: number;
  numeroAula?: number;
  aoRepetir: () => void;
  aoVoltar: () => void;
}) {
  const pct = Math.round(r.score_percentage);
  const certas = r.correccao.filter((c) => c.certa).length;
  const porPergunta = new Map(r.correccao.map((c) => [c.pergunta, c]));
  const falhadas = perguntas.map((q, i) => ({ q, i, c: porPergunta.get(q.id) })).filter((x) => x.c && !x.c.certa);
  const podeRepetir = !r.is_passed && restantes > 0;
  return (
    <Ecra
      rodape={
        <>
          {podeRepetir ? <Botao onPress={aoRepetir}>Tentar outra vez</Botao> : null}
          <Botao tipo={podeRepetir ? "secundario" : "principal"} onPress={aoVoltar}>
            {r.is_passed ? "Voltar à aula" : "Rever a aula"}
          </Botao>
        </>
      }
      style={{ paddingTop: 40, gap: 20 }}
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: 18 }}>
        <Anel valor={pct} cheio={r.is_passed ? cor.certo : cor.errado} vazio={r.is_passed ? cor.certoSuave : cor.erradoSuave} fundo={cor.fundo} rotulo={`${pct} por cento`} />
        <View style={{ flex: 1, gap: 4 }}>
          <Texto v="legenda" suave style={{ fontSize: 15 }}>
            {numeroAula ? `Questionário da aula ${numeroAula}` : "Questionário da aula"}
          </Texto>
          <Titulo v="tituloM" accessibilityLiveRegion="polite">
            {r.is_passed ? `Passou com ${pct}%.` : `Ficou nos ${pct}%. Precisa de ${minimo}% para passar.`}
          </Titulo>
        </View>
      </View>
      <Texto>
        Acertou {certas} de {r.correccao.length}.
        {!r.is_passed ? (restantes ? ` Tem mais ${restantes} ${restantes === 1 ? "tentativa" : "tentativas"}.` : ` ${SEM_TENTATIVAS}`) : ""}
        {!r.revela_respostas && !r.is_passed && restantes ? " As respostas certas aparecem quando passar ou quando acabarem as tentativas." : ""}
      </Texto>

      {falhadas.length ? (
        <View style={{ gap: 12 }}>
          <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
            O que falhou
          </Texto>
          {falhadas.map(({ q, i, c }) => {
            const minha = q.options.find((o) => o.id === respostas[q.id]);
            const certasTxt = c!.opcoes_certas?.map((id) => q.options.find((o) => o.id === id)?.text).filter(Boolean) ?? [];
            return (
              <View key={q.id} style={{ gap: 8, padding: 16, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md }}>
                <Texto v="legenda" forte suave>
                  Pergunta {i + 1}
                </Texto>
                <Texto forte>{q.question}</Texto>
                {minha ? (
                  <View style={{ flexDirection: "row", gap: 8, alignItems: "flex-start" }}>
                    <XCircle size={18} color={cor.errado} style={{ marginTop: 3 }} />
                    <Texto forte cor={cor.errado} style={{ flex: 1 }}>
                      Escolheu &quot;{minha.text}&quot;.
                    </Texto>
                  </View>
                ) : (
                  <Etiqueta tom="errado">Sem resposta</Etiqueta>
                )}
                {certasTxt.length ? (
                  <View style={{ flexDirection: "row", gap: 8, alignItems: "flex-start" }}>
                    <CheckCircle2 size={18} color={cor.certo} style={{ marginTop: 3 }} />
                    <Texto forte cor={cor.certo} style={{ flex: 1 }}>
                      Certa: &quot;{certasTxt.join('", "')}&quot;.
                    </Texto>
                  </View>
                ) : null}
                {c!.explicacao ? <Texto>{c!.explicacao}</Texto> : null}
              </View>
            );
          })}
        </View>
      ) : r.is_passed ? (
        <Aviso tom="certo">Acertou em todas as perguntas.</Aviso>
      ) : null}
    </Ecra>
  );
}
