/**
 * Sistema de design ProEnglish (o mesmo da web: apps/web/styles/pe.css e tailwind.config.ts).
 * Não inventar cores novas: tudo o que é visual sai daqui.
 */
import type { TextStyle } from "react-native";

export const cor = {
  azulMarca: "#000066",
  azulVivo: "#2f46e8",
  realce: "#ffc72c",
  realceSuave: "#fff1c2",
  fundo: "#ffffff",
  fundoSuave: "#f2f3fa",
  fundoForte: "#e3e5f4",
  tinta: "#14143f",
  tintaSuave: "#54577a",
  sobreMarca: "#ffffff",
  linha: "#cfd2e6",
  linhaForte: "#7479a3",
  certo: "#007268",
  certoSuave: "#d9f2ee",
  errado: "#c2330f",
  erradoSuave: "#fde4dc",
  vida: "#e5385a",
  sobreMarcaFraco: "rgba(255,255,255,0.25)",
} as const;

/** Nomes das famílias carregadas em src/app/_layout.tsx (@expo-google-fonts). */
export const fonte = {
  texto: "AtkinsonHyperlegibleNext_400Regular",
  textoForte: "AtkinsonHyperlegibleNext_600SemiBold",
  textoItalico: "AtkinsonHyperlegibleNext_400Regular_Italic",
  titulo: "Montserrat_700Bold",
  tituloMedio: "Montserrat_600SemiBold",
  /** A "voz": frases em inglês ditas pelo tutor ou pela lição (Montserrat leve, itálico). */
  voz: "Montserrat_300Light_Italic",
  numero: "Montserrat_700Bold",
} as const;

export const raio = {
  sm: 6,
  md: 12,
  lg: 16,
  pilula: 999,
} as const;

/** A assinatura visual: o balão de fala com o canto de baixo à esquerda recto. */
export const balao = {
  grande: { borderTopLeftRadius: 28, borderTopRightRadius: 28, borderBottomRightRadius: 28, borderBottomLeftRadius: 0 },
  aluno: { borderTopLeftRadius: 28, borderTopRightRadius: 28, borderBottomRightRadius: 0, borderBottomLeftRadius: 28 },
  medio: { borderTopLeftRadius: 20, borderTopRightRadius: 20, borderBottomRightRadius: 20, borderBottomLeftRadius: 0 },
  pequeno: { borderTopLeftRadius: 12, borderTopRightRadius: 12, borderBottomRightRadius: 12, borderBottomLeftRadius: 0 },
} as const;

export const espaco = { gutter: 20, xs: 4, s: 8, m: 12, l: 16, xl: 24, xxl: 32 } as const;

/** Escala tipográfica (tamanho / altura de linha) igual à da web. */
export const tipo = {
  tituloXL: { fontFamily: fonte.titulo, fontSize: 34, lineHeight: 40, letterSpacing: -0.5 },
  tituloL: { fontFamily: fonte.titulo, fontSize: 28, lineHeight: 34, letterSpacing: -0.3 },
  tituloM: { fontFamily: fonte.titulo, fontSize: 22, lineHeight: 28 },
  tituloS: { fontFamily: fonte.tituloMedio, fontSize: 20, lineHeight: 26 },
  tituloXS: { fontFamily: fonte.tituloMedio, fontSize: 16, lineHeight: 22 },
  voz: { fontFamily: fonte.voz, fontSize: 22, lineHeight: 32 },
  corpoL: { fontFamily: fonte.texto, fontSize: 18, lineHeight: 28 },
  corpo: { fontFamily: fonte.texto, fontSize: 16, lineHeight: 26 },
  rotulo: { fontFamily: fonte.textoForte, fontSize: 15, lineHeight: 20 },
  legenda: { fontFamily: fonte.texto, fontSize: 14, lineHeight: 20 },
  mini: { fontFamily: fonte.texto, fontSize: 12, lineHeight: 16 },
} satisfies Record<string, TextStyle>;

export const sombra = {
  s1: { shadowColor: "#000066", shadowOpacity: 0.08, shadowRadius: 2, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  s2: { shadowColor: "#000066", shadowOpacity: 0.12, shadowRadius: 12, shadowOffset: { width: 0, height: 8 }, elevation: 4 },
} as const;
