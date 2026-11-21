/**
 * Motor dos sons das lições no telemóvel (apps/web/components/pe/licao/sons.ts): toques de marimba,
 * frases da Professora Luena e vibração. As regras de quando tocam estão em @/dominios/laboratorio/sons.
 */
import { createAudioPlayer, type AudioPlayer } from "expo-audio";
import * as Haptics from "expo-haptics";
import type { FalaLuena, Toque } from "@/dominios/laboratorio/sons";
import { modoOuvir } from "./Audio";

const TOQUES: Record<Toque, number> = {
  certo: require("@/assets/sons/certo.mp3"),
  errado: require("@/assets/sons/errado.mp3"),
  sequencia: require("@/assets/sons/sequencia.mp3"),
  "sem-vidas": require("@/assets/sons/sem-vidas.mp3"),
  concluida: require("@/assets/sons/concluida.mp3"),
  meta: require("@/assets/sons/meta.mp3"),
};

const FALAS: Record<FalaLuena, number> = {
  "inicio-1": require("@/assets/sons/luena/inicio-1.mp3"),
  "inicio-2": require("@/assets/sons/luena/inicio-2.mp3"),
  "certo-1": require("@/assets/sons/luena/certo-1.mp3"),
  "certo-2": require("@/assets/sons/luena/certo-2.mp3"),
  "certo-3": require("@/assets/sons/luena/certo-3.mp3"),
  "certo-4": require("@/assets/sons/luena/certo-4.mp3"),
  "certo-5": require("@/assets/sons/luena/certo-5.mp3"),
  "certo-6": require("@/assets/sons/luena/certo-6.mp3"),
  "pronuncia-certo": require("@/assets/sons/luena/pronuncia-certo.mp3"),
  "seguidas-3": require("@/assets/sons/luena/seguidas-3.mp3"),
  "seguidas-5": require("@/assets/sons/luena/seguidas-5.mp3"),
  "errado-1": require("@/assets/sons/luena/errado-1.mp3"),
  "errado-2": require("@/assets/sons/luena/errado-2.mp3"),
  "errado-3": require("@/assets/sons/luena/errado-3.mp3"),
  "fala-errado": require("@/assets/sons/luena/fala-errado.mp3"),
  "sem-vidas": require("@/assets/sons/luena/sem-vidas.mp3"),
  "concluida-1": require("@/assets/sons/luena/concluida-1.mp3"),
  "concluida-2": require("@/assets/sons/luena/concluida-2.mp3"),
  meta: require("@/assets/sons/luena/meta.mp3"),
};

const VIBRACAO: Record<Toque, () => Promise<void>> = {
  certo: () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success),
  sequencia: () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success),
  errado: () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error),
  "sem-vidas": () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning),
  concluida: () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success),
  meta: () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success),
};

/** Um leitor por ficheiro, criado na primeira vez e reutilizado (a lição tem poucos sons). */
const leitores = new Map<number, AudioPlayer>();
function leitor(fonte: number, volume: number): AudioPlayer | null {
  try {
    let p = leitores.get(fonte);
    if (!p) {
      p = createAudioPlayer(fonte);
      leitores.set(fonte, p);
    }
    p.volume = volume;
    return p;
  } catch {
    return null;
  }
}

let falaActual: { p: AudioPlayer; fim: { remove: () => void } } | null = null;
let falaPendente: ReturnType<typeof setTimeout> | null = null;

/** Prepara os leitores ao abrir a lição, para o primeiro toque não atrasar. */
export function precarregar(comVoz: boolean) {
  Object.values(TOQUES).forEach((f) => leitor(f, 0.55));
  if (comVoz) Object.values(FALAS).forEach((f) => leitor(f, 1));
}

/** Liberta os leitores ao sair da lição. */
export function libertar() {
  pararFala();
  leitores.forEach((p) => {
    try {
      p.remove();
    } catch {}
  });
  leitores.clear();
}

/** Pára a frase da Luena (ao continuar ou ao sair). */
export function pararFala() {
  if (falaPendente) clearTimeout(falaPendente);
  falaPendente = null;
  if (falaActual) {
    falaActual.fim.remove();
    try {
      falaActual.p.pause();
    } catch {}
  }
  falaActual = null;
}

function tocarDoInicio(p: AudioPlayer) {
  void p.seekTo(0).catch(() => undefined);
  p.play();
}

/**
 * Toca o toque (com vibração) e, um pouco depois, a frase da Luena. `aoFalar` recebe a frase
 * quando começa e null quando acaba (legenda no rodapé).
 */
export function tocar(
  { toque, fala }: { toque: Toque | null; fala: FalaLuena | null },
  opcoes: { sons: boolean; voz: boolean; aoFalar?: (f: FalaLuena | null) => void }
) {
  pararFala();
  if (toque) {
    // A vibração acompanha o toque; com os sons desligados, fica só a vibração.
    void VIBRACAO[toque]().catch(() => undefined);
    if (opcoes.sons) {
      const p = leitor(TOQUES[toque], 0.55);
      if (p) {
        void modoOuvir();
        tocarDoInicio(p);
      }
    }
  }
  if (!opcoes.voz || !fala) return;
  falaPendente = setTimeout(
    () => {
      falaPendente = null;
      const p = leitor(FALAS[fala], 1);
      if (!p) return;
      void modoOuvir();
      const fim = p.addListener("playbackStatusUpdate", (s) => {
        if (!s.didJustFinish) return;
        fim.remove();
        if (falaActual?.p === p) falaActual = null;
        opcoes.aoFalar?.(null);
      });
      falaActual = { p, fim };
      tocarDoInicio(p);
      opcoes.aoFalar?.(fala);
    },
    opcoes.sons && toque ? 380 : 0
  );
}
