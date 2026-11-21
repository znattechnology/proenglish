/**
 * Conteúdo de uma aula escrito pelo professor (web components/pe/curso/TextoRico.tsx).
 * Pode vir em Markdown (editor novo) ou em HTML (editor antigo). No telemóvel mostra-se como texto
 * simples com títulos, listas e negrito; não se interpreta HTML nem se abrem ligações escondidas.
 */
import { View } from "react-native";
import { Texto } from "@/ui";
import { cor } from "@/tema";

type Bloco = { tipo: "titulo" | "item" | "paragrafo" | "citacao"; texto: string; nivel?: number };

const ENTIDADES: Record<string, string> = { "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&apos;": "'" };

function deHtml(t: string) {
  return t
    .replace(/<\s*br\s*\/?>/gi, "\n")
    .replace(/<\s*h([1-6])[^>]*>/gi, (_m, n) => `\n${"#".repeat(Number(n))} `)
    .replace(/<\s*li[^>]*>/gi, "\n- ")
    .replace(/<\s*blockquote[^>]*>/gi, "\n> ")
    .replace(/<\s*(strong|b)\s*>/gi, "**")
    .replace(/<\s*\/\s*(strong|b)\s*>/gi, "**")
    .replace(/<\s*\/\s*(p|div|h[1-6]|li|ul|ol|blockquote)\s*>/gi, "\n\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&[a-z#0-9]+;/gi, (e) => ENTIDADES[e.toLowerCase()] ?? e);
}

function blocos(texto: string): Bloco[] {
  const t = texto.trim().startsWith("<") ? deHtml(texto) : texto;
  const out: Bloco[] = [];
  let paragrafo: string[] = [];
  const fechar = () => {
    if (paragrafo.length) out.push({ tipo: "paragrafo", texto: paragrafo.join(" ") });
    paragrafo = [];
  };
  for (const bruta of t.split(/\r?\n/)) {
    const l = bruta.trim();
    if (!l) {
      fechar();
      continue;
    }
    const h = /^(#{1,6})\s+(.*)$/.exec(l);
    const item = /^([-*+]|\d+[.)])\s+(.*)$/.exec(l);
    if (h) {
      fechar();
      out.push({ tipo: "titulo", texto: h[2], nivel: h[1].length });
    } else if (item) {
      fechar();
      out.push({ tipo: "item", texto: item[2] });
    } else if (l.startsWith(">")) {
      fechar();
      out.push({ tipo: "citacao", texto: l.replace(/^>\s?/, "") });
    } else paragrafo.push(l);
  }
  fechar();
  return out;
}

/** Negrito (**x**) e itálico (*x* ou _x_) em linha; ligações [texto](url) ficam só com o texto. */
function Linha({ texto }: { texto: string }) {
  const limpo = texto.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1").replace(/`([^`]+)`/g, "$1");
  const partes = limpo.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {partes.map((p, i) =>
        p.startsWith("**") && p.endsWith("**") ? (
          <Texto key={i} forte style={{ fontSize: 17, lineHeight: 27 }}>
            {p.slice(2, -2)}
          </Texto>
        ) : (
          p.replace(/(^|\s)[*_]([^*_]+)[*_](?=\s|$|[.,;:!?])/g, "$1$2")
        )
      )}
    </>
  );
}

export function TextoRico({ texto }: { texto: string }) {
  const lista = blocos(texto);
  return (
    <View style={{ gap: 12 }}>
      {lista.map((b, i) =>
        b.tipo === "titulo" ? (
          <Texto key={i} v={b.nivel && b.nivel <= 2 ? "tituloS" : "tituloXS"} accessibilityRole="header">
            {b.texto.replace(/\*\*/g, "")}
          </Texto>
        ) : b.tipo === "item" ? (
          <View key={i} style={{ flexDirection: "row", gap: 10, paddingLeft: 4 }}>
            <Texto style={{ fontSize: 17, lineHeight: 27 }}>•</Texto>
            <Texto style={{ flex: 1, fontSize: 17, lineHeight: 27 }}>
              <Linha texto={b.texto} />
            </Texto>
          </View>
        ) : b.tipo === "citacao" ? (
          <Texto key={i} v="voz" cor={cor.azulMarca} style={{ fontSize: 20, lineHeight: 30 }}>
            <Linha texto={b.texto} />
          </Texto>
        ) : (
          <Texto key={i} style={{ fontSize: 17, lineHeight: 27 }}>
            <Linha texto={b.texto} />
          </Texto>
        )
      )}
    </View>
  );
}
