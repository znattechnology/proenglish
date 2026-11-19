"use client";

/**
 * Sons das lições do laboratório: toques de certo/errado (marimba, docs/conteudo/sons/sintetizar.py)
 * e frases curtas faladas pela Professora Luena. Tocam sempre depois da resposta do servidor;
 * nunca decidem nada. O aluno desliga-os nas definições (preferences.sons / voz_professora).
 */

/** Sobe quando os ficheiros mudam (p.ex. a voz clonada da Luena), para não ficar a versão em cache. */
const VERSAO = "1";

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

const urlToque = (t: Toque) => `/sons/${t}.mp3?v=${VERSAO}`;
const urlFala = (f: FalaLuena) => `/sons/luena/${f}.mp3?v=${VERSAO}`;

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

/* ------------------------------------------------------------------ */
/* Motor (Web Audio: baixa latência, volume por som)                    */
/* ------------------------------------------------------------------ */

let ctx: AudioContext | null = null;
const buffers = new Map<string, Promise<AudioBuffer | null>>();
let falaActual: AudioBufferSourceNode | null = null;
let falaPendente: ReturnType<typeof setTimeout> | null = null;

function contexto(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (!ctx) {
    const C = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!C) return null;
    try {
      ctx = new C();
    } catch {
      return null;
    }
  }
  return ctx;
}

function carregar(url: string): Promise<AudioBuffer | null> {
  let p = buffers.get(url);
  if (!p) {
    const c = contexto();
    p = !c
      ? Promise.resolve(null)
      : fetch(url)
          .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(String(r.status)))))
          .then((b) => c.decodeAudioData(b))
          .catch(() => {
            buffers.delete(url); // tenta outra vez da próxima
            return null;
          });
    buffers.set(url, p);
  }
  return p;
}

async function tocarUrl(url: string, volume: number): Promise<AudioBufferSourceNode | null> {
  const c = contexto();
  if (!c) return null;
  // Sem um gesto do aluno o browser deixa o contexto suspenso: tenta retomar e, se não der, cala-se.
  if (c.state === "suspended") await c.resume().catch(() => undefined);
  if (c.state !== "running") return null;
  const buf = await carregar(url);
  if (!buf) return null;
  const fonte = c.createBufferSource();
  const ganho = c.createGain();
  ganho.gain.value = volume;
  fonte.buffer = buf;
  fonte.connect(ganho).connect(c.destination);
  fonte.start();
  return fonte;
}

/** Descarrega os sons antes de serem precisos (chamado ao abrir a lição). */
export function precarregar(comVoz: boolean) {
  (["certo", "errado", "sequencia", "sem-vidas", "concluida", "meta"] as const).forEach((t) => void carregar(urlToque(t)));
  if (comVoz) (Object.keys(FRASES_LUENA) as FalaLuena[]).forEach((f) => void carregar(urlFala(f)));
}

/** Pára a frase da Luena (ao continuar para o exercício seguinte ou ao sair). */
export function pararFala() {
  if (falaPendente) clearTimeout(falaPendente);
  falaPendente = null;
  try {
    falaActual?.stop();
  } catch {}
  falaActual = null;
}

/**
 * Toca o toque e, um pouco depois, a frase da Luena. `aoFalar` recebe a frase quando começa e
 * null quando acaba (para a legenda no rodapé).
 */
export function tocar(
  { toque, fala }: { toque: Toque | null; fala: FalaLuena | null },
  opcoes: { sons: boolean; voz: boolean; aoFalar?: (f: FalaLuena | null) => void }
) {
  pararFala();
  if (opcoes.sons && toque) void tocarUrl(urlToque(toque), 0.55);
  if (!opcoes.voz || !fala) return;
  falaPendente = setTimeout(
    async () => {
      falaPendente = null;
      const fonte = await tocarUrl(urlFala(fala), 1);
      if (!fonte) return;
      falaActual = fonte;
      opcoes.aoFalar?.(fala);
      fonte.onended = () => {
        if (falaActual === fonte) falaActual = null;
        opcoes.aoFalar?.(null);
      };
    },
    opcoes.sons && toque ? 380 : 0
  );
}
