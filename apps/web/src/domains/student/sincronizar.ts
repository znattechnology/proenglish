/**
 * As APIs do estudante são fatias separadas (cada uma com a sua cache). Quando uma acção muda dados
 * que outras mostram, estas funções avisam as outras, para não ficarem ecrãs desactualizados.
 */
import type { ThunkDispatch, UnknownAction } from "@reduxjs/toolkit";
import { progressoApi } from "@/src/domains/student/progresso/api";
import { studentVideoCourseApiSlice } from "@/src/domains/student/video-courses/api/studentVideoCourseApiSlice";
import { studentPracticeApiSlice } from "@/src/domains/student/practice-courses/api/studentPracticeApiSlice";

type Despacho = ThunkDispatch<any, any, UnknownAction>;

/** Depois de estudar (lição, conversa, aula): estatísticas, liga, conquistas e certificados mudam. */
export function aposEstudo(dispatch: Despacho) {
  dispatch(progressoApi.util.invalidateTags(["Estatisticas", "Liga", "Conquistas", "Certificados"]));
}

/** Depois de mudar o progresso num curso em vídeo: painel, "os meus cursos" e certificados. */
export function aposCurso(dispatch: Despacho) {
  dispatch(studentVideoCourseApiSlice.util.invalidateTags(["StudentVideoCourse", "VideoProgress", "CourseEnrollment"]));
  aposEstudo(dispatch);
}

/** A meta diária mudou: a sequência e as estatísticas mostram a meta nova. */
export function aposMeta(dispatch: Despacho) {
  dispatch(studentPracticeApiSlice.util.invalidateTags(["StudentStreak"]));
  dispatch(progressoApi.util.invalidateTags(["Estatisticas"]));
}

/** Corre a função quando o pedido corre bem (para usar em onQueryStarted). */
export function quandoCorrerBem(f: (d: Despacho) => void) {
  return async (_arg: unknown, { dispatch, queryFulfilled }: { dispatch: Despacho; queryFulfilled: Promise<unknown> }) => {
    try {
      await queryFulfilled;
      f(dispatch);
    } catch {
      /* o ecrã trata o erro */
    }
  };
}
