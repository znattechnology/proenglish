/**
 * Estatísticas do estudante (igual a apps/web/src/domains/student/progresso/api.ts, parte "estatisticas").
 */
import { api } from "@/api/base";

export type PeriodoEstatisticas = "7" | "30" | "tudo";

export type Estatisticas = {
  periodo: PeriodoEstatisticas;
  inicio: string;
  fim: string;
  dias: number;
  meta_diaria_minutos: number;
  tempo_estudo: { minutos: number; por_tipo: { licoes: number; videos: number; conversacao: number }; periodo_anterior: number | null; variacao: number | null; variacao_pct: number | null };
  licoes_concluidas: { total: number; periodo_anterior: number | null; variacao: number | null };
  sequencia: { atual: number; maior: number; estudou_hoje: boolean };
  respostas: { certas: number; total: number; percentagem: number | null };
  dias_meta_cumprida: number;
  minutos_por_dia: { data: string; dia_semana: string; minutos: number; meta_cumprida: boolean }[];
  por_tipo_exercicio: { tipo: string; rotulo: string; grupo: string; certas: number; total: number; percentagem: number | null }[];
  conversacao: {
    sessoes: number;
    minutos: number;
    pontuacao_media: number | null;
    melhor_pontuacao: number | null;
    criterios: Record<string, number | null> | null;
    ultima_sessao: { data: string; pontuacao: number; duracao_minutos: number; nivel: string; tema: string; variacao_vs_anterior: number | null; resumo: string } | null;
  };
};

export const estatisticasApi = api.enhanceEndpoints({ addTagTypes: ["Estatisticas"] }).injectEndpoints({
  endpoints: (build) => ({
    estatisticasPeriodo: build.query<Estatisticas, PeriodoEstatisticas>({
      query: (periodo) => ({ url: "/student/practice-courses/estatisticas/", params: { periodo } }),
      providesTags: ["Estatisticas"],
    }),
  }),
});

export const { useEstatisticasPeriodoQuery } = estatisticasApi;

/** "45 min", "1 h 05", "2 h". */
export function duracao(minutos: number) {
  const m = Math.round(minutos);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? `${h} h ${String(r).padStart(2, "0")}` : `${h} h`;
}
