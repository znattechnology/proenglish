import { router } from "expo-router";
import { ChevronLeft, X } from "lucide-react-native";
import type { ReactNode } from "react";
import { KeyboardAvoidingView, Platform, RefreshControl, ScrollView, type StyleProp, View, type ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { cor, espaco } from "@/tema";
import { BotaoIcone } from "./Botao";
import { Texto } from "./Texto";

/**
 * Moldura de todos os ecrãs: fundo branco, margens laterais de 20, zona segura no topo,
 * deslocamento vertical e "puxar para actualizar" quando há `aoActualizar`.
 * `cabecalho` fica fixo por cima; `rodape` fica fixo em baixo (ex.: botão "Verificar").
 */
export function Ecra({
  children,
  cabecalho,
  rodape,
  semScroll,
  aoActualizar,
  aActualizar = false,
  semMargem,
  semTopo,
  style,
  fundo = cor.fundo,
}: {
  children: ReactNode;
  cabecalho?: ReactNode;
  rodape?: ReactNode;
  semScroll?: boolean;
  aoActualizar?: () => void;
  aActualizar?: boolean;
  semMargem?: boolean;
  /** Não aplicar a zona segura do topo (quando o ecrã está dentro de separadores com cabeçalho próprio). */
  semTopo?: boolean;
  style?: StyleProp<ViewStyle>;
  fundo?: string;
}) {
  const ins = useSafeAreaInsets();
  const conteudo: StyleProp<ViewStyle> = [{ paddingHorizontal: semMargem ? 0 : espaco.gutter, paddingTop: 16, paddingBottom: 24, gap: 24 }, style];
  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1, backgroundColor: fundo, paddingTop: semTopo ? 0 : ins.top }}>
      {cabecalho}
      {semScroll ? (
        <View style={[{ flex: 1 }, conteudo]}>{children}</View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={[{ flexGrow: 1 }, conteudo]}
          keyboardShouldPersistTaps="handled"
          refreshControl={aoActualizar ? <RefreshControl refreshing={aActualizar} onRefresh={aoActualizar} tintColor={cor.azulMarca} colors={[cor.azulMarca]} /> : undefined}
        >
          {children}
        </ScrollView>
      )}
      {rodape ? (
        <View style={{ paddingHorizontal: espaco.gutter, paddingTop: 12, paddingBottom: Math.max(ins.bottom, 16), borderTopWidth: 1, borderColor: cor.linha, backgroundColor: fundo, gap: 12 }}>{rodape}</View>
      ) : null}
    </KeyboardAvoidingView>
  );
}

/**
 * Cabeçalho de ecrã secundário: seta para voltar (ou X para fechar), título e subtítulo,
 * e acções à direita. Com `linha` desenha a linha de baixo (como na conversa).
 */
export function Cabecalho({
  titulo,
  subtitulo,
  fechar,
  aoVoltar,
  direita,
  linha = true,
  semVoltar,
}: {
  titulo?: string;
  subtitulo?: string;
  fechar?: boolean;
  aoVoltar?: () => void;
  direita?: ReactNode;
  linha?: boolean;
  semVoltar?: boolean;
}) {
  const voltar = aoVoltar ?? (() => (router.canGoBack() ? router.back() : router.replace("/inicio")));
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12, paddingVertical: 8, minHeight: 60, borderBottomWidth: linha ? 1 : 0, borderColor: cor.linha }}>
      {semVoltar ? null : (
        <BotaoIcone rotulo={fechar ? "Fechar" : "Voltar"} onPress={voltar}>
          {fechar ? <X size={24} color={cor.tinta} /> : <ChevronLeft size={26} color={cor.tinta} />}
        </BotaoIcone>
      )}
      <View style={{ flex: 1, paddingLeft: semVoltar ? 8 : 0 }}>
        {titulo ? (
          <Texto v="tituloXS" accessibilityRole="header" numberOfLines={1} style={{ fontFamily: "Montserrat_700Bold", fontSize: 18, lineHeight: 24 }}>
            {titulo}
          </Texto>
        ) : null}
        {subtitulo ? (
          <Texto v="legenda" suave numberOfLines={1}>
            {subtitulo}
          </Texto>
        ) : null}
      </View>
      {direita}
    </View>
  );
}

/** Secção com título h2 e, opcionalmente, uma ligação à direita ("Ver todos"). */
export function Seccao({ titulo, direita, children, gap = 8 }: { titulo: string; direita?: ReactNode; children: ReactNode; gap?: number }) {
  return (
    <View style={{ gap }}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <Texto v="tituloS" accessibilityRole="header" style={{ flex: 1 }}>
          {titulo}
        </Texto>
        {direita}
      </View>
      {children}
    </View>
  );
}
