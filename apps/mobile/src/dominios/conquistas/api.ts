/**
 * Conquistas, liga semanal e competições (igual a apps/web/src/domains/student/progresso/api.ts).
 */
import { api } from "@/api/base";

const P = "/student/practice-courses";

export type Conquista = {
  id: string;
  title: string;
  description: string;
  icon?: string;
  category?: string;
  points?: number;
  isSecret: boolean;
  isUnlocked: boolean;
  unlockedAt: string | null;
  unlockedAtIso: string | null;
  progress: { current: number; target: number; unit?: string; percentage: number } | null;
};

export type PremioCompeticao = "certificado_merito" | "medalha" | "plano";

export type Competicao = {
  id: string;
  nome: string;
  estado: "agendada" | "activa" | "terminada";
  cursos?: { id: string; titulo: string }[];
  conta: string;
  conta_nome: string;
  unidade: string;
  inicio: string;
  fim: string;
  dias_restantes?: number;
  premio: PremioCompeticao;
  premio_nome: string;
  premio_lugares: number;
  participantes: number;
  meu_lugar: number | null;
  meu_valor: number;
  meu_premio?: PremioCompeticao | null;
  certificado_url?: string | null;
  topo: { lugar: number; nome: string; valor: number; sou_eu: boolean }[];
};

export type PremioGanho = {
  competicao_id: string;
  competicao: string;
  premio: PremioCompeticao;
  premio_nome: string;
  lugar: number | null;
  valor: number;
  unidade: string;
  fim: string;
  certificado_url: string | null;
};

export type Liga = {
  competicoes?: Competicao[];
  competicoes_terminadas?: Competicao[];
  premios?: PremioGanho[];
  semana: { inicio: string; fim: string; segundos_ate_fim: number };
  liga: { id: string; nome: string; pontos_minimos: number; pontos_maximos: number | null };
  eu: { posicao: number; nome: string; pontos_semana: number; pontos_totais: number; pontos_para_lugar_acima: number | null };
  participantes: number;
  ranking: { posicao: number; nome: string; pontos_semana: number; sou_eu: boolean }[];
  regra_promocao: { tipo: string; descricao: string; proxima_liga: { id: string; nome: string; pontos_minimos: number } | null; pontos_em_falta: number | null };
};

export const conquistasApi = api.enhanceEndpoints({ addTagTypes: ["Conquistas", "Liga"] }).injectEndpoints({
  endpoints: (build) => ({
    labConquistas: build.query<Conquista[], void>({
      query: () => `${P}/achievements/`,
      transformResponse: (r: Conquista[] | { data: Conquista[] }) => (Array.isArray(r) ? r : (r.data ?? [])),
      providesTags: ["Conquistas"],
    }),
    labLiga: build.query<Liga, void>({
      query: () => `${P}/liga/semana/`,
      providesTags: ["Liga"],
    }),
  }),
});

export const { useLabConquistasQuery, useLabLigaQuery } = conquistasApi;
