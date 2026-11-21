/**
 * Colocação no curso geral (English Communication Skills): A1 a C1.
 * Igual a apps/web/src/domains/student/curso/colocacao.ts. API: /student/colocacao/.
 * O servidor decide o nível final e inscreve no curso: o A1 entra logo; outro nível pede UM teste
 * de 30 perguntas de todos os níveis abaixo do escolhido (70% em cada); o aluno entra a seguir ao
 * último nível aprovado sem falhar nenhum abaixo, a contar do A1. Ao colocar, o servidor
 * também guarda preferences.nivel e preferences.acolhimento = "concluido".
 */
import { testeBasicoApi, type NivelTeste, type TentativaTeste } from "./testeBasico";

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
  tem_nivel_basico: boolean;
  curso: { id: string; titulo: string } | null;
  inscrito: boolean;
  motivo: "plano" | "sem_curso" | (string & {}) | null;
  curso_pratica: { id: string; titulo: string } | null;
};

export const colocacaoApi = testeBasicoApi.enhanceEndpoints({ addTagTypes: ["Colocacao", "Perfil", "LabProgresso"] }).injectEndpoints({
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
      // O servidor inscreve no curso (vídeo e laboratório) e guarda o nível nas preferências.
      invalidatesTags: ["Colocacao", "Curso", "Inscricao", "MeusCursos", "CursosCatalogo", "InicioResumo", "Perfil", "LabProgresso", "LabTrilho", "LabCursos"],
    }),
  }),
});

export const { useColocacaoQuery, useIniciarTesteColocacaoMutation, useColocarMutation } = colocacaoApi;

/** O servidor pediu o teste de colocação (409 teste_necessario)? */
export function testeNecessario(e: unknown): boolean {
  const d = (e as { data?: { code?: string; codigo?: string } } | undefined)?.data;
  return d?.code === "teste_necessario" || d?.codigo === "teste_necessario";
}
