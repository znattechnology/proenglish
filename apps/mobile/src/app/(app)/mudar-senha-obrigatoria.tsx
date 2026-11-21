/**
 * Mudança obrigatória da palavra-passe (deve_mudar_senha). Normalmente aparece sozinha através de
 * <ObrigarMudarSenha> no layout; esta rota serve para abrir o ecrã directamente.
 */
import { Redirect, Stack } from "expo-router";
import { EcraMudarSenhaObrigatoria } from "@/componentes/conta/ObrigarMudarSenha";
import { useSessao } from "@/sessao/ContextoSessao";

export default function MudarSenhaObrigatoria() {
  const { utilizador } = useSessao();
  if (utilizador && !utilizador.deve_mudar_senha) return <Redirect href="/inicio" />;
  return (
    <>
      <Stack.Screen options={{ gestureEnabled: false }} />
      {/* Depois de mudar, o perfil deixa de pedir a mudança e o Redirect leva ao início. */}
      <EcraMudarSenhaObrigatoria />
    </>
  );
}
