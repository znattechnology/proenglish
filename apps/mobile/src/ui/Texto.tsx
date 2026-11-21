import { Text, type TextProps, type TextStyle } from "react-native";
import { cor, fonte, tipo } from "@/tema";

type Variante = keyof typeof tipo;

export type TextoProps = TextProps & {
  /** Estilo da escala tipográfica (por omissão, corpo). */
  v?: Variante;
  forte?: boolean;
  suave?: boolean;
  cor?: string;
  centro?: boolean;
  /** Algarismos alinhados (contadores, notas, preços). */
  numeros?: boolean;
};

/**
 * Todo o texto da app passa por aqui: a fonte e as cores do sistema ProEnglish.
 * Títulos usam Montserrat (v="tituloL"...), o resto Atkinson Hyperlegible Next.
 */
export function Texto({ v = "corpo", forte, suave, cor: c, centro, numeros, style, ...props }: TextoProps) {
  const base: TextStyle = {
    ...(tipo[v] as TextStyle),
    color: c ?? (suave ? cor.tintaSuave : cor.tinta),
    ...(forte && !v.startsWith("titulo") && v !== "voz" ? { fontFamily: fonte.textoForte } : null),
    ...(centro ? { textAlign: "center" as const } : null),
    ...(numeros ? { fontVariant: ["tabular-nums" as const] } : null),
  };
  return <Text maxFontSizeMultiplier={1.6} {...props} style={[base, style]} />;
}

/** Título de ecrã (h1). Lido como cabeçalho pelos leitores de ecrã. */
export function Titulo({ v = "tituloL", ...props }: TextoProps) {
  return <Texto accessibilityRole="header" v={v} {...props} />;
}
