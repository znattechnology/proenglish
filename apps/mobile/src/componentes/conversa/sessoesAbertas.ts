/**
 * A sessão acabada de criar no separador "Conversa" passa para o ecrã da chamada por aqui
 * (é grande demais para ir nos parâmetros da rota). Se a app recomeçar, perde-se: o ecrã da
 * chamada mostra então "Esta conversa já não está aberta".
 */
import type { ModoConversa, NovaSessao } from "@/dominios/conversa/api";

export type SessaoAberta = { sessao: NovaSessao; modo: ModoConversa; chavePublica: string | null; minutosUsadosHoje: number; minutosDia: number | null };

const abertas = new Map<string, SessaoAberta>();

export function guardarSessao(s: SessaoAberta) {
  abertas.set(s.sessao.id, s);
}

export function lerSessao(id: string | undefined) {
  return id ? abertas.get(id) ?? null : null;
}

export function esquecerSessao(id: string) {
  abertas.delete(id);
}
