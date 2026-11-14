/**
 * Gravar a voz do aluno (pronúncia, Responder, revisão) com o expo-audio.
 * Antes do primeiro pedido de microfone mostra a explicação (tela PermissaoMicrofone do canvas).
 * Pára sozinha aos 45 s. Cada gravação acabada vai para `aoGravado` ({uri, segundos}).
 */
import {
  getRecordingPermissionsAsync,
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
  type RecordingOptions,
} from "expo-audio";
import * as Speech from "expo-speech";
import { Check, Mic, ShieldCheck, Square } from "lucide-react-native";
import { useEffect, useRef, useState } from "react";
import { Linking, Pressable, View } from "react-native";
import { MAX_SEGUNDOS_GRAVACAO, type Gravacao } from "@/dominios/laboratorio/gravacao";
import { balao, cor } from "@/tema";
import { Botao, Dialogo, Texto } from "@/ui";
import { modoOuvir } from "./Audio";

/** Mono, 64 kbit/s: 45 s ficam em ~360 KB (o servidor aceita até 5 MB). */
const OPCOES: RecordingOptions = { ...RecordingPresets.HIGH_QUALITY, numberOfChannels: 1, bitRate: 64000 };

export type EstadoGravador = "parado" | "a-gravar" | "gravado" | "sem-permissao" | "sem-microfone";

/** A explicação só aparece uma vez por sessão da app. */
let explicado = false;

export function useGravador(aoGravado: (g: Gravacao | null) => void) {
  const recorder = useAudioRecorder(OPCOES);
  const estadoRec = useAudioRecorderState(recorder, 250);
  const [estado, setEstado] = useState<EstadoGravador>("parado");
  const [explicar, setExplicar] = useState(false);
  const limite = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inicio = useRef(0);
  const aGravar = useRef(false);

  useEffect(
    () => () => {
      if (limite.current) clearTimeout(limite.current);
      if (aGravar.current) {
        aGravar.current = false;
        recorder.stop().catch(() => undefined);
        void modoOuvir();
      }
    },
    [recorder]
  );

  const parar = async () => {
    if (!aGravar.current) return;
    aGravar.current = false;
    if (limite.current) clearTimeout(limite.current);
    try {
      await recorder.stop();
    } catch {
      /* já parada */
    }
    await modoOuvir();
    const uri = recorder.uri;
    if (!uri) {
      setEstado("sem-microfone");
      aoGravado(null);
      return;
    }
    setEstado("gravado");
    aoGravado({ uri, segundos: Math.max(1, Math.round((Date.now() - inicio.current) / 1000)) });
  };

  const gravar = async () => {
    try {
      Speech.stop();
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      aGravar.current = true;
      inicio.current = Date.now();
      limite.current = setTimeout(() => void parar(), MAX_SEGUNDOS_GRAVACAO * 1000);
      setEstado("a-gravar");
      aoGravado(null);
    } catch {
      aGravar.current = false;
      await modoOuvir();
      setEstado("sem-microfone");
    }
  };

  const pedirEGravar = async () => {
    const p = await requestRecordingPermissionsAsync();
    if (p.granted) await gravar();
    else setEstado("sem-permissao");
  };

  const comecar = async () => {
    const p = await getRecordingPermissionsAsync();
    if (p.granted) return gravar();
    if (!p.canAskAgain) return setEstado("sem-permissao");
    if (!explicado) return setExplicar(true);
    await pedirEGravar();
  };

  const explicacao = (
    <PedirMicrofone
      aberto={explicar}
      aoFechar={() => setExplicar(false)}
      aoContinuar={() => {
        explicado = true;
        setExplicar(false);
        void pedirEGravar();
      }}
    />
  );

  return { estado, segundos: Math.floor(estadoRec.durationMillis / 1000), comecar, parar, explicacao };
}

export type Gravador = ReturnType<typeof useGravador>;

/** Explicação antes do pedido do sistema (tela PermissaoMicrofone, adaptada às lições). */
function PedirMicrofone({ aberto, aoFechar, aoContinuar }: { aberto: boolean; aoFechar: () => void; aoContinuar: () => void }) {
  return (
    <Dialogo
      aberto={aberto}
      aoFechar={aoFechar}
      titulo="Para avaliar a sua fala, precisamos de o ouvir"
      texto="A seguir, o telemóvel pergunta se deixa usar o microfone. Toque em Permitir."
    >
      <View style={{ gap: 10 }}>
        {["Só gravamos quando toca no microfone, e no máximo 45 segundos.", "A gravação serve para corrigir a sua pronúncia e não é partilhada."].map((t) => (
          <View key={t} style={{ flexDirection: "row", gap: 10 }}>
            <ShieldCheck size={20} color={cor.certo} />
            <Texto v="legenda" style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>
              {t}
            </Texto>
          </View>
        ))}
      </View>
      <Botao larguraTotal onPress={aoContinuar}>
        Continuar
      </Botao>
      <Botao tipo="ligacao" larguraTotal onPress={aoFechar}>
        Agora não
      </Botao>
    </Dialogo>
  );
}

const MENSAGEM: Partial<Record<EstadoGravador, string>> = {
  "sem-permissao": "O telemóvel não deixou usar o microfone. Permita o microfone ao ProEnglish nas definições e volte a tocar em gravar.",
  "sem-microfone": "Não conseguimos gravar. Verifique se outra app está a usar o microfone e toque em gravar outra vez.",
};

export function textoGravacao(g: Gravador) {
  if (g.estado === "a-gravar") return `A gravar… ${g.segundos} s. Toque para parar (no máximo ${MAX_SEGUNDOS_GRAVACAO} segundos)`;
  if (g.estado === "gravado") return "Gravado. Pode verificar ou gravar outra vez.";
  return "Toque para gravar";
}

/** O botão grande de gravar (balão azul; vermelho com um quadrado enquanto grava) e o estado por baixo. */
export function BotaoGravar({ g, bloqueado, aoSaltar, textoSaltar, semLegenda }: { g: Gravador; bloqueado: boolean; aoSaltar?: () => void; textoSaltar?: string; semLegenda?: boolean }) {
  const aGravar = g.estado === "a-gravar";
  const aviso = MENSAGEM[g.estado];
  return (
    <View style={{ alignItems: "center", gap: 10 }}>
      {aviso ? (
        <View accessibilityRole="alert" style={{ backgroundColor: cor.realceSuave, borderRadius: 12, padding: 14, gap: 8, alignSelf: "stretch" }}>
          <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
            {aviso}
            {aoSaltar && textoSaltar ? ` ${textoSaltar}` : ""}
          </Texto>
          {g.estado === "sem-permissao" ? (
            <Botao tipo="ligacao" tamanho="pequeno" onPress={() => void Linking.openSettings()}>
              Abrir as definições
            </Botao>
          ) : null}
          {aoSaltar ? (
            <Botao tipo="ligacao" tamanho="pequeno" disabled={bloqueado} onPress={aoSaltar}>
              Saltar este exercício
            </Botao>
          ) : null}
        </View>
      ) : null}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={aGravar ? "Parar a gravação" : g.estado === "gravado" ? "Gravar outra vez" : "Gravar"}
        accessibilityState={{ disabled: bloqueado }}
        disabled={bloqueado}
        onPress={() => void (aGravar ? g.parar() : g.comecar())}
        style={({ pressed }) => [
          balao.grande,
          {
            width: 80,
            height: 80,
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: aGravar ? cor.errado : pressed ? cor.azulVivo : cor.azulMarca,
            opacity: bloqueado ? 0.6 : 1,
          },
        ]}
      >
        {aGravar ? <Square size={30} color={cor.sobreMarca} fill={cor.sobreMarca} /> : <Mic size={34} color={cor.sobreMarca} />}
      </Pressable>
      {semLegenda ? null : (
        <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          {g.estado === "gravado" ? <Check size={16} color={cor.certo} /> : null}
          <Texto v="legenda" suave centro accessibilityLiveRegion="polite">
            {textoGravacao(g)}
          </Texto>
        </View>
      )}
      {g.explicacao}
    </View>
  );
}
