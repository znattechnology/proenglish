/** Situações de conversa do professor, conquistas, competições e resultados de conversa.
 * Os ids das situações vêm como números da API; aqui tratam-se como texto (só servem para endereços). */
import { professorApi } from "./api";

export type Situacao = {
  id: string;
  nome: string;
  descricao: string;
  papel_tutor: string;
  frases: string[];
  curso: { id: string; titulo: string } | null;
  nivel: string;
  duracao_min: 3 | 5 | 10;
  correccao: "suave" | "directa";
  estado: "rascunho" | "activo";
  /** A aula depois da qual o aluno faz a conversa, no percurso do curso (só com curso). */
  aula?: { id: string; titulo: string } | null;
  tipo_conversa?: "guiada" | "livre" | null;
  sessoes?: number;
  pontuacao_media?: number | null;
  minha?: boolean;
};
export type LinhaSituacao = Pick<Situacao, "id" | "nome" | "curso" | "nivel" | "estado"> & { tipo: "conversa"; sessoes: number; pontuacao_media: number | null; minha: boolean };
export type NovaSituacao = Omit<Situacao, "id" | "curso" | "aula" | "tipo_conversa" | "sessoes" | "pontuacao_media" | "minha"> & { curso: string | null; aula: string | null; tipo_conversa: "guiada" | "livre" | "" };
export type AulaDoCurso = { id: string; titulo: string; unidade: string };
export type OpcoesSituacao = { cursos: { id: string; titulo: string }[]; aulas?: Record<string, AulaDoCurso[]>; niveis: { valor: string; nome: string }[]; duracoes: number[] };

export type ResultadosFala = {
  minutos: number;
  minutos_variacao_pct: number | null;
  sessoes: number;
  sessoes_por_dia: number;
  pontuacao_media: number | null;
  terminam_pct: number | null;
  competencias: { nome: string; media: number | null }[];
  situacoes: { id: string; nome: string; sessoes: number; media: number | null }[];
};

export type Raridade = "comum" | "rara" | "epica" | "lendaria";
export type Conquista = {
  id: string;
  nome: string;
  descricao: string;
  icone: string;
  regra: { tipo: string; meta: number; curso: { id: string; titulo: string } | null };
  como_se_ganha: string;
  raridade: Raridade;
  pontos: number;
  alunos_que_tem: number;
  activa: boolean;
  minha: boolean;
};
export type NovaConquista = { nome: string; descricao: string; icone: string; regra: { tipo: string; meta: number; curso: string | null }; raridade: Raridade; pontos: number; activa: boolean };
export type OpcoesConquista = { tipos: { valor: string; nome: string; unidade: string }[]; raridades: { valor: Raridade; nome: string }[]; cursos: { id: string; titulo: string }[] };

export type Competicao = {
  id: string;
  nome: string;
  cursos: { id: string; titulo: string }[];
  todos_os_cursos: boolean;
  estado: "agendada" | "activa" | "terminada";
  conta: "licoes" | "pontos" | "minutos_conversa" | "dias_seguidos";
  inicio: string;
  fim: string;
  participantes: number;
  premio: "certificado_merito" | "medalha" | "plano";
  premio_lugares: number;
  tempo_decorrido: number;
  minha: boolean;
};
export type NovaCompeticao = { nome: string; cursos: string[]; conta: Competicao["conta"]; inicio: string; fim: string; premio: "certificado_merito" | "medalha"; premio_lugares: number };
export type ListaCompeticoes = {
  numeros: { activas: number; terminam_esta_semana: number; participantes: number; pct_activos: number | null; media_pontos: number | null; media_dias_seguidos: number | null };
  resultados: Competicao[];
};
export type Classificacao = { conta: Competicao["conta"]; linhas: { lugar: number; aluno_id: string; nome: string; valor: number; pontos: number }[] };

export const falaApi = professorApi.enhanceEndpoints({ addTagTypes: ["Situacoes", "Conquistas", "Competicoes"] }).injectEndpoints({
  endpoints: (build) => ({
    situacoes: build.query<{ resultados: LinhaSituacao[] }, void>({ query: () => "/teacher/situacoes/", providesTags: ["Situacoes"] }),
    situacao: build.query<Situacao, string>({ query: (id) => `/teacher/situacoes/${id}/`, providesTags: ["Situacoes"] }),
    opcoesSituacao: build.query<OpcoesSituacao, void>({ query: () => "/teacher/situacoes/opcoes/" }),
    criarSituacao: build.mutation<Situacao, NovaSituacao>({ query: (body) => ({ url: "/teacher/situacoes/", method: "POST", body }), invalidatesTags: ["Situacoes"] }),
    mudarSituacao: build.mutation<Situacao, { id: string } & Partial<NovaSituacao>>({
      query: ({ id, ...body }) => ({ url: `/teacher/situacoes/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["Situacoes"],
    }),
    apagarSituacao: build.mutation<void, string>({ query: (id) => ({ url: `/teacher/situacoes/${id}/`, method: "DELETE" }), invalidatesTags: ["Situacoes"] }),
    resultadosFala: build.query<ResultadosFala, number>({ query: (periodo) => ({ url: "/teacher/resultados/fala/", params: { periodo } }) }),

    conquistas: build.query<{ resultados: Conquista[] }, string>({ query: (estado) => ({ url: "/teacher/conquistas/", params: { estado } }), providesTags: ["Conquistas"] }),
    opcoesConquista: build.query<OpcoesConquista, void>({ query: () => "/teacher/conquistas/opcoes/" }),
    criarConquista: build.mutation<Conquista, NovaConquista>({ query: (body) => ({ url: "/teacher/conquistas/", method: "POST", body }), invalidatesTags: ["Conquistas"] }),
    mudarConquista: build.mutation<Conquista, { id: string } & Partial<NovaConquista>>({
      query: ({ id, ...body }) => ({ url: `/teacher/conquistas/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["Conquistas"],
    }),
    apagarConquista: build.mutation<void, string>({ query: (id) => ({ url: `/teacher/conquistas/${id}/`, method: "DELETE" }), invalidatesTags: ["Conquistas"] }),

    competicoes: build.query<ListaCompeticoes, void>({ query: () => "/teacher/competicoes/", providesTags: ["Competicoes"] }),
    criarCompeticao: build.mutation<Competicao, NovaCompeticao>({ query: (body) => ({ url: "/teacher/competicoes/", method: "POST", body }), invalidatesTags: ["Competicoes"] }),
    apagarCompeticao: build.mutation<void, string>({ query: (id) => ({ url: `/teacher/competicoes/${id}/`, method: "DELETE" }), invalidatesTags: ["Competicoes"] }),
    classificacao: build.query<Classificacao, string>({ query: (id) => `/teacher/competicoes/${id}/classificacao/` }),
  }),
});

export const {
  useSituacoesQuery,
  useSituacaoQuery,
  useOpcoesSituacaoQuery,
  useCriarSituacaoMutation,
  useMudarSituacaoMutation,
  useApagarSituacaoMutation,
  useResultadosFalaQuery,
  useConquistasQuery,
  useOpcoesConquistaQuery,
  useCriarConquistaMutation,
  useMudarConquistaMutation,
  useApagarConquistaMutation,
  useCompeticoesQuery,
  useCriarCompeticaoMutation,
  useApagarCompeticaoMutation,
  useClassificacaoQuery,
} = falaApi;

export const CONTA: Record<Competicao["conta"], { nome: string; unidade: string }> = {
  licoes: { nome: "Lições concluídas", unidade: "Lições" },
  pontos: { nome: "Pontos", unidade: "Pontos" },
  minutos_conversa: { nome: "Minutos de conversa", unidade: "Minutos" },
  dias_seguidos: { nome: "Dias seguidos", unidade: "Dias" },
};
export const PREMIO: Record<Competicao["premio"], string> = {
  certificado_merito: "Certificado de mérito",
  medalha: "Medalha no perfil",
  plano: "Meses de plano",
};
export const RARIDADE: Record<Raridade, string> = { comum: "Comum", rara: "Rara", epica: "Épica", lendaria: "Lendária" };
