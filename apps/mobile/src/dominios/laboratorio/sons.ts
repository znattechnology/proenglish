/**
 * Regras dos sons das lições: igual a apps/web/components/pe/licao/sons.ts (manter as duas iguais).
 * Toques de certo/errado e frases da Professora Luena; só servem para escolher o som, nunca decidem nada.
 */

export type Toque = "certo" | "errado" | "sequencia" | "sem-vidas" | "concluida" | "meta";

/** Frases da Luena (o texto aparece no rodapé enquanto ela fala). */
export const FRASES_LUENA = {
  "inicio-1": "Hello! Let's practise together.",
  "inicio-2": "Hi! I'm here with you. Let's begin.",
  "certo-1": "Well done!",
  "certo-2": "Great job!",
  "certo-3": "Perfect!",
  "certo-4": "Excellent!",
  "certo-5": "That's right!",
  "certo-6": "Nice work!",
  "pronuncia-certo": "Beautiful pronunciation!",
  "seguidas-3": "Three in a row! Keep going!",
  "seguidas-5": "Five in a row! Fantastic!",
  "errado-1": "Almost! Let's try again later.",
  "errado-2": "Not quite. You'll get it next time.",
  "errado-3": "Don't worry. Mistakes help us learn.",
  "fala-errado": "Good try! Listen and say it again.",
  "sem-vidas": "Take a short break, and come back soon.",
  "concluida-1": "You did it! See you tomorrow.",
  "concluida-2": "Lesson complete! I'm proud of you.",
  meta: "You reached your daily goal. Brilliant!",
} as const;

export type FalaLuena = keyof typeof FRASES_LUENA;

/* ------------------------------------------------------------------ */
/* Quando é que a Luena fala                                            */
/* ------------------------------------------------------------------ */

/** Contagens da lição em curso (só no cliente; servem apenas para escolher o som). */
export type Contagem = { certos: number; seguidos: number; errados: number };

export type Momento =
  | { tipo: "certo"; falado: boolean }
  | { tipo: "errado"; falado: boolean }
  | { tipo: "sem-vidas" }
  | { tipo: "concluida"; meta: boolean };

const escolher = <T,>(lista: readonly T[], n: number) => lista[n % lista.length];

/**
 * O toque e a frase de cada momento. A Luena não fala a cada exercício, para não cansar:
 * nas sequências de 3 e 5 certos, no 1.º certo e depois de 4 em 4, no 1.º erro e depois de
 * 3 em 3, e sempre no fim. `contagem` já inclui a resposta deste momento.
 */
export function somDoMomento(m: Momento, c: Contagem): { toque: Toque; fala: FalaLuena | null } {
  switch (m.tipo) {
    case "certo": {
      if (c.seguidos === 3) return { toque: "sequencia", fala: "seguidas-3" };
      if (c.seguidos === 5) return { toque: "sequencia", fala: "seguidas-5" };
      if (c.certos % 4 !== 1) return { toque: "certo", fala: null };
      if (m.falado) return { toque: "certo", fala: "pronuncia-certo" };
      return { toque: "certo", fala: escolher(["certo-1", "certo-2", "certo-3", "certo-4", "certo-5", "certo-6"] as const, Math.floor(c.certos / 4)) };
    }
    case "errado":
      if (c.errados % 3 !== 1) return { toque: "errado", fala: null };
      if (m.falado) return { toque: "errado", fala: "fala-errado" };
      return { toque: "errado", fala: escolher(["errado-1", "errado-2", "errado-3"] as const, Math.floor(c.errados / 3)) };
    case "sem-vidas":
      return { toque: "sem-vidas", fala: "sem-vidas" };
    case "concluida":
      return m.meta ? { toque: "meta", fala: "meta" } : { toque: "concluida", fala: escolher(["concluida-1", "concluida-2"] as const, c.certos) };
  }
}
