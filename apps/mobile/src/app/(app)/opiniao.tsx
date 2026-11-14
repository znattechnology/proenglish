/**
 * Dar a sua opinião (canvas: Opiniao; web: user/feedback/page.tsx).
 * Aceita ?trigger=...&chave=... (quando vem de um pedido da app, como o cartão do início).
 */
import { router, useLocalSearchParams } from "expo-router";
import { CheckCircle2, Send, Star } from "lucide-react-native";
import { useState } from "react";
import { Pressable, View } from "react-native";
import { Caixa } from "@/componentes/perfil/Campos";
import { NOTAS, useOpiniaoEnviarMutation, useOpiniaoEstadoQuery } from "@/dominios/perfil/api";
import { cor } from "@/tema";
import { Aviso, Botao, Cabecalho, Campo, Ecra, Texto, Titulo } from "@/ui";

export default function EcraOpiniao() {
  const q = useLocalSearchParams<{ trigger?: string; chave?: string }>();
  const { data: estado } = useOpiniaoEstadoQuery();
  const chave = (typeof q.chave === "string" && q.chave) || (estado?.should_show_prompt ? estado.chave : null);
  const trigger = (typeof q.trigger === "string" && q.trigger) || (estado?.should_show_prompt ? estado.trigger : null);
  const frase = chave && estado?.chave === chave ? estado.frase : null;

  const [nota, setNota] = useState<number | null>(null);
  const [comentario, setComentario] = useState("");
  const [publico, setPublico] = useState(false);
  const [contacto, setContacto] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [enviada, setEnviada] = useState(false);
  const [enviar, { isLoading }] = useOpiniaoEnviarMutation();
  const temComentario = !!comentario.trim();

  if (enviada)
    return (
      <Ecra
        cabecalho={<Cabecalho fechar linha={false} />}
        rodape={
          <Botao larguraTotal onPress={() => (router.canGoBack() ? router.back() : router.replace("/inicio"))}>
            Voltar
          </Botao>
        }
        style={{ gap: 16, paddingTop: 24 }}
      >
        <CheckCircle2 size={44} color={cor.certo} />
        <Titulo v="tituloL" accessibilityLiveRegion="polite">
          Obrigado pela sua opinião
        </Titulo>
        <Texto suave>Lemos todas as opiniões.{publico ? " Se a escolhermos para o site, aparece com o seu primeiro nome, a inicial do apelido e a área." : ""}</Texto>
      </Ecra>
    );

  const submeter = async () => {
    setErro(null);
    if (!nota) return setErro("Escolha uma nota de 1 a 5.");
    try {
      await enviar({
        rating: nota,
        comment: comentario.trim(),
        trigger: trigger ?? "manual",
        context_data: chave ? { chave } : {},
        allow_public: publico && temComentario,
        allow_contact: contacto,
      }).unwrap();
      setEnviada(true);
    } catch (e) {
      const d = (e as { status?: string; data?: { non_field_errors?: string[]; detail?: string } })?.data;
      setErro(d?.non_field_errors?.[0] ?? d?.detail ?? ((e as { status?: string })?.status === "FETCH_ERROR" ? "Sem ligação ao servidor. Verifique a Internet e tente outra vez." : "Não foi possível enviar. Tente outra vez."));
    }
  };

  return (
    <Ecra
      cabecalho={<Cabecalho fechar linha={false} />}
      rodape={
        <Botao larguraTotal carregando={isLoading} icone={isLoading ? undefined : <Send size={20} color={cor.sobreMarca} />} onPress={() => void submeter()}>
          {isLoading ? "A enviar…" : "Enviar opinião"}
        </Botao>
      }
      style={{ gap: 20, paddingTop: 4 }}
    >
      <View style={{ gap: 6 }}>
        <Titulo v="tituloL" style={{ fontSize: 24, lineHeight: 30 }}>
          {frase ?? "Como está a correr o ProEnglish?"}
        </Titulo>
        <Texto suave>A sua opinião ajuda-nos a melhorar as lições.</Texto>
      </View>

      <View style={{ gap: 4 }}>
        <View accessibilityRole="radiogroup" accessibilityLabel="A sua nota" style={{ flexDirection: "row", gap: 4, marginLeft: -4 }}>
          {NOTAS.map((nome, i) => {
            const n = i + 1;
            const cheia = nota !== null && n <= nota;
            return (
              <Pressable
                key={n}
                accessibilityRole="radio"
                accessibilityLabel={`${n} de 5: ${nome.toLowerCase()}`}
                accessibilityState={{ selected: nota === n }}
                onPress={() => setNota(n)}
                style={({ pressed }) => ({ width: 52, height: 52, alignItems: "center", justifyContent: "center", opacity: pressed ? 0.7 : 1 })}
              >
                <Star size={36} color={cheia ? cor.azulMarca : cor.linhaForte} fill={cheia ? cor.azulMarca : "transparent"} strokeWidth={1.75} />
              </Pressable>
            );
          })}
        </View>
        <Texto v="rotulo" suave={!nota} accessibilityLiveRegion="polite">
          {nota ? `${nota} de 5: ${NOTAS[nota - 1].toLowerCase()}` : "1 é mau, 5 é muito bom."}
        </Texto>
      </View>

      <Campo
        rotulo="Quer contar mais? (opcional)"
        multilinha
        maxLength={2000}
        value={comentario}
        onChangeText={setComentario}
        placeholder="O que está a correr bem? O que mudaria?"
        ajuda={`${comentario.length} de 2000 caracteres`}
      />

      <View style={{ gap: 8 }}>
        <Caixa marcada={publico && temComentario} inactiva={!temComentario} aoMudar={setPublico}>
          {`Pode mostrar a minha opinião no site, só com o primeiro nome, a inicial do apelido e a área.${temComentario ? "" : " (Escreva um comentário para poder escolher.)"}`}
        </Caixa>
        <Caixa marcada={contacto} aoMudar={setContacto}>
          Podem contactar-me por email sobre esta opinião.
        </Caixa>
      </View>

      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
    </Ecra>
  );
}
