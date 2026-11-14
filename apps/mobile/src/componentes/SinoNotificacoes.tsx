import { Bell } from "lucide-react-native";
import { View } from "react-native";
import { usePorLer } from "@/dominios/avisos/api";
import { BotaoIcone, Texto } from "@/ui";
import { cor } from "@/tema";

/** Sino com o número por ler, para o cabeçalho do início. Abre /notificacoes. */
export function SinoNotificacoes() {
  const n = usePorLer();
  return (
    <BotaoIcone rotulo={n ? `Notificações, ${n} por ler` : "Notificações"} href="/notificacoes">
      <Bell size={22} color={cor.tinta} />
      {n ? (
        <View style={{ position: "absolute", top: 4, right: 2, minWidth: 20, height: 20, paddingHorizontal: 4, borderRadius: 10, backgroundColor: cor.azulVivo, alignItems: "center", justifyContent: "center" }}>
          <Texto v="mini" cor={cor.sobreMarca} forte numeros>
            {n > 9 ? "9+" : n}
          </Texto>
        </View>
      ) : null}
    </BotaoIcone>
  );
}
