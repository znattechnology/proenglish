import type { ReactNode } from "react";
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { cor, raio } from "@/tema";
import { Texto, Titulo } from "@/ui";

/**
 * Folha de baixo com formulário (mudar a palavra-passe, apagar a conta): como o Dialogo da base,
 * mas sobe com o teclado e desloca-se quando o conteúdo não cabe.
 */
export function Folha({ aberto, aoFechar, titulo, texto, children }: { aberto: boolean; aoFechar: () => void; titulo: string; texto?: string; children: ReactNode }) {
  const ins = useSafeAreaInsets();
  return (
    <Modal visible={aberto} transparent animationType="slide" onRequestClose={aoFechar} statusBarTranslucent>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={{ flex: 1, justifyContent: "flex-end" }}>
        <Pressable accessibilityLabel="Fechar" onPress={aoFechar} style={{ position: "absolute", inset: 0, backgroundColor: "rgba(20,20,63,0.5)" }} />
        <View accessibilityViewIsModal style={{ maxHeight: "92%", backgroundColor: cor.fundo, borderTopLeftRadius: 28, borderTopRightRadius: 28 }}>
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 24, paddingBottom: Math.max(ins.bottom, 24), gap: 20 }}>
            <View style={{ alignSelf: "center", width: 40, height: 4, borderRadius: raio.pilula, backgroundColor: cor.linha }} />
            <View style={{ gap: 8 }}>
              <Titulo v="tituloM">{titulo}</Titulo>
              {texto ? <Texto suave>{texto}</Texto> : null}
            </View>
            {children}
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}
