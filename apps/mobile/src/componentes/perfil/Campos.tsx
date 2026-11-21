/**
 * Campos de formulário que faltam na base: escolha numa lista (o <select> da web, numa folha de
 * baixo), telefone angolano com +244, caixa de confirmação e controlo segmentado.
 */
import { Check, ChevronDown } from "lucide-react-native";
import { type ReactNode, useState } from "react";
import { Modal, Pressable, ScrollView, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { telefoneLegivel } from "@/dominios/subscricao/api";
import { cor, fonte, raio } from "@/tema";
import { Texto, Titulo } from "@/ui";

export type Opcao<T extends string> = { valor: T; nome: string; descricao?: string };

/** Escolha numa lista: parece um campo; ao tocar abre uma folha com as opções. */
export function Escolha<T extends string>({
  rotulo,
  ajuda,
  valor,
  opcoes,
  aoMudar,
  vazio = "Escolha",
}: {
  rotulo: string;
  ajuda?: string;
  valor: T | "";
  opcoes: Opcao<T>[];
  aoMudar: (v: T | "") => void;
  /** Texto (e opção) quando não há escolha. */
  vazio?: string;
}) {
  const [aberto, setAberto] = useState(false);
  const ins = useSafeAreaInsets();
  const actual = opcoes.find((o) => o.valor === valor);
  const todas: Opcao<T | "">[] = [{ valor: "", nome: vazio }, ...opcoes];
  return (
    <View style={{ gap: 4 }}>
      <Texto v="rotulo">{rotulo}</Texto>
      {ajuda ? (
        <Texto v="legenda" suave>
          {ajuda}
        </Texto>
      ) : null}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${rotulo}: ${actual?.nome ?? vazio}`}
        accessibilityHint="Abre a lista de opções"
        onPress={() => setAberto(true)}
        style={({ pressed }) => ({
          minHeight: 48,
          flexDirection: "row",
          alignItems: "center",
          gap: 8,
          paddingHorizontal: 12,
          borderWidth: 1.5,
          borderColor: cor.linhaForte,
          borderRadius: raio.sm,
          backgroundColor: pressed ? cor.fundoSuave : cor.fundo,
        })}
      >
        <Texto style={{ flex: 1 }} cor={actual ? cor.tinta : cor.tintaSuave} numberOfLines={1}>
          {actual?.nome ?? vazio}
        </Texto>
        <ChevronDown size={20} color={cor.tintaSuave} />
      </Pressable>
      <Modal visible={aberto} transparent animationType="slide" onRequestClose={() => setAberto(false)} statusBarTranslucent>
        <View style={{ flex: 1, justifyContent: "flex-end" }}>
          <Pressable accessibilityLabel="Fechar" onPress={() => setAberto(false)} style={{ position: "absolute", inset: 0, backgroundColor: "rgba(20,20,63,0.5)" }} />
          <View accessibilityViewIsModal style={{ maxHeight: "80%", backgroundColor: cor.fundo, borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingTop: 12, paddingBottom: Math.max(ins.bottom, 16) }}>
            <View style={{ alignSelf: "center", width: 40, height: 4, borderRadius: raio.pilula, backgroundColor: cor.linha }} />
            <Titulo v="tituloS" style={{ paddingHorizontal: 20, paddingVertical: 12 }}>
              {rotulo}
            </Titulo>
            <ScrollView accessibilityRole="radiogroup" contentContainerStyle={{ paddingHorizontal: 12 }}>
              {todas.map((o) => {
                const sel = o.valor === valor;
                return (
                  <Pressable
                    key={o.valor || "_vazio"}
                    accessibilityRole="radio"
                    accessibilityState={{ selected: sel }}
                    onPress={() => {
                      aoMudar(o.valor);
                      setAberto(false);
                    }}
                    style={({ pressed }) => ({
                      minHeight: 52,
                      flexDirection: "row",
                      alignItems: "center",
                      gap: 12,
                      paddingHorizontal: 12,
                      paddingVertical: 8,
                      borderRadius: raio.md,
                      backgroundColor: sel ? cor.fundoSuave : pressed ? cor.fundoSuave : "transparent",
                    })}
                  >
                    <View style={{ flex: 1 }}>
                      <Texto forte={sel}>{o.nome}</Texto>
                      {o.descricao ? (
                        <Texto v="legenda" suave>
                          {o.descricao}
                        </Texto>
                      ) : null}
                    </View>
                    {sel ? <Check size={20} color={cor.azulMarca} /> : null}
                  </Pressable>
                );
              })}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
}

/** Telefone angolano: "+244" fixo e os 9 dígitos agrupados ("923 456 789"). */
export function CampoTelefone({ rotulo, valor, aoMudar, erro, ajuda }: { rotulo: string; valor: string; aoMudar: (v: string) => void; erro?: string | null; ajuda?: string }) {
  const [foco, setFoco] = useState(false);
  return (
    <View style={{ gap: 4 }}>
      <Texto v="rotulo">{rotulo}</Texto>
      <View
        style={{
          flexDirection: "row",
          minHeight: 48,
          borderWidth: foco || erro ? 2 : 1.5,
          borderColor: erro ? cor.errado : foco ? cor.azulVivo : cor.linhaForte,
          borderRadius: raio.sm,
          overflow: "hidden",
        }}
      >
        <View style={{ justifyContent: "center", paddingHorizontal: 12, backgroundColor: cor.fundoSuave, borderRightWidth: 1, borderColor: cor.linha }}>
          <Texto forte>+244</Texto>
        </View>
        <TextInput
          accessibilityLabel={rotulo}
          accessibilityHint={erro ?? ajuda}
          value={valor}
          onChangeText={(t) => aoMudar(telefoneLegivel(t.replace(/^\+?244/, "")))}
          keyboardType="number-pad"
          textContentType="telephoneNumber"
          autoComplete="tel"
          placeholder="923 456 789"
          placeholderTextColor={cor.tintaSuave}
          maxLength={11}
          onFocus={() => setFoco(true)}
          onBlur={() => setFoco(false)}
          style={{ flex: 1, paddingHorizontal: 12, fontFamily: fonte.texto, fontSize: 16, color: cor.tinta, fontVariant: ["tabular-nums"] }}
        />
      </View>
      {erro ? (
        <Texto v="legenda" cor={cor.errado} forte accessibilityLiveRegion="polite">
          {erro}
        </Texto>
      ) : ajuda ? (
        <Texto v="legenda" suave>
          {ajuda}
        </Texto>
      ) : null}
    </View>
  );
}

/** Caixa de confirmação com texto ao lado (alvo de toque em toda a linha). */
export function Caixa({ marcada, aoMudar, children, inactiva, corMarca = cor.azulMarca }: { marcada: boolean; aoMudar: (v: boolean) => void; children: ReactNode; inactiva?: boolean; corMarca?: string }) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked: marcada, disabled: inactiva }}
      disabled={inactiva}
      onPress={() => aoMudar(!marcada)}
      style={{ flexDirection: "row", alignItems: "flex-start", gap: 12, minHeight: 44, paddingVertical: 4 }}
    >
      <View
        style={{
          width: 24,
          height: 24,
          marginTop: 1,
          borderRadius: 4,
          borderWidth: 2,
          borderColor: inactiva ? cor.linha : marcada ? corMarca : cor.linhaForte,
          backgroundColor: marcada ? corMarca : cor.fundo,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {marcada ? <Check size={16} color={cor.sobreMarca} strokeWidth={3} /> : null}
      </View>
      <View style={{ flex: 1 }}>{typeof children === "string" ? <Texto v="legenda" suave={inactiva} style={{ fontSize: 15, lineHeight: 22 }}>{children}</Texto> : children}</View>
    </Pressable>
  );
}

/** Controlo segmentado ("7 dias | 30 dias | Tudo", "Mensal | Anual") como no canvas. */
export function Segmentos<T extends string>({ opcoes, valor, aoMudar, rotulo }: { opcoes: { valor: T; nome: string }[]; valor: T; aoMudar: (v: T) => void; rotulo: string }) {
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={rotulo} style={{ flexDirection: "row", gap: 4, padding: 4, backgroundColor: cor.fundoSuave, borderRadius: raio.sm }}>
      {opcoes.map((o) => {
        const a = o.valor === valor;
        return (
          <Pressable
            key={o.valor}
            accessibilityRole="radio"
            accessibilityState={{ selected: a }}
            onPress={() => aoMudar(o.valor)}
            style={{ flex: 1, minHeight: 44, alignItems: "center", justifyContent: "center", paddingHorizontal: 6, borderRadius: 4, backgroundColor: a ? cor.azulMarca : "transparent" }}
          >
            <Texto v="legenda" centro cor={a ? cor.sobreMarca : cor.tinta} style={{ fontSize: 15, fontFamily: a ? fonte.textoForte : fonte.texto }}>
              {o.nome}
            </Texto>
          </Pressable>
        );
      })}
    </View>
  );
}
