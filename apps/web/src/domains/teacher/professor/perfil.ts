/** Perfil público do professor: o que os alunos vêem na página de cada curso. */
import { professorApi } from "./api";

export type PerfilProfessor = {
  id: string;
  nome: string;
  iniciais: string;
  fotografia: string | null;
  cidade: string;
  especialidade: string;
  experiencia: string;
  sobre: string;
  desde: string | null;
  cursos_publicados: number;
  alunos: number;
};
export type MudancaPerfilProfessor = Partial<Pick<PerfilProfessor, "nome" | "cidade" | "especialidade" | "experiencia" | "sobre">>;

export const perfilApi = professorApi.enhanceEndpoints({ addTagTypes: ["Perfil"] }).injectEndpoints({
  endpoints: (build) => ({
    perfilProfessor: build.query<PerfilProfessor, void>({ query: () => "/teacher/perfil/", providesTags: ["Perfil"] }),
    mudarPerfilProfessor: build.mutation<PerfilProfessor, MudancaPerfilProfessor>({
      query: (body) => ({ url: "/teacher/perfil/", method: "PATCH", body }),
      invalidatesTags: ["Perfil"],
    }),
    tirarFotografia: build.mutation<PerfilProfessor, void>({
      query: () => ({ url: "/teacher/perfil/fotografia/", method: "DELETE" }),
      invalidatesTags: ["Perfil"],
    }),
  }),
});

export const { usePerfilProfessorQuery, useMudarPerfilProfessorMutation, useTirarFotografiaMutation } = perfilApi;
