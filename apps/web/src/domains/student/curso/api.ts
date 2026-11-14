/**
 * Curso em vídeo do estudante: detalhe, inscrição, capítulos, progresso, questionários e notas.
 * Tipos iguais ao que a API Django devolve (/api/v1/student/video-courses/...).
 * O acesso a cada curso vem do plano (não há compras de cursos).
 */
import { createApi } from "@reduxjs/toolkit/query/react";
import { aposCurso, quandoCorrerBem } from "@/src/domains/student/sincronizar";
import { sharedBaseQuery } from "@/src/domains/shared/api/baseQuery";

const BASE = "/student/video-courses";

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
  /* Só para quem está inscrito: */
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
  sections: { sectionId: string; chapters: { chapterId: string; completed: boolean }[] }[];
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
    quizzes: { score: number; count: number; completed: number; passed: number; details: { quiz_id: string; quiz_title: string; chapter_title: string; section_title: string; score: number; is_passed: boolean; attempts_used: number; max_attempts: number; passing_score: number }[] };
    practice: { score: number; count: number; completed: number };
    conversation: { score: number; sessions: number; minutes: number; required: boolean };
  };
  final_grade: { percentage: number; letter: string };
  weight_info: { quiz_weight: number; practice_weight: number; conversation_weight: number; active_components: string[] };
  certificate_eligibility: {
    is_eligible: boolean;
    /** Elegível e o plano inclui certificados. */
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

type Envelope<T> = { message?: string; data: T };
const dados = <T,>(r: Envelope<T> | T) => (r && typeof r === "object" && "data" in (r as object) ? (r as Envelope<T>).data : (r as T));

export const cursoApi = createApi({
  reducerPath: "cursoApi",
  baseQuery: sharedBaseQuery,
  tagTypes: ["Curso", "Progresso", "Inscricao", "Quiz", "Notas"],
  endpoints: (build) => ({
    curso: build.query<DetalheCurso, string>({
      query: (id) => `${BASE}/${id}/`,
      transformResponse: (r: Envelope<Curso> & { access_info?: { has_access: boolean; content_limited: boolean } }) => ({
        curso: { ...r.data, sections: (r.data.sections ?? []).slice().sort((a, b) => a.order - b.order).map((s) => ({ ...s, chapters: (s.chapters ?? []).slice().sort((a, b) => a.order - b.order) })) },
        temAcesso: r.access_info?.has_access ?? r.data.user_has_access,
        conteudoLimitado: !!r.access_info?.content_limited,
      }),
      providesTags: (_r, _e, id) => [{ type: "Curso", id }],
    }),
    professorPublico: build.query<ProfessorPublico, string>({
      query: (id) => `/professores/${id}/`,
      keepUnusedDataFor: 600,
    }),
    inscricao: build.query<EstadoInscricao, string>({
      query: (id) => `${BASE}/${id}/enrollment-status/`,
      transformResponse: dados<EstadoInscricao>,
      providesTags: (_r, _e, id) => [{ type: "Inscricao", id }],
    }),
    inscrever: build.mutation<unknown, string>({
      query: (courseId) => ({ url: `${BASE}/transactions/create/`, method: "POST", body: { courseId } }),
      invalidatesTags: (_r, _e, id) => [{ type: "Inscricao", id }, { type: "Curso", id }, { type: "Progresso", id }, { type: "Notas", id: "TODAS" }],
      onQueryStarted: quandoCorrerBem(aposCurso),
    }),
    capitulo: build.query<Capitulo & { resources_data?: unknown[] }, string>({
      query: (id) => `${BASE}/chapters/${id}/`,
    }),
    recursos: build.query<Recurso[], string>({
      query: (id) => `${BASE}/chapters/${id}/resources/`,
      transformResponse: (r: Envelope<Recurso[]> | Recurso[]) => dados(r) ?? [],
    }),
    progresso: build.query<Progresso | null, { userId: string; courseId: string }>({
      query: ({ userId, courseId }) => `${BASE}/users/${userId}/progress/${courseId}/`,
      transformResponse: (r: Envelope<Progresso>) => r?.data ?? null,
      providesTags: (_r, _e, a) => [{ type: "Progresso", id: a.courseId }],
    }),
    marcarCapitulo: build.mutation<Progresso, { userId: string; courseId: string; sectionId: string; chapterId: string; concluido: boolean; segundos?: number }>({
      query: ({ userId, courseId, sectionId, chapterId, concluido, segundos }) => ({
        url: `${BASE}/users/${userId}/progress/${courseId}/update/`,
        method: "PUT",
        body: { sections: [{ sectionId, chapters: [{ chapterId, completed: concluido }] }], ...(segundos ? { watched_seconds: Math.round(segundos) } : {}) },
      }),
      transformResponse: dados<Progresso>,
      invalidatesTags: (_r, _e, a) => [{ type: "Progresso", id: a.courseId }, { type: "Notas", id: a.courseId }, { type: "Notas", id: "TODAS" }],
      onQueryStarted: quandoCorrerBem(aposCurso),
    }),
    resumoQuiz: build.query<ResumoQuiz | null, string>({
      query: (chapterId) => `${BASE}/chapters/${chapterId}/quiz/summary/`,
      transformResponse: (r: Envelope<ResumoQuiz | null>) => r?.data ?? null,
      providesTags: (_r, _e, id) => [{ type: "Quiz", id }],
    }),
    responderQuiz: build.mutation<ResultadoQuiz, { chapterId: string; courseId: string; respostas: Record<string, string>; segundos: number }>({
      query: ({ chapterId, respostas, segundos }) => ({ url: `${BASE}/chapters/${chapterId}/quiz/attempts/`, method: "POST", body: { respostas, time_taken: Math.round(segundos) } }),
      transformResponse: dados<ResultadoQuiz>,
      invalidatesTags: (_r, _e, a) => [{ type: "Quiz", id: a.chapterId }, { type: "Notas", id: a.courseId }, { type: "Notas", id: "TODAS" }],
      onQueryStarted: quandoCorrerBem(aposCurso),
    }),
    notasDeTodos: build.query<NotasDeTodos, void>({
      query: () => `${BASE}/grades/all/`,
      transformResponse: dados<NotasDeTodos>,
      providesTags: [{ type: "Notas", id: "TODAS" }],
    }),
    notas: build.query<Notas, string>({
      query: (courseId) => `${BASE}/${courseId}/grade/`,
      transformResponse: dados<Notas>,
      providesTags: (_r, _e, id) => [{ type: "Notas", id }],
    }),
  }),
});

export const {
  useCursoQuery,
  useProfessorPublicoQuery,
  useInscricaoQuery,
  useInscreverMutation,
  useCapituloQuery,
  useRecursosQuery,
  useProgressoQuery,
  useMarcarCapituloMutation,
  useResumoQuizQuery,
  useResponderQuizMutation,
  useNotasQuery,
  useNotasDeTodosQuery,
} = cursoApi;

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

export const TIPO_PT: Record<TipoCapitulo, string> = { Video: "Vídeo", Text: "Leitura", Quiz: "Questionário", Exercise: "Prática" };

export const PLANO_DO_CURSO: Record<NivelAcesso, { nome: string; tipo: "FREE" | "PREMIUM" | "PREMIUM_PLUS" }> = {
  free: { nome: "Gratuito", tipo: "FREE" },
  premium: { nome: "Premium", tipo: "PREMIUM" },
  premium_plus: { nome: "Premium Plus", tipo: "PREMIUM_PLUS" },
};
