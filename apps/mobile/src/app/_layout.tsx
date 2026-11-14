import { AtkinsonHyperlegibleNext_400Regular, AtkinsonHyperlegibleNext_400Regular_Italic, AtkinsonHyperlegibleNext_600SemiBold } from "@expo-google-fonts/atkinson-hyperlegible-next";
import { Montserrat_300Light_Italic, Montserrat_600SemiBold, Montserrat_700Bold } from "@expo-google-fonts/montserrat";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { Provider } from "react-redux";
import { store } from "@/lib/store";
import { SessaoProvider, useSessao } from "@/sessao/ContextoSessao";
import { cor } from "@/tema";

SplashScreen.preventAutoHideAsync();

export default function Raiz() {
  const [letras, erroLetras] = useFonts({
    AtkinsonHyperlegibleNext_400Regular,
    AtkinsonHyperlegibleNext_400Regular_Italic,
    AtkinsonHyperlegibleNext_600SemiBold,
    Montserrat_300Light_Italic,
    Montserrat_600SemiBold,
    Montserrat_700Bold,
  });
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: cor.fundo }}>
      <SafeAreaProvider>
        <Provider store={store}>
          <SessaoProvider>
            <StatusBar style="dark" />
            {letras || erroLetras ? <Navegacao /> : null}
          </SessaoProvider>
        </Provider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

/** Com sessão: a área do estudante (app). Sem sessão: entrar, criar conta, recuperar palavra-passe. */
function Navegacao() {
  const { estado } = useSessao();
  useEffect(() => {
    if (estado !== "a-carregar") SplashScreen.hideAsync();
  }, [estado]);
  if (estado === "a-carregar") return null;
  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: cor.fundo } }}>
      <Stack.Protected guard={estado === "com-sessao"}>
        <Stack.Screen name="(app)" />
      </Stack.Protected>
      <Stack.Protected guard={estado === "sem-sessao"}>
        <Stack.Screen name="(conta)" />
      </Stack.Protected>
    </Stack>
  );
}
