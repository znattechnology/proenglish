/**
 * Envio das gravações (multipart) com `pedir()` — como apps/web/src/domains/student/laboratorio/enviarGravacao.ts.
 * Usado pela lição (pronúncia e Responder) e pela revisão.
 *
 * Respostas que o ecrã trata:
 * - 422 sem_fala / gravacao_invalida e 413 gravacao_grande: gravar outra vez (nunca tiram vidas);
 * - 503 analise_indisponivel (+ token_saltar na lição, pode_saltar na revisão): saltar sem perder nada;
 * - 400 {error: "hearts"}: sem vidas; 429: limite de análises do dia.
 */
import { pedir } from "@/api/base";
import type { ResultadoPronuncia, ResultadoResponder } from "./api";

/** Gravações curtas: param sozinhas ao fim deste tempo (o servidor recusa mais de 5 MB). */
export const MAX_SEGUNDOS_GRAVACAO = 90;

export type Gravacao = { uri: string; segundos: number };

export type ErroGravacao = {
  status: number | "FETCH_ERROR";
  data?: { codigo?: string; error?: string; mensagem?: string; message?: string; pode_saltar?: boolean; token_saltar?: string };
};

export type ResultadoEnvio<T> = { data: T; error?: undefined } | { error: ErroGravacao; data?: undefined };

/** O ficheiro gravado pelo expo-audio (.m4a, AAC) como parte de um FormData do React Native. */
function ficheiro(g: Gravacao, nome: string) {
  return { uri: g.uri, name: `${nome}.m4a`, type: "audio/mp4" } as unknown as Blob;
}

export async function enviarGravacao<T>(caminho: string, campos: Record<string, string>, g: Gravacao, nome = "gravacao"): Promise<ResultadoEnvio<T>> {
  const corpo = new FormData();
  corpo.append("audio", ficheiro(g, nome));
  for (const [k, v] of Object.entries(campos)) corpo.append(k, v);
  try {
    const r = await pedir<T>(caminho, { method: "POST", body: corpo });
    return r.ok ? { data: r.data } : { error: { status: r.status, data: (r.data ?? {}) as ErroGravacao["data"] } };
  } catch {
    return { error: { status: "FETCH_ERROR" } };
  }
}

/** Exercício de pronúncia (SPEAKING): a frase vem do exercício no servidor. */
export function analisarPronuncia(challengeId: string, frase: string, g: Gravacao) {
  return enviarGravacao<ResultadoPronuncia>("/practice/analyze-ai-pronunciation/", { challenge_id: challengeId, expected_text: frase }, g);
}

/** Responder em voz alta: transcrição e avaliação no servidor. */
export function responderEmVoz(challengeId: string, g: Gravacao) {
  return enviarGravacao<ResultadoResponder>(`/student/practice-courses/challenges/${challengeId}/responder/`, {}, g, "resposta");
}
