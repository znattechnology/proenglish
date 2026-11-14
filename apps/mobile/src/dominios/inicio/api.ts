/**
 * Dados do separador Início que vêm de outras áreas (sequência, vidas, liga e revisão de hoje).
 * Os mesmos endpoints do laboratório e da liga (apps/web/src/domains/student/{laboratorio,progresso,revisao}/api.ts),
 * com nomes próprios para não colidirem com os endpoints dos outros domínios da app.
 */
import { api } from "@/api/base";

const PRATICA = "/student/practice-courses";

export type SequenciaInicio = { current_streak: number; longest_streak: number; practiced_today: boolean; daily_goal_minutes: number; minutes_today: number; goal_completed: boolean };
export type VidasInicio = { current: number; maximum: number; unlimited: boolean };
export type LigaInicio = { liga: { id: string; nome: string }; eu: { posicao: number; pontos_semana: number } };
export type RevisaoInicio = { para_rever: number; minutos: number; feitas_hoje: number };

export const inicioApi = api.enhanceEndpoints({ addTagTypes: ["InicioResumo", "Liga"] }).injectEndpoints({
  endpoints: (build) => ({
    inicioSequencia: build.query<SequenciaInicio, void>({ query: () => `${PRATICA}/study-streak/`, providesTags: ["InicioResumo"] }),
    inicioVidas: build.query<VidasInicio, void>({ query: () => `${PRATICA}/hearts-status/`, providesTags: ["InicioResumo"] }),
    inicioLiga: build.query<LigaInicio, void>({ query: () => `${PRATICA}/liga/semana/`, providesTags: ["Liga"] }),
    inicioRevisao: build.query<RevisaoInicio, void>({ query: () => "/student/revisao/resumo/", providesTags: ["InicioResumo"] }),
  }),
});

export const { useInicioSequenciaQuery, useInicioVidasQuery, useInicioLigaQuery, useInicioRevisaoQuery } = inicioApi;

/** A API representa "vidas ilimitadas" (planos pagos) com 999. */
export const VIDAS_ILIMITADAS = 999;

/** "Bom dia, Maria" conforme a hora. */
export function saudacao(nome?: string, agora = new Date()) {
  const h = agora.getHours();
  const parte = h < 12 ? "Bom dia" : h < 19 ? "Boa tarde" : "Boa noite";
  const primeiro = nome?.trim().split(/\s+/)[0];
  return primeiro ? `${parte}, ${primeiro}` : parte;
}
