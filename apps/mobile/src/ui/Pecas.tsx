import { router, type Href } from "expo-router";
import { ChevronRight, Heart } from "lucide-react-native";
import { type ReactNode, useEffect, useState } from "react";
import { AccessibilityInfo, Animated, Image, Pressable, type StyleProp, Switch, View, type ViewStyle } from "react-native";
import { balao, cor, raio } from "@/tema";
import { Texto } from "./Texto";

/** Etiqueta pequena (estado, nível, plano). */
export function Etiqueta({ children, tom = "neutro", icone }: { children: ReactNode; tom?: "neutro" | "certo" | "errado" | "realce" | "marca" | "info"; icone?: ReactNode }) {
  const t = {
    neutro: { f: cor.fundoSuave, c: cor.tinta },
    certo: { f: cor.certoSuave, c: cor.certo },
    errado: { f: cor.erradoSuave, c: cor.errado },
    realce: { f: cor.realceSuave, c: cor.tinta },
    marca: { f: cor.azulMarca, c: cor.sobreMarca },
    info: { f: cor.fundoForte, c: cor.azulMarca },
  }[tom];
  return (
    <View style={{ alignSelf: "flex-start", flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: t.f, paddingHorizontal: 10, paddingVertical: 4, borderRadius: raio.sm }}>
      {icone}
      <Texto v="rotulo" cor={t.c}>
        {children}
      </Texto>
    </View>
  );
}

/** Bloco com contorno (cursos, listas). Com `href` ou `onPress` fica tocável. */
export function Cartao({ children, href, onPress, suave, style, rotulo }: { children: ReactNode; href?: Href; onPress?: () => void; suave?: boolean; style?: StyleProp<ViewStyle>; rotulo?: string }) {
  const base: ViewStyle = suave
    ? { backgroundColor: cor.fundoSuave, borderRadius: raio.md, padding: 16, gap: 8 }
    : { borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, padding: 16, gap: 8, backgroundColor: cor.fundo };
  if (!href && !onPress) return <View style={[base, style]}>{children}</View>;
  return (
    <Pressable
      accessibilityRole={href ? "link" : "button"}
      accessibilityLabel={rotulo}
      onPress={() => (href ? router.push(href) : onPress?.())}
      style={({ pressed }) => [base, pressed ? { backgroundColor: cor.fundoSuave } : null, style]}
    >
      {children}
    </Pressable>
  );
}

/** O balão de fala azul-marca: o elemento-assinatura do ProEnglish (frases do tutor, cartão "Continuar"). */
export function BalaoFala({ children, aluno, tamanho = "grande", style }: { children: ReactNode; aluno?: boolean; tamanho?: "grande" | "medio" | "pequeno"; style?: StyleProp<ViewStyle> }) {
  const forma = aluno ? balao.aluno : balao[tamanho];
  return (
    <View style={[forma, { backgroundColor: aluno ? cor.fundoSuave : cor.azulMarca, padding: tamanho === "grande" ? 24 : 16, gap: 8 }, style]}>{children}</View>
  );
}

/** Palavra/expressão destacada a amarelo dentro de uma frase. */
export function Realce({ children }: { children: ReactNode }) {
  return (
    <Texto style={{ backgroundColor: cor.realce, color: cor.tinta }} forte>
      {` ${children} `}
    </Texto>
  );
}

/** Barra de progresso (0–100). `sobreMarca` para usar dentro de um bloco azul. */
export function BarraProgresso({ valor, rotulo, sobreMarca, altura = 8, corBarra }: { valor: number; rotulo: string; sobreMarca?: boolean; altura?: number; corBarra?: string }) {
  const v = Math.max(0, Math.min(100, Math.round(valor || 0)));
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel={rotulo}
      accessibilityValue={{ min: 0, max: 100, now: v }}
      style={{ height: altura, backgroundColor: sobreMarca ? cor.sobreMarcaFraco : cor.fundoForte, borderRadius: raio.pilula, overflow: "hidden" }}
    >
      <View style={{ width: `${v}%`, height: "100%", backgroundColor: corBarra ?? (sobreMarca ? cor.sobreMarca : cor.azulVivo), borderRadius: raio.pilula }} />
    </View>
  );
}

/** Corações (vidas) do laboratório de prática. */
export function Vidas({ quantas, ilimitadas }: { quantas: number; ilimitadas?: boolean }) {
  return (
    <View accessible accessibilityLabel={ilimitadas ? "Vidas ilimitadas" : `${quantas} ${quantas === 1 ? "vida" : "vidas"}`} style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
      <Heart size={20} color={cor.vida} fill={cor.vida} />
      <Texto v="rotulo" numeros>
        {ilimitadas ? "∞" : quantas}
      </Texto>
    </View>
  );
}

/** Filtros em pílulas, com deslocamento horizontal. */
export function Pilulas<T extends string>({ opcoes, valor, aoMudar, rotulo }: { opcoes: { valor: T; nome: string }[]; valor: T; aoMudar: (v: T) => void; rotulo: string }) {
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={rotulo} style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      {opcoes.map((o) => {
        const a = o.valor === valor;
        return (
          <Pressable
            key={o.valor}
            accessibilityRole="radio"
            accessibilityState={{ selected: a }}
            onPress={() => aoMudar(o.valor)}
            style={{ minHeight: 40, paddingHorizontal: 14, justifyContent: "center", borderRadius: raio.pilula, borderWidth: 1.5, borderColor: a ? cor.azulMarca : cor.linhaForte, backgroundColor: a ? cor.azulMarca : cor.fundo }}
          >
            <Texto v="rotulo" cor={a ? cor.sobreMarca : cor.tinta}>
              {o.nome}
            </Texto>
          </Pressable>
        );
      })}
    </View>
  );
}

/** Interruptor com rótulo e descrição (definições, avisos). */
export function Interruptor({ rotulo, descricao, valor, aoMudar, inactivo }: { rotulo: string; descricao?: string; valor: boolean; aoMudar: (v: boolean) => void; inactivo?: boolean }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 12, minHeight: 56, paddingVertical: 8 }}>
      <View style={{ flex: 1, gap: 2 }}>
        <Texto forte>{rotulo}</Texto>
        {descricao ? <Texto v="legenda" suave>{descricao}</Texto> : null}
      </View>
      <Switch
        accessibilityLabel={rotulo}
        value={valor}
        onValueChange={aoMudar}
        disabled={inactivo}
        trackColor={{ true: cor.azulMarca, false: cor.linhaForte }}
        thumbColor={cor.fundo}
        ios_backgroundColor={cor.linhaForte}
      />
    </View>
  );
}

/** Aviso em bloco: info (azul claro), certo, erro, realce. */
export function Aviso({ titulo, children, tom = "info", accao }: { titulo?: string; children?: ReactNode; tom?: "info" | "certo" | "erro" | "realce"; accao?: ReactNode }) {
  const t = { info: cor.fundoSuave, certo: cor.certoSuave, erro: cor.erradoSuave, realce: cor.realceSuave }[tom];
  const c = { info: cor.tinta, certo: cor.certo, erro: cor.errado, realce: cor.tinta }[tom];
  return (
    <View accessibilityRole={tom === "erro" ? "alert" : undefined} style={{ backgroundColor: t, borderRadius: raio.md, padding: 16, gap: 6 }}>
      {titulo ? (
        <Texto v="rotulo" cor={c} style={{ fontSize: 16, lineHeight: 22 }}>
          {titulo}
        </Texto>
      ) : null}
      {typeof children === "string" ? <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>{children}</Texto> : children}
      {accao}
    </View>
  );
}

/** Esqueleto de carregamento que pulsa devagar (pára com "reduzir movimento"). */
export function Osso({ altura = 20, largura, raio: r = raio.md, style }: { altura?: number; largura?: number | `${number}%`; raio?: number; style?: StyleProp<ViewStyle> }) {
  const [op] = useState(() => new Animated.Value(1));
  useEffect(() => {
    let laco: Animated.CompositeAnimation | null = null;
    AccessibilityInfo.isReduceMotionEnabled().then((reduzir) => {
      if (reduzir) return;
      laco = Animated.loop(
        Animated.sequence([
          Animated.timing(op, { toValue: 0.55, duration: 800, useNativeDriver: true }),
          Animated.timing(op, { toValue: 1, duration: 800, useNativeDriver: true }),
        ])
      );
      laco.start();
    });
    return () => laco?.stop();
  }, [op]);
  return <Animated.View aria-hidden style={[{ height: altura, width: largura ?? "100%", borderRadius: r, backgroundColor: cor.fundoForte, opacity: op }, style]} />;
}

/** Ícone num quadrado com canto de balão (listas "Praticar hoje", definições). */
export function MarcaIcone({ children, marca, tamanho = 40 }: { children: ReactNode; marca?: boolean; tamanho?: number }) {
  return (
    <View style={[marca ? balao.pequeno : { borderRadius: raio.md }, { width: tamanho, height: tamanho, alignItems: "center", justifyContent: "center", backgroundColor: marca ? cor.azulMarca : cor.fundoForte }]}>
      {children}
    </View>
  );
}

/** Linha de lista tocável: ícone, título, descrição e seta (como "Praticar hoje" no início). */
export function LinhaLista({ icone, titulo, descricao, href, onPress, direita, suave = true }: { icone?: ReactNode; titulo: string; descricao?: string; href?: Href; onPress?: () => void; direita?: ReactNode; suave?: boolean }) {
  return (
    <Pressable
      accessibilityRole={href ? "link" : "button"}
      accessibilityLabel={descricao ? `${titulo}. ${descricao}` : titulo}
      onPress={() => (href ? router.push(href) : onPress?.())}
      style={({ pressed }) => [
        { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 64, paddingVertical: 8, paddingHorizontal: 12, borderRadius: raio.md },
        suave ? { backgroundColor: cor.fundoSuave } : { borderBottomWidth: 1, borderColor: cor.linha, borderRadius: 0, paddingHorizontal: 0 },
        pressed ? { backgroundColor: cor.fundoForte } : null,
      ]}
    >
      {icone}
      <View style={{ flex: 1 }}>
        <Texto forte style={{ lineHeight: 22 }}>
          {titulo}
        </Texto>
        {descricao ? <Texto v="legenda" suave>{descricao}</Texto> : null}
      </View>
      {direita ?? <ChevronRight size={20} color={cor.tintaSuave} />}
    </Pressable>
  );
}

/** Número grande com rótulo pequeno (estatísticas, fim de lição). */
export function Numero({ rotulo, valor }: { rotulo: string; valor: string | number }) {
  return (
    <View accessible accessibilityLabel={`${rotulo}: ${valor}`} style={{ flex: 1, gap: 2, paddingVertical: 14, paddingHorizontal: 12, backgroundColor: cor.fundoSuave, borderRadius: raio.md }}>
      <Texto v="legenda" suave>
        {rotulo}
      </Texto>
      <Texto v="tituloM" numeros style={{ fontSize: 24, lineHeight: 30 }}>
        {valor}
      </Texto>
    </View>
  );
}

const LOGOS = {
  azul: { src: require("@/assets/images/logo/Logo_azul.png"), r: 1216 / 946 },
  branco: { src: require("@/assets/images/logo/Logo_Branco.png"), r: 1216 / 946 },
  "azul-assinatura": { src: require("@/assets/images/logo/Logo_azul_com_assinatura.png"), r: 2022 / 946 },
  "branco-assinatura": { src: require("@/assets/images/logo/Logo_Branco_com_assinatura.png"), r: 2022 / 946 },
} as const;

export function Logo({ versao = "azul", altura = 36 }: { versao?: keyof typeof LOGOS; altura?: number }) {
  const l = LOGOS[versao];
  return <Image source={l.src} accessibilityLabel="ProEnglish" style={{ height: altura, width: altura * l.r }} resizeMode="contain" />;
}
