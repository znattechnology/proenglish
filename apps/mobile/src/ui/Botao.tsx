import { type Href, router } from "expo-router";
import type { ReactNode } from "react";
import { ActivityIndicator, Pressable, type PressableProps, type StyleProp, StyleSheet, View, type ViewStyle } from "react-native";
import { cor, fonte, raio } from "@/tema";
import { Texto } from "./Texto";

/**
 * Botão do sistema ProEnglish (igual à web, components/pe/Botao.tsx).
 * - principal: a acção principal do ecrã (uma por ecrã).
 * - secundario: alternativa à principal.
 * - realce: só para continuar/começar (amarelo).
 * - perigo: acções destrutivas.
 * - ligacao: acção terciária sublinhada.
 * - sobreMarca: ligação branca sublinhada dentro de um bloco azul-marca.
 */
export type TipoBotao = "principal" | "secundario" | "realce" | "perigo" | "ligacao" | "sobreMarca";
export type TamanhoBotao = "grande" | "medio" | "pequeno";

export type BotaoProps = Omit<PressableProps, "children" | "style"> & {
  children: ReactNode;
  tipo?: TipoBotao;
  tamanho?: TamanhoBotao;
  larguraTotal?: boolean;
  carregando?: boolean;
  /** Ícone à esquerda (ex.: <Mic size={20} color=... />). */
  icone?: ReactNode;
  /** Navega para esta rota ao tocar (em vez de onPress). */
  href?: Href;
  /** Substitui o ecrã actual em vez de empilhar. */
  substituir?: boolean;
  style?: StyleProp<ViewStyle>;
};

const ALTURA: Record<TamanhoBotao, number> = { grande: 52, medio: 48, pequeno: 44 };

export function Botao({
  children,
  tipo = "principal",
  tamanho = "grande",
  larguraTotal,
  carregando,
  icone,
  href,
  substituir,
  disabled,
  onPress,
  style,
  ...props
}: BotaoProps) {
  const inactivo = disabled || carregando;
  const c = cores(tipo, !!inactivo);
  const ligacao = tipo === "ligacao" || tipo === "sobreMarca";
  return (
    <Pressable
      accessibilityRole={href ? "link" : "button"}
      accessibilityState={{ disabled: !!inactivo, busy: !!carregando }}
      disabled={inactivo}
      hitSlop={ligacao ? 4 : undefined}
      onPress={(e) => {
        if (href) (substituir ? router.replace : router.push)(href);
        onPress?.(e);
      }}
      style={({ pressed }) => [
        s.base,
        { minHeight: ALTURA[tamanho], paddingHorizontal: ligacao ? 4 : tamanho === "pequeno" ? 16 : 20 },
        { backgroundColor: c.fundo, borderColor: c.borda, borderWidth: c.borda ? 2 : 0 },
        larguraTotal ? s.total : ligacao ? s.inicio : null,
        pressed && !inactivo ? { opacity: 0.85 } : null,
        style,
      ]}
      {...props}
    >
      {carregando ? <ActivityIndicator color={c.texto} /> : icone ? <View>{icone}</View> : null}
      <Texto
        style={{
          fontFamily: fonte.textoForte,
          fontSize: tamanho === "pequeno" ? 15 : 16,
          lineHeight: 20,
          color: c.texto,
          textDecorationLine: ligacao ? "underline" : "none",
          textAlign: "center",
        }}
      >
        {children}
      </Texto>
    </Pressable>
  );
}

function cores(tipo: TipoBotao, inactivo: boolean): { fundo: string; texto: string; borda?: string } {
  if (inactivo && tipo !== "ligacao" && tipo !== "sobreMarca")
    return tipo === "secundario" || tipo === "perigo"
      ? { fundo: cor.fundo, texto: cor.tintaSuave, borda: cor.linha }
      : { fundo: cor.fundoForte, texto: cor.tintaSuave };
  switch (tipo) {
    case "secundario":
      return { fundo: cor.fundo, texto: cor.azulMarca, borda: cor.azulMarca };
    case "realce":
      return { fundo: cor.realce, texto: cor.tinta };
    case "perigo":
      return { fundo: cor.fundo, texto: cor.errado, borda: cor.errado };
    case "ligacao":
      return { fundo: "transparent", texto: inactivo ? cor.tintaSuave : cor.azulMarca };
    case "sobreMarca":
      return { fundo: "transparent", texto: cor.sobreMarca };
    default:
      return { fundo: cor.azulMarca, texto: cor.sobreMarca };
  }
}

/** Botão quadrado só com ícone (44×44 no mínimo). `rotulo` é obrigatório para leitores de ecrã. */
export function BotaoIcone({
  rotulo,
  children,
  onPress,
  href,
  contorno,
  tamanho = 44,
  style,
}: {
  rotulo: string;
  children: ReactNode;
  onPress?: () => void;
  href?: Href;
  contorno?: boolean;
  tamanho?: number;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={rotulo}
      hitSlop={6}
      onPress={() => {
        if (href) router.push(href);
        onPress?.();
      }}
      style={({ pressed }) => [
        { width: tamanho, height: tamanho, alignItems: "center", justifyContent: "center", borderRadius: raio.sm },
        contorno ? { borderWidth: 2, borderColor: cor.azulMarca, backgroundColor: cor.fundo } : null,
        pressed ? { backgroundColor: cor.fundoSuave } : null,
        style,
      ]}
    >
      {children}
    </Pressable>
  );
}

const s = StyleSheet.create({
  base: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, borderRadius: raio.sm },
  total: { alignSelf: "stretch" },
  inicio: { alignSelf: "flex-start" },
});
