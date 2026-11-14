import type { ReactNode } from "react";
import { View } from "react-native";
import { CloudOff, Inbox } from "lucide-react-native";
import { balao, cor } from "@/tema";
import { mensagemErro } from "@/api/erros";
import { Botao } from "./Botao";
import { Osso } from "./Pecas";
import { Texto, Titulo } from "./Texto";

/** Erro ao carregar (tela "Erro ao carregar" do canvas): diz o que falhou e oferece tentar outra vez. */
export function EstadoErro({ erro, aoTentar, titulo = "Não conseguimos carregar isto", outra }: { erro?: unknown; aoTentar?: () => void; titulo?: string; outra?: ReactNode }) {
  const detalhe = erro ? mensagemErro(erro, "Verifique a ligação à Internet e tente outra vez.") : "Verifique a ligação à Internet e tente outra vez.";
  return (
    <View accessibilityRole="alert" style={{ gap: 16, paddingVertical: 24 }}>
      <View style={[balao.medio, { width: 56, height: 56, alignItems: "center", justifyContent: "center", backgroundColor: cor.erradoSuave }]}>
        <CloudOff size={26} color={cor.errado} />
      </View>
      <View style={{ gap: 6 }}>
        <Titulo v="tituloM">{titulo}</Titulo>
        <Texto suave>{detalhe}</Texto>
      </View>
      <View style={{ gap: 8 }}>
        {aoTentar ? (
          <Botao onPress={aoTentar} larguraTotal>
            Tentar outra vez
          </Botao>
        ) : null}
        {outra}
      </View>
    </View>
  );
}

/** Ecrã vazio: diz porque está vazio e qual o próximo passo. */
export function EstadoVazio({ titulo, texto, icone, accao, nota }: { titulo: string; texto: string; icone?: ReactNode; accao?: ReactNode; nota?: string }) {
  return (
    <View style={{ gap: 16, paddingVertical: 16 }}>
      <View style={[balao.medio, { width: 56, height: 56, alignItems: "center", justifyContent: "center", backgroundColor: cor.fundoSuave }]}>{icone ?? <Inbox size={26} color={cor.azulMarca} />}</View>
      <View style={{ gap: 6 }}>
        <Titulo v="tituloS">{titulo}</Titulo>
        <Texto suave>{texto}</Texto>
      </View>
      {accao}
      {nota ? (
        <Texto v="legenda" suave>
          {nota}
        </Texto>
      ) : null}
    </View>
  );
}

/** Esqueleto genérico de lista enquanto carrega. */
export function ACarregar({ linhas = 4, altura = 76, rotulo = "A carregar" }: { linhas?: number; altura?: number; rotulo?: string }) {
  return (
    <View accessible accessibilityLabel={rotulo} accessibilityState={{ busy: true }} style={{ gap: 12 }}>
      <Osso altura={34} largura="60%" raio={6} />
      {Array.from({ length: linhas }, (_, i) => (
        <Osso key={i} altura={altura} />
      ))}
    </View>
  );
}
