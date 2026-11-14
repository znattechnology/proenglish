/**
 * Entrar (Entrar.dc.html; web components/pe/conta/Entrar.tsx). Se a sessão terminou sozinha,
 * mostra por cima o aviso "A sua sessão terminou" (EstadoSessao.dc.html).
 */
import { router, useLocalSearchParams } from "expo-router";
import { Lock } from "lucide-react-native";
import { useRef, useState } from "react";
import { Modal, Pressable, type TextInputInstance, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { mensagemErro } from "@/api/erros";
import { BotaoGoogle, ComGoogle, type EntradaGoogle } from "@/componentes/conta/Google";
import { FraseComLigacao, Ligacao, Ou, TituloConta } from "@/componentes/conta/Partes";
import { useSessao } from "@/sessao/ContextoSessao";
import { Aviso, Botao, Campo, Ecra, Logo, Texto, Titulo } from "@/ui";
import { balao, cor } from "@/tema";

export default function Entrar() {
  return <ComGoogle>{(g) => <Formulario g={g} />}</ComGoogle>;
}

function Formulario({ g }: { g: EntradaGoogle }) {
  const p = useLocalSearchParams<{ email?: string; senha?: string }>();
  const { entrar, terminouSozinha } = useSessao();
  const [email, setEmail] = useState(p.email ?? "");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [aEntrar, setAEntrar] = useState(false);
  const [avisoFechado, setAvisoFechado] = useState(false);
  const refSenha = useRef<TextInputInstance>(null);
  const senhaMudou = p.senha === "alterada";

  const submeter = async () => {
    setErro(null);
    const mail = email.trim().toLowerCase();
    if (!mail || !senha) return setErro("Escreva o email e a palavra-passe.");
    setAEntrar(true);
    const r = await entrar(mail, senha);
    setAEntrar(false);
    if (r.ok) return; // a navegação muda sozinha para a área do estudante
    const m = mensagemErro(r.erro, "O email ou a palavra-passe não estão certos.");
    if (/verificad|verified|confirmou o seu email/i.test(m)) {
      router.push(`/verificar-email?email=${encodeURIComponent(mail)}&de=entrar`);
      return;
    }
    if (r.status === 403 || r.status === 429) return setErro("Tentou muitas vezes seguidas. Espere um minuto e tente outra vez.");
    setErro(/inválid|invalid|credenciais/i.test(m) ? "O email ou a palavra-passe não estão certos." : m);
  };

  return (
    <Ecra style={{ paddingTop: 40, paddingHorizontal: 24, gap: 32 }}>
      <Logo versao="azul-assinatura" altura={112} />
      <TituloConta titulo="Entrar na sua conta" texto="Retome a lição onde parou." />
      {senhaMudou ? <Aviso tom="certo">A palavra-passe foi alterada. Entre com a nova.</Aviso> : null}

      <View style={{ gap: 20 }}>
        <Campo
          rotulo="Email"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          inputMode="email"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          textContentType="emailAddress"
          returnKeyType="next"
          onSubmitEditing={() => refSenha.current?.focus()}
          submitBehavior="submit"
        />
        <View>
          <Campo
            ref={refSenha}
            rotulo="Palavra-passe"
            senha
            value={senha}
            onChangeText={setSenha}
            autoCapitalize="none"
            autoComplete="current-password"
            textContentType="password"
            returnKeyType="go"
            onSubmitEditing={() => void submeter()}
          />
          <Ligacao href={`/recuperar-senha${email.trim() ? `?email=${encodeURIComponent(email.trim().toLowerCase())}` : ""}`}>Esqueci-me da palavra-passe</Ligacao>
        </View>
        {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
        <Botao larguraTotal carregando={aEntrar} onPress={() => void submeter()}>
          {aEntrar ? "A entrar…" : "Entrar"}
        </Botao>
      </View>

      <Ou />
      <View style={{ gap: 12 }}>
        {g.erro ? <Aviso tom="erro">{g.erro}</Aviso> : null}
        <BotaoGoogle texto="Entrar com o Google" g={g} />
      </View>

      <View style={{ marginTop: "auto" }}>
        <FraseComLigacao centro frase="Ainda não tem conta?" ligacao="Criar conta grátis" href="/criar-conta" />
      </View>

      <SessaoTerminada
        aberto={terminouSozinha && !avisoFechado}
        aoFechar={() => setAvisoFechado(true)}
        aoGoogle={() => {
          setAvisoFechado(true);
          g.abrir();
        }}
      />
    </Ecra>
  );
}

/** EstadoSessao.dc.html: folha de baixo com o cadeado, "Entrar outra vez" e "Continuar com o Google". */
function SessaoTerminada({ aberto, aoFechar, aoGoogle }: { aberto: boolean; aoFechar: () => void; aoGoogle: () => void }) {
  const ins = useSafeAreaInsets();
  return (
    <Modal visible={aberto} transparent animationType="slide" onRequestClose={aoFechar} statusBarTranslucent>
      <View style={{ flex: 1, justifyContent: "flex-end" }}>
        <Pressable accessibilityLabel="Fechar" onPress={aoFechar} style={{ position: "absolute", inset: 0, backgroundColor: "rgba(20,20,63,0.55)" }} />
        <View accessibilityViewIsModal style={{ backgroundColor: cor.fundo, borderTopLeftRadius: 12, borderTopRightRadius: 12, paddingTop: 28, paddingHorizontal: 20, paddingBottom: Math.max(ins.bottom, 24), gap: 18 }}>
          <View style={[balao.medio, { width: 64, height: 64, alignItems: "center", justifyContent: "center", backgroundColor: cor.fundoForte }]}>
            <Lock size={32} color={cor.tinta} />
          </View>
          <View style={{ gap: 8 }}>
            <Titulo v="tituloM" style={{ fontSize: 24, lineHeight: 30 }}>
              A sua sessão terminou
            </Titulo>
            <Texto>Por segurança, saímos da sua conta. O que fez até agora está guardado.</Texto>
          </View>
          <Botao larguraTotal onPress={aoFechar}>
            Entrar outra vez
          </Botao>
          <Botao tipo="secundario" larguraTotal onPress={aoGoogle}>
            Continuar com o Google
          </Botao>
        </View>
      </View>
    </Modal>
  );
}
