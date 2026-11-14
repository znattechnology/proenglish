/**
 * Dados das telas novas do estudante (Início e Cursos).
 *
 * Os tipos aqui seguem o que a API Django devolve de facto (verificado contra
 * /api/v1/student/video-courses/...). As fatias antigas declaram formatos que a API
 * não devolve, por isso estes endpoints são injectados com tipos correctos.
 */
import { studentVideoCourseApiSlice } from "../video-courses/api/studentVideoCourseApiSlice";

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

export type ProgressoCurso = {
  courseId: string;
  overallProgress: number;
  lastAccessedTimestamp?: string;
};

export type Subscricao = {
  plan: { name: string; plan_type: "FREE" | "PREMIUM" | "PREMIUM_PLUS" | string };
  status?: string;
};

const API = process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://localhost:8000/api/v1";

type Paginado<T> = {
  message?: string;
  data: { count: number; results: T[] };
};

export const estudanteApi = studentVideoCourseApiSlice.injectEndpoints({
  endpoints: (build) => ({
    /** Catálogo de cursos em vídeo publicados. */
    catalogoCursos: build.query<{ total: number; cursos: CursoVideo[] }, { procura?: string; categoria?: string } | void>({
      query: (f) => ({
        url: "/",
        params: {
          status: "Published",
          // O catálogo cabe numa página (o filtro por área e a procura sem acentos fazem-se no browser).
          page_size: 50,
          ...(f?.procura ? { search: f.procura } : {}),
          ...(f?.categoria ? { category: f.categoria } : {}),
        },
      }),
      transformResponse: (r: Paginado<CursoVideo>) => ({ total: r.data?.count ?? 0, cursos: r.data?.results ?? [] }),
      providesTags: ["StudentVideoCourse"],
    }),

    /** Cursos em vídeo em que o estudante está inscrito. */
    meusCursos: build.query<CursoVideo[], string>({
      query: (userId) => `/users/${userId}/enrolled/`,
      transformResponse: (r: { data: CursoVideo[] }) => r.data ?? [],
      providesTags: ["CourseEnrollment"],
    }),

    /**
     * Progresso num curso. A API responde 404 quando o estudante ainda não começou;
     * isso não é um erro para a interface: é progresso zero.
     */
    progressoCurso: build.query<ProgressoCurso | null, { userId: string; courseId: string }>({
      queryFn: async ({ userId, courseId }, _api, _extra, baseQuery) => {
        const r = await baseQuery(`/users/${userId}/progress/${courseId}/`);
        if (r.error) {
          if (r.error.status === 404) return { data: null };
          return { error: r.error };
        }
        const corpo = r.data as { data?: ProgressoCurso } & Partial<ProgressoCurso>;
        return { data: (corpo.data ?? (corpo as ProgressoCurso)) || null };
      },
      providesTags: ["VideoProgress"],
    }),

    /** Plano actual da pessoa (Gratuito, Premium, Premium Plus). */
  }),
  overrideExisting: false,
});

export const { useCatalogoCursosQuery, useMeusCursosQuery, useProgressoCursoQuery } = estudanteApi;

/* ------------------------------------------------------------------ */
/* Texto para o estudante (a API devolve alguns valores em inglês).    */
/* ------------------------------------------------------------------ */
const NIVEIS: Record<string, string> = {
  Beginner: "Iniciante",
  Intermediate: "Intermédio",
  Advanced: "Avançado",
};

export function nivelPt(nivel?: string) {
  if (!nivel) return undefined;
  return NIVEIS[nivel] ?? nivel;
}

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

export function categoriaPt(categoria?: string) {
  if (!categoria) return undefined;
  return CATEGORIAS[categoria] ?? categoria;
}
