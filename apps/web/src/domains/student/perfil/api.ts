/**
 * Perfil e definições: dados da pessoa, preferências, meta diária, palavra-passe e apagar a conta.
 * Rotas: /api/v1/users/... e /api/v1/student/practice-courses/study-goal/.
 */
import { createApi } from "@reduxjs/toolkit/query/react";
import { aposMeta, quandoCorrerBem } from "@/src/domains/student/sincronizar";
import { sharedBaseQuery } from "@/src/domains/shared/api/baseQuery";
import type { NivelCefr } from "@/src/domains/shared/niveis";

/** Nível CEFR (A1 a C2); a API traduz os valores antigos na leitura. */
export type Nivel = NivelCefr;

export type Perfil = {
  id: string;
  email: string;
  name: string;
  phone: string | null;
  avatar: string | null;
  role: string;
  created_at: string;
  /** false nas contas criadas com o Google, que ainda não têm palavra-passe. */
  has_password?: boolean;
  /** Província (slug); opcional. */
  provincia?: string | null;
  /** A administração pediu para mudar a palavra-passe: até lá, a API recusa o resto. */
  deve_mudar_senha?: boolean;
  preferences: {
    cidade?: string;
    area?: string;
    nivel?: Nivel;
    acolhimento?: "concluido";
    /** Toques de certo/errado nas lições (ligados se ausente). */
    sons?: boolean;
    /** Frases faladas da Professora Luena nas lições (ligadas se ausente). */
    voz_professora?: boolean;
  };
};

export type MudancaPerfil = { name?: string; phone?: string | null; provincia?: string | null; preferences?: Perfil["preferences"] };

export const perfilApi = createApi({
  reducerPath: "perfilApi",
  baseQuery: sharedBaseQuery,
  tagTypes: ["Perfil", "Meta"],
  endpoints: (build) => ({
    perfil: build.query<Perfil, void>({
      query: () => "/users/profile/",
      providesTags: ["Perfil"],
    }),
    guardarPerfil: build.mutation<Perfil, MudancaPerfil>({
      query: (body) => ({ url: "/users/profile/", method: "PATCH", body }),
      invalidatesTags: ["Perfil"],
    }),
    provincias: build.query<{ valor: string; nome: string }[], void>({ query: () => "/users/provincias/", keepUnusedDataFor: 3600 }),
    meta: build.query<{ daily_goal_minutes: number }, void>({
      query: () => "/student/practice-courses/study-goal/",
      providesTags: ["Meta"],
    }),
    mudarMeta: build.mutation<{ daily_goal_minutes: number }, number>({
      query: (minutos) => ({ url: "/student/practice-courses/study-goal/", method: "PATCH", body: { daily_goal_minutes: minutos } }),
      invalidatesTags: ["Meta"],
      onQueryStarted: quandoCorrerBem(aposMeta),
    }),
    mudarPalavraPasse: build.mutation<{ message: string; has_password?: boolean }, { actual: string; nova: string; confirmar: string }>({
      query: ({ actual, nova, confirmar }) => ({
        url: "/users/change-password/",
        method: "POST",
        body: { ...(actual ? { current_password: actual } : {}), new_password: nova, new_password_confirm: confirmar },
      }),
      invalidatesTags: ["Perfil"],
    }),
    apagarConta: build.mutation<{ message: string }, { password: string } | { confirmar: true }>({
      query: (body) => ({ url: "/users/apagar-conta/", method: "POST", body }),
    }),
  }),
});

export const { usePerfilQuery, useProvinciasQuery, useGuardarPerfilMutation, useMetaQuery, useMudarMetaMutation, useMudarPalavraPasseMutation, useApagarContaMutation } = perfilApi;

/** Erros de validação do DRF: {campo: ["mensagem"]} ou {error|message|detail}. */
export function errosDoServidor(e: unknown): { campos: Record<string, string>; geral: string | null } {
  const d = (e as { data?: Record<string, unknown> } | undefined)?.data ?? {};
  const fonte = (d.details as Record<string, unknown>) ?? d;
  const campos: Record<string, string> = {};
  let geral: string | null = null;
  for (const [k, v] of Object.entries(fonte)) {
    const texto = Array.isArray(v) ? String(v[0]) : typeof v === "string" ? v : typeof v === "object" && v ? String(Object.values(v)[0]) : null;
    if (!texto) continue;
    if (["error", "message", "detail", "non_field_errors"].includes(k)) geral = geral ?? texto;
    else campos[k] = texto;
  }
  if (!geral && !Object.keys(campos).length) geral = "Não foi possível guardar. Tente outra vez.";
  return { campos, geral };
}

export function iniciais(nome?: string) {
  const p = (nome ?? "").trim().split(/\s+/).filter(Boolean);
  return ((p[0]?.[0] ?? "") + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase() || "?";
}

/** As mesmas categorias dos cursos (ver categoriaPt), para recomendar cursos da área. */
export const AREAS: { valor: string; nome: string }[] = [
  { valor: "General English", nome: "Inglês geral" },
  { valor: "Industry English", nome: "Petróleo e Gás" },
  { valor: "Financial English", nome: "Banca" },
  { valor: "Business English", nome: "Negócios" },
  { valor: "Medical English", nome: "Saúde" },
  { valor: "Legal English", nome: "Direito" },
  { valor: "Technical English", nome: "Tecnologia" },
];

/** Níveis para escolher (A1 a C2, com nome e descrição): ver src/domains/shared/niveis.ts. */
export { OPCOES_NIVEL as NIVEIS } from "@/src/domains/shared/niveis";
