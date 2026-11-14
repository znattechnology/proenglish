/**
 * Notificações na app, preferências de avisos e notificações push (lembrete da meta diária).
 */
import { createApi } from "@reduxjs/toolkit/query/react";
import { sharedBaseQuery } from "@/src/domains/shared/api/baseQuery";
import { diaMesCurto } from "@/src/domains/student/subscricao/api";

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

export const avisosApi = createApi({
  reducerPath: "avisosApi",
  baseQuery: sharedBaseQuery,
  tagTypes: ["Notificacoes", "Avisos"],
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
    registarPush: build.mutation<unknown, PushSubscriptionJSON>({
      query: (s) => ({ url: "/users/avisos/push/", method: "POST", body: s }),
      invalidatesTags: ["Avisos"],
    }),
    retirarPush: build.mutation<unknown, string>({
      query: (endpoint) => ({ url: "/users/avisos/push/", method: "DELETE", body: { endpoint } }),
      invalidatesTags: ["Avisos"],
    }),
  }),
});

export const {
  useNotificacoesQuery,
  usePorLerQuery,
  useMarcarLidaMutation,
  useMarcarTodasMutation,
  useAvisosQuery,
  useMudarAvisosMutation,
  useRegistarPushMutation,
  useRetirarPushMutation,
} = avisosApi;

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
  return diaMesCurto(d);
}

/** Chave VAPID (base64url) no formato que o PushManager pede. */
function chaveParaBytes(b64: string) {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const bin = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

export const pushSuportado = () => typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

/** Pede permissão e devolve a subscrição push deste browser (ou null se a pessoa recusar). */
export async function subscreverPush(chavePublica: string): Promise<PushSubscriptionJSON | null> {
  if (!pushSuportado()) return null;
  const permissao = await Notification.requestPermission();
  if (permissao !== "granted") return null;
  const reg = await navigator.serviceWorker.ready;
  const existente = await reg.pushManager.getSubscription();
  const sub = existente ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: chaveParaBytes(chavePublica) }));
  return sub.toJSON();
}

export async function cancelarPushLocal(): Promise<string | null> {
  if (!pushSuportado()) return null;
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  if (!sub) return null;
  const endpoint = sub.endpoint;
  await sub.unsubscribe().catch(() => {});
  return endpoint;
}
