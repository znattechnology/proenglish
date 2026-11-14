import { Tabs } from "expo-router";
import { BarraSeparadores } from "@/componentes/BarraSeparadores";

/** Os 5 destinos do estudante, como na barra de baixo da web (Início, Cursos, Praticar, Conversa, Perfil). */
export default function LayoutSeparadores() {
  return (
    <Tabs screenOptions={{ headerShown: false }} tabBar={(p) => <BarraSeparadores {...p} />}>
      <Tabs.Screen name="inicio" options={{ title: "Início" }} />
      <Tabs.Screen name="cursos" options={{ title: "Cursos" }} />
      <Tabs.Screen name="praticar" options={{ title: "Praticar" }} />
      <Tabs.Screen name="conversa" options={{ title: "Conversa" }} />
      <Tabs.Screen name="perfil" options={{ title: "Perfil" }} />
    </Tabs>
  );
}
