import { Image, View } from "react-native";
import { urlAbsoluto } from "@/api/config";
import { iniciais } from "@/dominios/perfil/api";
import { cor, fonte } from "@/tema";
import { Texto } from "@/ui";

/** Fotografia ou iniciais num balão azul-marca (canto de baixo-esquerdo recto), como no canvas. */
export function Avatar({ nome, foto, tamanho = 72 }: { nome?: string | null; foto?: string | null; tamanho?: number }) {
  const r = Math.round(tamanho / 3);
  const url = urlAbsoluto(foto);
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={{
        width: tamanho,
        height: tamanho,
        overflow: "hidden",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: cor.azulMarca,
        borderTopLeftRadius: r,
        borderTopRightRadius: r,
        borderBottomRightRadius: r,
        borderBottomLeftRadius: 0,
      }}
    >
      {url ? (
        <Image source={{ uri: url }} style={{ width: tamanho, height: tamanho }} />
      ) : (
        <Texto cor={cor.sobreMarca} style={{ fontFamily: fonte.titulo, fontSize: Math.round(tamanho * 0.36), lineHeight: Math.round(tamanho * 0.46) }}>
          {iniciais(nome)}
        </Texto>
      )}
    </View>
  );
}
