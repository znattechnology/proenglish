/**
 * Ler um texto em inglês com a voz do telemóvel (expo-speech, funciona também no Expo Go).
 * Usado no modo de ensaio (o tutor "fala" a resposta do guião), em "Ouvir outra vez",
 * "Ouvir a frase certa" e nas frases-alvo. Não gasta nada no servidor.
 */
import * as Speech from "expo-speech";

let actual = 0;

export function falar(texto: string, aoAcabar?: () => void) {
  const t = texto.trim();
  if (!t) return aoAcabar?.();
  const minha = ++actual;
  let acabou = false;
  const fim = () => {
    if (acabou) return;
    acabou = true;
    aoAcabar?.();
  };
  void Speech.stop()
    .catch(() => {})
    .then(() => {
      if (minha !== actual) return fim(); // outra fala começou entretanto
      Speech.speak(t, { language: "en-GB", rate: 0.95, onDone: fim, onStopped: fim, onError: fim });
    });
}

export function pararDeFalar() {
  actual++;
  void Speech.stop().catch(() => {});
}
