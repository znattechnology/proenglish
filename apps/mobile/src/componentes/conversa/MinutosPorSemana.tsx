/**
 * Minutos a falar por semana (últimas 8 semanas): barras finas de uma só cor, linha da meta
 * semanal e o valor da barra tocada. Cada barra tem rótulo para leitores de ecrã.
 */
import { useState } from "react";
import { Pressable, View } from "react-native";
import { Texto } from "@/ui";
import { cor } from "@/tema";

export type Barra = { chave: string; rotulo: string; rotuloLongo: string; minutos: number; actual?: boolean };

const ALTURA = 140;

export function MinutosPorSemana({ barras, meta, legendaMeta }: { barras: Barra[]; meta: number; legendaMeta: string }) {
  const [tocada, setTocada] = useState<string | null>(null);
  const maximo = Math.max(meta, ...barras.map((b) => b.minutos), 1);
  const escolhida = barras.find((b) => b.chave === tocada) ?? barras.find((b) => b.actual) ?? barras[barras.length - 1];
  const yMeta = ALTURA - (meta / maximo) * ALTURA;
  return (
    <View style={{ gap: 8 }}>
      {escolhida ? (
        <Texto v="legenda" accessibilityLiveRegion="polite">
          <Texto v="legenda" forte>{`${escolhida.rotuloLongo}: `}</Texto>
          {`${escolhida.minutos} min a falar`}
        </Texto>
      ) : null}
      <View style={{ height: ALTURA, flexDirection: "row", alignItems: "flex-end", gap: 2, borderBottomWidth: 1, borderColor: cor.linha }}>
        {meta > 0 ? <View pointerEvents="none" style={{ position: "absolute", left: 0, right: 0, top: yMeta, borderTopWidth: 1, borderStyle: "dashed", borderColor: cor.linhaForte }} /> : null}
        {barras.map((b) => {
          const h = b.minutos > 0 ? Math.max(4, (b.minutos / maximo) * ALTURA) : 0;
          const sel = escolhida?.chave === b.chave;
          return (
            <Pressable
              key={b.chave}
              accessibilityRole="button"
              accessibilityLabel={`${b.rotuloLongo}: ${b.minutos} minutos a falar`}
              onPress={() => setTocada(b.chave)}
              style={{ flex: 1, height: ALTURA, justifyContent: "flex-end", alignItems: "center" }}
            >
              <View style={{ width: "70%", maxWidth: 28, height: h, backgroundColor: sel ? cor.azulMarca : cor.azulVivo, borderTopLeftRadius: 4, borderTopRightRadius: 4 }} />
            </Pressable>
          );
        })}
      </View>
      <View style={{ flexDirection: "row", gap: 2 }}>
        {barras.map((b) => (
          <Texto key={b.chave} v="mini" suave={!b.actual} forte={b.actual} centro numberOfLines={1} style={{ flex: 1 }}>
            {b.rotulo}
          </Texto>
        ))}
      </View>
      {meta > 0 ? (
        <Texto v="mini" suave>
          {`Linha tracejada: ${legendaMeta}`}
        </Texto>
      ) : null}
    </View>
  );
}
