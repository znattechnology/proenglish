/** Regras comuns das gravações dos alunos (lições e revisão). */

/** Gravações curtas: pára sozinha ao fim deste tempo (o servidor recusa ficheiros grandes). */
export const MAX_SEGUNDOS_GRAVACAO = 90;

export type EstadoMicrofone = "parado" | "a-gravar" | "gravado" | "sem-permissao" | "sem-microfone" | "sem-suporte";

/** O motivo pelo qual não se conseguiu gravar, a partir do erro do getUserMedia. */
export function motivoSemGravacao(e: unknown): EstadoMicrofone {
  const nome = e instanceof DOMException || e instanceof Error ? e.name : "";
  if (nome === "NotFoundError" || nome === "OverconstrainedError" || nome === "NotReadableError") return "sem-microfone";
  if (nome === "NotAllowedError" || nome === "SecurityError") return "sem-permissao";
  return typeof navigator !== "undefined" && !navigator.mediaDevices?.getUserMedia ? "sem-suporte" : "sem-permissao";
}

export const MENSAGEM_SEM_GRAVACAO: Partial<Record<EstadoMicrofone, string>> = {
  "sem-permissao": "O navegador não deixou usar o microfone. Permita o microfone nas definições do navegador e volte a tocar em gravar.",
  "sem-microfone": "Não encontrámos nenhum microfone neste aparelho. Ligue um microfone (ou uns auscultadores com microfone) e volte a tocar em gravar.",
  "sem-suporte": "Este navegador não consegue gravar áudio.",
};
