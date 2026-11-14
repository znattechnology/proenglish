/**
 * Cursos em vídeo do estudante: catálogo, os meus cursos, detalhe, inscrição, aulas, progresso,
 * questionários, notas, certificados e frases da aula.
 * Igual a apps/web/src/domains/student/{inicio,curso}/api.ts, curso/fala.ts e progresso/api.ts (certificados).
 * O acesso a cada curso vem do plano (não há compras de cursos).
 */
import { api } from "@/api/base";

const BASE = "/student/video-courses";

/* ------------------------------------------------------------------ */
/* Tipos (o que a API Django devolve)                                  */
/* ------------------------------------------------------------------ */
export type CursoVideo = {
  courseId: string;
  title: string;
  description?: string;
  category?: string;
  image?: string;
  level?: string;
  teacherName?: string;
  access_level?: string;
  access_level_display?: string;
  is_free?: boolean;
  is_premium?: boolean;
  user_has_access?: boolean;
};

export type ProgressoResumo = { courseId?: string; overallProgress: number; lastAccessedTimestamp?: string };

export type TipoCapitulo = "Video" | "Text" | "Quiz" | "Exercise";
export type NivelAcesso = "free" | "premium" | "premium_plus";

export type OpcaoQuiz = { id: string; text: string };
export type PerguntaQuiz = { id: string; question: string; points?: number; options: OpcaoQuiz[] };
export type QuizData = { title?: string; settings?: { passingScore?: number; maxAttempts?: number; timeLimit?: number | null }; questions: PerguntaQuiz[] };

export type Capitulo = {
  chapterId: string;
  title: string;
  type: TipoCapitulo;
  order: number;
  duracao_s?: number | null;
  content?: string;
  video?: string;
  transcript?: string;
  quiz_enabled?: boolean;
  quiz_data?: QuizData | null;
  practice_lesson?: string | null;
};

export type Seccao = { sectionId: string; sectionTitle: string; sectionDescription?: string; order: number; chapters: Capitulo[] };

export type Curso = {
  courseId: string;
  title: string;
  description: string;
  category: string;
  image: string;
  level: string;
  teacherName: string;
  teacherId?: string;
  sections: Seccao[];
  total_chapters: number;
  access_level: NivelAcesso;
  access_level_display: string;
  user_has_access: boolean;
};

export type ProfessorPublico = {
  id: string;
  nome: string;
  iniciais: string;
  fotografia: string | null;
  cidade: string;
  especialidade: string;
  experiencia: string;
  sobre: string;
  desde: string | null;
  cursos_publicados: number;
  alunos: number;
};

export type DetalheCurso = { curso: Curso; temAcesso: boolean; conteudoLimitado: boolean };
export type EstadoInscricao = { is_enrolled: boolean; has_access: boolean; can_enroll: boolean; access_level: NivelAcesso };

export type Progresso = {
  overallProgress: number;
  /** video_visto: numa aula com questionário, o vídeo já foi visto (a aula só conclui ao passar). */
  sections: { sectionId: string; chapters: { chapterId: string; completed: boolean; video_visto?: boolean }[] }[];
  lastAccessedTimestamp?: string;
};

export type Recurso = { id: string; title: string; description?: string; resource_type: string; file_url?: string | null; external_url?: string | null };

export type ResumoQuiz = { attempts_count: number; best_score: number; is_passed: boolean; attempts_remaining: number; quiz_info?: { passing_score: number; max_attempts: number } };

export type ResultadoQuiz = {
  score: number;
  max_score: number;
  score_percentage: number;
  is_passed: boolean;
  attempt_number: number;
  tentativas_restantes: number;
  /** As respostas certas só vêm quando passou ou já não tem tentativas. */
  revela_respostas?: boolean;
  correccao: { pergunta: string; certa: boolean; respondida: boolean; opcoes_certas?: string[]; explicacao?: string | null }[];
};

export type Requisito = { met: boolean; required: number | null; actual: number | null; message: string; info_only?: boolean };

export type Notas = {
  grades: {
    quizzes: {
      score: number;
      count: number;
      completed: number;
      passed: number;
      details: { quiz_id: string; quiz_title: string; chapter_title: string; section_title: string; score: number; is_passed: boolean; attempts_used: number; max_attempts: number; passing_score: number }[];
    };
    practice: { score: number; count: number; completed: number };
    conversation: { score: number; sessions: number; minutes: number; required: boolean };
  };
  final_grade: { percentage: number; letter: string };
  weight_info: {
    quiz_weight: number;
    practice_weight: number;
    conversation_weight: number;
    exam_weight?: number;
    phrases_weight?: number;
    study_weight?: number;
    study_score?: number | null;
    active_components: string[];
  };
  exame_oral?: { score: number | null; passed: boolean; attempts: number; min_score: number | null };
  frases_curso?: { score: number; total: number; mastered: number };
  certificate_eligibility: {
    is_eligible: boolean;
    pode_emitir?: boolean;
    progresso?: number;
    nota_minima?: number;
    plano_inclui_certificados?: boolean;
    details: Record<string, Requisito>;
  };
  nota_minima?: number;
  plano_inclui_certificados?: boolean;
};

export type NotasDeTodos = {
  courses: {
    course: { id: string; title: string; thumbnail: string | null; level: string; category: string };
    final_grade: { percentage: number; letter: string };
    is_eligible_for_certificate: boolean;
    grading_mode: "full" | "simplified" | "no_content" | string;
    active_components: string[];
    missing_requirements?: { requirement: string; message: string; required: number | null; actual: number | null }[];
    pode_emitir_certificado?: boolean;
    progresso?: number;
    nota_minima?: number;
  }[];
  summary: { total_courses: number; courses_with_grades: number; average_grade: { percentage: number; letter: string } | number; certificates_earned: number; eligible_for_certificate: number };
};

/** Estado do exame oral (só o que o cartão da página do curso precisa; o ecrã do exame é do agente da conversa). */
export type EstadoExameCurso = {
  disponivel: boolean;
  motivo: null | "progresso" | "aprovado" | "aguardar" | "tentativas" | "curso_pratica" | "desligado";
  mensagem: string | null;
  duracao_minutos: number;
  nota_minima: number;
  aprovado: boolean;
  tentativas: { estado: string; nivel_cefr?: string | null }[];
};

export type RequisitoCertificado = { requisito: string; mensagem: string; necessario: number | null; atual: number | null };
export type NotaFala = { chave: string; nome: string; nota: number };
export type Certificados = {
  plano_inclui_certificados: boolean;
  certificados: {
    id: string;
    numero: string;
    curso: { id: string; titulo: string; imagem: string | null };
    emitido_em: string;
    nota_final: number;
    nota_letra?: string;
    nivel_fala?: string | null;
    nivel_fala_texto?: string | null;
    notas_fala?: NotaFala[];
    estado: "valido" | "revogado";
    ligacao_verificacao: string;
    pdf_url: string;
  }[];
  em_curso: { curso: { id: string; titulo: string }; progresso: number; nota_final: number; nota_minima: number; pode_emitir: boolean; em_falta: RequisitoCertificado[] }[];
};

/* Frases da aula ("Repetir em voz alta") */
export type EstadoBanco = "vista" | "reconhecida" | "com_ajuda" | "sozinho";
export type FraseDaAula = { id: number; texto: string; traducao: string; tipo: "frase" | "palavra"; inicio: number | null; fim: number | null; estado: EstadoBanco | null };
export type FalaDaAula = { frases: FraseDaAula[]; conversa: { disponivel: boolean; motivo: string | null; mensagem: string | null; max_segundos: number } };
export type DetalhePronuncia = { palavras: { palavra: string; nota: number | null; erro_tipo: string }[]; fluencia: number | null; completude: number | null; prosodia: number | null; dica: string | null; fonte: string };
export type AnaliseGravacao = { nota: number; aceite: boolean; transcricao: string; palavras: string[]; mensagem: string | null; detalhe?: DetalhePronuncia | null };
export type AnaliseFrase = { analise: AnaliseGravacao; estado: EstadoBanco | null };

export type PlanoActual = { plan: { name: string; plan_type: string }; status?: string };

type Envelope<T> = { message?: string; data: T };
const dados = <T,>(r: Envelope<T> | T) => (r && typeof r === "object" && "data" in (r as object) ? (r as Envelope<T>).data : (r as T));

/** Depois de mudar o progresso: estatísticas, liga, conquistas e certificados (de outros domínios) mudam. */
const DEPOIS_DE_ESTUDAR = ["Estatisticas", "Liga", "Conquistas", "Certificados", "InicioResumo"] as const;

export const cursosApi = api
  .enhanceEndpoints({
    addTagTypes: ["CursosCatalogo", "MeusCursos", "ProgressoCurso", "Curso", "Inscricao", "Quiz", "NotasCurso", "Certificados", "FalaAula", "Exame", "Estatisticas", "Liga", "Conquistas", "InicioResumo"],
  })
  .injectEndpoints({
    endpoints: (build) => ({
      catalogoCursos: build.query<{ total: number; cursos: CursoVideo[] }, void>({
        // O catálogo cabe numa página (o filtro por área e a procura sem acentos fazem-se na app).
        query: () => ({ url: `${BASE}/`, params: { status: "Published", page_size: 50 } }),
        transformResponse: (r: Envelope<{ count: number; results: CursoVideo[] }>) => ({ total: r.data?.count ?? 0, cursos: r.data?.results ?? [] }),
        providesTags: ["CursosCatalogo"],
      }),
      meusCursos: build.query<CursoVideo[], string>({
        query: (userId) => `${BASE}/users/${userId}/enrolled/`,
        transformResponse: (r: Envelope<CursoVideo[]>) => r.data ?? [],
        providesTags: ["MeusCursos"],
      }),
      /** Progresso num curso. 404 quer dizer que ainda não começou: é progresso zero (null), não um erro. */
      progressoCurso: build.query<Progresso | null, { userId: string; courseId: string }>({
        queryFn: async ({ userId, courseId }, _api, _extra, baseQuery) => {
          const r = await baseQuery(`${BASE}/users/${userId}/progress/${courseId}/`);
          if (r.error) return r.error.status === 404 ? { data: null } : { error: r.error };
          const corpo = r.data as Envelope<Progresso> & Partial<Progresso>;
          return { data: (corpo.data ?? (corpo as Progresso)) || null };
        },
        providesTags: (_r, _e, a) => [{ type: "ProgressoCurso", id: a.courseId }],
      }),
      cursoDetalhe: build.query<DetalheCurso, string>({
        query: (id) => `${BASE}/${id}/`,
        transformResponse: (r: Envelope<Curso> & { access_info?: { has_access: boolean; content_limited: boolean } }) => ({
          curso: {
            ...r.data,
            sections: (r.data.sections ?? [])
              .slice()
              .sort((a, b) => a.order - b.order)
              .map((s) => ({ ...s, chapters: (s.chapters ?? []).slice().sort((a, b) => a.order - b.order) })),
          },
          temAcesso: r.access_info?.has_access ?? r.data.user_has_access,
          conteudoLimitado: !!r.access_info?.content_limited,
        }),
        providesTags: (_r, _e, id) => [{ type: "Curso", id }],
      }),
      professorPublico: build.query<ProfessorPublico, string>({
        query: (id) => `/professores/${id}/`,
        keepUnusedDataFor: 600,
      }),
      inscricaoCurso: build.query<EstadoInscricao, string>({
        query: (id) => `${BASE}/${id}/enrollment-status/`,
        transformResponse: dados<EstadoInscricao>,
        providesTags: (_r, _e, id) => [{ type: "Inscricao", id }],
      }),
      inscreverCurso: build.mutation<unknown, string>({
        query: (courseId) => ({ url: `${BASE}/transactions/create/`, method: "POST", body: { courseId } }),
        invalidatesTags: (_r, _e, id) => [{ type: "Inscricao", id }, { type: "Curso", id }, { type: "ProgressoCurso", id }, { type: "NotasCurso", id: "TODAS" }, "MeusCursos", "CursosCatalogo", ...DEPOIS_DE_ESTUDAR],
      }),
      capituloCurso: build.query<Capitulo, string>({
        query: (id) => `${BASE}/chapters/${id}/`,
        transformResponse: dados<Capitulo>,
      }),
      recursosCapitulo: build.query<Recurso[], string>({
        query: (id) => `${BASE}/chapters/${id}/resources/`,
        transformResponse: (r: Envelope<Recurso[]> | Recurso[]) => dados(r) ?? [],
      }),
      marcarCapitulo: build.mutation<Progresso, { userId: string; courseId: string; sectionId: string; chapterId: string; concluido: boolean; segundos?: number }>({
        query: ({ userId, courseId, sectionId, chapterId, concluido, segundos }) => ({
          url: `${BASE}/users/${userId}/progress/${courseId}/update/`,
          method: "PUT",
          body: { sections: [{ sectionId, chapters: [{ chapterId, completed: concluido }] }], ...(segundos ? { watched_seconds: Math.round(segundos) } : {}) },
        }),
        transformResponse: dados<Progresso>,
        invalidatesTags: (_r, _e, a) => [{ type: "ProgressoCurso", id: a.courseId }, { type: "NotasCurso", id: a.courseId }, { type: "NotasCurso", id: "TODAS" }, "MeusCursos", ...DEPOIS_DE_ESTUDAR],
      }),
      resumoQuiz: build.query<ResumoQuiz | null, string>({
        query: (chapterId) => `${BASE}/chapters/${chapterId}/quiz/summary/`,
        transformResponse: (r: Envelope<ResumoQuiz | null>) => r?.data ?? null,
        providesTags: (_r, _e, id) => [{ type: "Quiz", id }],
      }),
      responderQuiz: build.mutation<ResultadoQuiz, { chapterId: string; courseId: string; respostas: Record<string, string>; segundos: number }>({
        query: ({ chapterId, respostas, segundos }) => ({ url: `${BASE}/chapters/${chapterId}/quiz/attempts/`, method: "POST", body: { respostas, time_taken: Math.round(segundos) } }),
        transformResponse: dados<ResultadoQuiz>,
        // Passar o questionário pode concluir a aula: o progresso volta a ser lido.
        invalidatesTags: (_r, _e, a) => [{ type: "Quiz", id: a.chapterId }, { type: "ProgressoCurso", id: a.courseId }, { type: "NotasCurso", id: a.courseId }, { type: "NotasCurso", id: "TODAS" }, "MeusCursos", ...DEPOIS_DE_ESTUDAR],
      }),
      notasDeTodos: build.query<NotasDeTodos, void>({
        query: () => `${BASE}/grades/all/`,
        transformResponse: dados<NotasDeTodos>,
        providesTags: [{ type: "NotasCurso", id: "TODAS" }],
      }),
      notasCurso: build.query<Notas, string>({
        query: (courseId) => `${BASE}/${courseId}/grade/`,
        transformResponse: dados<Notas>,
        providesTags: (_r, _e, id) => [{ type: "NotasCurso", id }],
      }),
      cursoExameEstado: build.query<EstadoExameCurso, string>({
        query: (courseId) => `${BASE}/${courseId}/exame/`,
        providesTags: (_r, _e, id) => [{ type: "Exame", id }],
      }),
      cursoCertificados: build.query<Certificados, void>({
        query: () => `${BASE}/certificados/`,
        providesTags: ["Certificados"],
      }),
      emitirCertificadoCurso: build.mutation<unknown, string>({
        query: (courseId) => ({ url: `${BASE}/${courseId}/certificado/`, method: "POST", body: {} }),
        invalidatesTags: ["Certificados", { type: "NotasCurso", id: "TODAS" }],
      }),
      falaDaAula: build.query<FalaDaAula, string>({
        query: (chapterId) => `${BASE}/chapters/${chapterId}/fala/`,
        providesTags: (_r, _e, id) => [{ type: "FalaAula", id }],
      }),
      cursosPlanoActual: build.query<PlanoActual, void>({
        query: () => "/subscriptions/my-subscription/",
      }),
    }),
  });

export const {
  useCatalogoCursosQuery,
  useMeusCursosQuery,
  useProgressoCursoQuery,
  useCursoDetalheQuery,
  useProfessorPublicoQuery,
  useInscricaoCursoQuery,
  useInscreverCursoMutation,
  useCapituloCursoQuery,
  useRecursosCapituloQuery,
  useMarcarCapituloMutation,
  useResumoQuizQuery,
  useResponderQuizMutation,
  useNotasDeTodosQuery,
  useNotasCursoQuery,
  useCursoExameEstadoQuery,
  useCursoCertificadosQuery,
  useEmitirCertificadoCursoMutation,
  useFalaDaAulaQuery,
  useCursosPlanoActualQuery,
} = cursosApi;

/* ------------------------------------------------------------------ */
/* Ajudas                                                              */
/* ------------------------------------------------------------------ */
export type CapituloNoCurso = Capitulo & { sectionId: string; seccao: string; indiceSeccao: number; numero: number; numeroNaSeccao: number; totalNaSeccao: number };

/** Lista plana dos capítulos pela ordem do curso, com o número de cada um. */
export function capitulosPorOrdem(curso: Curso): CapituloNoCurso[] {
  const lista: CapituloNoCurso[] = [];
  curso.sections.forEach((s, i) =>
    s.chapters.forEach((c, j) =>
      lista.push({ ...c, sectionId: s.sectionId, seccao: s.sectionTitle, indiceSeccao: i + 1, numero: lista.length + 1, numeroNaSeccao: j + 1, totalNaSeccao: s.chapters.length })
    )
  );
  return lista;
}

export function concluidos(p: Progresso | null | undefined) {
  return new Set((p?.sections ?? []).flatMap((s) => s.chapters.filter((c) => c.completed).map((c) => c.chapterId)));
}

/** Aulas com o vídeo visto (concluídas ou à espera de passar o questionário). */
export function videosVistos(p: Progresso | null | undefined) {
  return new Set((p?.sections ?? []).flatMap((s) => s.chapters.filter((c) => c.completed || c.video_visto).map((c) => c.chapterId)));
}

/** A aula tem um questionário (aulas do tipo Questionário ou outras com questionário ligado). */
export function temQuestionario(c: Pick<Capitulo, "type" | "quiz_enabled" | "quiz_data">) {
  return c.type === "Quiz" || (!!c.quiz_enabled && !!c.quiz_data?.questions?.length);
}

export const TIPO_PT: Record<TipoCapitulo, string> = { Video: "Vídeo", Text: "Leitura", Quiz: "Questionário", Exercise: "Prática" };

export const PLANO_DO_CURSO: Record<NivelAcesso, { nome: string; tipo: "FREE" | "PREMIUM" | "PREMIUM_PLUS" }> = {
  free: { nome: "Gratuito", tipo: "FREE" },
  premium: { nome: "Premium", tipo: "PREMIUM" },
  premium_plus: { nome: "Premium Plus", tipo: "PREMIUM_PLUS" },
};

const CATEGORIAS: Record<string, string> = {
  "Industry English": "Petróleo e Gás",
  "Financial English": "Banca",
  "Technical English": "Tecnologia",
  "Business English": "Negócios",
  "General English": "Geral",
  "Medical English": "Saúde",
  "Legal English": "Direito",
  "Technology English": "Tecnologia",
};

/** Área do curso em português (a API devolve algumas em inglês). */
export function categoriaPt(categoria?: string) {
  if (!categoria) return undefined;
  return CATEGORIAS[categoria] ?? categoria;
}

/* Níveis (CEFR), como apps/web/src/domains/shared/niveis.ts */
const NIVEIS = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;
type Nivel = (typeof NIVEIS)[number];
const NOME_NIVEL: Record<Nivel, string> = { A1: "Iniciante", A2: "Elementar", B1: "Intermédio", B2: "Intermédio avançado", C1: "Avançado", C2: "Proficiente" };
const ANTIGOS: Record<string, Nivel> = { Beginner: "A2", Intermediate: "B1", Advanced: "B2" };

function normalizarNivel(valor?: string | null): Nivel | undefined {
  if (!valor) return undefined;
  const v = valor.trim().replace(/^nível\s+/i, "");
  if ((NIVEIS as readonly string[]).includes(v.toUpperCase())) return v.toUpperCase() as Nivel;
  return ANTIGOS[v];
}

/** "nível B1" (a meio de uma frase). */
export function nivelEmFrase(valor?: string | null) {
  const c = normalizarNivel(valor);
  return c ? `nível ${c}` : undefined;
}

/** "B1 (Intermédio)". */
export function nomeCompletoNivel(valor?: string | null) {
  const c = normalizarNivel(valor);
  return c ? `${c} (${NOME_NIVEL[c]})` : undefined;
}

/** Linha de contexto do curso: área e nível, em português. */
export function contextoCurso(c: { category?: string; level?: string }) {
  return [categoriaPt(c.category), nivelEmFrase(c.level)].filter(Boolean).join(", ");
}

const MESES_CURTOS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
export function diaMesCurto(d: Date, comAno = false) {
  return `${d.getDate()} ${MESES_CURTOS[d.getMonth()]}${comAno ? ` ${d.getFullYear()}` : ""}`;
}

/** "Hoje", "Ontem", "Há 5 dias", "3 Nov" (última vez que abriu o curso). */
export function vistoHa(iso?: string, agora = Date.now()) {
  if (!iso) return undefined;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return undefined;
  const hoje = new Date(agora);
  hoje.setHours(0, 0, 0, 0);
  const dia = new Date(d);
  dia.setHours(0, 0, 0, 0);
  const dias = Math.round((hoje.getTime() - dia.getTime()) / 86_400_000);
  if (dias <= 0) return "Hoje";
  if (dias === 1) return "Ontem";
  if (dias < 7) return `Há ${dias} dias`;
  return diaMesCurto(d, d.getFullYear() !== hoje.getFullYear());
}

/** Minutos de uma aula a partir da duração em segundos ("8 min"). */
export function duracaoAula(s?: number | null) {
  if (!s) return undefined;
  return `${Math.max(1, Math.round(s / 60))} min`;
}
