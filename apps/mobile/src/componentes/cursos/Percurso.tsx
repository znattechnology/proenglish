/**
 * Percurso do curso (web components/pe/curso/Percurso.tsx): os passos por baixo de cada aula
 * (questionário, laboratório e conversas com o tutor) e o bloco "A seguir" do fim de cada actividade.
 * O servidor decide a ordem e o que está feito; aqui só se mostra.
 */
import { router } from "expo-router";
import { Check, Dumbbell, ListChecks, Mic, Play } from "lucide-react-native";
import { Pressable, View, type StyleProp, type ViewStyle } from "react-native";
import { accaoDoPasso, nomeDoPasso, rotaDoPasso, type Passo, type ProximoPasso, type TipoPasso } from "@/dominios/cursos/api";
import { Botao, Texto } from "@/ui";
import { cor, raio } from "@/tema";

const ICONE: Record<TipoPasso, typeof Mic> = { aula: Play, questionario: ListChecks, pratica: Dumbbell, conversa: Mic };

export function duracaoDoPasso(p: Pick<Passo, "minutos">) {
  return p.minutos ? `${p.minutos} min` : null;
}

/** Os passos de uma aula além do vídeo, recuados por baixo da linha da aula. */
export function PassosDaAula({ courseId, passos }: { courseId: string; passos: Passo[] }) {
  const outros = passos.filter((p) => p.tipo !== "aula");
  if (!outros.length) return null;
  return (
    <View style={{ marginLeft: 13, paddingLeft: 14, borderLeftWidth: 2, borderColor: cor.fundoForte }}>
      {outros.map((p) => {
        const Icone = ICONE[p.tipo];
        const feito = p.estado === "feito";
        const actual = p.estado === "actual";
        const nome = nomeDoPasso(p);
        const duracao = duracaoDoPasso(p);
        return (
          <Pressable
            key={p.chave}
            accessibilityRole="link"
            accessibilityLabel={`${nome}${p.tipo === "questionario" ? "" : `: ${p.titulo}`}${duracao ? `, ${duracao}` : ""}${feito ? ", feito" : actual ? ", a seguir" : ""}`}
            onPress={() => router.push(rotaDoPasso(courseId, p))}
            style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 10, minHeight: 48, paddingVertical: 4, borderBottomWidth: 1, borderColor: cor.fundoForte, backgroundColor: pressed ? cor.fundoSuave : undefined })}
          >
            <View style={{ width: 24, height: 24, borderRadius: 12, alignItems: "center", justifyContent: "center", backgroundColor: feito ? cor.certoSuave : actual ? cor.realce : cor.fundoForte }}>
              {feito ? <Check size={13} strokeWidth={3} color={cor.certo} /> : <Icone size={13} color={actual ? cor.tinta : cor.tintaSuave} />}
            </View>
            <Texto numberOfLines={2} style={{ flex: 1, fontSize: 14, lineHeight: 20 }}>
              <Texto forte cor={actual ? cor.azulMarca : cor.tinta} style={{ fontSize: 14, lineHeight: 20 }}>
                {nome}
              </Texto>
              {p.tipo === "questionario" ? "" : `: ${p.titulo}`}
            </Texto>
            {duracao ? (
              <Texto v="legenda" suave numeros>
                {duracao}
              </Texto>
            ) : null}
          </Pressable>
        );
      })}
    </View>
  );
}

/** "A seguir": o passo seguinte do percurso, no fim de uma aula, de uma lição ou de uma conversa. */
export function ASeguir({ proximo, substituir, style }: { proximo: ProximoPasso; substituir?: boolean; style?: StyleProp<ViewStyle> }) {
  const p = proximo.passo;
  const duracao = duracaoDoPasso(p);
  return (
    <View style={[{ gap: 12, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, padding: 16 }, style]}>
      <View style={{ gap: 2 }}>
        <Texto v="legenda" suave>
          A seguir em {proximo.curso.titulo}, {p.unidade}
        </Texto>
        <Texto v="tituloXS" accessibilityRole="header">
          {p.tipo === "questionario" ? "Questionário" : p.titulo}
        </Texto>
        <Texto v="legenda" suave numeros>
          {nomeDoPasso(p)}
          {duracao ? `, cerca de ${duracao}` : ""}
        </Texto>
      </View>
      <Botao tipo="realce" tamanho="medio" larguraTotal substituir={substituir} href={rotaDoPasso(proximo.curso.id, p)}>
        {accaoDoPasso(p)}
      </Botao>
    </View>
  );
}
