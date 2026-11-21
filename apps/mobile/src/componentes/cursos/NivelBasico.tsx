/**
 * O requisito dos cursos de sector (nível básico): o aviso com o caminho para o teste, usado no
 * catálogo, na página do curso, no laboratório e na primeira entrada. Quem decide é a API; aqui só
 * se mostra o que ela diz (apps/api/apps/courses/teste_basico.py).
 */
import { Lock } from "lucide-react-native";
import { View } from "react-native";
import { ROTA_TESTE_BASICO, useEstadoTesteBasicoQuery } from "@/dominios/cursos/testeBasico";
import { cor, raio } from "@/tema";
import { Botao, Texto } from "@/ui";

/** true enquanto a pessoa não tiver o nível básico (false enquanto não se sabe, para não fechar à toa). */
export function useFaltaNivelBasico() {
  const { data } = useEstadoTesteBasicoQuery();
  return data ? !data.tem_nivel_basico : false;
}

export function AvisoNivelBasico({ texto, semCursoGeral }: { texto?: string; semCursoGeral?: boolean }) {
  const { data } = useEstadoTesteBasicoQuery();
  const minutos = data?.regras.minutos ?? 20;
  return (
    <View style={{ gap: 12, padding: 16, backgroundColor: cor.realceSuave, borderRadius: raio.md }}>
      <View style={{ flexDirection: "row", gap: 10 }}>
        <Lock size={20} color={cor.tinta} style={{ marginTop: 2 }} />
        <Texto style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>
          {texto ?? `Os cursos de sector pedem, no mínimo, o nível básico de inglês. ${semCursoGeral ? "Prove-o" : "Conclua o curso geral ou prove-o"} num teste de ${minutos} minutos.`}
        </Texto>
      </View>
      <Botao tamanho="medio" larguraTotal href={ROTA_TESTE_BASICO}>
        Fazer o teste do nível básico
      </Botao>
    </View>
  );
}
