/**
 * Teste do nível básico (A2), o requisito para entrar num curso de sector sem ter feito o curso
 * geral. O mesmo motor serve o teste de colocação (./colocacao.ts): anular e entregar são os mesmos
 * endereços. Igual a apps/web/src/domains/student/curso/testeBasico.ts.
 * API: /student/teste-basico/ (as perguntas vêm sem as respostas; a nota é do servidor).
 * Se o aluno sai da app durante o teste, a pergunta em que estava é anulada no servidor (/anular/).
 */
import { cursosApi } from "./api";

const BASE = "/student/teste-basico";

export const CODIGO_REQUISITO_BASICO = "requisito_basico";
export const ROTA_TESTE_BASICO = "/teste-basico";

export type PerguntaTeste = { id: string; enunciado: string; opcoes: string[] };

export type NivelTeste = "A1" | "A2" | "B1" | "B2";

export type ResultadoNivel = { certas: number; total: number; aprovado: boolean };

export type TentativaTeste = {
  id: string;
  niveis: NivelTeste[];
  para: string | null;
  resultado: Partial<Record<NivelTeste, ResultadoNivel>> | null;
  provado: NivelTeste | null;
  nivel: NivelTeste;
  anuladas: string[];
  iniciado_em: string;
  expira_em: string;
  submetido_em: string | null;
  certas: number | null;
  total: number;
  aprovado: boolean | null;
  perguntas?: PerguntaTeste[];
};

export type EstadoTesteBasico = {
  nivel: NivelTeste;
  aprovado_no_nivel: boolean;
  tem_nivel_basico: boolean;
  pode_iniciar: boolean;
  proxima_tentativa_em: string | null;
  em_curso: TentativaTeste | null;
  ultima: TentativaTeste | null;
  regras: { perguntas: number; aprovacao: number; minutos: number; espera_horas: number };
};

export const testeBasicoApi = cursosApi.enhanceEndpoints({ addTagTypes: ["TesteBasico", "Colocacao", "LabCursos", "LabTrilho", "LabLicao"] }).injectEndpoints({
  endpoints: (build) => ({
    estadoTesteBasico: build.query<EstadoTesteBasico, void>({
      query: () => `${BASE}/`,
      providesTags: ["TesteBasico"],
    }),
    iniciarTesteBasico: build.mutation<TentativaTeste, void>({
      query: () => ({ url: `${BASE}/iniciar/`, method: "POST" }),
      invalidatesTags: ["TesteBasico"],
    }),
    /** O aluno saiu da app: a pergunta em que estava conta como errada. */
    anularPerguntaTeste: build.mutation<{ anuladas: string[] }, { id: string; pergunta: string }>({
      query: ({ id, pergunta }) => ({ url: `${BASE}/${id}/anular/`, method: "POST", body: { pergunta } }),
    }),
    entregarTesteBasico: build.mutation<TentativaTeste & { estado: EstadoTesteBasico }, { id: string; respostas: Record<string, number> }>({
      query: ({ id, respostas }) => ({ url: `${BASE}/${id}/entregar/`, method: "POST", body: { respostas } }),
      // Aprovado: os cursos de sector (vídeo e laboratório) passam a abrir.
      invalidatesTags: ["TesteBasico", "Colocacao", "Curso", "Inscricao", "CursosCatalogo", "LabCursos", "LabTrilho", "LabLicao"],
    }),
  }),
});

export const { useEstadoTesteBasicoQuery, useIniciarTesteBasicoMutation, useEntregarTesteBasicoMutation, useAnularPerguntaTesteMutation } = testeBasicoApi;

/** O erro de uma inscrição ou de uma lição é a falta do nível básico? */
export function faltaNivelBasico(e: unknown) {
  const d = (e as { data?: { code?: string; codigo?: string } } | undefined)?.data;
  return d?.code === CODIGO_REQUISITO_BASICO || d?.codigo === CODIGO_REQUISITO_BASICO;
}
