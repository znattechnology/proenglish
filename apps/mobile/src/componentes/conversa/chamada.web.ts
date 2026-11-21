/**
 * Versão web da chamada de voz: a app web (react-native-web) não tem o módulo nativo Daily/WebRTC.
 * Mesma interface que chamada.ts; `vozDisponivel()` diz sempre que não e `ligar()` falha.
 */
import type { Chamada, Disponibilidade, EventosChamada } from "./chamada";

export type { Chamada, Disponibilidade, EventosChamada, Quem } from "./chamada";

export function vozDisponivel(): Disponibilidade {
  return { disponivel: false, motivo: "A conversa por voz não funciona na versão web da app. Use o site do ProEnglish ou a app no telemóvel." };
}

export async function ligar(_chave: string, _assistente: string, _overrides: Record<string, unknown>, _ev: EventosChamada): Promise<Chamada> {
  throw new Error("sem_modulo");
}
