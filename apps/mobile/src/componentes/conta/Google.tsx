/**
 * Entrar com o Google na app: expo-auth-session abre a página do Google e devolve um `id_token`
 * emitido para o client id da app (Android, iOS ou web); a API confirma-o em
 * POST /users/oauth/google/login/ {id_token} e devolve a sessão (tokens no corpo).
 *
 * Os client ids vêm de EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID, EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID e
 * EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID. Sem o desta plataforma, o botão explica que não está disponível.
 */
import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { AccessibilityInfo, Animated, Easing, Modal, Platform, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { mensagemErro } from "@/api/erros";
import { useContaGoogleMutation } from "@/dominios/conta/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { Botao, Logo, Texto, Titulo } from "@/ui";
import { cor } from "@/tema";
import { FraseComLigacao, IconeGoogle } from "./Partes";

WebBrowser.maybeCompleteAuthSession();

const IDS = {
  android: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID || undefined,
  ios: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID || undefined,
  web: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID || undefined,
};
const ID_DESTA_PLATAFORMA = Platform.select({ android: IDS.android, ios: IDS.ios, default: IDS.web });

export const SEM_GOOGLE = "A entrada com o Google ainda não está disponível nesta app. Entre com o email e a palavra-passe.";

export type EntradaGoogle = { abrir: () => void; aAbrir: boolean; erro: string | null };

/**
 * Hook de "Entrar com o Google". Use-o uma vez por ecrã e ponha `<EsperaGoogle />` no ecrã
 * (o componente `ComGoogle` faz as duas coisas).
 */
function useGoogleActivo(clientId: string, aoMostrarEspera: (v: boolean) => void): EntradaGoogle {
  const { iniciar } = useSessao();
  const [entrarGoogle] = useContaGoogleMutation();
  const [erro, setErro] = useState<string | null>(null);
  const [aAbrir, setAAbrir] = useState(false);
  const [pedido, resposta, abrirGoogle] = Google.useIdTokenAuthRequest({
    clientId,
    androidClientId: IDS.android,
    iosClientId: IDS.ios,
    webClientId: IDS.web,
    selectAccount: true,
    language: "pt-PT",
  });
  const tratado = useRef<string | null>(null);

  useEffect(() => {
    // Cancelar ou erro tratam-se no fim de abrirGoogle(); aqui só o sucesso (com o id_token já trocado).
    if (resposta?.type !== "success") return;
    const idToken = resposta.params.id_token || resposta.authentication?.idToken;
    if (!idToken || tratado.current === idToken) return; // o mesmo token só se usa uma vez
    tratado.current = idToken;
    aoMostrarEspera(true);
    entrarGoogle({ id_token: idToken })
      .unwrap()
      .then((r) => iniciar(r))
      .catch((e) => {
        aoMostrarEspera(false);
        setAAbrir(false);
        setErro(mensagemErro(e, "Não foi possível entrar com o Google. Tente outra vez."));
      });
  }, [resposta, entrarGoogle, iniciar, aoMostrarEspera]);

  return {
    aAbrir,
    erro,
    abrir: () => {
      setErro(null);
      if (!pedido) return setErro("O Google ainda está a preparar. Tente outra vez daqui a um segundo.");
      setAAbrir(true);
      abrirGoogle()
        .then((r) => {
          if (r.type === "success") return;
          setAAbrir(false);
          if (r.type === "error") setErro("O Google não devolveu a autorização. Tente outra vez.");
        })
        .catch(() => {
        setAAbrir(false);
        setErro("Não foi possível abrir o Google. Tente outra vez ou entre com o email.");
      });
    },
  };
}

/**
 * Dá aos filhos a entrada com o Google e mostra a tela "A entrar com o Google" enquanto a API
 * confirma a conta. Sem client id para esta plataforma, `abrir` só mostra a mensagem SEM_GOOGLE.
 */
export function ComGoogle({ children }: { children: (g: EntradaGoogle) => ReactNode }) {
  const [espera, setEspera] = useState(false);
  if (!ID_DESTA_PLATAFORMA) return <SemGoogle>{children}</SemGoogle>;
  return (
    <ComGoogleActivo clientId={ID_DESTA_PLATAFORMA} espera={espera} setEspera={setEspera}>
      {children}
    </ComGoogleActivo>
  );
}

function SemGoogle({ children }: { children: (g: EntradaGoogle) => ReactNode }) {
  const [erro, setErro] = useState<string | null>(null);
  return <>{children({ abrir: () => setErro(SEM_GOOGLE), aAbrir: false, erro })}</>;
}

function ComGoogleActivo({ clientId, espera, setEspera, children }: { clientId: string; espera: boolean; setEspera: (v: boolean) => void; children: (g: EntradaGoogle) => ReactNode }) {
  const g = useGoogleActivo(clientId, setEspera);
  return (
    <>
      {children(g)}
      <EsperaGoogle aberto={espera} aoVoltar={() => setEspera(false)} />
    </>
  );
}

/** Botão secundário "Entrar com o Google" (com o G a azul-marca). */
export function BotaoGoogle({ texto, g }: { texto: string; g: EntradaGoogle }) {
  return (
    <Botao tipo="secundario" larguraTotal onPress={g.abrir} carregando={g.aAbrir} icone={g.aAbrir ? undefined : <IconeGoogle />}>
      {g.aAbrir ? "A abrir o Google…" : texto}
    </Botao>
  );
}

/** Tela "A entrar com o Google" (EntrarGoogle.dc.html): três balões a pulsar, e "Está a demorar?". */
function EsperaGoogle({ aberto, aoVoltar }: { aberto: boolean; aoVoltar: () => void }) {
  const ins = useSafeAreaInsets();
  const [demora, setDemora] = useState(false);
  useEffect(() => {
    if (!aberto) return;
    const t = setTimeout(() => setDemora(true), 8000);
    return () => {
      clearTimeout(t);
      setDemora(false);
    };
  }, [aberto]);
  return (
    <Modal visible={aberto} animationType="fade" onRequestClose={aoVoltar} statusBarTranslucent>
      <View style={{ flex: 1, backgroundColor: cor.fundo, paddingTop: ins.top + 24, paddingBottom: Math.max(ins.bottom, 24), paddingHorizontal: 24 }}>
        <Logo altura={40} />
        <View accessibilityRole="progressbar" accessibilityLiveRegion="polite" style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: 24 }}>
          <Baloes />
          <View style={{ gap: 8, maxWidth: 280 }}>
            <Titulo v="tituloM" centro style={{ fontSize: 24, lineHeight: 30 }}>
              A entrar com o Google
            </Titulo>
            <Texto suave centro>
              Estamos a confirmar a sua conta. Demora uns segundos.
            </Texto>
          </View>
        </View>
        {demora ? <FraseComLigacao centro frase="Está a demorar?" ligacao="Voltar à entrada" onPress={aoVoltar} /> : <View style={{ height: 44 }} />}
      </View>
    </Modal>
  );
}

function Baloes() {
  const cores = [cor.azulMarca, cor.azulVivo, cor.fundoForte];
  const [valores] = useState(() => cores.map(() => new Animated.Value(0)));
  useEffect(() => {
    const laco = Animated.loop(
      Animated.stagger(
        180,
        valores.map((v) =>
          Animated.sequence([
            Animated.timing(v, { toValue: 1, duration: 320, easing: Easing.out(Easing.quad), useNativeDriver: true }),
            Animated.timing(v, { toValue: 0, duration: 320, easing: Easing.in(Easing.quad), useNativeDriver: true }),
          ])
        )
      )
    );
    AccessibilityInfo.isReduceMotionEnabled().then((reduzir) => {
      if (!reduzir) laco.start();
    });
    return () => laco.stop();
  }, [valores]);
  return (
    <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 10, height: 32 }}>
      {valores.map((v, i) => (
        <Animated.View
          key={i}
          style={{
            width: 20,
            height: 20,
            backgroundColor: cores[i],
            borderTopLeftRadius: 8,
            borderTopRightRadius: 8,
            borderBottomRightRadius: 8,
            borderBottomLeftRadius: 0,
            transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [0, -10] }) }],
          }}
        />
      ))}
    </View>
  );
}
