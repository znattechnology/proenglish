/**
 * Estatísticas, certificados, conquistas e liga do estudante.
 * Tipos iguais ao que a API Django devolve (exemplos reais verificados).
 */
import { createApi } from "@reduxjs/toolkit/query/react";
import { sharedBaseQuery } from "@/src/domains/shared/api/baseQuery";

export type Periodo = "7" | "30" | "tudo";

export type Estatisticas = {
  periodo: Periodo;
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

export type Requisito = { requisito: string; mensagem: string; necessario: number | null; atual: number | null };

export type Certificados = {
  plano_inclui_certificados: boolean;
  certificados: {
    id: string;
    numero: string;
    curso: { id: string; titulo: string; imagem: string | null };
    emitido_em: string;
    nota_final: number;
    nota_letra?: string;
    estado: "valido" | "revogado";
    ligacao_verificacao: string;
    pdf_url: string;
  }[];
  em_curso: { curso: { id: string; titulo: string }; progresso: number; nota_final: number; nota_minima: number; pode_emitir: boolean; em_falta: Requisito[] }[];
};

export type Verificacao = { valido: boolean; estado: "valido" | "revogado"; numero: string; nome_aluno: string; curso: string; emitido_em: string; nota_final: number | null; revogado_em: string | null };

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

export type ContaCompeticao = "licoes" | "pontos" | "minutos_conversa" | "dias_seguidos";
export type PremioCompeticao = "certificado_merito" | "medalha" | "plano";

/** Competição dos cursos do aluno (participação automática). */
export type Competicao = {
  id: string;
  nome: string;
  estado: "agendada" | "activa" | "terminada";
  /** Só nas activas e agendadas (vazio = toda a plataforma). */
  cursos?: { id: string; titulo: string }[];
  conta: ContaCompeticao;
  conta_nome: string;
  unidade: string;
  /** Dias (AAAA-MM-DD, hora de Luanda); `fim` é o último dia. */
  inicio: string;
  fim: string;
  dias_restantes?: number;
  premio: PremioCompeticao;
  premio_nome: string;
  premio_lugares: number;
  participantes: number;
  meu_lugar: number | null;
  meu_valor: number;
  /** Só nas terminadas: prémio que o aluno ganhou (null = nenhum). */
  meu_premio?: PremioCompeticao | null;
  certificado_url?: string | null;
  /** Os 3 primeiros (empatados partilham o lugar); nome curto ("Ana M."). */
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

const BASE_PRATICA = "/student/practice-courses";
const BASE_VIDEO = "/student/video-courses";

export const progressoApi = createApi({
  reducerPath: "progressoApi",
  baseQuery: sharedBaseQuery,
  tagTypes: ["Certificados", "Estatisticas", "Liga", "Conquistas"],
  endpoints: (build) => ({
    estatisticas: build.query<Estatisticas, Periodo>({
      query: (periodo) => ({ url: `${BASE_PRATICA}/estatisticas/`, params: { periodo } }),
      providesTags: ["Estatisticas"],
    }),
    certificados: build.query<Certificados, void>({
      query: () => `${BASE_VIDEO}/certificados/`,
      providesTags: ["Certificados"],
    }),
    emitirCertificado: build.mutation<unknown, string>({
      query: (courseId) => ({ url: `${BASE_VIDEO}/${courseId}/certificado/`, method: "POST", body: {} }),
      invalidatesTags: ["Certificados"],
    }),
    verificarCertificado: build.query<Verificacao, string>({
      query: (numero) => `/certificados/verificar/${encodeURIComponent(numero)}/`,
    }),
    conquistas: build.query<Conquista[], void>({
      query: () => `${BASE_PRATICA}/achievements/`,
      transformResponse: (r: Conquista[] | { data: Conquista[] }) => (Array.isArray(r) ? r : r.data ?? []),
      providesTags: ["Conquistas"],
    }),
    liga: build.query<Liga, void>({
      query: () => `${BASE_PRATICA}/liga/semana/`,
      providesTags: ["Liga"],
    }),
  }),
});

export const { useEstatisticasQuery, useCertificadosQuery, useEmitirCertificadoMutation, useVerificarCertificadoQuery, useConquistasQuery, useLigaQuery } = progressoApi;

/** "1 h 30", "45 min". */
export function duracao(minutos: number) {
  const m = Math.round(minutos);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? `${h} h ${String(r).padStart(2, "0")}` : `${h} h`;
}
