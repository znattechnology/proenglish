/**
 * Perfil e definições: dados da pessoa, meta diária, meta de fala, palavra-passe, apagar a conta,
 * os números do perfil (dias seguidos, pontos, certificados) e a opinião.
 * Igual a apps/web/src/domains/student/perfil/api.ts e opiniao/api.ts.
 */
import { api } from "@/api/base";
import type { OfertaPlano } from "@/dominios/subscricao/api";
import type { RespostaSessao } from "@/sessao/ContextoSessao";

export type Nivel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export type Perfil = {
  id: string;
  email: string;
  name: string;
  phone: string | null;
  avatar: string | null;
  role: string;
  created_at: string;
  has_password?: boolean;
  provincia?: string | null;
  deve_mudar_senha?: boolean;
  preferences: { cidade?: string; area?: string; nivel?: string; acolhimento?: "concluido" };
};

export type MudancaPerfil = { name?: string; phone?: string | null; provincia?: string | null; preferences?: Perfil["preferences"] };

export type Sequencia = { current_streak: number; longest_streak: number; practiced_today: boolean; daily_goal_minutes: number; minutes_today: number; goal_completed: boolean };
export type EstadoVidas = { current: number; maximum: number; unlimited: boolean; points: number; oferta?: OfertaPlano | null };
export type ResumoCertificados = { plano_inclui_certificados: boolean; certificados: { id: string; estado: "valido" | "revogado" }[]; em_curso: unknown[] };

export type EstadoOpiniao = { should_show_prompt: boolean; trigger: string | null; chave: string | null; frase: string | null };
export type NovaOpiniao = { rating: number; comment?: string; trigger?: string; context_data?: Record<string, unknown>; allow_public?: boolean; allow_contact?: boolean };

/** Resposta de mudar a palavra-passe: com X-Cliente: app traz a sessão nova em `tokens`. */
export type SenhaMudada = { message: string; has_password?: boolean } & RespostaSessao;

const PRATICA = "/student/practice-courses";

export const perfilApi = api
  .enhanceEndpoints({ addTagTypes: ["Perfil", "MetaEstudo", "FalaMeta", "StudentStreak", "StudentProgress", "Estatisticas", "Certificados", "Opiniao"] })
  .injectEndpoints({
    endpoints: (build) => ({
      perfilDados: build.query<Perfil, void>({
        query: () => "/users/profile/",
        providesTags: ["Perfil"],
      }),
      perfilGuardar: build.mutation<Perfil, MudancaPerfil>({
        query: (body) => ({ url: "/users/profile/", method: "PATCH", body }),
        invalidatesTags: ["Perfil"],
      }),
      perfilProvincias: build.query<{ valor: string; nome: string }[], void>({
        query: () => "/users/provincias/",
        keepUnusedDataFor: 3600,
      }),
      perfilMetaEstudo: build.query<{ daily_goal_minutes: number }, void>({
        query: () => `${PRATICA}/study-goal/`,
        providesTags: ["MetaEstudo"],
      }),
      perfilMudarMetaEstudo: build.mutation<{ daily_goal_minutes: number }, number>({
        query: (minutos) => ({ url: `${PRATICA}/study-goal/`, method: "PATCH", body: { daily_goal_minutes: minutos } }),
        invalidatesTags: ["MetaEstudo", "StudentStreak", "Estatisticas"],
      }),
      perfilMetaFala: build.query<{ meta_fala_min: number; opcoes: number[] }, void>({
        query: () => "/student/fala/meta/",
        providesTags: ["FalaMeta"],
      }),
      perfilMudarMetaFala: build.mutation<{ meta_fala_min: number; opcoes: number[] }, number>({
        query: (minutos) => ({ url: "/student/fala/meta/", method: "PATCH", body: { meta_fala_min: minutos } }),
        invalidatesTags: ["FalaMeta"],
      }),
      perfilMudarSenha: build.mutation<SenhaMudada, { actual: string; nova: string; confirmar: string; refresh: string | null }>({
        query: ({ actual, nova, confirmar, refresh }) => ({
          url: "/users/change-password/",
          method: "POST",
          // O refresh desta sessão faz a API mantê-la (e terminar só as outras).
          body: { ...(actual ? { current_password: actual } : {}), new_password: nova, new_password_confirm: confirmar, ...(refresh ? { refresh_token: refresh } : {}) },
        }),
        invalidatesTags: ["Perfil"],
      }),
      perfilApagarConta: build.mutation<{ message: string }, { password: string } | { confirmar: true }>({
        query: (body) => ({ url: "/users/apagar-conta/", method: "POST", body }),
      }),
      perfilSequencia: build.query<Sequencia, void>({
        query: () => `${PRATICA}/study-streak/`,
        providesTags: ["StudentStreak"],
      }),
      perfilVidas: build.query<EstadoVidas, void>({
        query: () => `${PRATICA}/hearts-status/`,
        providesTags: ["StudentProgress"],
      }),
      perfilCertificados: build.query<ResumoCertificados, void>({
        query: () => "/student/video-courses/certificados/",
        providesTags: ["Certificados"],
      }),
      opiniaoEstado: build.query<EstadoOpiniao, void>({
        query: () => "/users/feedback/status/",
        providesTags: ["Opiniao"],
      }),
      opiniaoEnviar: build.mutation<{ message: string }, NovaOpiniao>({
        query: (body) => ({ url: "/users/feedback/submit/", method: "POST", body }),
        invalidatesTags: ["Opiniao"],
      }),
    }),
  });

export const {
  usePerfilDadosQuery,
  usePerfilGuardarMutation,
  usePerfilProvinciasQuery,
  usePerfilMetaEstudoQuery,
  usePerfilMudarMetaEstudoMutation,
  usePerfilMetaFalaQuery,
  usePerfilMudarMetaFalaMutation,
  usePerfilMudarSenhaMutation,
  usePerfilApagarContaMutation,
  usePerfilSequenciaQuery,
  usePerfilVidasQuery,
  usePerfilCertificadosQuery,
  useOpiniaoEstadoQuery,
  useOpiniaoEnviarMutation,
} = perfilApi;

/** Erros de validação do DRF: {campo: ["mensagem"]} ou {error|message|detail}. */
export function errosDoServidor(e: unknown): { campos: Record<string, string>; geral: string | null } {
  const erro = e as { status?: number | string; data?: Record<string, unknown> } | undefined;
  if (erro?.status === "FETCH_ERROR") return { campos: {}, geral: "Sem ligação ao servidor. Verifique a Internet e tente outra vez." };
  const d = erro?.data ?? {};
  const fonte = (d.details as Record<string, unknown>) ?? d;
  const campos: Record<string, string> = {};
  let geral: string | null = null;
  for (const [k, v] of Object.entries(fonte)) {
    const texto = Array.isArray(v) ? String(v[0]) : typeof v === "string" ? v : typeof v === "object" && v ? String(Object.values(v)[0]) : null;
    if (!texto) continue;
    if (["error", "message", "detail", "non_field_errors", "mensagem"].includes(k)) geral = geral ?? texto;
    else if (!["code", "codigo"].includes(k)) campos[k] = texto;
  }
  if (!geral && !Object.keys(campos).length) geral = "Não foi possível guardar. Tente outra vez.";
  return { campos, geral };
}

export function iniciais(nome?: string | null) {
  const p = (nome ?? "").trim().split(/\s+/).filter(Boolean);
  return ((p[0]?.[0] ?? "") + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase() || "?";
}

/** As mesmas categorias dos cursos, para recomendar cursos da área. */
export const AREAS: { valor: string; nome: string }[] = [
  { valor: "Industry English", nome: "Petróleo e Gás" },
  { valor: "Financial English", nome: "Banca" },
  { valor: "Business English", nome: "Negócios" },
  { valor: "Medical English", nome: "Saúde" },
  { valor: "Legal English", nome: "Direito" },
  { valor: "Technical English", nome: "Tecnologia" },
  { valor: "General English", nome: "Outra área" },
];

export const nomeArea = (valor?: string | null) => AREAS.find((a) => a.valor === valor)?.nome ?? null;

const NOME_NIVEL: Record<Nivel, string> = { A1: "Iniciante", A2: "Elementar", B1: "Intermédio", B2: "Intermédio avançado", C1: "Avançado", C2: "Proficiente" };
const DESCRICAO_NIVEL: Record<Nivel, string> = {
  A1: "Conheço palavras e frases muito simples",
  A2: "Consigo falar de rotinas e tarefas simples",
  B1: "Consigo conversar sobre o trabalho com algum apoio",
  B2: "Participo em reuniões e discussões com à-vontade",
  C1: "Exprimo-me com fluência e precisão em contexto profissional",
  C2: "Uso o inglês como um falante nativo",
};
export const NIVEIS = (Object.keys(NOME_NIVEL) as Nivel[]).map((valor) => ({ valor, nome: `${valor} (${NOME_NIVEL[valor]})`, descricao: DESCRICAO_NIVEL[valor] }));

const ANTIGOS: Record<string, Nivel> = { Beginner: "A2", Intermediate: "B1", Advanced: "B2" };
/** Código CEFR de um valor vindo da API (aceita os nomes antigos). */
export function normalizarNivel(valor?: string | null): Nivel | undefined {
  if (!valor) return undefined;
  const v = valor.trim().replace(/^nível\s+/i, "").toUpperCase();
  if (v in NOME_NIVEL) return v as Nivel;
  return ANTIGOS[valor.trim()];
}

export const NOTAS = ["Mau", "Fraco", "Razoável", "Bom", "Muito bom"];
