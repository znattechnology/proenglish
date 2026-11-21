/**
 * Uma conversa curta a decorrer, dentro de outro ecrã (lição, aula, exame oral, teste de nível):
 * frases a usar, legendas, tempo que falta, microfone, escrever e terminar.
 * Igual ao `Viva` de apps/web/components/pe/licao/ConversaCurta.tsx.
 *
 * semTexto (exame oral e teste de nível): sem caixa para escrever e sem ajustes durante a conversa.
 * No modo de ensaio (sem voz real) escreve-se sempre.
 */
import { Mic, MicOff, Send } from "lucide-react-native";
import { useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, type ScrollViewInstance, TextInput, View } from "react-native";
import { Aviso, Botao, Texto } from "@/ui";
import { balao, cor, fonte, raio } from "@/tema";
import { disseFrase, mmss, type ConversaAberta, type Resumo } from "@/dominios/conversa/api";
import { Bolha, FrasesAlvo, REGRA_FRASES } from "./Pecas";
import { useConversa } from "./useConversa";

export function Viva({
  dados,
  frases,
  aoTerminar,
  aoSaltar,
  tituloFrases,
  semTexto: pedidoSemTexto = false,
}: {
  dados: ConversaAberta;
  frases: string[];
  aoTerminar: (r: Resumo) => void;
  aoSaltar?: () => void;
  tituloFrases?: string;
  semTexto?: boolean;
}) {
  const semTexto = pedidoSemTexto && dados.modo === "vapi";
  const c = useConversa(dados.sessao, dados.modo, dados.chave_publica, { semTexto, semAjustes: pedidoSemTexto });
  const [texto, setTexto] = useState("");
  const lista = useRef<ScrollViewInstance>(null);
  const avisado = useRef(false);

  useEffect(() => {
    if (c.estado === "terminada" && c.resumo && !avisado.current) {
      avisado.current = true;
      aoTerminar(c.resumo);
    }
  }, [c.estado, c.resumo, aoTerminar]);

  const falasAluno = c.falas.filter((f) => f.quem === "aluno").map((f) => f.texto);
  const chave = falasAluno.join("\n");
  const ditas = useMemo(() => {
    const falas = chave.split("\n");
    return new Set(frases.filter((f) => falas.some((x) => disseFrase(f, x))));
  }, [frases, chave]);

  const comSentido = useMemo(() => {
    const pt = new Map([...(dados.sessao.frases ?? []), ...(dados.sessao.objectivos ?? [])].filter((f) => f.pt).map((f) => [f.en, f.pt]));
    return frases.map((en) => ({ en, pt: pt.get(en) ?? "" }));
  }, [frases, dados.sessao.frases, dados.sessao.objectivos]);

  const restante = dados.sessao.max_segundos - c.segundos;
  const aTerminar = c.estado === "a_terminar" || c.estado === "terminada";
  const estadoTexto =
    c.estado === "a_ligar"
      ? "A ligar ao tutor…"
      : aTerminar
        ? "A guardar a conversa…"
        : c.tutorAFalar
          ? "O tutor está a falar"
          : c.soEscrita
            ? "Escreva a sua resposta"
            : c.microfone
              ? "A ouvir"
              : "Microfone desligado. Toque para falar";

  if (c.estado === "erro") {
    return (
      <View style={{ gap: 12 }}>
        <Aviso tom="erro">{`${c.erro ?? "A ligação ao tutor falhou."}${aoSaltar ? " Pode saltar esta conversa: não perde vidas nem pontos." : ""}`}</Aviso>
        {aoSaltar ? (
          <Botao tipo="secundario" tamanho="medio" onPress={aoSaltar} style={{ alignSelf: "flex-start" }}>
            Saltar esta conversa
          </Botao>
        ) : null}
      </View>
    );
  }

  const enviar = () => {
    if (!texto.trim()) return;
    c.escrever(texto);
    setTexto("");
  };
  const podeEscrever = !semTexto || c.soEscrita;

  return (
    <View style={{ gap: 16 }}>
      {comSentido.length ? (
        <View style={{ gap: 4 }}>
          <Texto v="legenda" suave>
            {tituloFrases ?? "Use estas frases da lição"}
          </Texto>
          <FrasesAlvo frases={comSentido} ditas={ditas} reveladas={c.reveladas} aoRevelar={c.revelar} compacta />
          <Texto v="legenda" suave>
            {REGRA_FRASES}
          </Texto>
        </View>
      ) : null}

      <View style={{ gap: 12, borderWidth: 1.5, borderColor: cor.linha, borderRadius: raio.md, padding: 12 }}>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <Texto v="legenda" suave accessibilityLiveRegion="polite" style={{ flex: 1 }}>
            {estadoTexto}
          </Texto>
          <Texto v="legenda" forte numeros cor={restante <= 20 ? cor.errado : cor.tinta} accessibilityLabel={`Faltam ${mmss(restante)}`}>
            {mmss(restante)}
          </Texto>
        </View>
        <ScrollView
          ref={lista}
          nestedScrollEnabled
          style={{ maxHeight: 320, minHeight: 120 }}
          contentContainerStyle={{ gap: 10 }}
          onContentSizeChange={() => lista.current?.scrollToEnd({ animated: true })}
        >
          {c.estado === "a_ligar" ? (
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 24, alignSelf: "center" }}>
              <ActivityIndicator color={cor.azulMarca} />
              <Texto suave>A ligar ao tutor…</Texto>
            </View>
          ) : null}
          {c.falas.map((f) => (
            <Bolha key={f.id} quem={f.quem} compacta>
              {f.texto}
            </Bolha>
          ))}
          {c.parcial ? (
            <Bolha quem={c.parcial.quem} compacta parcial>
              {c.parcial.texto}
            </Bolha>
          ) : null}
        </ScrollView>
        {c.erro ? (
          <View accessibilityRole="alert" style={{ backgroundColor: cor.erradoSuave, borderRadius: raio.sm, paddingHorizontal: 12, paddingVertical: 8 }}>
            <Texto v="legenda">{c.erro}</Texto>
          </View>
        ) : null}
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          {c.soEscrita ? null : (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={c.microfone ? "Desligar o microfone" : "Ligar o microfone"}
              accessibilityState={{ selected: c.microfone, disabled: c.estado !== "em_curso" }}
              disabled={c.estado !== "em_curso"}
              onPress={c.alternarMicrofone}
              style={[balao.pequeno, { width: 48, height: 48, alignItems: "center", justifyContent: "center", backgroundColor: c.estado !== "em_curso" ? cor.fundoForte : c.microfone ? cor.azulMarca : cor.tintaSuave }]}
            >
              {c.microfone ? <Mic size={24} color={cor.sobreMarca} /> : <MicOff size={24} color={cor.sobreMarca} />}
            </Pressable>
          )}
          {podeEscrever ? (
            <>
              <TextInput
                value={texto}
                onChangeText={setTexto}
                editable={c.estado === "em_curso"}
                placeholder={c.soEscrita ? "Write your answer…" : "Ou escreva em inglês"}
                placeholderTextColor={cor.tintaSuave}
                accessibilityLabel="Escrever a resposta em inglês"
                autoCapitalize="sentences"
                autoCorrect={false}
                returnKeyType="send"
                onSubmitEditing={enviar}
                style={{ flex: 1, minWidth: 0, height: 48, borderWidth: 1.5, borderColor: cor.linhaForte, borderRadius: raio.sm, paddingHorizontal: 12, fontFamily: fonte.texto, fontSize: 16, color: cor.tinta, backgroundColor: cor.fundo }}
              />
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Enviar"
                disabled={!texto.trim() || c.estado !== "em_curso"}
                onPress={enviar}
                style={{ width: 48, height: 48, alignItems: "center", justifyContent: "center", opacity: !texto.trim() || c.estado !== "em_curso" ? 0.4 : 1 }}
              >
                <Send size={22} color={cor.azulMarca} />
              </Pressable>
            </>
          ) : null}
        </View>
      </View>

      <Botao tipo="secundario" tamanho="medio" onPress={() => void c.terminar()} disabled={aTerminar || c.estado === "a_ligar"} carregando={aTerminar} style={{ alignSelf: "flex-start" }}>
        {aTerminar ? "A guardar…" : `Terminar a conversa (${falasAluno.length} ${falasAluno.length === 1 ? "resposta" : "respostas"})`}
      </Botao>
    </View>
  );
}
