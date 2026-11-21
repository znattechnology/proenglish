/**
 * Níveis CEFR (A1 a C2) usados na primeira entrada. Igual a apps/web/src/domains/shared/niveis.ts.
 */
export const NIVEIS_CEFR = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;
export type NivelCefr = (typeof NIVEIS_CEFR)[number];

export const NOME_NIVEL: Record<NivelCefr, string> = {
  A1: "Iniciante",
  A2: "Elementar",
  B1: "Intermédio",
  B2: "Intermédio avançado",
  C1: "Avançado",
  C2: "Proficiente",
};

export const DESCRICAO_NIVEL: Record<NivelCefr, string> = {
  A1: "Conheço palavras e frases muito simples",
  A2: "Consigo falar de rotinas e tarefas simples",
  B1: "Consigo conversar sobre o trabalho com algum apoio",
  B2: "Participo em reuniões e discussões com à-vontade",
  C1: "Exprimo-me com fluência e precisão em contexto profissional",
  C2: "Uso o inglês como um falante nativo",
};

const ANTIGOS: Record<string, NivelCefr> = { Beginner: "A2", Intermediate: "B1", Advanced: "B2" };

export function eNivel(valor: unknown): valor is NivelCefr {
  return typeof valor === "string" && (NIVEIS_CEFR as readonly string[]).includes(valor);
}

export function normalizarNivel(valor?: string | null): NivelCefr | undefined {
  if (!valor) return undefined;
  const v = valor.trim().replace(/^nível\s+/i, "");
  if (eNivel(v.toUpperCase())) return v.toUpperCase() as NivelCefr;
  return ANTIGOS[v];
}

/** "B1 (Intermédio)". */
export function nomeCompletoNivel(valor?: string | null) {
  const c = normalizarNivel(valor);
  return c ? `${c} (${NOME_NIVEL[c]})` : "";
}

export const OPCOES_NIVEL = NIVEIS_CEFR.map((valor) => ({ valor, nome: `${valor} (${NOME_NIVEL[valor]})`, descricao: DESCRICAO_NIVEL[valor] }));

function distancia(a?: string | null, b?: string | null) {
  const x = normalizarNivel(a);
  const y = normalizarNivel(b);
  if (!x || !y) return undefined;
  return NIVEIS_CEFR.indexOf(y) - NIVEIS_CEFR.indexOf(x);
}

/** Curso a sugerir: o do mesmo nível, depois um abaixo; depois o mais perto abaixo e só depois acima. */
export function sugerirPorNivel<T extends { level?: string | null }>(cursos: T[], nivel?: string | null): T | undefined {
  const alvo = normalizarNivel(nivel);
  if (!alvo) return cursos[0];
  const custo = (c: T) => {
    const d = distancia(alvo, c.level);
    if (d === undefined) return 100;
    if (d === 0) return 0;
    if (d === -1) return 1;
    return d < 0 ? 10 - d : 20 + d;
  };
  return cursos.reduce<T | undefined>((melhor, c) => (melhor === undefined || custo(c) < custo(melhor) ? c : melhor), undefined);
}

/** Nível das 5 perguntas escritas: 0 certas A1; 1-2 A2; 3 B1; 4-5 B2. */
export function nivelDoTeste(certas: number): NivelCefr {
  if (certas <= 0) return "A1";
  if (certas <= 2) return "A2";
  if (certas === 3) return "B1";
  return "B2";
}
