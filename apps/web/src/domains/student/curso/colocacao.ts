/**
 * Colocação no curso geral (English Communication Skills): A1 a C1.
 * API Django: /api/v1/student/colocacao/. O servidor decide o nível final e inscreve no curso:
 * o A1 entra logo; outro nível pede 70% no teste escrito do nível anterior; quem reprova entra no
 * nível testado.
 */
import { cursoApi } from "./api";
import type { NivelTeste } from "./testeBasico";

export type NivelColocacao = "A1" | "A2" | "B1" | "B2" | "C1";

export type NivelDisponivel = {
  nivel: NivelColocacao;
  nome: string;
  descricao: string;
  teste: NivelTeste | null;
  curso: { id: string; titulo: string } | null;
  pode_entrar: boolean;
  teste_em_curso: boolean;
  teste_reprovado: boolean;
  proxima_tentativa_em: string | null;
};

export type EstadoColocacao = {
  niveis: NivelDisponivel[];
  colocacao: { nivel: NivelColocacao; escolhido: NivelColocacao; em: string } | null;
  regras: { aprovacao: number; perguntas: number; minutos: number };
};

export type ResultadoColocacao = {
  nivel: NivelColocacao;
  escolhido: NivelColocacao;
  no_nivel_escolhido: boolean;
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
    colocar: build.mutation<ResultadoColocacao, NivelColocacao>({
      query: (nivel) => ({ url: "/student/colocacao/", method: "POST", body: { nivel } }),
      invalidatesTags: ["Colocacao", "Curso", "Inscricao"],
    }),
  }),
});

export const { useColocacaoQuery, useColocarMutation } = colocacaoApi;

/** O servidor pediu o teste do nível anterior (409 teste_necessario)? Devolve o nível do teste. */
export function testeNecessario(e: unknown): NivelTeste | null {
  const d = (e as { data?: { code?: string; teste?: NivelTeste } } | undefined)?.data;
  return d?.code === "teste_necessario" && d.teste ? d.teste : null;
}
