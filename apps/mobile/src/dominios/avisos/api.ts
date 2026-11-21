/**
 * Notificações na app e preferências de avisos (igual a apps/web/src/domains/student/avisos/api.ts).
 * Exemplo do padrão dos domínios: injectEndpoints sobre a `api` única de src/api/base.ts.
 */
import { api } from "@/api/base";

export type TipoNotificacao = "achievement" | "streak" | "league" | "course" | "certificate" | "subscription" | "system";
export type Notificacao = { id: string; kind: TipoNotificacao; title: string; body: string; link: string; created_at: string; read: boolean };
export type PaginaNotificacoes = { results: Notificacao[]; count: number; next: string | null; unread: number };

export type Avisos = {
  tipos: { meta: boolean; liga: boolean; certificados: boolean; cursos: boolean; subscricao: boolean };
  lembrete: { ligado: boolean; hora: string };
  push: { disponivel: boolean; chave_publica: string | null; subscricoes: number };
};
export type MudancaAvisos = { tipos?: Partial<Avisos["tipos"]>; lembrete?: Partial<Avisos["lembrete"]> };

const NOTIF = "/student/practice-courses/notifications";

export const avisosApi = api.enhanceEndpoints({ addTagTypes: ["Notificacoes", "Avisos"] }).injectEndpoints({
  endpoints: (build) => ({
    notificacoes: build.query<PaginaNotificacoes, number>({
      query: (pagina) => ({ url: `${NOTIF}/`, params: { page: pagina } }),
      providesTags: ["Notificacoes"],
    }),
    porLer: build.query<{ unread: number }, void>({
      query: () => `${NOTIF}/unread-count/`,
      providesTags: ["Notificacoes"],
    }),
    marcarLida: build.mutation<unknown, string>({
      query: (id) => ({ url: `${NOTIF}/${id}/read/`, method: "POST", body: {} }),
      invalidatesTags: ["Notificacoes"],
    }),
    marcarTodas: build.mutation<unknown, void>({
      query: () => ({ url: `${NOTIF}/read-all/`, method: "POST", body: {} }),
      invalidatesTags: ["Notificacoes"],
    }),
    avisos: build.query<Avisos, void>({
      query: () => "/users/avisos/",
      providesTags: ["Avisos"],
    }),
    mudarAvisos: build.mutation<Avisos, MudancaAvisos>({
      query: (body) => ({ url: "/users/avisos/", method: "PATCH", body }),
      invalidatesTags: ["Avisos"],
    }),
  }),
});

export const { useNotificacoesQuery, usePorLerQuery, useMarcarLidaMutation, useMarcarTodasMutation, useAvisosQuery, useMudarAvisosMutation } = avisosApi;

/** Número de notificações por ler (actualiza a cada minuto e ao voltar à app). */
export function usePorLer() {
  const { data } = usePorLerQuery(undefined, { pollingInterval: 60_000, refetchOnFocus: true });
  return data?.unread ?? 0;
}

const MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

/** "Há 20 min", "Há 2 h", "Ontem", "3 Nov". */
export function quando(iso: string, agora = Date.now()) {
  const d = new Date(iso);
  const min = Math.round((agora - d.getTime()) / 60_000);
  if (min < 1) return "Agora";
  if (min < 60) return `Há ${min} min`;
  const h = Math.round(min / 60);
  const hoje = new Date(agora);
  if (h < 24 && d.getDate() === hoje.getDate()) return `Há ${h} h`;
  const ontem = new Date(agora - 86_400_000);
  if (d.toDateString() === ontem.toDateString()) return "Ontem";
  return `${d.getDate()} ${MESES[d.getMonth()]}`;
}
