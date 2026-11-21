/**
 * Peças partilhadas pelos ecrãs de cursos: capa, cartões de curso (inscrito e catálogo),
 * separadores "Os meus / Explorar", esqueleto da lista e anel de nota.
 */
import { Image } from "expo-image";
import { router } from "expo-router";
import { BookOpen, ChevronRight, Lock } from "lucide-react-native";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, View } from "react-native";
import Svg, { Circle } from "react-native-svg";
import { urlAbsoluto } from "@/api/config";
import { contextoCurso, categoriaPt, nivelEmFrase, useProgressoCursoQuery, vistoHa, type CursoVideo } from "@/dominios/cursos/api";
import { ROTA_TESTE_BASICO } from "@/dominios/cursos/testeBasico";
import { type CursoPratica, useEscolherCursoPraticaMutation } from "@/dominios/laboratorio/api";
import { Etiqueta, Osso, BarraProgresso, Texto } from "@/ui";
import { balao, cor, fonte, raio } from "@/tema";

/** Miniatura do curso. A imagem é decorativa: o título já diz o que é. */
export function Capa({ imagem, tamanho = 56 }: { imagem?: string | null; tamanho?: number }) {
  const uri = urlAbsoluto(imagem || null);
  const forma = tamanho >= 64 ? { borderTopLeftRadius: 16, borderTopRightRadius: 16, borderBottomRightRadius: 16, borderBottomLeftRadius: 0 } : balao.pequeno;
  if (!uri)
    return (
      <View style={[forma, { width: tamanho, height: tamanho, alignItems: "center", justifyContent: "center", backgroundColor: cor.fundoForte }]}>
        <BookOpen size={Math.round(tamanho * 0.4)} color={cor.azulMarca} />
      </View>
    );
  return <Image source={{ uri }} accessible={false} contentFit="cover" style={[forma, { width: tamanho, height: tamanho, backgroundColor: cor.fundoForte }]} />;
}

/** Separadores da área Cursos (Os meus / Explorar), sublinhado azul no activo. */
export function SeparadoresCursos<T extends string>({ itens, activo, aoMudar }: { itens: { valor: T; nome: string }[]; activo: T; aoMudar: (v: T) => void }) {
  return (
    <View accessibilityRole="tablist" style={{ flexDirection: "row", borderBottomWidth: 1, borderColor: cor.linha }}>
      {itens.map((i) => {
        const a = i.valor === activo;
        return (
          <Pressable
            key={i.valor}
            accessibilityRole="tab"
            accessibilityState={{ selected: a }}
            onPress={() => aoMudar(i.valor)}
            style={{ minHeight: 44, paddingHorizontal: 16, justifyContent: "center", borderBottomWidth: 3, borderColor: a ? cor.azulMarca : "transparent", marginBottom: -1 }}
          >
            <Texto forte={a} cor={a ? cor.azulMarca : cor.tintaSuave}>
              {i.nome}
            </Texto>
          </Pressable>
        );
      })}
    </View>
  );
}

/**
 * Curso em que o estudante está inscrito, com o progresso real (tela "Os meus cursos").
 * `aoSaberProgresso` deixa a lista saber o progresso para filtrar Em progresso / Concluídos.
 */
export function CartaoCursoInscrito({
  curso,
  userId,
  aoSaberProgresso,
  escondido,
}: {
  curso: CursoVideo;
  userId: string;
  aoSaberProgresso?: (courseId: string, pct: number) => void;
  escondido?: boolean;
}) {
  const { data: progresso, isLoading } = useProgressoCursoQuery({ userId, courseId: curso.courseId });
  const pct = Math.round(progresso?.overallProgress ?? 0);
  useEffect(() => {
    if (!isLoading) aoSaberProgresso?.(curso.courseId, pct);
  }, [isLoading, pct, curso.courseId, aoSaberProgresso]);
  if (escondido) return null;
  const feito = pct >= 100;
  const visto = vistoHa(progresso?.lastAccessedTimestamp);
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`${curso.title}. ${feito ? "Concluído" : `${pct}% feito`}`}
      onPress={() => router.push(`/curso/${curso.courseId}`)}
      style={({ pressed }) => [{ gap: 10, padding: 16, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, backgroundColor: pressed ? cor.fundoSuave : cor.fundo }]}
    >
      <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 8 }}>
        <Texto v="legenda" suave style={{ flex: 1 }} numberOfLines={1}>
          {contextoCurso(curso) || " "}
        </Texto>
        {visto ? (
          <Texto v="legenda" suave>
            Visto: {visto}
          </Texto>
        ) : null}
      </View>
      <Texto v="tituloXS" style={{ fontSize: 18, lineHeight: 24 }}>
        {curso.title}
      </Texto>
      {isLoading ? (
        <Osso altura={8} />
      ) : (
        <>
          <BarraProgresso valor={pct} rotulo={`Progresso em ${curso.title}`} corBarra={feito ? cor.certo : undefined} />
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <Texto v="legenda">{feito ? "Todas as aulas vistas" : pct > 0 ? "Em curso" : "Ainda não começou"}</Texto>
            <Texto v="legenda" forte numeros>
              {feito ? "Feito" : `${pct}%`}
            </Texto>
          </View>
        </>
      )}
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
        <Texto forte cor={cor.azulVivo}>
          {feito ? "Ver o curso" : pct > 0 ? "Continuar" : "Começar"}
        </Texto>
        <ChevronRight size={18} color={cor.azulVivo} />
      </View>
    </Pressable>
  );
}

/** Linha de baixo de um cartão do catálogo fechado pelo nível básico. */
function PedeNivelBasico() {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
      <Lock size={14} color={cor.tinta} />
      <Texto v="legenda" forte>
        Pede o nível básico
      </Texto>
    </View>
  );
}

/**
 * Curso em vídeo do catálogo: capa, área e nível, título, e se já está inscrito ou o plano.
 * `bloqueado`: curso de sector que ainda pede o nível básico (abre na mesma, para a pessoa o ver).
 */
export function CartaoCursoCatalogo({ curso, inscrito, bloqueado }: { curso: CursoVideo; inscrito?: boolean; bloqueado?: boolean }) {
  const acesso = curso.is_free ? "Gratuito" : curso.is_premium ? "Premium" : curso.access_level_display;
  const contexto = [categoriaPt(curso.category), nivelEmFrase(curso.level)].filter(Boolean).join(", ");
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={[curso.title, "Aulas em vídeo", contexto, inscrito ? "Inscrito" : bloqueado ? "Pede o nível básico" : acesso].filter(Boolean).join(". ")}
      onPress={() => router.push(`/curso/${curso.courseId}`)}
      style={({ pressed }) => [{ flexDirection: "row", gap: 14, padding: 14, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, backgroundColor: pressed ? cor.fundoSuave : cor.fundo }]}
    >
      <Capa imagem={curso.image} tamanho={76} />
      <View style={{ flex: 1, minWidth: 0, gap: 4 }}>
        <Texto v="legenda" suave forte style={{ fontSize: 13, lineHeight: 18 }}>
          {["Aulas em vídeo", contexto].filter(Boolean).join(", ")}
        </Texto>
        <Texto v="tituloXS">{curso.title}</Texto>
        <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
          {inscrito ? (
            <Texto v="legenda" forte cor={cor.azulVivo}>
              Inscrito
            </Texto>
          ) : bloqueado ? (
            <PedeNivelBasico />
          ) : acesso ? (
            <Etiqueta tom={curso.is_premium ? "marca" : "neutro"}>{acesso}</Etiqueta>
          ) : null}
          {curso.teacherName ? (
            <Texto v="legenda" suave>
              {curso.teacherName}
            </Texto>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}

/**
 * Curso do laboratório no catálogo: tocar escolhe-o como curso de prática e abre o trilho.
 * Se ainda pedir o nível básico, abre o teste.
 */
export function CartaoCursoPratica({ curso, actual }: { curso: CursoPratica; actual?: boolean }) {
  const [escolher, { isLoading }] = useEscolherCursoPraticaMutation();
  const [erro, setErro] = useState(false);
  const contexto = [categoriaPt(curso.category), nivelEmFrase(curso.level)].filter(Boolean).join(", ");
  const bloqueado = !!curso.requisito_basico;
  const abrir = async () => {
    if (bloqueado) return router.push(ROTA_TESTE_BASICO);
    if (actual) return router.push("/praticar");
    setErro(false);
    const r = await escolher(curso.id);
    if ("error" in r && r.error) return setErro(true);
    router.push("/praticar");
  };
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={[curso.title, "Lições de prática", contexto, bloqueado ? "Pede o nível básico" : actual ? "É o seu curso de prática" : "Praticar"].filter(Boolean).join(". ")}
      accessibilityState={{ busy: isLoading }}
      disabled={isLoading}
      onPress={() => void abrir()}
      style={({ pressed }) => [{ flexDirection: "row", gap: 14, padding: 14, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, backgroundColor: pressed ? cor.fundoSuave : cor.fundo }]}
    >
      <Capa imagem={curso.image} tamanho={76} />
      <View style={{ flex: 1, minWidth: 0, gap: 4 }}>
        <Texto v="legenda" suave forte style={{ fontSize: 13, lineHeight: 18 }}>
          {["Lições de prática", contexto].filter(Boolean).join(", ")}
        </Texto>
        <Texto v="tituloXS">{curso.title}</Texto>
        {erro ? (
          <Texto v="legenda" cor={cor.errado}>
            Não foi possível abrir o curso. Tente outra vez.
          </Texto>
        ) : bloqueado ? (
          <PedeNivelBasico />
        ) : (
          <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            {isLoading ? <ActivityIndicator size="small" color={cor.azulVivo} /> : null}
            <Texto v="legenda" forte cor={cor.azulVivo}>
              {isLoading ? "A abrir…" : actual ? "Continuar a praticar" : "Praticar"}
            </Texto>
            {isLoading ? null : <ChevronRight size={16} color={cor.azulVivo} />}
          </View>
        )}
      </View>
    </Pressable>
  );
}

export function EsqueletoCursos({ linhas = 3, rotulo = "A carregar cursos" }: { linhas?: number; rotulo?: string }) {
  return (
    <View accessible accessibilityLabel={rotulo} accessibilityState={{ busy: true }} style={{ gap: 12 }}>
      {Array.from({ length: linhas }, (_, i) => (
        <View key={i} style={{ flexDirection: "row", gap: 14, padding: 14, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md }}>
          <Osso altura={64} largura={64} />
          <View style={{ flex: 1, gap: 8 }}>
            <Osso altura={14} largura="40%" />
            <Osso altura={18} largura="85%" />
            <Osso altura={8} />
          </View>
        </View>
      ))}
    </View>
  );
}

/** Anel de percentagem (nota final, resultado do questionário). */
export function Anel({ valor, tamanho = 92, cheio, vazio, fundo, rotulo, corTexto = cor.tinta }: { valor: number; tamanho?: number; cheio: string; vazio: string; fundo: string; rotulo: string; corTexto?: string }) {
  const v = Math.max(0, Math.min(100, Math.round(valor)));
  const espessura = 9;
  const r = (tamanho - espessura) / 2;
  const c = 2 * Math.PI * r;
  return (
    <View accessible accessibilityRole="image" accessibilityLabel={rotulo} style={{ width: tamanho, height: tamanho, alignItems: "center", justifyContent: "center" }}>
      <Svg width={tamanho} height={tamanho} style={{ position: "absolute" }}>
        <Circle cx={tamanho / 2} cy={tamanho / 2} r={r + espessura / 2} fill={fundo} />
        <Circle cx={tamanho / 2} cy={tamanho / 2} r={r} stroke={vazio} strokeWidth={espessura} fill="none" />
        <Circle
          cx={tamanho / 2}
          cy={tamanho / 2}
          r={r}
          stroke={cheio}
          strokeWidth={espessura}
          fill="none"
          strokeDasharray={`${(c * v) / 100} ${c}`}
          transform={`rotate(-90 ${tamanho / 2} ${tamanho / 2})`}
        />
      </Svg>
      <Texto numeros style={{ fontFamily: fonte.numero, fontSize: 24, lineHeight: 30, color: corTexto }}>
        {v}%
      </Texto>
    </View>
  );
}
