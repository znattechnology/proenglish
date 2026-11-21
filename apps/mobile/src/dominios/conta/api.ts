/**
 * Conta: criar, confirmar o email, recuperar e mudar a palavra-passe, entrar com o Google e
 * a primeira entrada (área, meta diária, nível e o primeiro curso).
 * Igual a apps/web/src/domains/auth/services/authApi.ts e às partes de perfil/inicio/laboratorio
 * que a página web da primeira entrada usa.
 *
 * Com `X-Cliente: app`, verify-email, Google e change-password devolvem `{ user?, tokens }` no
 * corpo: essa resposta vai para `iniciar()` da sessão.
 */
import { api } from "@/api/base";
import type { RespostaSessao } from "@/sessao/ContextoSessao";
import type { NivelCefr } from "./niveis";

export type Preferencias = { cidade?: string | null; area?: string | null; nivel?: NivelCefr | null; acolhimento?: "concluido" | null };

export type CursoVideoSugerido = { courseId: string; title: string; category?: string; level?: string | null; de_sector?: boolean };
export type CursoPraticaSugerido = { id: string; title: string; category?: string; level?: string | null; de_sector?: boolean; requisito_basico?: boolean };

type Paginado<T> = { data?: { count: number; results: T[] } };

export const contaApi = api.enhanceEndpoints({ addTagTypes: ["Perfil", "Meta", "MetaEstudo", "LabProgresso", "LabTrilho", "LabCursos"] }).injectEndpoints({
  endpoints: (build) => ({
    contaRegistar: build.mutation<{ message: string; email: string; requires_verification: boolean }, { name: string; email: string; password: string; password_confirm: string }>({
      query: (body) => ({ url: "/users/register/", method: "POST", body: { ...body, role: "student" } }),
    }),
    contaVerificarEmail: build.mutation<RespostaSessao & { message?: string }, { email: string; code: string }>({
      query: (body) => ({ url: "/users/verify-email/", method: "POST", body }),
    }),
    contaReenviarCodigo: build.mutation<{ message: string; aguardar_segundos?: number }, { email: string }>({
      query: (body) => ({ url: "/users/resend-verification/", method: "POST", body }),
    }),
    contaPedirRecuperacao: build.mutation<{ message: string }, { email: string }>({
      query: (body) => ({ url: "/users/password-reset/", method: "POST", body }),
    }),
    contaConfirmarRecuperacao: build.mutation<{ message: string }, { email: string; code: string; newPassword: string }>({
      query: (body) => ({ url: "/users/password-reset-confirm/", method: "POST", body }),
    }),
    contaGoogle: build.mutation<RespostaSessao & { message?: string }, { id_token: string }>({
      query: (body) => ({ url: "/users/oauth/google/login/", method: "POST", body }),
    }),
    /** Mudar (ou criar, nas contas do Google) a palavra-passe. `refresh_token` mantém esta sessão viva. */
    contaMudarSenha: build.mutation<RespostaSessao & { message: string; has_password?: boolean }, { actual: string; nova: string; confirmar: string; refresh: string | null }>({
      query: ({ actual, nova, confirmar, refresh }) => ({
        url: "/users/change-password/",
        method: "POST",
        body: { ...(actual ? { current_password: actual } : {}), new_password: nova, new_password_confirm: confirmar, ...(refresh ? { refresh_token: refresh } : {}) },
      }),
      invalidatesTags: ["Perfil"],
    }),

    /* Primeira entrada */
    peGuardarPreferencias: build.mutation<unknown, Preferencias>({
      query: (preferences) => ({ url: "/users/profile/", method: "PATCH", body: { preferences } }),
      invalidatesTags: ["Perfil"],
    }),
    peMeta: build.query<{ daily_goal_minutes: number }, void>({
      query: () => "/student/practice-courses/study-goal/",
      providesTags: ["Meta"],
    }),
    peMudarMeta: build.mutation<{ daily_goal_minutes: number }, number>({
      query: (minutos) => ({ url: "/student/practice-courses/study-goal/", method: "PATCH", body: { daily_goal_minutes: minutos } }),
      // MetaEstudo é a etiqueta da meta no domínio perfil.
      invalidatesTags: ["Meta", "MetaEstudo"],
    }),
    peCursosVideoDaArea: build.query<CursoVideoSugerido[], string | null>({
      query: (categoria) => ({ url: "/student/video-courses/", params: { status: "Published", page_size: 50, ...(categoria ? { category: categoria } : {}) } }),
      transformResponse: (r: Paginado<CursoVideoSugerido>) => r.data?.results ?? [],
    }),
    peCursosPratica: build.query<CursoPraticaSugerido[], void>({
      query: () => "/student/practice-courses/courses/",
    }),
    peEscolherCursoPratica: build.mutation<unknown, string>({
      query: (courseId) => ({ url: "/student/practice-courses/user-progress/", method: "PUT", body: { active_course: courseId } }),
      // Etiquetas do domínio laboratorio: o separador Praticar mostra logo o curso escolhido.
      invalidatesTags: ["LabProgresso", "LabTrilho", "LabCursos"],
    }),
  }),
});

export const {
  useContaRegistarMutation,
  useContaVerificarEmailMutation,
  useContaReenviarCodigoMutation,
  useContaPedirRecuperacaoMutation,
  useContaConfirmarRecuperacaoMutation,
  useContaGoogleMutation,
  useContaMudarSenhaMutation,
  usePeGuardarPreferenciasMutation,
  usePeMetaQuery,
  usePeMudarMetaMutation,
  usePeCursosVideoDaAreaQuery,
  usePeCursosPraticaQuery,
  usePeEscolherCursoPraticaMutation,
} = contaApi;

/** Erros por campo do Django (`{email: [...]}` ou `{details: {email: [...]}}`), para mostrar junto de cada campo. */
export function errosPorCampo(e: unknown): Record<string, string> {
  const d = (e as { data?: unknown } | undefined)?.data as Record<string, unknown> | undefined;
  if (!d || typeof d !== "object") return {};
  const fonte = d.details && typeof d.details === "object" ? (d.details as Record<string, unknown>) : d;
  const r: Record<string, string> = {};
  for (const [k, v] of Object.entries(fonte)) {
    const m = typeof v === "string" ? v : Array.isArray(v) && typeof v[0] === "string" ? v[0] : null;
    if (m && !["error", "detail", "message", "code", "codigo", "mensagem", "non_field_errors"].includes(k)) r[k] = m;
  }
  return r;
}

/** Segundos de espera que a API manda nos erros de "pedir outro código". */
export function segundosDoErro(e: unknown) {
  const n = (e as { data?: { aguardar_segundos?: number } } | undefined)?.data?.aguardar_segundos;
  return typeof n === "number" ? n : null;
}

export const EMAIL_VALIDO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
