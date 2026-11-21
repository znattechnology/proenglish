/**
 * Ouvir: áudio de referência do professor (URL, expo-audio) e frases sem áudio lidas pela voz do
 * telemóvel em inglês (expo-speech), como a web faz com a voz do browser.
 */
import { setAudioModeAsync, useAudioPlayer, useAudioPlayerStatus } from "expo-audio";
import * as Speech from "expo-speech";
import { Volume2 } from "lucide-react-native";
import { useEffect, useState } from "react";
import { Pressable, View } from "react-native";
import { urlAbsoluto } from "@/api/config";
import { balao, cor } from "@/tema";
import { Texto } from "@/ui";

/** Volta ao modo de reprodução pelo altifalante (depois de gravar, o iOS fica em modo de chamada). */
export function modoOuvir() {
  return setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true }).catch(() => undefined);
}

/** Lê uma frase em inglês com a voz do telemóvel. */
export function falarTexto(texto: string, aoAcabar?: () => void) {
  Speech.stop();
  Speech.speak(texto, { language: "en-GB", rate: 0.95, onDone: aoAcabar, onStopped: aoAcabar, onError: aoAcabar });
}

function LigacaoOuvir({ rotulo, aTocar, sobreMarca, onPress, textoATocar = "A tocar" }: { rotulo: string; aTocar: boolean; sobreMarca?: boolean; onPress: () => void; textoATocar?: string }) {
  const c = sobreMarca ? cor.sobreMarca : cor.azulMarca;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={aTocar ? textoATocar : rotulo}
      onPress={onPress}
      hitSlop={4}
      style={{ alignSelf: "flex-start", minHeight: 44, flexDirection: "row", alignItems: "center", gap: 8 }}
    >
      <Volume2 size={20} color={c} />
      <Texto v="rotulo" cor={c} style={{ textDecorationLine: "underline" }}>
        {aTocar ? textoATocar : rotulo}
      </Texto>
    </Pressable>
  );
}

/** Ligação "Ouvir" que toca um ficheiro de áudio. */
export function BotaoOuvir({ src, rotulo = "Ouvir", sobreMarca }: { src: string; rotulo?: string; sobreMarca?: boolean }) {
  const player = useAudioPlayer(urlAbsoluto(src));
  const estado = useAudioPlayerStatus(player);
  const tocar = async () => {
    Speech.stop();
    await modoOuvir();
    await player.seekTo(0);
    player.play();
  };
  return <LigacaoOuvir rotulo={rotulo} aTocar={estado.playing} sobreMarca={sobreMarca} onPress={() => void tocar()} />;
}

/** Ligação "Ouvir" que lê o texto em inglês. */
export function BotaoOuvirTexto({ texto, rotulo = "Ouvir", sobreMarca, textoATocar = "A ler" }: { texto: string; rotulo?: string; sobreMarca?: boolean; textoATocar?: string }) {
  const [aTocar, setATocar] = useState(false);
  useEffect(() => () => void Speech.stop(), []);
  return (
    <LigacaoOuvir
      rotulo={rotulo}
      textoATocar={textoATocar}
      aTocar={aTocar}
      sobreMarca={sobreMarca}
      onPress={() => {
        setATocar(true);
        void modoOuvir().then(() => falarTexto(texto, () => setATocar(false)));
      }}
    />
  );
}

/** Ditado (LicaoEscuta): botão grande em balão e "Devagar". */
export function OuvirGrande({ src }: { src: string }) {
  const player = useAudioPlayer(urlAbsoluto(src));
  const estado = useAudioPlayerStatus(player);
  const tocar = async (ritmo: number) => {
    await modoOuvir();
    player.setPlaybackRate(ritmo);
    await player.seekTo(0);
    player.play();
  };
  return (
    <View style={[balao.grande, { backgroundColor: cor.fundoSuave, padding: 24, alignItems: "center", gap: 16 }]}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 20 }}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={estado.playing ? "A tocar" : "Ouvir a frase"}
          onPress={() => void tocar(1)}
          style={({ pressed }) => [balao.grande, { width: 84, height: 84, alignItems: "center", justifyContent: "center", backgroundColor: pressed ? cor.azulVivo : cor.azulMarca }]}
        >
          <Volume2 size={36} color={cor.sobreMarca} />
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Ouvir devagar"
          onPress={() => void tocar(0.7)}
          style={({ pressed }) => ({ minHeight: 52, paddingHorizontal: 18, justifyContent: "center", borderWidth: 2, borderColor: cor.azulMarca, borderRadius: 6, backgroundColor: pressed ? cor.fundoSuave : cor.fundo })}
        >
          <Texto v="rotulo" cor={cor.azulMarca} style={{ fontSize: 16 }}>
            Devagar
          </Texto>
        </Pressable>
      </View>
      <Texto v="legenda" suave accessibilityLiveRegion="polite">
        {estado.playing ? "A tocar…" : "Toque para ouvir. Pode ouvir as vezes que precisar."}
      </Texto>
    </View>
  );
}
