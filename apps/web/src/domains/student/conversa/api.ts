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
/** Frase-alvo da conversa (perfil de fala). pt pode vir vazio. */
export type Objectivo = { en: string; pt: string };
export type ObjectivoResultado = Objectivo & { usado: boolean; com_ajuda: boolean };
/** Padrão de erro nesta conversa: novo, recorrente ou já superado (estado de agora). */
export type PadraoConversa = { chave: string; descricao: string; errado: string; certo: string; estado: "novo" | "recorrente" | "superado" };
export type PadraoPerfil = { chave: string; descricao: string; errado: string; certo: string; ocorrencias: number; ultima_ocorrencia: string | null; superado: boolean };

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
  /** Frases-alvo por situação (id da situação -> 2 a 4 frases). */
  objectivos: Record<string, Objectivo[]>;
  /** Nível de fala do perfil do aluno (null enquanto não há). */
  perfil: { nivel: Nivel | null };
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
  objectivos: Objectivo[];
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
  objectivos: ObjectivoResultado[];
  padroes: PadraoConversa[];
  /** Fase 3: quanto falou o aluno (medido com os tempos do Vapi, ou estimado pelas palavras). */
  fala?: { segundos: number; ppm: number | null; palavras_por_turno: number | null; quota: number | null; fonte: "medido" | "estimado"; frase: string } | null;
};

export type Progresso = {
  media: number | null;
  variacao_mes: number | null;
  sessoes: number;
  minutos: number;
  por_competencia: { chave: string; nome: string; valor: number | null; nota: string }[];
  ultimas: { id: string; titulo: string; iniciada_em: string; minutos: number; geral: number | null }[];
  padroes: PadraoPerfil[];
  frases_sozinho: { total: number; recentes: { texto: string; traducao: string; vezes: number; dias: number; ultima_vez: string | null }[] };
};

/** Teste de nível falado da primeira entrada (fase 6). */
export type ResultadoDiagnostico = {
  id: string;
  estado: Resumo["estado"];
  avaliado: boolean;
  nivel: Nivel | null;
  niveis: { falar: Nivel | null; ouvir: Nivel | null; gramatica: Nivel | null; vocabulario: Nivel | null } | null;
  explicacoes: Partial<Record<"falar" | "ouvir" | "gramatica" | "vocabulario", string>>;
  resumo: string | null;
  feito_em: string;
};
export type EstadoDiagnostico = {
  disponivel: boolean;
  feitos_30_dias: number;
  limite: number;
  proximo_em: string | null;
  max_segundos: number;
  ultimo: ResultadoDiagnostico | null;
  modo: "vapi" | "simulado";
};

/** A fala contém a frase? (aproximado, só para o painel ao vivo: quem decide é o servidor no fim). */
export function disseFrase(frase: string, fala: string) {
  const norm = (t: string) =>
    t
      .toLowerCase()
      .replace(/[\u2018\u2019`]/g, "'")
      .replace(/\bcan't\b/g, "can not")
      .replace(/\bwon't\b/g, "will not")
      .replace(/n't\b/g, " not")
      .replace(/'ll\b/g, " will")
      .replace(/'re\b/g, " are")
      .replace(/'m\b/g, " am")
      .replace(/'ve\b/g, " have")
      .replace(/'d\b/g, " would")
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter(Boolean);
  const a = norm(frase);
  const b = norm(fala);
  if (!a.length || !b.length) return false;
  // Maior subsequência comum (as palavras da frase, pela ordem): 80% chega.
  let ant = new Array(b.length + 1).fill(0);
  for (const x of a) {
    const act = [0];
    for (let j = 1; j <= b.length; j++) act.push(x === b[j - 1] ? ant[j - 1] + 1 : Math.max(ant[j], act[j - 1]));
    ant = act;
  }
  return ant[b.length] / a.length >= 0.8;
}

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
    ligada: build.mutation<unknown, string | { id: string; call_id?: string }>({
      query: (a) => {
        const { id, call_id } = typeof a === "string" ? { id: a, call_id: undefined } : a;
        return { url: `${BASE}/sessoes/${id}/ligada/`, method: "POST", body: call_id ? { call_id } : {} };
      },
    }),
    diagnostico: build.query<EstadoDiagnostico, void>({
      query: () => `${BASE}/diagnostico/`,
      keepUnusedDataFor: 0,
    }),
    comecarDiagnostico: build.mutation<{ sessao: NovaSessao; modo: "vapi" | "simulado"; chave_publica: string | null }, void>({
      query: () => ({ url: `${BASE}/diagnostico/comecar/`, method: "POST", body: {} }),
    }),
    resultadoDiagnostico: build.query<ResultadoDiagnostico, string>({
      query: (id) => `${BASE}/diagnostico/${id}/`,
      keepUnusedDataFor: 0,
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

export const { useDiagnosticoQuery, useComecarDiagnosticoMutation, useLazyResultadoDiagnosticoQuery, usePrepararQuery, useComecarMutation, useLigadaMutation, useResponderMutation, useAjusteMutation, useTerminarMutation, useResumoQuery, useProgressoQuery } = conversaApi;

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
