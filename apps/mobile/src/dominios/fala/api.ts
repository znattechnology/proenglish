/**
 * Quanto e como o aluno fala (minutos a falar, ritmo, palavras a treinar, meta de fala).
 * Igual a apps/web/src/domains/student/fala/api.ts. API Django: /api/v1/student/fala/.
 */
import { api } from "@/api/base";

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

const F = "/student/fala";

export const falaApi = api.enhanceEndpoints({ addTagTypes: ["FalaMeta"] }).injectEndpoints({
  endpoints: (build) => ({
    falaResumo: build.query<ResumoFala, void>({
      query: () => `${F}/resumo/`,
      providesTags: ["FalaMeta"],
      keepUnusedDataFor: 0, // muda a cada gravação e conversa
    }),
    falaProgresso: build.query<ProgressoFala, void>({
      query: () => `${F}/progresso/`,
      providesTags: ["FalaMeta"],
      keepUnusedDataFor: 0,
    }),
    falaMeta: build.query<{ meta_fala_min: number; opcoes: number[] }, void>({
      query: () => `${F}/meta/`,
      providesTags: ["FalaMeta"],
    }),
    falaMudarMeta: build.mutation<{ meta_fala_min: number; opcoes: number[] }, number>({
      query: (minutos) => ({ url: `${F}/meta/`, method: "PATCH", body: { meta_fala_min: minutos } }),
      invalidatesTags: ["FalaMeta"],
    }),
  }),
});

export const { useFalaResumoQuery, useFalaProgressoQuery, useFalaMetaQuery, useFalaMudarMetaMutation } = falaApi;

/** "3 min 10 s", "45 s", "0 s". */
export function minSeg(segundos: number) {
  const s = Math.max(0, Math.round(segundos));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r ? `${m} min ${r} s` : `${m} min`;
}

/** Minutos inteiros para gráficos e metas (arredondados). */
export const minutosDe = (segundos: number) => Math.round(segundos / 60);
