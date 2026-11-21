import { Stack } from "expo-router";
import { cor } from "@/tema";

export const unstable_settings = { anchor: "entrar" };

export default function LayoutConta() {
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: cor.fundo } }} />;
}
