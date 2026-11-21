/*
 * Aviso «pratique primeiro»: ao abrir uma aula, o laboratório da aula anterior ainda por fazer.
 * Quem decide é o servidor (apps/api/apps/courses/percurso.py, campo pratica_anterior de cada aula);
 * aqui só se procura a aula e se lembra quando o aluno o fechou. Recomenda, nunca bloqueia.
 */

export type PraticaAnterior = {
  aula_id: string;
  aula_titulo: string;
  licao_id: string;
  curso_pratica_id: string;
  minutos: number | null;
};

type PercursoMinimo = { unidades: { aulas: { id: string; pratica_anterior?: PraticaAnterior | null }[] }[] };

/** O laboratório por fazer da aula anterior a esta, ou null. */
export function praticaAnterior(percurso: PercursoMinimo | undefined | null, aulaId: string): PraticaAnterior | null {
  if (!percurso) return null;
  for (const u of percurso.unidades) {
    for (const a of u.aulas) {
      if (a.id === aulaId) return a.pratica_anterior ?? null;
    }
  }
  return null;
}

/** Chave do «Continuar esta aula»: o aviso fecha nesta aula, para esta lição (volta na aula seguinte). */
export function chaveFechado(aulaId: string, licaoId: string): string {
  return `pe:pratica-anterior:${aulaId}:${licaoId}`;
}

export function foiFechado(guardado: Pick<Storage, "getItem"> | null, aulaId: string, licaoId: string): boolean {
  try {
    return guardado?.getItem(chaveFechado(aulaId, licaoId)) === "1";
  } catch {
    return false;
  }
}

export function fechar(guardado: Pick<Storage, "setItem"> | null, aulaId: string, licaoId: string): void {
  try {
    guardado?.setItem(chaveFechado(aulaId, licaoId), "1");
  } catch {
    /* sem armazenamento (janela privada): fecha só até sair da página */
  }
}
