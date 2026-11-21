/**
 * "Para conversar, o tutor precisa de o ouvir" (tela PermissaoMicrofone do canvas).
 * Explica antes de o sistema perguntar, pede a permissão e, se foi recusada, leva às definições.
 *
 * Uso: const mic = useMicrofone(); ... if (!(await mic.garantir())) return; // abre a folha se for preciso
 *      <PermissaoMicrofone {...mic.folha} />
 */
import { getRecordingPermissionsAsync, requestRecordingPermissionsAsync } from "expo-audio";
import { ChevronLeft, Lock, Mic } from "lucide-react-native";
import { useRef, useState } from "react";
import { Linking, Modal, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Botao, BotaoIcone, Texto, Titulo } from "@/ui";
import { balao, cor } from "@/tema";

type Pedido = { resolver: (ok: boolean) => void };

/** Garante a permissão do microfone, mostrando a explicação quando o sistema ainda não perguntou ou foi recusada. */
export function useMicrofone() {
  const [aberta, setAberta] = useState(false);
  const [recusada, setRecusada] = useState(false);
  const pedido = useRef<Pedido | null>(null);

  const fechar = (ok: boolean) => {
    setAberta(false);
    pedido.current?.resolver(ok);
    pedido.current = null;
  };

  const garantir = async () => {
    try {
      const p = await getRecordingPermissionsAsync();
      if (p.granted) return true;
      setRecusada(!p.canAskAgain);
    } catch {
      return true; // sem forma de saber: a chamada pede ela própria
    }
    setAberta(true);
    return new Promise<boolean>((resolver) => {
      pedido.current = { resolver };
    });
  };

  const continuar = async () => {
    try {
      const p = await requestRecordingPermissionsAsync();
      if (p.granted) return fechar(true);
      setRecusada(true);
    } catch {
      setRecusada(true);
    }
  };

  return { garantir, folha: { aberta, recusada, aoContinuar: continuar, aoFechar: () => fechar(false) } };
}

export function PermissaoMicrofone({ aberta, recusada, aoContinuar, aoFechar, aoEscrever }: { aberta: boolean; recusada: boolean; aoContinuar: () => void; aoFechar: () => void; aoEscrever?: () => void }) {
  const ins = useSafeAreaInsets();
  return (
    <Modal visible={aberta} animationType="slide" onRequestClose={aoFechar} statusBarTranslucent>
      <View style={{ flex: 1, backgroundColor: cor.fundo, paddingTop: ins.top + 8, paddingBottom: Math.max(ins.bottom, 24), paddingHorizontal: 24 }}>
        <BotaoIcone rotulo="Voltar" onPress={aoFechar} style={{ marginLeft: -10 }}>
          <ChevronLeft size={26} color={cor.tinta} />
        </BotaoIcone>
        <View style={{ flex: 1, justifyContent: "center", gap: 24 }}>
          <View style={[balao.grande, { borderTopLeftRadius: 32, borderTopRightRadius: 32, borderBottomRightRadius: 32, width: 96, height: 96, alignItems: "center", justifyContent: "center", backgroundColor: cor.azulMarca }]}>
            <Mic size={44} color={cor.sobreMarca} />
          </View>
          <View style={{ gap: 10 }}>
            <Titulo>Para conversar, o tutor precisa de o ouvir</Titulo>
            {recusada ? (
              <Texto suave>
                O microfone está desligado para o ProEnglish. Abra as definições do telemóvel, ligue o <Texto forte>Microfone</Texto> e volte aqui.
              </Texto>
            ) : (
              <Texto suave>
                A seguir, o telemóvel pergunta se deixa usar o microfone. Toque em <Texto forte>Permitir</Texto>.
              </Texto>
            )}
          </View>
          <View style={{ gap: 10 }}>
            <Ponto>Só ouvimos durante a conversa, quando o microfone está aceso.</Ponto>
            <Ponto>O exame oral só é gravado se o autorizar. As conversas não são gravadas: guardamos o texto do que disse.</Ponto>
          </View>
        </View>
        <View style={{ gap: 10 }}>
          {recusada ? (
            <Botao larguraTotal onPress={() => void Linking.openSettings()}>
              Abrir as definições
            </Botao>
          ) : (
            <Botao larguraTotal onPress={aoContinuar}>
              Continuar
            </Botao>
          )}
          {recusada ? (
            <Botao tipo="ligacao" style={{ alignSelf: "center" }} onPress={aoContinuar}>
              Já autorizei
            </Botao>
          ) : null}
          {aoEscrever ? (
            <Botao tipo="ligacao" style={{ alignSelf: "center" }} onPress={aoEscrever}>
              Prefiro escrever as respostas
            </Botao>
          ) : null}
        </View>
      </View>
    </Modal>
  );
}

function Ponto({ children }: { children: string }) {
  return (
    <View style={{ flexDirection: "row", gap: 10 }}>
      <Lock size={20} color={cor.tinta} style={{ marginTop: 1 }} />
      <Texto v="legenda" style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>
        {children}
      </Texto>
    </View>
  );
}
