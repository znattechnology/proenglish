/**
 * A conversa com o tutor em curso, em ecrã inteiro (tela Conversa do canvas).
 * Web: apps/web/components/pe/conversa/Conversa.tsx.
 * Recebe ?id=<sessão> criada no separador "Conversa" (sessoesAbertas). No fim abre o resumo.
 */
import { router, useLocalSearchParams, usePreventRemove } from "expo-router";
import { ChevronLeft, Keyboard, ListChecks, Mic, MicOff, Send, Volume2 } from "lucide-react-native";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, type ScrollViewInstance, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Aviso, Botao, BotaoIcone, Cabecalho, Dialogo, Ecra, EstadoVazio, Texto, Titulo } from "@/ui";
import { balao, cor, fonte, raio } from "@/tema";
import { disseFrase, mmss } from "@/dominios/conversa/api";
import { Bolha, CartaoAjuste, FrasesAlvo, REGRA_FRASES } from "@/componentes/conversa/Pecas";
import { esquecerSessao, lerSessao, type SessaoAberta } from "@/componentes/conversa/sessoesAbertas";
import { useConversa } from "@/componentes/conversa/useConversa";

export default function EcraSessaoConversa() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const [aberta] = useState(() => lerSessao(id));
  if (!aberta)
    return (
      <Ecra cabecalho={<Cabecalho titulo="Conversa com o tutor" aoVoltar={() => router.replace("/conversa")} />}>
        <EstadoVazio
          titulo="Esta conversa já não está aberta"
          texto="A app foi fechada a meio ou a conversa já terminou. O que disse fica guardado no seu progresso."
          accao={
            <View style={{ gap: 10 }}>
              <Botao href="/conversa" substituir larguraTotal>
                Começar outra conversa
              </Botao>
              <Botao tipo="secundario" href="/conversa/progresso" substituir larguraTotal>
                Ver o progresso a falar
              </Botao>
            </View>
          }
        />
      </Ecra>
    );
  return <Chamada a={aberta} />;
}

function Chamada({ a }: { a: SessaoAberta }) {
  const { sessao, modo, chavePublica, minutosUsadosHoje, minutosDia } = a;
  const c = useConversa(sessao, modo, chavePublica);
  const ins = useSafeAreaInsets();
  const [aEscrever, setAEscrever] = useState(false);
  const [texto, setTexto] = useState("");
  const [sair, setSair] = useState(false);
  const [verFrases, setVerFrases] = useState(false);
  const lista = useRef<ScrollViewInstance>(null);

  const aTerminar = c.estado === "a_terminar" || c.estado === "terminada";
  const emCurso = c.estado === "em_curso" || c.estado === "a_ligar";

  // No fim, o resumo substitui este ecrã.
  useEffect(() => {
    if (c.estado === "terminada" && c.resumo) {
      esquecerSessao(sessao.id);
      router.replace(`/conversa/resumo/${c.resumo.id}`);
    }
  }, [c.estado, c.resumo, sessao.id]);

  // Voltar atrás (gesto, botão do Android) a meio da conversa: pergunta antes de terminar.
  usePreventRemove(emCurso, () => setSair(true));

  const objectivos = useMemo(() => sessao.objectivos ?? [], [sessao.objectivos]);
  const falasAluno = c.falas.filter((f) => f.quem === "aluno").map((f) => f.texto).join("\n");
  const ditos = useMemo(() => {
    const falas = falasAluno.split("\n");
    return new Set(objectivos.filter((o) => falas.some((f) => disseFrase(o.en, f))).map((o) => o.en));
  }, [objectivos, falasAluno]);
  const chaves = new Set(objectivos.map((o) => o.en.toLowerCase()));
  const outrasFrases = sessao.frases.filter((f) => !chaves.has(f.en.toLowerCase()));
  const temFrases = objectivos.length + outrasFrases.length > 0;

  const restante = sessao.max_segundos - c.segundos;
  const respostas = c.falas.filter((f) => f.quem === "aluno").length;
  const ajustes = c.falas.filter((f) => f.ajuste).length;
  const minutosHoje = Math.min(minutosDia ?? Infinity, minutosUsadosHoje + Math.floor(c.segundos / 60));
  const escrita = aEscrever || c.soEscrita;

  const instrucao =
    c.estado === "a_ligar"
      ? "A ligar ao tutor…"
      : aTerminar
        ? "A preparar o resumo…"
        : c.tutorAFalar
          ? "O tutor está a falar"
          : c.soEscrita
            ? "Escreva a resposta em inglês"
            : c.microfone
              ? "Responda em inglês. O tutor está a ouvir."
              : "Microfone desligado. Toque para voltar a falar.";

  if (c.estado === "erro") {
    return (
      <Ecra cabecalho={<Cabecalho titulo={sessao.situacao.titulo} fechar aoVoltar={() => router.back()} />}>
        <Titulo v="tituloM">Não foi possível conversar agora</Titulo>
        <Aviso tom="erro">{c.erro ?? "Não foi possível ligar ao tutor."}</Aviso>
        <Botao onPress={() => router.back()} larguraTotal>
          Voltar a preparar a conversa
        </Botao>
      </Ecra>
    );
  }

  const enviar = () => {
    if (!texto.trim()) return;
    c.escrever(texto);
    setTexto("");
  };

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1, backgroundColor: cor.fundo, paddingTop: ins.top }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12, paddingVertical: 8, minHeight: 64, borderBottomWidth: 1, borderColor: cor.linha }}>
        <BotaoIcone rotulo="Terminar e ver o resumo" onPress={() => (aTerminar ? null : setSair(true))}>
          <ChevronLeft size={26} color={cor.tinta} />
        </BotaoIcone>
        <View style={{ flex: 1 }}>
          <Texto accessibilityRole="header" numberOfLines={1} style={{ fontFamily: fonte.titulo, fontSize: 18, lineHeight: 24 }}>
            {sessao.situacao.titulo}
          </Texto>
          <Texto v="legenda" suave numeros numberOfLines={1}>
            {`Conversa com o tutor, ${mmss(c.segundos)} de ${Math.round(sessao.max_segundos / 60)} min`}
          </Texto>
        </View>
        {temFrases ? (
          <BotaoIcone rotulo="Frases e objectivos desta conversa" onPress={() => setVerFrases(true)}>
            <ListChecks size={24} color={cor.tinta} />
          </BotaoIcone>
        ) : null}
      </View>

      <ScrollView
        ref={lista}
        style={{ flex: 1 }}
        contentContainerStyle={{ flexGrow: 1, gap: 16, paddingHorizontal: 16, paddingVertical: 20 }}
        onContentSizeChange={() => lista.current?.scrollToEnd({ animated: true })}
        keyboardShouldPersistTaps="handled"
      >
        {c.estado === "a_ligar" ? (
          <View style={{ margin: "auto", alignItems: "center", gap: 12, paddingHorizontal: 24 }}>
            <ActivityIndicator color={cor.azulMarca} size="large" />
            <Texto suave centro>
              A ligar ao tutor. Fale depois de ouvir o tutor.
            </Texto>
          </View>
        ) : null}
        {c.falas.map((f) => (
          <View key={f.id} style={{ gap: 12 }}>
            <Bolha quem={f.quem}>{f.texto}</Bolha>
            {f.ajuste ? <CartaoAjuste ajuste={f.ajuste} /> : null}
          </View>
        ))}
        {c.parcial ? (
          <Bolha quem={c.parcial.quem} parcial>
            {c.parcial.texto}
          </Bolha>
        ) : null}
      </ScrollView>

      <View style={{ alignItems: "center", gap: 12, paddingHorizontal: 20, paddingTop: 16, paddingBottom: Math.max(ins.bottom, 20), backgroundColor: cor.fundoSuave }}>
        {c.erro ? (
          <View style={{ alignSelf: "stretch" }}>
            <Aviso tom="erro">{c.erro}</Aviso>
          </View>
        ) : null}
        {restante <= 30 && c.estado === "em_curso" ? (
          <View style={{ alignSelf: "stretch" }}>
            <Aviso>{`Faltam ${Math.max(0, restante)} segundos. A conversa termina sozinha e o resumo fica guardado.`}</Aviso>
          </View>
        ) : null}
        <Texto v="voz" centro accessibilityRole="text" accessibilityLiveRegion="polite" style={{ fontSize: 18, lineHeight: 26 }}>
          {instrucao}
        </Texto>
        {objectivos.length ? (
          <Pressable accessibilityRole="button" onPress={() => setVerFrases(true)} hitSlop={6}>
            <Texto v="legenda" suave style={{ textDecorationLine: "underline" }}>
              {`Objectivos já ditos: ${ditos.size} de ${objectivos.length}`}
            </Texto>
          </Pressable>
        ) : minutosDia ? (
          <Texto v="legenda" suave>{`Hoje já usou ${minutosHoje} dos ${minutosDia} minutos.`}</Texto>
        ) : null}

        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 28 }}>
          <BotaoLateral rotulo="Ouvir outra vez" onPress={c.ouvirOutraVez} inactivo={c.estado !== "em_curso"}>
            <Volume2 size={22} color={c.estado !== "em_curso" ? cor.tintaSuave : cor.azulMarca} />
          </BotaoLateral>
          {c.soEscrita ? (
            <View style={[balao.grande, { width: 80, height: 80, alignItems: "center", justifyContent: "center", backgroundColor: cor.fundoForte }]} accessible accessibilityLabel="Microfone indisponível no modo de ensaio">
              <MicOff size={34} color={cor.tintaSuave} />
            </View>
          ) : (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={c.microfone ? "Desligar o microfone" : "Ligar o microfone"}
              accessibilityState={{ selected: c.microfone, disabled: c.estado !== "em_curso" }}
              disabled={c.estado !== "em_curso"}
              onPress={c.alternarMicrofone}
              style={({ pressed }) => [
                balao.grande,
                {
                  width: 80,
                  height: 80,
                  alignItems: "center",
                  justifyContent: "center",
                  backgroundColor: c.estado !== "em_curso" ? cor.fundoForte : c.microfone ? cor.azulMarca : cor.tintaSuave,
                  borderWidth: c.microfone && !c.tutorAFalar && c.estado === "em_curso" ? 4 : 0,
                  borderColor: cor.realce,
                  opacity: pressed ? 0.85 : 1,
                },
              ]}
            >
              {c.microfone ? <Mic size={34} color={c.estado !== "em_curso" ? cor.tintaSuave : cor.sobreMarca} /> : <MicOff size={34} color={c.estado !== "em_curso" ? cor.tintaSuave : cor.sobreMarca} />}
            </Pressable>
          )}
          <BotaoLateral rotulo="Escrever em vez de falar" onPress={() => setAEscrever((v) => !v)} inactivo={c.estado !== "em_curso" || c.soEscrita} activo={escrita}>
            <Keyboard size={22} color={escrita ? cor.sobreMarca : c.estado !== "em_curso" ? cor.tintaSuave : cor.azulMarca} />
          </BotaoLateral>
        </View>

        {escrita && c.estado === "em_curso" ? (
          <View style={{ flexDirection: "row", alignSelf: "stretch", gap: 8 }}>
            <TextInput
              value={texto}
              onChangeText={setTexto}
              placeholder="Write your answer…"
              placeholderTextColor={cor.tintaSuave}
              accessibilityLabel="Resposta em inglês"
              autoFocus={!c.soEscrita}
              autoCorrect={false}
              returnKeyType="send"
              onSubmitEditing={enviar}
              style={{ flex: 1, minWidth: 0, height: 48, borderWidth: 1.5, borderColor: cor.linhaForte, borderRadius: raio.sm, paddingHorizontal: 14, fontFamily: fonte.texto, fontSize: 16, color: cor.tinta, backgroundColor: cor.fundo }}
            />
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Enviar"
              accessibilityState={{ disabled: !texto.trim() }}
              disabled={!texto.trim()}
              onPress={enviar}
              style={{ width: 48, height: 48, alignItems: "center", justifyContent: "center", borderRadius: raio.sm, backgroundColor: texto.trim() ? cor.azulMarca : cor.fundoForte }}
            >
              <Send size={20} color={texto.trim() ? cor.sobreMarca : cor.tintaSuave} />
            </Pressable>
          </View>
        ) : null}
      </View>

      <Dialogo aberto={sair} aoFechar={() => setSair(false)} titulo="Terminar a conversa?" texto="Guardamos o que disse e mostramos o resumo com as correcções.">
        <Botao
          larguraTotal
          onPress={() => {
            setSair(false);
            void c.terminar();
          }}
        >
          Terminar e ver o resumo
        </Botao>
        <Botao tipo="secundario" larguraTotal onPress={() => setSair(false)}>
          Continuar a conversa
        </Botao>
      </Dialogo>

      <Dialogo
        aberto={verFrases}
        aoFechar={() => setVerFrases(false)}
        titulo={objectivos.length ? "Objectivos desta conversa" : "Frases que pode usar"}
        texto={objectivos.length ? `Já disse ${ditos.size} de ${objectivos.length}. ${REGRA_FRASES}` : REGRA_FRASES}
      >
        <ScrollView style={{ maxHeight: 380 }} contentContainerStyle={{ gap: 16 }}>
          <FrasesAlvo frases={objectivos} ditas={ditos} reveladas={c.reveladas} aoRevelar={c.revelar} />
          {outrasFrases.length ? (
            <View style={{ gap: 4 }}>
              {objectivos.length ? <Texto v="rotulo">Outras frases que pode usar</Texto> : null}
              <FrasesAlvo frases={outrasFrases} ditas={new Set()} reveladas={c.reveladas} aoRevelar={c.revelar} />
            </View>
          ) : null}
          <View style={{ gap: 4, backgroundColor: cor.fundoSuave, borderRadius: raio.md, padding: 16 }}>
            <Texto forte>Nesta conversa</Texto>
            <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
              {respostas === 0 ? "Ainda não respondeu." : `${respostas} ${respostas === 1 ? "resposta dada" : "respostas dadas"}, ${ajustes} ${ajustes === 1 ? "ajuste" : "ajustes"}.`}
            </Texto>
            <Texto v="legenda" suave>
              No fim recebe um resumo com as frases a rever.
            </Texto>
          </View>
        </ScrollView>
        <Botao tipo="secundario" larguraTotal onPress={() => setVerFrases(false)}>
          Voltar à conversa
        </Botao>
      </Dialogo>
    </KeyboardAvoidingView>
  );
}

function BotaoLateral({ rotulo, onPress, inactivo, activo, children }: { rotulo: string; onPress: () => void; inactivo?: boolean; activo?: boolean; children: ReactNode }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={rotulo}
      accessibilityState={{ disabled: !!inactivo, expanded: activo }}
      disabled={inactivo}
      onPress={onPress}
      style={({ pressed }) => ({
        width: 52,
        height: 52,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: raio.sm,
        borderWidth: 2,
        borderColor: inactivo ? cor.linha : cor.azulMarca,
        backgroundColor: activo ? cor.azulMarca : pressed ? cor.fundoSuave : cor.fundo,
      })}
    >
      {children}
    </Pressable>
  );
}
