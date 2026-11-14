import type { Tabs } from "expo-router";
import type { ComponentProps } from "react";
import { BookOpen, House, Mic, Star, User } from "lucide-react-native";
import { Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Texto } from "@/ui";
import { cor, fonte } from "@/tema";

type BottomTabBarProps = Parameters<NonNullable<ComponentProps<typeof Tabs>["tabBar"]>>[0];

const ICONES = { inicio: House, cursos: BookOpen, praticar: Star, conversa: Mic, perfil: User } as const;
const CHEIOS = new Set(["inicio", "praticar", "perfil"]);

/** Barra de baixo do telemóvel (tela "Início" do canvas): 5 destinos, activo a azul-marca e a negrito. */
export function BarraSeparadores({ state, descriptors, emitter, navigateToTab }: BottomTabBarProps) {
  const ins = useSafeAreaInsets();
  return (
    <View
      accessibilityRole="tablist"
      style={{ flexDirection: "row", borderTopWidth: 1, borderColor: cor.linha, backgroundColor: cor.fundo, paddingHorizontal: 4, paddingTop: 6, paddingBottom: Math.max(ins.bottom, 10) }}
    >
      {state.routes.map((rota, i) => {
        const activo = state.index === i;
        const nome = (descriptors[rota.key].options.title ?? rota.name) as string;
        const Icone = ICONES[rota.name as keyof typeof ICONES] ?? House;
        const c = activo ? cor.azulMarca : cor.tintaSuave;
        return (
          <Pressable
            key={rota.key}
            accessibilityRole="tab"
            accessibilityState={{ selected: activo }}
            accessibilityLabel={nome}
            onPress={() => {
              const ev = emitter.emit({ type: "tabPress", target: rota.key, canPreventDefault: true });
              if (!activo && !ev.defaultPrevented) navigateToTab(rota.key);
            }}
            style={{ flex: 1, minHeight: 52, alignItems: "center", justifyContent: "center", gap: 2 }}
          >
            <Icone size={22} color={c} fill={activo && CHEIOS.has(rota.name) ? cor.azulMarca : "transparent"} strokeWidth={2} />
            <Texto v="mini" cor={c} style={activo ? { fontFamily: fonte.textoForte } : undefined}>
              {nome}
            </Texto>
          </Pressable>
        );
      })}
    </View>
  );
}
