import type { ReactNode } from "react";
import { Modal, Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { cor, raio } from "@/tema";
import { Texto, Titulo } from "./Texto";

/**
 * Folha de baixo (bottom sheet) para confirmações: "Sair da lição?", "Cancelar a renovação?".
 * As acções vêm em `children` (normalmente dois Botao com larguraTotal).
 */
export function Dialogo({ aberto, aoFechar, titulo, texto, children }: { aberto: boolean; aoFechar: () => void; titulo: string; texto?: string; children?: ReactNode }) {
  const ins = useSafeAreaInsets();
  return (
    <Modal visible={aberto} transparent animationType="slide" onRequestClose={aoFechar} statusBarTranslucent>
      <View style={{ flex: 1, justifyContent: "flex-end" }}>
        <Pressable accessibilityLabel="Fechar" onPress={aoFechar} style={{ position: "absolute", inset: 0, backgroundColor: "rgba(20,20,63,0.5)" }} />
        <View
          accessibilityViewIsModal
          style={{ backgroundColor: cor.fundo, borderTopLeftRadius: 28, borderTopRightRadius: 28, padding: 24, paddingBottom: Math.max(ins.bottom, 24), gap: 20 }}
        >
          <View style={{ alignSelf: "center", width: 40, height: 4, borderRadius: raio.pilula, backgroundColor: cor.linha }} />
          <View style={{ gap: 8 }}>
            <Titulo v="tituloM">{titulo}</Titulo>
            {texto ? <Texto suave>{texto}</Texto> : null}
          </View>
          <View style={{ gap: 12 }}>{children}</View>
        </View>
      </View>
    </Modal>
  );
}
