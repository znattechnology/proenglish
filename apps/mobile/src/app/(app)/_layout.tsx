import { Stack } from "expo-router";
import { View } from "react-native";
import { useSessao } from "@/sessao/ContextoSessao";
import { cor } from "@/tema";
import { SemPermissao } from "@/componentes/SemPermissao";
import { ObrigarMudarSenha } from "@/componentes/conta/ObrigarMudarSenha";
import { useAbrirAoTocarNotificacao } from "@/dominios/perfil/lembrete";

/**
 * Área do estudante: os 5 separadores e todos os ecrãs que se abrem por cima deles.
 * Os ecrãs de lição, exame e conversa abrem em ecrã inteiro (sem barra de baixo).
 */
export default function LayoutApp() {
  const { utilizador } = useSessao();
  // Tocar no lembrete diário (notificação local) abre o ecrã certo.
  useAbrirAoTocarNotificacao();
  if (utilizador && utilizador.role !== "student") return <SemPermissao />;
  return (
    <View style={{ flex: 1, backgroundColor: cor.fundo }}>
      <ObrigarMudarSenha>
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: cor.fundo } }}>
          <Stack.Screen name="(tabs)" />
        </Stack>
      </ObrigarMudarSenha>
    </View>
  );
}
