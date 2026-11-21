/**
 * Peças comuns aos ecrãs de conta (entrar, criar conta, códigos). Iguais a
 * apps/web/components/pe/conta/Partes.tsx, adaptadas ao telemóvel e às telas do canvas.
 */
import { router, type Href } from "expo-router";
import { Check, ChevronLeft } from "lucide-react-native";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Pressable, TextInput, type TextInputInstance, View } from "react-native";
import Svg, { Path } from "react-native-svg";
import { BotaoIcone, Texto, Titulo } from "@/ui";
import { cor, fonte, raio } from "@/tema";

/** Título h1 de um ecrã de conta, com o passo por cima e o texto por baixo. */
export function TituloConta({ titulo, texto, passo }: { titulo: string; texto?: ReactNode; passo?: string }) {
  return (
    <View style={{ gap: 8 }}>
      {passo ? (
        <Texto v="legenda" forte suave>
          {passo}
        </Texto>
      ) : null}
      <Titulo>{titulo}</Titulo>
      {texto ? typeof texto === "string" ? <Texto suave>{texto}</Texto> : texto : null}
    </View>
  );
}

/** Email em destaque dentro de uma frase suave. */
export function EmailForte({ children }: { children: string }) {
  return (
    <Texto forte cor={cor.tinta}>
      {children}
    </Texto>
  );
}

/** Seta de voltar no topo (sem cabeçalho com título, como nas telas do canvas). */
export function Voltar({ rotulo = "Voltar", para = "/entrar" }: { rotulo?: string; para?: Href }) {
  return (
    <BotaoIcone rotulo={rotulo} onPress={() => (router.canGoBack() ? router.back() : router.replace(para))} style={{ marginLeft: -10 }}>
      <ChevronLeft size={26} color={cor.tinta} />
    </BotaoIcone>
  );
}

export function Ou() {
  return (
    <View accessible={false} importantForAccessibility="no-hide-descendants" style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
      <View style={{ flex: 1, height: 1, backgroundColor: cor.linha }} />
      <Texto v="legenda" suave>
        ou
      </Texto>
      <View style={{ flex: 1, height: 1, backgroundColor: cor.linha }} />
    </View>
  );
}

/** "Ainda não tem conta? Criar conta grátis" — frase com uma ligação no fim. */
export function FraseComLigacao({ frase, ligacao, href, onPress, centro }: { frase: string; ligacao: string; href?: Href; onPress?: () => void; centro?: boolean }) {
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: centro ? "center" : "flex-start", columnGap: 4 }}>
      <Texto suave>{frase}</Texto>
      <Pressable
        accessibilityRole="link"
        hitSlop={8}
        onPress={() => (href ? router.push(href) : onPress?.())}
        style={{ minHeight: 44, justifyContent: "center" }}
      >
        <Texto forte cor={cor.azulVivo} style={{ textDecorationLine: "underline" }}>
          {ligacao}
        </Texto>
      </Pressable>
    </View>
  );
}

/** Ligação de texto solta ("Esqueci-me da palavra-passe", "Enviar outro código"). */
export function Ligacao({ children, onPress, href, inactivo }: { children: string; onPress?: () => void; href?: Href; inactivo?: boolean }) {
  return (
    <Pressable
      accessibilityRole={href ? "link" : "button"}
      accessibilityState={{ disabled: !!inactivo }}
      disabled={inactivo}
      hitSlop={4}
      onPress={() => (href ? router.push(href) : onPress?.())}
      style={{ alignSelf: "flex-start", minHeight: 44, justifyContent: "center" }}
    >
      <Texto v="rotulo" cor={inactivo ? cor.tintaSuave : cor.azulVivo} style={{ textDecorationLine: "underline" }}>
        {children}
      </Texto>
    </Pressable>
  );
}

/** Ajuda da palavra-passe nova: fica verde com um visto quando já tem 8 caracteres. */
export function AjudaSenha({ senha }: { senha: string }) {
  const ok = senha.length >= 8;
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: -2 }}>
      {ok ? <Check size={16} color={cor.certo} strokeWidth={2.5} /> : null}
      <Texto v="legenda" forte={ok} cor={ok ? cor.certo : cor.tintaSuave}>
        Tem 8 caracteres ou mais
      </Texto>
    </View>
  );
}

/** Contagem decrescente para "pedir outro código". */
export function useEspera(inicial: number) {
  const [s, setS] = useState(inicial);
  useEffect(() => {
    if (s <= 0) return;
    const t = setTimeout(() => setS((x) => x - 1), 1000);
    return () => clearTimeout(t);
  }, [s]);
  return [s, setS] as const;
}

export function textoEspera(s: number) {
  return `Pode pedir outro código daqui a ${s} ${s === 1 ? "segundo" : "segundos"}.`;
}

/**
 * Código de 6 algarismos em 6 quadrados (tela VerificarEmail). Por baixo é um só campo, para
 * funcionar com colar e com o preenchimento automático do código que chega por email/SMS.
 */
export function CampoCodigo6({ valor, aoMudar, erro, rotulo = "Código de verificação", autoFocus }: { valor: string; aoMudar: (v: string) => void; erro?: string | null; rotulo?: string; autoFocus?: boolean }) {
  const ref = useRef<TextInputInstance>(null);
  const [foco, setFoco] = useState(false);
  return (
    <View style={{ gap: 8 }}>
      <Texto v="rotulo">{rotulo}</Texto>
      <Pressable accessible={false} onPress={() => ref.current?.focus()} style={{ flexDirection: "row", gap: 8 }}>
        {Array.from({ length: 6 }, (_, i) => {
          const c = valor[i] ?? "";
          const actual = foco && i === Math.min(valor.length, 5);
          return (
            <View
              key={i}
              style={{
                flex: 1,
                height: 60,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: raio.sm,
                borderWidth: 2,
                borderColor: erro ? cor.errado : actual ? cor.azulVivo : c ? cor.azulMarca : cor.linhaForte,
                backgroundColor: c ? cor.fundoSuave : cor.fundo,
              }}
            >
              <Texto style={{ fontFamily: fonte.titulo, fontSize: 26, lineHeight: 32 }} numeros>
                {c}
              </Texto>
            </View>
          );
        })}
        <TextInput
          ref={ref}
          value={valor}
          onChangeText={(t) => aoMudar(t.replace(/\D/g, "").slice(0, 6))}
          onFocus={() => setFoco(true)}
          onBlur={() => setFoco(false)}
          keyboardType="number-pad"
          inputMode="numeric"
          autoComplete="one-time-code"
          textContentType="oneTimeCode"
          maxLength={6}
          autoFocus={autoFocus}
          accessibilityLabel={rotulo}
          accessibilityHint={erro ?? "Escreva os 6 algarismos"}
          caretHidden
          style={{ position: "absolute", inset: 0, opacity: 0.02, color: "transparent", fontSize: 1 }}
        />
      </Pressable>
      {erro ? (
        <Texto v="legenda" forte cor={cor.errado} accessibilityLiveRegion="polite">
          {erro}
        </Texto>
      ) : null}
    </View>
  );
}

/** Código num só campo largo (tela NovaSenha). */
export function CampoCodigoLinha({ valor, aoMudar, erro, autoFocus }: { valor: string; aoMudar: (v: string) => void; erro?: string | null; autoFocus?: boolean }) {
  const [foco, setFoco] = useState(false);
  return (
    <View style={{ gap: 4 }}>
      <Texto v="rotulo">Código de 6 algarismos</Texto>
      <TextInput
        value={valor}
        onChangeText={(t) => aoMudar(t.replace(/\D/g, "").slice(0, 6))}
        onFocus={() => setFoco(true)}
        onBlur={() => setFoco(false)}
        keyboardType="number-pad"
        inputMode="numeric"
        autoComplete="one-time-code"
        textContentType="oneTimeCode"
        maxLength={6}
        autoFocus={autoFocus}
        placeholder="000000"
        placeholderTextColor={cor.linha}
        accessibilityLabel="Código de 6 algarismos"
        accessibilityHint={erro ?? undefined}
        style={{
          height: 52,
          paddingHorizontal: 14,
          fontFamily: fonte.titulo,
          fontSize: 22,
          letterSpacing: 6,
          color: cor.tinta,
          backgroundColor: cor.fundo,
          borderWidth: foco || erro ? 2 : 1.5,
          borderColor: erro ? cor.errado : foco ? cor.azulVivo : cor.linhaForte,
          borderRadius: raio.sm,
        }}
      />
      {erro ? (
        <Texto v="legenda" forte cor={cor.errado}>
          {erro}
        </Texto>
      ) : null}
    </View>
  );
}

/** O "G" do Google a azul-marca, como no canvas (botão secundário). */
export function IconeGoogle({ tamanho = 20, corIcone = cor.azulMarca }: { tamanho?: number; corIcone?: string }) {
  return (
    <Svg width={tamanho} height={tamanho} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no">
      <Path fill={corIcone} d="M21.6 12.23c0-.68-.06-1.34-.17-1.97H12v3.73h5.39a4.6 4.6 0 0 1-2 3.02v2.51h3.24c1.89-1.74 2.97-4.3 2.97-7.29z" />
      <Path fill={corIcone} d="M12 22c2.7 0 4.96-.9 6.62-2.43l-3.24-2.51c-.9.6-2.04.96-3.38.96-2.6 0-4.8-1.76-5.59-4.12H3.07v2.59A10 10 0 0 0 12 22z" />
      <Path fill={corIcone} d="M6.41 13.9a6 6 0 0 1 0-3.8V7.51H3.07a10 10 0 0 0 0 8.98z" />
      <Path fill={corIcone} d="M12 5.98c1.47 0 2.79.5 3.82 1.5l2.87-2.87C16.95 2.99 14.7 2 12 2A10 10 0 0 0 3.07 7.51l3.34 2.59C7.2 7.74 9.4 5.98 12 5.98z" />
    </Svg>
  );
}
