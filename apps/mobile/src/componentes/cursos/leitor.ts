/**
 * Pequenas acções sobre o leitor de vídeo e o relógio, fora dos componentes
 * (o React Compiler não deixa mudar o leitor nem ler o relógio dentro do corpo de um componente).
 */
import type { VideoPlayer } from "expo-video";

/** Salta para um instante do vídeo e reproduz. */
export function tocarDesde(player: VideoPlayer, segundos: number) {
  player.currentTime = segundos;
  player.play();
}

/** Milissegundos actuais. */
export function agora() {
  return Date.now();
}
