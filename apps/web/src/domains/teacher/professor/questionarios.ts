/** Questionários que um aluno ainda não passou nos cursos do professor, e tentativas extra. */
import { professorApi } from "./api";

export type QuestionarioDoAluno = {
  id: string;
  curso: { id: string; titulo: string };
  aula: { id: string; titulo: string };
  tentativas: number;
  limite: number;
  restantes: number;
  melhor_nota: number | null;
  nota_minima: number;
};

const questionariosApi = professorApi.enhanceEndpoints({ addTagTypes: ["QuestionariosAluno"] }).injectEndpoints({
  endpoints: (build) => ({
    questionariosAluno: build.query<QuestionarioDoAluno[], string>({
      query: (alunoId) => `/teacher/alunos/${alunoId}/questionarios/`,
      transformResponse: (r: { questionarios: QuestionarioDoAluno[] }) => r.questionarios ?? [],
      providesTags: (_r, _e, id) => [{ type: "QuestionariosAluno", id }],
    }),
    darTentativas: build.mutation<QuestionarioDoAluno, { alunoId: string; quizId: string; extra: number }>({
      query: ({ alunoId, quizId, extra }) => ({ url: `/teacher/alunos/${alunoId}/questionarios/${quizId}/tentativas/`, method: "POST", body: { extra } }),
      invalidatesTags: (_r, _e, a) => [{ type: "QuestionariosAluno", id: a.alunoId }],
    }),
  }),
});

export const { useQuestionariosAlunoQuery, useDarTentativasMutation } = questionariosApi;
