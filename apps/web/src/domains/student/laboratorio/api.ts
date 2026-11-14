/**
 * Dados do laboratório de prática (trilho, lição, vidas, loja, escolher curso).
 * Tipos iguais ao que a API Django devolve (rotas verificadas com testes no backend).
 */
import { aposEstudo, quandoCorrerBem } from "@/src/domains/student/sincronizar";
import { studentPracticeApiSlice } from "../practice-courses/api/studentPracticeApiSlice";

const API = process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://localhost:8000/api/v1";

/* ------------------------------------------------------------------ */
/* Tipos                                                               */
/* ------------------------------------------------------------------ */
export type EstadoLicao = "feita" | "actual" | "bloqueada";

export type Trilho = {
  curso: { id: string; titulo: string; categoria?: string; nivel?: string };
  licoes_feitas: number;
  licoes_total: number;
  percentagem: number;
  unidades: {
    id: string;
    titulo: string;
    descricao?: string;
    ordem: number;
    licoes: { id: string; titulo: string; ordem: number; estado: EstadoLicao; exercicios: number; exercicios_feitos: number }[];
  }[];
};

export type Opcao = { id: string; texto: string; imagem: string | null; audio: string | null };

export type Exercicio = {
  id: string;
  tipo: "SELECT" | "ASSIST" | "TRUE_FALSE" | "FILL_BLANK" | "TRANSLATION" | "LISTENING" | "SENTENCE_ORDER" | "MATCH_PAIRS" | "SPEAKING" | "VAPI_CONVERSATION";
  /** "indisponivel": o aluno não pode fazer este exercício e salta-o (saltarExercicio, sem pontos nem vidas). */
  modo: "escolha" | "banco" | "escrever" | "ordenar" | "pares" | "falar" | "indisponivel";
  /** Só com modo "indisponivel": conversa desligada ou escuta sem áudio. */
  motivo?: "conversa" | "sem_audio";
  pergunta: string;
  instrucao: string | null;
  audio: string | null;
  ordem: number;
  feito: boolean;
  opcoes?: Opcao[];
  espacos?: number;
  palavras?: { id: string; texto: string }[];
  esquerda?: { id: string; texto: string }[];
  direita?: string[];
  frase?: string;
};

export type LicaoParaJogar = {
  id: string;
  titulo: string;
  unidade: { id: string; titulo: string };
  curso: { id: string; titulo: string };
  repeticao: boolean;
  exercicios: Exercicio[];
};

export type Resposta =
  | { selected_option: string }
  | { text_answer: string }
  | { text_answers: string[] }
  | { ordered_options: string[] }
  | { paired_options: Record<string, string> };

export type ResultadoResposta = {
  correct: boolean;
  explicacao?: string | null;
  dica?: string | null;
  user_progress?: { hearts: number; points: number };
  heartsUsed?: number;
  feedback?: { similarity?: number; hint?: string };
};

export type ResultadoPronuncia = {
  ai_analysis: { overall_score: number; is_acceptable: boolean; transcribed_text?: string };
  feedback?: { message?: string; problematic_words?: string[] };
  explicacao?: string | null;
  dica?: string | null;
  user_progress?: { hearts: number; points: number };
};

export type ConclusaoLicao = {
  first_completion: boolean;
  points_awarded: number;
  hearts_awarded: number;
  already_recorded: boolean;
  total_points: number;
  hearts: number;
  streak: number;
  minutes_today: number;
  daily_goal_minutes: number;
  goal_completed: boolean;
  goal_just_completed: boolean;
};

export type EstadoVidas = {
  current: number;
  maximum: number;
  unlimited: boolean;
  recharge_hours: number;
  next_heart_at: string | null;
  refill_cost_points: number;
  can_refill_with_points: boolean;
  points: number;
  /** Lições novas feitas hoje (hora de Angola); limite null = sem limite. */
  licoes_hoje?: { feitas: number; limite: number | null; renova_em: string };
};

export type Sequencia = {
  current_streak: number;
  longest_streak: number;
  practiced_today: boolean;
  daily_goal_minutes: number;
  minutes_today: number;
  goal_completed: boolean;
};

export type CursoPratica = { id: string; title: string; description?: string; image?: string; category?: string; level?: string };

/* ------------------------------------------------------------------ */
/* Endpoints                                                           */
/* ------------------------------------------------------------------ */
export const laboratorioApi = studentPracticeApiSlice.injectEndpoints({
  endpoints: (build) => ({
    trilho: build.query<Trilho, string>({
      query: (courseId) => `/courses/${courseId}/trilho/`,
      providesTags: ["StudentUnit"],
    }),
    licaoParaJogar: build.query<LicaoParaJogar, string>({
      query: (lessonId) => `/lessons/${lessonId}/jogar/`,
      providesTags: ["StudentLesson"],
      keepUnusedDataFor: 0,
    }),
    responder: build.mutation<ResultadoResposta, { challengeId: string; resposta: Resposta }>({
      query: ({ challengeId, resposta }) => ({
        url: "/challenge-progress/",
        method: "POST",
        body: { challenge_id: challengeId, ...resposta },
      }),
      // Um 400 {error:'hearts'} é "sem vidas", não um erro técnico: devolve-se como resultado.
    }),
    /** Exercício de falar sem análise disponível: conta como feito, sem pontos nem vidas. */
    saltarExercicio: build.mutation<{ success: boolean; saltado: boolean; user_progress?: { hearts: number; points: number } }, { challengeId: string; token?: string | null }>({
      query: ({ challengeId, token }) => ({ url: "/challenge-progress/", method: "POST", body: { challenge_id: challengeId, saltar: true, ...(token ? { token_saltar: token } : {}) } }),
    }),
    analisarPronuncia: build.mutation<ResultadoPronuncia, { challengeId: string; frase: string; audio: Blob }>({
      // fetch próprio: a base desta fatia força JSON e a gravação tem de ir em multipart.
      queryFn: async ({ challengeId, frase, audio }) => {
        const corpo = new FormData();
        corpo.append("audio", audio, "gravacao.webm");
        corpo.append("challenge_id", challengeId);
        corpo.append("expected_text", frase);
        try {
          const r = await fetch(`${API}/practice/analyze-ai-pronunciation/`, { method: "POST", body: corpo, credentials: "include" });
          const dados = await r.json().catch(() => ({}));
          if (!r.ok) return { error: { status: r.status, data: dados } };
          return { data: dados as ResultadoPronuncia };
        } catch (e) {
          return { error: { status: "FETCH_ERROR", error: String(e) } };
        }
      },
    }),
    concluirLicao: build.mutation<ConclusaoLicao, { lessonId: string; segundos: number }>({
      query: ({ lessonId, segundos }) => ({
        url: "/complete-lesson/",
        method: "POST",
        body: { lesson_id: lessonId, time_spent: segundos },
      }),
      // Sem "StudentLesson": a lição aberta não deve recarregar por baixo do ecrã de conclusão.
      invalidatesTags: ["StudentUnit", "StudentProgress", "StudentStreak"],
      onQueryStarted: quandoCorrerBem(aposEstudo),
    }),
    estadoVidas: build.query<EstadoVidas, void>({
      query: () => "/hearts-status/",
      providesTags: ["StudentProgress"],
    }),
    recarregarVidas: build.mutation<{ hearts: number; points: number; points_spent: number; message: string }, void>({
      query: () => ({ url: "/refill-hearts/", method: "POST", body: {} }),
      invalidatesTags: ["StudentProgress"],
    }),
    sequencia: build.query<Sequencia, void>({
      query: () => "/study-streak/",
      providesTags: ["StudentStreak"],
    }),
    cursosPratica: build.query<CursoPratica[], void>({
      query: () => "/courses/",
      providesTags: ["StudentCourse"],
    }),
    progressoPratica: build.query<{ hearts: number; points: number; active_course: string | { id: string; title?: string } | null; has_unlimited_hearts?: boolean }, void>({
      query: () => "/user-progress/",
      providesTags: ["StudentProgress"],
    }),
    escolherCurso: build.mutation<unknown, string>({
      query: (courseId) => ({ url: "/user-progress/", method: "PUT", body: { active_course: courseId } }),
      invalidatesTags: ["StudentProgress", "StudentUnit", "StudentCourse"],
    }),
  }),
  // Em desenvolvimento o recarregamento a quente volta a injectar estes endpoints.
  overrideExisting: process.env.NODE_ENV === "development",
});

export const {
  useTrilhoQuery,
  useLicaoParaJogarQuery,
  useResponderMutation,
  useAnalisarPronunciaMutation,
  useSaltarExercicioMutation,
  useConcluirLicaoMutation,
  useEstadoVidasQuery,
  useRecarregarVidasMutation,
  useSequenciaQuery,
  useCursosPraticaQuery,
  useProgressoPraticaQuery,
  useEscolherCursoMutation,
} = laboratorioApi;

/** O curso activo pode vir como id ou como objecto, consoante a versão da API. */
export function idCursoActivo(ativo: string | { id: string } | null | undefined) {
  if (!ativo) return null;
  return typeof ativo === "string" ? ativo : ativo.id;
}
