/**
 * Unidade, aula ou passo fora das unidades de amostra (web components/pe/curso/Amostra.tsx).
 * A API marca-os com bloqueada/bloqueado; aqui só se mostra o cadeado e a ligação para os planos.
 */
import { router } from "expo-router";
import { Lock } from "lucide-react-native";
import { Pressable, type StyleProp, type ViewStyle } from "react-native";
import { Texto } from "@/ui";
import { cor } from "@/tema";

export const TEXTO_PLANOS_PAGOS = "Disponível nos planos pagos";

export function DisponivelNosPlanos({ cor: corTexto = cor.azulVivo, style }: { cor?: string; style?: StyleProp<ViewStyle> }) {
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`${TEXTO_PLANOS_PAGOS}. Ver os planos`}
      onPress={() => router.push("/planos")}
      hitSlop={6}
      style={({ pressed }) => [{ flexDirection: "row", alignItems: "center", gap: 6, minHeight: 44, opacity: pressed ? 0.7 : 1 }, style]}
    >
      <Lock size={16} color={corTexto} />
      <Texto v="legenda" forte cor={corTexto}>
        {TEXTO_PLANOS_PAGOS}
      </Texto>
    </Pressable>
  );
}
