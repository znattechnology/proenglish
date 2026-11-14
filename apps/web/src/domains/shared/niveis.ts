/**
 * Escala única de níveis de inglês (CEFR A1 a C2), usada nos cursos (vídeo e prática), no perfil
 * do estudante e no tutor. Espelha apps/api/apps/courses/niveis.py.
 *
 * A API já só guarda CEFR; os nomes antigos (Beginner/Intermediate/Advanced) ainda são lidos e
 * traduzidos por `normalizarNivel` para não partir dados em cache.
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

/** O que a pessoa consegue fazer em cada nível, na primeira pessoa e em linguagem simples. */
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

/** Código CEFR de um valor vindo da API (aceita os nomes antigos); undefined se não for um nível. */
export function normalizarNivel(valor?: string | null): NivelCefr | undefined {
  if (!valor) return undefined;
  const v = valor.trim().replace(/^nível\s+/i, ""); // a API mostra "Nível B1"
  if (eNivel(v.toUpperCase())) return v.toUpperCase() as NivelCefr;
  return ANTIGOS[v];
}

/** "Nível B1" (para metadados e etiquetas); undefined sem nível. */
export function rotuloNivel(valor?: string | null): string | undefined {
  const c = normalizarNivel(valor);
  return c ? `Nível ${c}` : undefined;
}

/** "nível B1" (a meio de uma frase: "Petróleo e Gás, nível B1"); undefined sem nível. */
export function nivelEmFrase(valor?: string | null): string | undefined {
  const c = normalizarNivel(valor);
  return c ? `nível ${c}` : undefined;
}

/** "B1 (Intermédio)" (para opções de escolha do professor). */
export function nomeCompletoNivel(valor?: string | null): string | undefined {
  const c = normalizarNivel(valor);
  return c ? `${c} (${NOME_NIVEL[c]})` : undefined;
}

/** Opções para selects: valor CEFR, nome "B1 (Intermédio)" e a descrição em linguagem simples. */
export const OPCOES_NIVEL = NIVEIS_CEFR.map((valor) => ({
  valor,
  nome: `${valor} (${NOME_NIVEL[valor]})`,
  descricao: DESCRICAO_NIVEL[valor],
}));

/** Distância em níveis (b - a); undefined se algum não for reconhecido. */
export function distanciaNivel(a?: string | null, b?: string | null): number | undefined {
  const x = normalizarNivel(a);
  const y = normalizarNivel(b);
  if (!x || !y) return undefined;
  return NIVEIS_CEFR.indexOf(y) - NIVEIS_CEFR.indexOf(x);
}

/**
 * Curso a sugerir para um nível: primeiro um do mesmo nível, depois um nível abaixo; sem nenhum
 * nessa banda, o mais próximo abaixo e só depois o mais próximo acima. undefined se a lista for vazia.
 */
export function sugerirPorNivel<T extends { level?: string | null }>(cursos: T[], nivel?: string | null): T | undefined {
  const alvo = normalizarNivel(nivel);
  if (!alvo) return cursos[0];
  const custo = (c: T) => {
    const d = distanciaNivel(alvo, c.level);
    if (d === undefined) return 100;
    if (d === 0) return 0;
    if (d === -1) return 1;
    return d < 0 ? 10 - d : 20 + d; // abaixo antes de acima, o mais perto primeiro
  };
  return cursos.reduce<T | undefined>((melhor, c) => (melhor === undefined || custo(c) < custo(melhor) ? c : melhor), undefined);
}

/**
 * Nível do teste de 5 perguntas da primeira entrada (dificuldade A1, A2, B1, B2, C1).
 * 0 certas: A1; 1 ou 2: A2; 3: B1; 4 ou 5: B2. Não passa de B2: uma só pergunta de C1 não chega
 * para o confirmar (o teste falado da fase 6 substitui este).
 */
export function nivelDoTeste(certas: number): NivelCefr {
  if (certas <= 0) return "A1";
  if (certas <= 2) return "A2";
  if (certas === 3) return "B1";
  return "B2";
}
