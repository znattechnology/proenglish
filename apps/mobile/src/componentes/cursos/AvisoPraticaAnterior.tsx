/**
 * «Pratique primeiro» (web components/pe/curso/AvisoPraticaAnterior.tsx): o laboratório da aula
 * anterior ainda está por fazer. Não bloqueia a aula; «Continuar esta aula» fecha o aviso nesta aula.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Dumbbell } from "lucide-react-native";
import { useEffect, useState } from "react";
import { View } from "react-native";
import { chaveFechado, type PraticaAnterior } from "@/dominios/cursos/praticaAnterior";
import { Botao, Texto } from "@/ui";
import { balao, cor } from "@/tema";

export function AvisoPraticaAnterior({ aulaId, pratica }: { aulaId: string; pratica: PraticaAnterior }) {
  const chave = chaveFechado(aulaId, pratica.licao_id);
  // Escondido até ler o armazenamento, para não piscar num aviso já fechado; sem armazenamento, aparece.
  const [fechado, setFechado] = useState<boolean | null>(null);
  useEffect(() => {
    let vivo = true;
    AsyncStorage.getItem(chave)
      .then((v) => vivo && setFechado(v === "1"))
      .catch(() => vivo && setFechado(false));
    return () => {
      vivo = false;
    };
  }, [chave]);
  if (fechado !== false) return null;

  const continuar = () => {
    setFechado(true);
    AsyncStorage.setItem(chave, "1").catch(() => {});
  };

  return (
    <View
      accessibilityRole="summary"
      style={[balao.medio, { gap: 12, padding: 16, borderWidth: 2, borderColor: cor.realce, backgroundColor: cor.realceSuave }]}
    >
      <View style={{ flexDirection: "row", gap: 12 }}>
        <View style={{ width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center", backgroundColor: cor.azulMarca }}>
          <Dumbbell size={20} color={cor.realce} />
        </View>
        <View style={{ flex: 1, gap: 4 }}>
          <Texto v="tituloXS" accessibilityRole="header">
            Ainda não praticou a aula anterior
          </Texto>
          <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
            O laboratório de «{pratica.aula_titulo}» está por fazer. Recomendamos que pratique primeiro: é a praticar que o que aprendeu fica
            consolidado{pratica.minutos ? ` (cerca de ${pratica.minutos} minutos)` : ""}.
          </Texto>
        </View>
      </View>
      <Botao tamanho="medio" href={`/licao/${pratica.licao_id}`}>
        Praticar a aula anterior
      </Botao>
      <Botao tipo="secundario" tamanho="medio" onPress={continuar}>
        Continuar esta aula
      </Botao>
    </View>
  );
}
