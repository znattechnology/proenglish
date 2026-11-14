import { Linking, View } from "react-native";
import { ShieldAlert } from "lucide-react-native";
import { SITE_URL } from "@/api/config";
import { useSessao } from "@/sessao/ContextoSessao";
import { Botao, Ecra, Logo, Texto, Titulo } from "@/ui";
import { balao, cor } from "@/tema";

/** Tela "Sem permissão": a app é só para estudantes; professores e administradores usam o site. */
export function SemPermissao() {
  const { sair, utilizador } = useSessao();
  const area = utilizador?.role === "admin" ? "a administração" : "a área do professor";
  return (
    <Ecra style={{ gap: 32 }}>
      <Logo altura={36} />
      <View style={[balao.medio, { width: 56, height: 56, alignItems: "center", justifyContent: "center", backgroundColor: cor.realceSuave }]}>
        <ShieldAlert size={26} color={cor.tinta} />
      </View>
      <View style={{ gap: 8 }}>
        <Titulo>A app é para estudantes</Titulo>
        <Texto suave>{`Entrou com uma conta que usa ${area}. Abra o ProEnglish no browser para continuar.`}</Texto>
      </View>
      <View style={{ gap: 12, marginTop: "auto" }}>
        <Botao larguraTotal onPress={() => Linking.openURL(SITE_URL)}>
          Abrir o site
        </Botao>
        <Botao tipo="secundario" larguraTotal onPress={() => void sair()}>
          Sair da conta
        </Botao>
      </View>
    </Ecra>
  );
}
