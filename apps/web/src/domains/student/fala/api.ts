/**
 * Quanto o aluno fala (fase 3). API Django: /api/v1/student/fala/.
 * Fica na fatia do laboratório para partilhar a cache com a revisão e as lições.
 */
import { DJANGO_BASE_URL } from "@/src/domains/shared/api/baseQuery";
import { studentPracticeApiSlice } from "../practice-courses/api/studentPracticeApiSlice";

const F = `${DJANGO_BASE_URL}/student/fala`;

export type DiaFala = { dia: string; segundos: number; hoje: boolean };

export type ResumoFala = {
  frase: string;
  hoje: { segundos: number; meta_min: number; cumprida: boolean; percentagem: number };
  semana: { segundos: number; dias: DiaFala[]; frases_sozinho: number };
  padrao: string | null;
  metas_validas: number[];
};

export type PalavraTreinar = { palavra: string; tentativas: number; falhas: number; media: number | null; fonema: string | null; ultima: string | null };

export type SemanaFala = {
  inicio: string;
  segundos: number;
  ppm: number | null;
  palavras_por_resposta: number | null;
  pausas_por_minuto: number | null;
  actual: boolean;
};

export type ProgressoFala = {
  semanas: SemanaFala[];
  palavras_treinar: PalavraTreinar[];
  meta_min: number;
  avaliacao_detalhada: { disponivel: boolean; limite: number; usadas?: number; restantes: number };
};

/** Notas por palavra (só com a avaliação detalhada; sem ela vem null). */
export type DetalhePronuncia = {
  palavras: { palavra: string; nota: number | null; erro_tipo: string }[];
  fluencia: number | null;
  completude: number | null;
  prosodia: number | null;
  dica: string | null;
  fonte: string;
};

/** Métricas de fluência de uma gravação. */
export type MetricasGravacao = {
  segundos_fala: number;
  palavras_ditas: number | null;
  ppm: number | null;
  pausas_longas: number | null;
  pausas_longas_s: number | null;
  maior_pausa_s: number | null;
  fonte_tempo: "medido" | "estimado" | "";
};

export const falaApi = studentPracticeApiSlice.enhanceEndpoints({ addTagTypes: ["FalaMeta"] }).injectEndpoints({
  endpoints: (build) => ({
    resumoFala: build.query<ResumoFala, void>({
      query: () => `${F}/resumo/`,
      providesTags: ["FalaMeta"],
      keepUnusedDataFor: 0, // muda a cada gravação e conversa: lê-se sempre que o painel abre
    }),
    progressoFala: build.query<ProgressoFala, void>({
      query: () => `${F}/progresso/`,
      providesTags: ["FalaMeta"],
      keepUnusedDataFor: 0,
    }),
    metaFala: build.query<{ meta_fala_min: number; opcoes: number[] }, void>({
      query: () => `${F}/meta/`,
      providesTags: ["FalaMeta"],
    }),
    mudarMetaFala: build.mutation<{ meta_fala_min: number; opcoes: number[] }, number>({
      query: (minutos) => ({ url: `${F}/meta/`, method: "PATCH", body: { meta_fala_min: minutos } }),
      invalidatesTags: ["FalaMeta"],
    }),
  }),
  overrideExisting: process.env.NODE_ENV === "development",
});

export const { useResumoFalaQuery, useProgressoFalaQuery, useMetaFalaQuery, useMudarMetaFalaMutation } = falaApi;

/** "3 min 10 s", "45 s", "0 s". */
export function minSeg(segundos: number) {
  const s = Math.max(0, Math.round(segundos));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r ? `${m} min ${r} s` : `${m} min`;
}

/** Minutos inteiros para gráficos e metas (arredondados). */
export const minutos = (segundos: number) => Math.round(segundos / 60);
