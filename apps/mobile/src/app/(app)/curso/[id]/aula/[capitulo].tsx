/**
 * Aula (canvas AulaMovel; web user/courses/[courseId]/chapters/[chapterId]/page.tsx):
 * vídeo (expo-video) com o tempo visto enviado ao marcar a aula, texto da aula, transcrição
 * sincronizada, "Repetir em voz alta", "Usar isto numa conversa", questionário, prática e materiais.
 */
import { useEventListener } from "expo";
import { router, useLocalSearchParams } from "expo-router";
import { useVideoPlayer, VideoView, type VideoPlayer } from "expo-video";
import { Check, Dumbbell, ExternalLink, FileText, ListChecks } from "lucide-react-native";
import { type ReactNode, useMemo, useRef, useState } from "react";
import { Linking, Pressable, View } from "react-native";
import { urlAbsoluto } from "@/api/config";
import { mensagemErro } from "@/api/erros";
import { RepetirEmVozAlta, UsarNumaConversa } from "@/componentes/cursos/FalaDaAula";
import { ASeguir } from "@/componentes/cursos/Percurso";
import { TEXTO_PLANOS_PAGOS } from "@/componentes/cursos/Amostra";
import { SeparadoresCursos } from "@/componentes/cursos/Pecas";
import { TextoRico } from "@/componentes/cursos/TextoRico";
import { tocarDesde } from "@/componentes/cursos/leitor";
import {
  capitulosPorOrdem,
  concluidos,
  temQuestionario,
  useCapituloCursoQuery,
  useCursoDetalheQuery,
  useFalaDaAulaQuery,
  usePercursoCursoQuery,
  useInscricaoCursoQuery,
  useMarcarCapituloMutation,
  useProgressoCursoQuery,
  useRecursosCapituloQuery,
  useResumoQuizQuery,
  videosVistos,
  type CapituloNoCurso,
} from "@/dominios/cursos/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { Aviso, BalaoFala, Botao, Cabecalho, Ecra, EstadoErro, EstadoVazio, Etiqueta, Osso, Texto, Titulo } from "@/ui";
import { balao, cor, raio } from "@/tema";

type Linha = { start: number; end: number; text: string };
type Separador = "aula" | "transcricao" | "frases";

export default function PaginaAula() {
  const { id: courseId, capitulo: chapterId } = useLocalSearchParams<{ id: string; capitulo: string }>();
  const { utilizador } = useSessao();
  const curso = useCursoDetalheQuery(courseId);
  const inscricao = useInscricaoCursoQuery(courseId);
  const lista = useMemo(() => (curso.data ? capitulosPorOrdem(curso.data.curso) : []), [curso.data]);
  const i = lista.findIndex((c) => c.chapterId === chapterId);
  const aqui = lista[i];
  // Unidades de amostra: sem o plano, só as aulas que a API não marca como bloqueadas.
  const amostra = !curso.data?.temAcesso && curso.data?.acesso === "amostra";
  const podeVer = !!inscricao.data?.is_enrolled && (!!curso.data?.temAcesso || (amostra && !!aqui && !aqui.bloqueada));
  const cap = useCapituloCursoQuery(chapterId, { skip: !podeVer });
  const progresso = useProgressoCursoQuery({ userId: utilizador?.id ?? "", courseId }, { skip: !utilizador || !podeVer });

  const anterior = i > 0 ? lista[i - 1] : null;
  const seguinte = i >= 0 && i < lista.length - 1 && !lista[i + 1].bloqueada ? lista[i + 1] : null;
  const voltar = <Cabecalho subtitulo={aqui ? `Aula ${aqui.numero} de ${lista.length}` : undefined} linha={false} aoVoltar={() => (router.canGoBack() ? router.back() : router.replace(`/curso/${courseId}`))} />;

  if (curso.isError) return <Problema titulo="Não conseguimos abrir este curso" courseId={courseId} erro={curso.error} aoTentar={() => void curso.refetch()} />;
  if (inscricao.isError) return <Problema titulo="Não conseguimos abrir esta aula" courseId={courseId} erro={inscricao.error} aoTentar={() => void inscricao.refetch()} />;
  if (!curso.data || !inscricao.data) return <Esqueleto cabecalho={voltar} />;
  if (!podeVer && inscricao.data.is_enrolled && amostra && aqui?.bloqueada) {
    return (
      <Ecra cabecalho={voltar}>
        <EstadoVazio
          titulo={TEXTO_PLANOS_PAGOS}
          texto={`${aqui.title}, ${aqui.seccao}. As primeiras unidades de ${curso.data.curso.title} são gratuitas; esta faz parte dos planos pagos.`}
          accao={
            <Botao larguraTotal href="/planos">
              Ver os planos
            </Botao>
          }
        />
      </Ecra>
    );
  }
  if (!podeVer) {
    return (
      <Ecra cabecalho={voltar}>
        <EstadoVazio
          titulo={inscricao.data.is_enrolled ? "Esta aula precisa de outro plano" : "Comece o curso para ver as aulas"}
          texto={curso.data.curso.title}
          accao={
            <Botao larguraTotal href={`/curso/${courseId}`} substituir>
              Ver o curso
            </Botao>
          }
        />
      </Ecra>
    );
  }
  if (!aqui) return <Problema titulo="Esta aula já não existe" courseId={courseId} />;
  if (cap.isError) return <Problema titulo="Não conseguimos abrir esta aula" courseId={courseId} erro={cap.error} aoTentar={cap.refetch} />;
  if (!cap.data) return <Esqueleto cabecalho={voltar} />;

  return (
    <Conteudo
      key={chapterId}
      cabecalho={voltar}
      cap={{ ...aqui, ...cap.data }}
      courseId={courseId}
      userId={utilizador?.id ?? ""}
      feito={concluidos(progresso.data).has(chapterId)}
      videoVisto={videosVistos(progresso.data).has(chapterId)}
      anterior={anterior}
      seguinte={seguinte}
    />
  );
}

function Conteudo({
  cabecalho,
  cap,
  courseId,
  userId,
  feito,
  videoVisto,
  anterior,
  seguinte,
}: {
  cabecalho: ReactNode;
  cap: CapituloNoCurso;
  courseId: string;
  userId: string;
  feito: boolean;
  videoVisto: boolean;
  anterior: CapituloNoCurso | null;
  seguinte: CapituloNoCurso | null;
}) {
  const [marcar, { isLoading }] = useMarcarCapituloMutation();
  // O passo seguinte do percurso (o servidor decide); o vídeo e o questionário desta aula já têm
  // o seu botão no rodapé, por isso só se mostra quando o passo é outro (laboratório, conversa, outra aula).
  const percurso = usePercursoCursoQuery(courseId, { refetchOnMountOrArgChange: true });
  const passo = percurso.data?.proximo ?? null;
  const mostrarSeguinte = !!passo && !(passo.aula_id === cap.chapterId && (passo.tipo === "aula" || passo.tipo === "questionario"));
  const [erro, setErro] = useState<string | null>(null);
  // O progresso pode chegar depois de a aula abrir: conta o que vem do servidor e o que se marcou agora.
  const [vistoAgora, setVisto] = useState(false);
  const comQuiz = temQuestionario(cap);
  const soQuiz = cap.type === "Quiz";
  const visto = comQuiz ? feito : feito || vistoAgora;
  const videoFeito = videoVisto || vistoAgora;
  const segundos = useRef(0);
  const recursos = useRecursosCapituloQuery(cap.chapterId);
  const linhas = useMemo(() => lerTranscricao(cap.transcript), [cap.transcript]);
  const fonteVideo = cap.type === "Video" ? urlAbsoluto(cap.video || null) : null;
  const comVideo = !!fonteVideo;
  const fala = useFalaDaAulaQuery(cap.chapterId, { skip: !comVideo });
  const temFrases = !!fala.data?.frases.length;
  const quiz = useResumoQuizQuery(cap.chapterId, { skip: !comQuiz });
  const [separador, setSeparador] = useState<Separador>("aula");

  const player = useVideoPlayer(fonteVideo, (p) => {
    p.timeUpdateEventInterval = 0.5;
  });

  const concluir = async () => {
    setErro(null);
    const r = await marcar({ userId, courseId, sectionId: cap.sectionId, chapterId: cap.chapterId, concluido: true, segundos: segundos.current });
    if ("error" in r && r.error) {
      setErro(mensagemErro(r.error, "Não foi possível guardar. Tente outra vez."));
      return;
    }
    segundos.current = 0;
    setVisto(true);
  };

  const itens: { valor: Separador; nome: string }[] = [{ valor: "aula", nome: "Aula" }];
  if (linhas.length) itens.push({ valor: "transcricao", nome: "Transcrição" });
  if (temFrases) itens.push({ valor: "frases", nome: "Frases" });

  const irQuestionario = () => router.push(`/curso/${courseId}/questionario/${cap.chapterId}`);
  const irSeguinte = () => (seguinte ? router.replace(`/curso/${courseId}/aula/${seguinte.chapterId}`) : router.push(`/curso/${courseId}/notas`));
  const principal = soQuiz ? (
    <Botao onPress={irQuestionario} style={{ flex: 1 }}>
      {quiz.data?.is_passed ? "Ver o questionário" : "Começar o questionário"}
    </Botao>
  ) : visto ? (
    <Botao onPress={irSeguinte} style={{ flex: 1 }}>
      {seguinte ? "Aula seguinte" : "Ver as notas"}
    </Botao>
  ) : comQuiz && videoFeito ? (
    <Botao tipo="realce" onPress={irQuestionario} style={{ flex: 1 }}>
      Fazer o questionário
    </Botao>
  ) : (
    <Botao carregando={isLoading} onPress={() => void concluir()} style={{ flex: 1 }}>
      {isLoading ? "A guardar…" : cap.type === "Text" ? "Marcar como lida" : "Marcar como vista"}
    </Botao>
  );

  return (
    <Ecra
      cabecalho={
        <>
          {cabecalho}
          {comVideo ? <Video player={player} titulo={cap.title} aoAvancar={(s) => (segundos.current += s)} aoTerminar={() => !visto && !(comQuiz && videoFeito) && void concluir()} /> : null}
        </>
      }
      rodape={
        <View style={{ flexDirection: "row", gap: 10 }}>
          {anterior ? (
            <Botao tipo="secundario" style={{ flex: 1 }} onPress={() => router.replace(`/curso/${courseId}/aula/${anterior.chapterId}`)} accessibilityLabel={`Aula anterior: ${anterior.title}`}>
              Aula anterior
            </Botao>
          ) : null}
          {principal}
        </View>
      }
      style={{ gap: 16 }}
    >
      <View style={{ gap: 4 }}>
        <Titulo v="tituloM">{cap.title}</Titulo>
        <Texto v="legenda" suave>
          {cap.seccao}, aula {cap.numeroNaSeccao} de {cap.totalNaSeccao}
        </Texto>
      </View>

      {visto && !soQuiz ? (
        <Etiqueta tom="certo" icone={<Check size={16} strokeWidth={3} color={cor.certo} />}>
          {comQuiz ? "Concluída" : cap.type === "Text" ? "Lida" : "Vista"}
        </Etiqueta>
      ) : comQuiz && videoFeito && !soQuiz ? (
        <View style={{ gap: 4 }}>
          <Etiqueta icone={<Check size={16} strokeWidth={3} color={cor.tinta} />}>{cap.type === "Text" ? "Lida" : "Vídeo visto"}</Etiqueta>
          <Texto v="legenda" suave>
            Passe o questionário para concluir a aula.
          </Texto>
        </View>
      ) : null}
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}

      {itens.length > 1 ? <SeparadoresCursos itens={itens} activo={separador} aoMudar={setSeparador} /> : null}

      {separador === "transcricao" ? (
        <Transcricao player={player} linhas={linhas} />
      ) : separador === "frases" && fala.data && comVideo ? (
        <View style={{ gap: 24 }}>
          <RepetirEmVozAlta chapterId={cap.chapterId} player={player} dados={fala.data} />
          <UsarNumaConversa chapterId={cap.chapterId} courseId={courseId} titulo={cap.title} dados={fala.data} />
        </View>
      ) : (
        <>
          {cap.content ? soQuiz ? <Texto v="corpoL">{cap.content}</Texto> : <TextoRico texto={cap.content} /> : null}

          {mostrarSeguinte && percurso.data && passo ? (
            <ASeguir proximo={{ curso: percurso.data.curso, passo, feitos: percurso.data.feitos, total: percurso.data.total }} />
          ) : null}

          {temFrases ? (
            <Pressable
              accessibilityRole="button"
              onPress={() => setSeparador("frases")}
              style={({ pressed }) => ({ gap: 6, padding: 16, borderRadius: raio.md, backgroundColor: pressed ? cor.fundoForte : cor.fundoSuave })}
            >
              <Texto forte>Repetir em voz alta</Texto>
              <Texto v="legenda" suave>
                {fala.data!.frases.filter((f) => f.tipo === "frase").length} frases desta aula para dizer em voz alta e usar numa conversa com o tutor.
              </Texto>
              <Texto v="voz" cor={cor.azulMarca} style={{ fontSize: 19, lineHeight: 28 }}>
                {fala.data!.frases[0].texto}
              </Texto>
            </Pressable>
          ) : null}

          {comQuiz && !soQuiz && cap.quiz_data ? (
            <View style={{ gap: 10, padding: 16, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                <ListChecks size={22} color={cor.azulMarca} />
                <Texto v="tituloXS" accessibilityRole="header" style={{ flex: 1 }}>
                  Questionário da aula
                </Texto>
              </View>
              <Texto suave>{visto ? (quiz.data?.is_passed ? `Já passou (melhor nota: ${Math.round(quiz.data.best_score)}%).` : "Aula concluída.") : videoFeito ? "Responda para concluir a aula." : "Veja o vídeo e responda ao questionário para concluir a aula."}</Texto>
              <Botao tipo="secundario" tamanho="medio" onPress={irQuestionario}>
                {quiz.data?.attempts_count ? "Ver o questionário" : "Abrir o questionário"}
              </Botao>
            </View>
          ) : null}

          {cap.practice_lesson ? (
            <BalaoFala tamanho="medio" style={{ gap: 12 }}>
              <Texto v="tituloS" cor={cor.sobreMarca}>
                Praticar no laboratório
              </Texto>
              <Texto v="legenda" cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
                {cap.type === "Exercise"
                  ? "Esta aula é uma lição de prática: responde, ganha pontos e volta aqui quando terminar."
                  : "Pratique o que viu nesta aula. Os exercícios contam para a nota do curso."}
              </Texto>
              <Botao tipo="realce" tamanho="medio" icone={<Dumbbell size={20} color={cor.tinta} />} href={`/licao/${cap.practice_lesson}`}>
                Começar a prática
              </Botao>
            </BalaoFala>
          ) : null}

          {recursos.data?.length ? (
            <View style={{ gap: 4 }}>
              <Texto v="tituloXS" accessibilityRole="header">
                Materiais da aula
              </Texto>
              {recursos.data.map((r) => {
                const url = urlAbsoluto(r.file_url || r.external_url || null);
                const pdf = r.resource_type === "PDF";
                return (
                  <Pressable
                    key={r.id}
                    accessibilityRole="link"
                    accessibilityLabel={`${r.title}. ${pdf ? "Abrir PDF" : "Abrir"}`}
                    disabled={!url}
                    onPress={() => url && Linking.openURL(url)}
                    style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 12, minHeight: 56, paddingVertical: 8, borderBottomWidth: 1, borderColor: cor.fundoForte, backgroundColor: pressed ? cor.fundoSuave : undefined })}
                  >
                    <View style={[balao.pequeno, { width: 36, height: 36, alignItems: "center", justifyContent: "center", backgroundColor: cor.fundoForte }]}>
                      {pdf ? <FileText size={20} color={cor.tinta} /> : <ExternalLink size={20} color={cor.tinta} />}
                    </View>
                    <View style={{ flex: 1 }}>
                      <Texto forte style={{ lineHeight: 22 }}>
                        {r.title}
                      </Texto>
                      {r.description ? (
                        <Texto v="legenda" suave>
                          {r.description}
                        </Texto>
                      ) : null}
                    </View>
                    <Texto v="legenda" cor={cor.azulVivo}>
                      {pdf ? "Abrir PDF" : "Abrir"}
                    </Texto>
                  </Pressable>
                );
              })}
            </View>
          ) : null}

          {!cap.content && !comVideo && !soQuiz && !cap.practice_lesson && !recursos.data?.length ? <Texto suave>Esta aula ainda não tem conteúdo.</Texto> : null}
          {soQuiz && !cap.quiz_data?.questions?.length ? <Aviso>O professor ainda não pôs perguntas neste questionário.</Aviso> : null}
        </>
      )}
    </Ecra>
  );
}

/* ------------------------------------------------------------------ */
/* Vídeo: conta só o tempo visto a reproduzir (saltos para a frente não contam), como a web. */
/* ------------------------------------------------------------------ */
function Video({ player, titulo, aoAvancar, aoTerminar }: { player: VideoPlayer; titulo: string; aoAvancar: (s: number) => void; aoTerminar: () => void }) {
  const ultimo = useRef(0);
  useEventListener(player, "timeUpdate", ({ currentTime }) => {
    const delta = currentTime - ultimo.current;
    if (player.playing && delta > 0 && delta < 2) aoAvancar(delta);
    ultimo.current = currentTime;
  });
  useEventListener(player, "playToEnd", aoTerminar);
  return (
    <View style={{ aspectRatio: 16 / 9, width: "100%", backgroundColor: cor.azulMarca }}>
      <VideoView
        player={player}
        accessibilityLabel={`Vídeo: ${titulo}`}
        style={{ width: "100%", height: "100%" }}
        nativeControls
        contentFit="contain"
        fullscreenOptions={{ enable: true }}
        allowsPictureInPicture={false}
      />
    </View>
  );
}

/** Transcrição em inglês: a linha que está a ser dita fica azul; tocar numa linha salta para lá. */
function Transcricao({ player, linhas }: { player: VideoPlayer; linhas: Linha[] }) {
  const [tempo, setTempo] = useState(0);
  useEventListener(player, "timeUpdate", ({ currentTime }) => setTempo(currentTime));
  const actual = linhas.findIndex((l) => tempo >= l.start && tempo < l.end);
  return (
    <View style={{ gap: 4 }}>
      <Texto v="legenda" suave>
        Toque numa frase para a ouvir no vídeo.
      </Texto>
      {linhas.map((l, n) => {
        const a = n === actual;
        return (
          <Pressable
            key={`${l.start}-${n}`}
            accessibilityRole="button"
            accessibilityState={{ selected: a }}
            accessibilityLabel={`${minSeg(l.start)}: ${l.text}`}
            onPress={() => {
              tocarDesde(player, l.start);
            }}
            style={({ pressed }) => ({ flexDirection: "row", gap: 12, paddingHorizontal: 8, paddingVertical: 6, borderRadius: raio.sm, backgroundColor: a ? cor.azulMarca : pressed ? cor.fundoForte : undefined })}
          >
            <Texto v="legenda" numeros cor={a ? cor.sobreMarca : cor.tintaSuave} style={{ width: 40, paddingTop: 3 }}>
              {minSeg(l.start)}
            </Texto>
            <Texto v="voz" cor={a ? cor.sobreMarca : cor.tinta} style={{ flex: 1, fontSize: 18, lineHeight: 28 }}>
              {l.text}
            </Texto>
          </Pressable>
        );
      })}
    </View>
  );
}

const minSeg = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

function lerTranscricao(t?: string): Linha[] {
  if (!t) return [];
  try {
    const d = JSON.parse(t);
    return Array.isArray(d) ? d.filter((l) => typeof l?.text === "string").map((l) => ({ start: Number(l.start) || 0, end: Number(l.end) || 0, text: l.text })) : [];
  } catch {
    return [];
  }
}

function Problema({ titulo, courseId, erro, aoTentar }: { titulo: string; courseId: string; erro?: unknown; aoTentar?: () => void }) {
  return (
    <Ecra cabecalho={<Cabecalho />}>
      <EstadoErro
        titulo={titulo}
        erro={erro}
        aoTentar={aoTentar}
        outra={
          <Botao tipo="secundario" larguraTotal href={`/curso/${courseId}`} substituir>
            Voltar ao curso
          </Botao>
        }
      />
    </Ecra>
  );
}

function Esqueleto({ cabecalho }: { cabecalho: ReactNode }) {
  return (
    <Ecra cabecalho={cabecalho} semMargem style={{ paddingTop: 0 }}>
      <View accessible accessibilityLabel="A carregar a aula" accessibilityState={{ busy: true }} style={{ gap: 16 }}>
        <Osso altura={220} raio={0} />
        <View style={{ paddingHorizontal: 20, gap: 12 }}>
          <Osso altura={28} largura="70%" />
          <Osso altura={16} largura="40%" />
          <Osso altura={120} />
        </View>
      </View>
    </Ecra>
  );
}
