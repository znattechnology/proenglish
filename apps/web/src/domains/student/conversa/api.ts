/**
 * Conversa com o tutor: preparar, sessão em curso, resumo e progresso.
 * A duração, os minutos do plano e as notas são sempre calculados no servidor.
 */
import { createApi } from "@reduxjs/toolkit/query/react";
import { aposEstudo, quandoCorrerBem } from "@/src/domains/student/sincronizar";
import { sharedBaseQuery } from "@/src/domains/shared/api/baseQuery";

export type Nivel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";
export type Correcao = "suave" | "directa";
export type Frase = { en: string; pt: string };
export type Ajuste = { disse: string; certo: string; porque: string };
export type Fala = { quem: "tutor" | "aluno"; texto: string };

export type Preparar = {
  situacoes: {
    id: string;
    titulo: string;
    /** Resumo curto para o aluno (1.ª frase da descrição). */
    descricao: string;
    minutos_sugeridos: number;
    area: string;
    /** Sugestões do professor (null nas situações da plataforma: ficam as preferências do aluno). */
    nivel: Nivel | null;
    correcao: Correcao | null;
    curso: { id: string; titulo: string } | null;
  }[];
  niveis: Nivel[];
  areas: { id: string; nome: string }[];
  preferencias: { nivel: Nivel; correcao: Correcao; area: string };
  quota: {
    plano: string;
    minutos_dia: number | null;
    minutos_usados: number;
    minutos_restantes: number | null;
    max_minutos_sessao: number;
    pode_comecar: boolean;
    motivo: null | "sem_minutos" | "plano_sem_tutor" | "teste_expirado";
  };
  modo: "vapi" | "simulado";
  vapi: { public_key: string; assistant_id: string } | null;
};

export type NovaSessao = {
  id: string;
  situacao: { id: string; titulo: string };
  max_segundos: number;
  primeira_fala: string;
  frases: Frase[];
  vapi: { assistant_id: string; assistant_overrides: Record<string, unknown> } | null;
};

export type Notas = { geral: number | null; fluencia: number | null; gramatica: number | null; pronuncia: number | null; vocabulario: number | null };

export type Resumo = {
  id: string;
  situacao: { id: string | null; titulo: string };
  iniciada_em: string;
  minutos: number;
  /** Minutos que contaram para o limite do dia (pode diferir de "minutos" por arredondamento). */
  minutos_cobrados: number;
  segundos: number;
  estado: "avaliada" | "sem_avaliacao" | "em_curso" | "a_avaliar" | "nao_ligou";
  notas: Notas | null;
  transcricao: Fala[];
  correccoes: Ajuste[];
  palavras_bem_usadas: string[];
  resumo: string | null;
};

export type Progresso = {
  media: number | null;
  variacao_mes: number | null;
  sessoes: number;
  minutos: number;
  por_competencia: { chave: string; nome: string; valor: number | null; nota: string }[];
  ultimas: { id: string; titulo: string; iniciada_em: string; minutos: number; geral: number | null }[];
};

const BASE = "/practice/conversa";

export const conversaApi = createApi({
  reducerPath: "conversaApi",
  baseQuery: sharedBaseQuery,
  tagTypes: ["Preparar", "Progresso"],
  endpoints: (build) => ({
    preparar: build.query<Preparar, void>({
      query: () => `${BASE}/preparar/`,
      providesTags: ["Preparar"],
      keepUnusedDataFor: 0,
    }),
    comecar: build.mutation<NovaSessao, { situacao: string; nivel: Nivel; correcao: Correcao; area: string }>({
      query: (body) => ({ url: `${BASE}/sessoes/`, method: "POST", body }),
    }),
    /** A chamada ligou de facto: o tempo cobrado começa aqui (não ao criar a sessão). */
    ligada: build.mutation<unknown, string>({
      query: (id) => ({ url: `${BASE}/sessoes/${id}/ligada/`, method: "POST", body: {} }),
    }),
    responder: build.mutation<{ tutor: string }, { id: string; texto: string }>({
      query: ({ id, texto }) => ({ url: `${BASE}/sessoes/${id}/responder/`, method: "POST", body: { texto } }),
    }),
    ajuste: build.mutation<{ ajuste: Ajuste | null }, { id: string; frase: string }>({
      query: ({ id, frase }) => ({ url: `${BASE}/sessoes/${id}/ajuste/`, method: "POST", body: { frase } }),
    }),
    terminar: build.mutation<Resumo, { id: string; transcricao: Fala[] }>({
      query: ({ id, transcricao }) => ({ url: `${BASE}/sessoes/${id}/terminar/`, method: "POST", body: { transcricao } }),
      invalidatesTags: ["Preparar", "Progresso"],
      onQueryStarted: quandoCorrerBem(aposEstudo),
    }),
    resumo: build.query<Resumo, string>({
      query: (id) => `${BASE}/sessoes/${id}/`,
      providesTags: ["Progresso"],
    }),
    progresso: build.query<Progresso, void>({
      query: () => `${BASE}/progresso/`,
      providesTags: ["Progresso"],
    }),
  }),
});

export const { usePrepararQuery, useComecarMutation, useLigadaMutation, useResponderMutation, useAjusteMutation, useTerminarMutation, useResumoQuery, useProgressoQuery } = conversaApi;

export const URL_TERMINAR = (id: string) => `${process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://localhost:8000/api/v1"}${BASE}/sessoes/${id}/terminar/`;

/** Mensagem do erro da API (`{codigo, mensagem}`), ou uma mensagem por omissão. */
export function erroConversa(e: unknown, padrao = "Não foi possível começar a conversa. Tente outra vez.") {
  const d = (e as { data?: { mensagem?: string; error?: string; detail?: string } } | undefined)?.data;
  return d?.mensagem ?? d?.error ?? d?.detail ?? padrao;
}

export const NIVEIS_DESCRICAO: Record<Nivel, string> = {
  A1: "o tutor usa frases curtas e fala muito devagar.",
  A2: "o tutor fala devagar, com frases simples do trabalho.",
  B1: "o tutor fala devagar e usa frases do dia a dia de trabalho.",
  B2: "o tutor fala a um ritmo normal e pede mais detalhes.",
  C1: "o tutor fala como um colega e usa expressões idiomáticas.",
  C2: "o tutor fala ao ritmo de um falante nativo.",
};

export const COMPETENCIAS: Record<string, string> = {
  geral: "Geral",
  fluencia: "Fluência",
  gramatica: "Gramática",
  pronuncia: "Pronúncia",
  vocabulario: "Vocabulário",
};
