/**
 * Colocação no curso geral (English Communication Skills): A1 a C1.
 * API Django: /api/v1/student/colocacao/. O A1 entra logo; outro nível pede UM teste com 30
 * perguntas de todos os níveis abaixo do escolhido (70% em cada nível); o aluno entra a seguir ao
 * último nível aprovado sem falhar nenhum abaixo, a contar do A1. O servidor decide e inscreve.
 */
import { cursoApi } from "./api";
import type { NivelTeste, TentativaTeste } from "./testeBasico";

export type NivelColocacao = "A1" | "A2" | "B1" | "B2" | "C1";

export type NivelDisponivel = {
  nivel: NivelColocacao;
  nome: string;
  descricao: string;
  niveis_teste: NivelTeste[];
  perguntas: number;
  minutos: number;
  curso: { id: string; titulo: string } | null;
  pode_entrar: boolean;
};

export type EstadoColocacao = {
  niveis: NivelDisponivel[];
  provado: NivelTeste | null;
  em_curso: TentativaTeste | null;
  ultima: TentativaTeste | null;
  proxima_tentativa_em: string | null;
  colocacao: { nivel: NivelColocacao; escolhido: NivelColocacao; em: string } | null;
  regras: { aprovacao: number; espera_horas: number };
};

export type ResultadoColocacao = {
  nivel: NivelColocacao;
  escolhido: NivelColocacao;
  no_nivel_escolhido: boolean;
  provado: NivelTeste | null;
  curso: { id: string; titulo: string } | null;
  inscrito: boolean;
  motivo: "plano" | "sem_curso" | string | null;
  curso_pratica: { id: string; titulo: string } | null;
};

export const colocacaoApi = cursoApi.enhanceEndpoints({ addTagTypes: ["Colocacao", "TesteBasico"] }).injectEndpoints({
  endpoints: (build) => ({
    colocacao: build.query<EstadoColocacao, void>({
      query: () => "/student/colocacao/",
      providesTags: ["Colocacao", "TesteBasico"],
    }),
    iniciarTesteColocacao: build.mutation<TentativaTeste, NivelColocacao>({
      query: (nivel) => ({ url: "/student/colocacao/teste/", method: "POST", body: { nivel } }),
      invalidatesTags: ["Colocacao"],
    }),
    colocar: build.mutation<ResultadoColocacao, NivelColocacao>({
      query: (nivel) => ({ url: "/student/colocacao/", method: "POST", body: { nivel } }),
      invalidatesTags: ["Colocacao", "Curso", "Inscricao"],
    }),
  }),
});

export const { useColocacaoQuery, useIniciarTesteColocacaoMutation, useColocarMutation } = colocacaoApi;

/** O servidor pediu o teste de colocação (409 teste_necessario)? */
export function testeNecessario(e: unknown): boolean {
  return (e as { data?: { code?: string } } | undefined)?.data?.code === "teste_necessario";
}
