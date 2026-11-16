/**
 * Laboratório de prática (trilho, lição, vidas, loja, escolher curso). Igual a
 * apps/web/src/domains/student/laboratorio/api.ts: a correcção das respostas é sempre feita no servidor.
 */
import { api } from "@/api/base";
import type { OfertaPlano } from "@/dominios/subscricao/api";

const P = "/student/practice-courses";

/* ------------------------------------------------------------------ */
/* Tipos                                                               */
/* ------------------------------------------------------------------ */
export type EstadoLicao = "feita" | "actual" | "bloqueada";

export type LicaoTrilho = { id: string; titulo: string; ordem: number; estado: EstadoLicao; exercicios: number; exercicios_feitos: number };

export type Trilho = {
  curso: { id: string; titulo: string; categoria?: string; nivel?: string };
  licoes_feitas: number;
  licoes_total: number;
  percentagem: number;
  unidades: { id: string; titulo: string; descricao?: string; ordem: number; licoes: LicaoTrilho[] }[];
};

export type Opcao = { id: string; texto: string; imagem: string | null; audio: string | null };

export type Exercicio = {
  id: string;
  tipo: "SELECT" | "ASSIST" | "TRUE_FALSE" | "FILL_BLANK" | "TRANSLATION" | "LISTENING" | "SENTENCE_ORDER" | "MATCH_PAIRS" | "SPEAKING" | "RESPONDER" | "VAPI_CONVERSATION";
  modo: "escolha" | "banco" | "escrever" | "ordenar" | "pares" | "falar" | "responder" | "conversa" | "indisponivel";
  motivo?: "conversa" | "incompleto" | "sem_audio";
  contexto?: string | null;
  frases?: string[];
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
  | { paired_options: Record<string, string> }
  | { sessao_id: string };

export type ResultadoResposta = {
  correct: boolean;
  explicacao?: string | null;
  dica?: string | null;
  solucao?: string | null;
  user_progress?: { hearts: number; points: number };
  heartsUsed?: number;
};

export type DetalhePronuncia = {
  palavras: { palavra: string; nota: number | null; erro_tipo: string }[];
  fluencia: number | null;
  completude: number | null;
  prosodia: number | null;
  dica: string | null;
  fonte: string;
};

export type ResultadoPronuncia = {
  ai_analysis: {
    overall_score: number;
    is_acceptable: boolean;
    transcribed_text?: string;
    /** null quando a análise é só pelo texto (não se mede fluência nem clareza). */
    fluency_score?: number | null;
    clarity_score?: number | null;
    /** 'texto': aproximada (palavras ouvidas); 'azure': detalhada. */
    fonte?: "texto" | "azure" | "simulada";
  };
  feedback?: { message?: string; problematic_words?: string[] };
  detalhe?: DetalhePronuncia | null;
  explicacao?: string | null;
  dica?: string | null;
  heartsUsed?: number;
  user_progress?: { hearts: number; points: number };
};

export type ResultadoResponder = {
  aceite: boolean;
  transcricao: string;
  responde: "sim" | "parcial" | "nao";
  usou_frase: boolean;
  correccao: { disse: string; certo: string; porque: string } | null;
  comentario: string | null;
  frase_alvo: string;
  exemplo: string | null;
  explicacao?: string | null;
  dica?: string | null;
  heartsUsed: number;
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
  licoes_hoje?: { feitas: number; limite: number | null; renova_em: string };
  /** Plano com vidas ilimitadas quando current <= 0 e as vidas não são ilimitadas; senão null. */
  oferta?: OfertaPlano | null;
};

export type Sequencia = {
  current_streak: number;
  longest_streak: number;
  practiced_today: boolean;
  daily_goal_minutes: number;
  minutes_today: number;
  goal_completed: boolean;
};

export type CursoPratica = {
  id: string;
  title: string;
  description?: string;
  image?: string;
  category?: string;
  level?: string;
  /** Curso de um sector. */
  de_sector?: boolean;
  /** Esta pessoa ainda precisa do nível básico para começar este curso. */
  requisito_basico?: boolean;
};

export type ProgressoPratica = { hearts: number; points: number; active_course: string | { id: string; title?: string } | null; has_unlimited_hearts?: boolean };

export type PlanoLab = {
  id: string;
  name: string;
  plan_type: string;
  monthly_price: string;
  daily_speaking_minutes: number | null;
  /** 0 = vidas ilimitadas. */
  hearts_limit?: number;
  /** null ou 0 = lições novas sem limite. */
  daily_lessons_limit?: number | null;
  certificates?: boolean;
  sort_order: number;
};

/** Tags que outros ecrãs (estatísticas, liga, conquistas, certificados, início) também usam. */
const DEPOIS_DE_ESTUDAR = ["LabTrilho", "LabProgresso", "LabSequencia", "Estatisticas", "Liga", "Conquistas", "Certificados", "InicioResumo"] as const;

export const laboratorioApi = api
  .enhanceEndpoints({ addTagTypes: ["LabTrilho", "LabLicao", "LabProgresso", "LabSequencia", "LabCursos", "Estatisticas", "Liga", "Conquistas", "Certificados", "InicioResumo", "Planos"] })
  .injectEndpoints({
    endpoints: (build) => ({
      labTrilho: build.query<Trilho, string>({
        query: (cursoId) => `${P}/courses/${cursoId}/trilho/`,
        providesTags: ["LabTrilho"],
      }),
      licaoParaJogar: build.query<LicaoParaJogar, string>({
        query: (licaoId) => `${P}/lessons/${licaoId}/jogar/`,
        providesTags: ["LabLicao"],
        keepUnusedDataFor: 0,
      }),
      responderExercicio: build.mutation<ResultadoResposta, { challengeId: string; resposta: Resposta }>({
        query: ({ challengeId, resposta }) => ({ url: `${P}/challenge-progress/`, method: "POST", body: { challenge_id: challengeId, ...resposta } }),
      }),
      /** Exercício que não se pode fazer (ou análise indisponível com token): conta como feito, sem pontos nem vidas. */
      saltarExercicio: build.mutation<{ success: boolean; saltado: boolean }, { challengeId: string; token?: string | null }>({
        query: ({ challengeId, token }) => ({ url: `${P}/challenge-progress/`, method: "POST", body: { challenge_id: challengeId, saltar: true, ...(token ? { token_saltar: token } : {}) } }),
      }),
      concluirLicao: build.mutation<ConclusaoLicao, { lessonId: string; segundos: number }>({
        query: ({ lessonId, segundos }) => ({ url: `${P}/complete-lesson/`, method: "POST", body: { lesson_id: lessonId, time_spent: segundos } }),
        // Sem "LabLicao": a lição aberta não recarrega por baixo do ecrã de conclusão.
        invalidatesTags: [...DEPOIS_DE_ESTUDAR],
      }),
      estadoVidas: build.query<EstadoVidas, void>({
        query: () => `${P}/hearts-status/`,
        providesTags: ["LabProgresso"],
      }),
      recarregarVidas: build.mutation<{ hearts: number; points: number; points_spent: number; message: string }, void>({
        query: () => ({ url: `${P}/refill-hearts/`, method: "POST", body: {} }),
        invalidatesTags: ["LabProgresso"],
      }),
      sequencia: build.query<Sequencia, void>({
        query: () => `${P}/study-streak/`,
        providesTags: ["LabSequencia"],
      }),
      cursosPratica: build.query<CursoPratica[], void>({
        query: () => `${P}/courses/`,
        providesTags: ["LabCursos"],
      }),
      progressoPratica: build.query<ProgressoPratica, void>({
        query: () => `${P}/user-progress/`,
        providesTags: ["LabProgresso"],
      }),
      escolherCursoPratica: build.mutation<unknown, string>({
        query: (courseId) => ({ url: `${P}/user-progress/`, method: "PUT", body: { active_course: courseId } }),
        invalidatesTags: ["LabProgresso", "LabTrilho", "LabCursos", "InicioResumo"],
      }),
      labPlanos: build.query<PlanoLab[], void>({
        query: () => "/subscriptions/plans/",
        transformResponse: (r: PlanoLab[] | { results: PlanoLab[] }) => (Array.isArray(r) ? r : r.results).slice().sort((a, b) => a.sort_order - b.sort_order),
        providesTags: ["Planos"],
      }),
    }),
  });

export const {
  useLabTrilhoQuery,
  useLicaoParaJogarQuery,
  useResponderExercicioMutation,
  useSaltarExercicioMutation,
  useConcluirLicaoMutation,
  useEstadoVidasQuery,
  useRecarregarVidasMutation,
  useSequenciaQuery,
  useCursosPraticaQuery,
  useProgressoPraticaQuery,
  useEscolherCursoPraticaMutation,
  useLabPlanosQuery,
} = laboratorioApi;

/** O curso activo pode vir como id ou como objecto. */
export function idCursoActivo(ativo: ProgressoPratica["active_course"] | undefined) {
  if (!ativo) return null;
  return typeof ativo === "string" ? ativo : ativo.id;
}

export const ILIMITADAS = 999;

/** Tempo até à próxima vida: "2 h 40 min". */
export function tempoAte(iso: string | null | undefined) {
  if (!iso) return null;
  const falta = Math.max(0, new Date(iso).getTime() - Date.now());
  const h = Math.floor(falta / 3_600_000);
  const m = Math.ceil((falta % 3_600_000) / 60_000);
  return h ? `${h} h ${m} min` : `${m} min`;
}

/** "1 240" (espaço como separador de milhares, como na web). */
export const fmt = (n: number) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");

/** "14 950 Kz". */
export const kz = (v: number | string | null | undefined) => `${fmt(Number(v ?? 0))} Kz`;

const CATEGORIAS: Record<string, string> = {
  "Industry English": "Petróleo e Gás",
  "Financial English": "Banca",
  "Technical English": "Tecnologia",
  "Business English": "Negócios",
  "General English": "Geral",
  "Medical English": "Saúde",
  "Legal English": "Direito",
  "Technology English": "Tecnologia",
  "Inglês Geral": "Geral",
  "Oil & Gas": "Petróleo e Gás",
  General: "Geral",
  Banking: "Banca",
  Technology: "Tecnologia",
  Executive: "Executivo",
  "AI Enhanced": "Inglês com IA",
};
export const categoriaPt = (c?: string) => (c ? (CATEGORIAS[c] ?? c) : undefined);

/** "nível B1" (aceita "Nível B1" e os nomes antigos). */
export function nivelEmFrase(valor?: string | null) {
  if (!valor) return undefined;
  const v = valor.trim().replace(/^nível\s+/i, "").toUpperCase();
  const antigos: Record<string, string> = { BEGINNER: "A2", INTERMEDIATE: "B1", ADVANCED: "B2" };
  const c = ["A1", "A2", "B1", "B2", "C1", "C2"].includes(v) ? v : antigos[v];
  return c ? `nível ${c}` : undefined;
}
