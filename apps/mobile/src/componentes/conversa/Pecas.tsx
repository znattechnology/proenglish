/**
 * Peças partilhadas pelos ecrãs da conversa: a fala em balão (tutor à esquerda, aluno à direita),
 * o "Um ajuste" depois de uma resposta e as frases-alvo com "Ver em inglês".
 */
import { CheckCircle2, Circle, Eye, Volume2 } from "lucide-react-native";
import type { ReactNode } from "react";
import { Pressable, View } from "react-native";
import { BotaoIcone, Texto } from "@/ui";
import { balao, cor, raio } from "@/tema";
import type { Ajuste, Frase } from "@/dominios/conversa/api";
import { falar } from "./voz";

/** Uma fala da conversa. O tutor no balão azul-marca (a assinatura), o aluno em cinzento à direita. */
export function Bolha({ quem, children, compacta, parcial }: { quem: "tutor" | "aluno"; children: ReactNode; compacta?: boolean; parcial?: boolean }) {
  const tutor = quem === "tutor";
  const forma = compacta ? (tutor ? balao.medio : { ...balao.medio, borderBottomLeftRadius: 20, borderBottomRightRadius: 0 }) : tutor ? balao.grande : balao.aluno;
  return (
    <View
      accessible
      accessibilityLabel={`${tutor ? "Tutor" : "Você"}: ${typeof children === "string" ? children : ""}`}
      style={[
        forma,
        {
          alignSelf: tutor ? "flex-start" : "flex-end",
          maxWidth: "86%",
          backgroundColor: tutor ? cor.azulMarca : cor.fundoSuave,
          paddingVertical: compacta ? 10 : 14,
          paddingHorizontal: compacta ? 16 : 20,
          gap: 2,
          opacity: parcial ? 0.7 : 1,
        },
      ]}
    >
      <Texto v="legenda" forte cor={tutor ? cor.sobreMarca : cor.tintaSuave}>
        {tutor ? "Tutor" : "Você"}
      </Texto>
      {typeof children === "string" ? (
        <Texto v={compacta ? "corpo" : "corpoL"} cor={tutor ? cor.sobreMarca : cor.tinta}>
          {parcial ? `${children}…` : children}
        </Texto>
      ) : (
        children
      )}
    </View>
  );
}

/** "Um ajuste": a forma certa do que o aluno acabou de dizer (balão amarelo-claro à direita). */
export function CartaoAjuste({ ajuste }: { ajuste: Ajuste }) {
  return (
    <View style={{ alignSelf: "flex-end", maxWidth: "86%", gap: 6, paddingVertical: 12, paddingHorizontal: 16, backgroundColor: cor.realceSuave, borderRadius: raio.md }}>
      <Texto v="legenda" forte>
        Um ajuste
      </Texto>
      <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
        {ajuste.porque} <Texto v="legenda" forte style={{ fontSize: 15, lineHeight: 22 }}>{ajuste.certo}</Texto>
      </Texto>
      <Pressable accessibilityRole="button" onPress={() => falar(ajuste.certo)} hitSlop={4} style={{ minHeight: 44, justifyContent: "center", alignSelf: "flex-start", paddingHorizontal: 4 }}>
        <Texto v="rotulo" cor={cor.azulMarca} style={{ textDecorationLine: "underline" }}>
          Ouvir a frase certa
        </Texto>
      </Pressable>
    </View>
  );
}

export const REGRA_FRASES = "Diga-as em inglês sem as ler. Se abrir a frase em inglês, conta como dita com ajuda.";

/**
 * Frases-alvo durante a conversa: mostra só o sentido em português. Para contar como dita sozinho,
 * o aluno tem de a dizer sem a ler. "Ver em inglês" mostra-a (e deixa ouvi-la), mas nesta conversa
 * passa a contar só "com ajuda" (o servidor é avisado).
 */
export function FrasesAlvo({ frases, ditas, reveladas, aoRevelar, compacta }: { frases: Frase[]; ditas: Set<string>; reveladas: string[]; aoRevelar: (en: string) => void; compacta?: boolean }) {
  if (!frases.length) return null;
  return (
    <View>
      {frases.map((f, i) => {
        const dita = ditas.has(f.en);
        const vista = reveladas.includes(f.en);
        const sentido = f.pt?.trim() || `Frase ${i + 1} da lição`;
        return (
          <View key={f.en} style={{ flexDirection: "row", alignItems: "flex-start", gap: 10, paddingVertical: compacta ? 6 : 10, borderBottomWidth: i === frases.length - 1 ? 0 : 1, borderColor: cor.fundoForte }}>
            <View style={{ marginTop: 3 }} accessible accessibilityLabel={dita ? "Já disse" : "Ainda não disse"}>
              {dita ? <CheckCircle2 size={20} color={cor.certo} /> : <Circle size={20} color={cor.tintaSuave} />}
            </View>
            <View style={{ flex: 1, gap: 2 }}>
              <Texto forte={dita} cor={dita ? cor.certo : undefined} style={{ lineHeight: 22 }}>
                {sentido}
              </Texto>
              {vista ? (
                <View style={{ flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: 4 }}>
                  <Texto v="rotulo" style={{ flexShrink: 1 }}>
                    {f.en}
                  </Texto>
                  <BotaoIcone rotulo={`Ouvir: ${f.en}`} onPress={() => falar(f.en)}>
                    <Volume2 size={20} color={cor.azulMarca} />
                  </BotaoIcone>
                </View>
              ) : (
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={`Ver em inglês: ${sentido}. Esta frase passa a contar com ajuda.`}
                  onPress={() => aoRevelar(f.en)}
                  hitSlop={4}
                  style={{ flexDirection: "row", alignItems: "center", gap: 6, minHeight: 40, alignSelf: "flex-start" }}
                >
                  <Eye size={16} color={cor.azulMarca} />
                  <Texto v="legenda" forte cor={cor.azulMarca} style={{ textDecorationLine: "underline" }}>
                    Ver em inglês
                  </Texto>
                </Pressable>
              )}
            </View>
          </View>
        );
      })}
    </View>
  );
}

/** Lista simples de frases em inglês, com o visto das que já disse (antes e depois de uma conversa curta). */
export function ListaFrases({ frases, ditas, titulo = "Use estas frases da lição" }: { frases: string[]; ditas?: Set<string>; titulo?: string }) {
  if (!frases.length) return null;
  return (
    <View style={{ gap: 8 }}>
      <Texto v="legenda" suave>
        {titulo}
      </Texto>
      {frases.map((f) => {
        const dita = ditas?.has(f);
        return (
          <View key={f} style={{ flexDirection: "row", alignItems: "flex-start", gap: 10 }}>
            <View style={{ marginTop: 3 }} accessible={!!dita} accessibilityLabel={dita ? "Dita" : undefined}>
              {dita ? <CheckCircle2 size={20} color={cor.certo} /> : <Circle size={20} color={cor.linhaForte} />}
            </View>
            <Texto forte={dita} style={{ flex: 1, fontSize: 17, lineHeight: 24 }}>
              {f}
            </Texto>
          </View>
        );
      })}
    </View>
  );
}

/** Opção de escolha única em cartão (situação, forma de corrigir), com o círculo de rádio. */
export function OpcaoCartao({ titulo, descricao, escolhida, aoEscolher }: { titulo: string; descricao?: string; escolhida: boolean; aoEscolher: () => void }) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ checked: escolhida }}
      accessibilityLabel={descricao ? `${titulo}. ${descricao}` : titulo}
      onPress={aoEscolher}
      style={({ pressed }) => [
        { flexDirection: "row", alignItems: "flex-start", gap: 12, paddingVertical: 14, paddingHorizontal: 16, borderRadius: raio.md, minHeight: 56 },
        escolhida ? { borderWidth: 2, borderColor: cor.azulMarca, backgroundColor: cor.fundoSuave } : { borderWidth: 1, borderColor: cor.linha, backgroundColor: pressed ? cor.fundoSuave : cor.fundo },
      ]}
    >
      <View style={{ width: 20, height: 20, marginTop: 1, borderRadius: 10, borderWidth: 2, borderColor: escolhida ? cor.azulMarca : cor.linhaForte, alignItems: "center", justifyContent: "center" }}>
        {escolhida ? <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: cor.azulMarca }} /> : null}
      </View>
      <View style={{ flex: 1 }}>
        <Texto forte style={{ lineHeight: 22 }}>
          {titulo}
        </Texto>
        {descricao ? (
          <Texto v="legenda" suave>
            {descricao}
          </Texto>
        ) : null}
      </View>
    </Pressable>
  );
}

/** Os seis níveis em botões (A1 a C2). */
export function EscolherNivel({ niveis, valor, aoMudar }: { niveis: readonly string[]; valor: string; aoMudar: (n: string) => void }) {
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel="Nível" style={{ flexDirection: "row", gap: 6 }}>
      {niveis.map((n) => {
        const a = n === valor;
        return (
          <Pressable
            key={n}
            accessibilityRole="radio"
            accessibilityState={{ checked: a }}
            onPress={() => aoMudar(n)}
            style={{ flex: 1, minHeight: 44, alignItems: "center", justifyContent: "center", borderRadius: raio.sm, borderWidth: a ? 2 : 1.5, borderColor: a ? cor.azulMarca : cor.linhaForte, backgroundColor: a ? cor.azulMarca : cor.fundo }}
          >
            <Texto v="tituloXS" style={{ fontFamily: "Montserrat_700Bold", fontSize: 15 }} cor={a ? cor.sobreMarca : cor.tinta}>
              {n}
            </Texto>
          </Pressable>
        );
      })}
    </View>
  );
}
