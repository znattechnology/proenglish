/**
 * Separador Cursos (canvas MeusCursos, CursosMovel e EstadoSemCursos; web user/courses/page.tsx e
 * user/courses/explore/page.tsx): "Os meus" com Em progresso / Concluídos, e "Explorar" (catálogo).
 */
import { router } from "expo-router";
import { BookOpen } from "lucide-react-native";
import { useCallback, useMemo, useState } from "react";
import { Pressable, View } from "react-native";
import { ExplorarCursos, useCatalogo } from "@/componentes/cursos/Explorar";
import { CartaoCursoInscrito, EsqueletoCursos, SeparadoresCursos } from "@/componentes/cursos/Pecas";
import { categoriaPt, useCatalogoCursosQuery, useMeusCursosQuery } from "@/dominios/cursos/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { Botao, Ecra, EstadoErro, Pilulas, Texto, Titulo } from "@/ui";
import { cor, raio } from "@/tema";

type Vista = "meus" | "explorar";
type Estado = "progresso" | "concluidos";

export default function SeparadorCursos() {
  const [vista, setVista] = useState<Vista>("meus");
  const { catalogo, meus } = useCatalogo();
  const [aActualizar, setAActualizar] = useState(false);

  const actualizar = async () => {
    setAActualizar(true);
    await Promise.allSettled([meus.refetch(), catalogo.refetch()]);
    setAActualizar(false);
  };

  return (
    <Ecra
      cabecalho={
        <View style={{ paddingHorizontal: 20, paddingTop: 14, gap: 6 }}>
          <Titulo style={{ fontSize: 24, lineHeight: 30 }}>Cursos</Titulo>
          <SeparadoresCursos
            itens={[
              { valor: "meus", nome: "Os meus" },
              { valor: "explorar", nome: "Explorar" },
            ]}
            activo={vista}
            aoMudar={setVista}
          />
        </View>
      }
      aoActualizar={actualizar}
      aActualizar={aActualizar}
    >
      {vista === "meus" ? <OsMeus aoExplorar={() => setVista("explorar")} /> : <ExplorarCursos />}
    </Ecra>
  );
}

function OsMeus({ aoExplorar }: { aoExplorar: () => void }) {
  const { utilizador } = useSessao();
  const userId = utilizador?.id ?? "";
  const { data: cursos, isLoading, isError, error, refetch } = useMeusCursosQuery(userId, { skip: !userId });
  const [estado, setEstado] = useState<Estado>("progresso");
  const [progressos, setProgressos] = useState<Record<string, number>>({});

  const aoSaberProgresso = useCallback((id: string, pct: number) => {
    setProgressos((p) => (p[id] === pct ? p : { ...p, [id]: pct }));
  }, []);

  const contagem = useMemo(() => {
    const valores = (cursos ?? []).map((c) => progressos[c.courseId]).filter((v) => v !== undefined);
    const concluidos = valores.filter((v) => v >= 100).length;
    return { concluidos, emProgresso: (cursos?.length ?? 0) - concluidos };
  }, [cursos, progressos]);

  if (isLoading || (!cursos && !isError)) return <EsqueletoCursos />;
  if (isError) return <EstadoErro titulo="Não conseguimos carregar os seus cursos" erro={error} aoTentar={refetch} />;
  if (!cursos?.length) return <SemCursos aoExplorar={aoExplorar} />;

  return (
    <View style={{ gap: 14 }}>
      <Pilulas
        rotulo="Mostrar cursos"
        opcoes={[
          { valor: "progresso", nome: `Em progresso (${contagem.emProgresso})` },
          { valor: "concluidos", nome: `Concluídos (${contagem.concluidos})` },
        ]}
        valor={estado}
        aoMudar={setEstado}
      />
      {cursos.map((c) => {
        const pct = progressos[c.courseId];
        const concluido = pct !== undefined && pct >= 100;
        const escondido = pct !== undefined && (estado === "concluidos" ? !concluido : concluido);
        return <CartaoCursoInscrito key={c.courseId} curso={c} userId={userId} aoSaberProgresso={aoSaberProgresso} escondido={escondido} />;
      })}
      {estado === "concluidos" && contagem.concluidos === 0 ? (
        <Texto suave>Ainda não concluiu nenhum curso. Quando terminar um, o certificado aparece em Certificados.</Texto>
      ) : null}
      {estado === "concluidos" && contagem.concluidos > 0 ? (
        <Botao tipo="ligacao" href="/certificados">
          Ver os certificados
        </Botao>
      ) : null}
    </View>
  );
}

/** Estado vazio: convida a escolher o primeiro curso e sugere dois. */
function SemCursos({ aoExplorar }: { aoExplorar: () => void }) {
  const { data } = useCatalogoCursosQuery();
  const sugestoes = data?.cursos.slice(0, 2) ?? [];
  return (
    <View style={{ gap: 20 }}>
      <View style={{ gap: 18, alignItems: "flex-start" }}>
        <View style={{ width: 80, height: 80, alignItems: "center", justifyContent: "center", backgroundColor: cor.azulMarca, borderTopLeftRadius: 26, borderTopRightRadius: 26, borderBottomRightRadius: 26, borderBottomLeftRadius: 0 }}>
          <BookOpen size={36} color={cor.sobreMarca} />
        </View>
        <View style={{ gap: 8 }}>
          <Texto v="tituloM" accessibilityRole="header" style={{ fontSize: 24, lineHeight: 30 }}>
            Ainda não começou nenhum curso
          </Texto>
          <Texto suave>Escolha um curso da sua área. A primeira aula leva cerca de 8 minutos.</Texto>
        </View>
        <Botao larguraTotal onPress={aoExplorar}>
          Explorar cursos
        </Botao>
      </View>
      {sugestoes.length ? (
        <View style={{ gap: 8 }}>
          <Texto v="tituloXS" accessibilityRole="header">
            Para começar
          </Texto>
          {sugestoes.map((c) => (
            <Pressable
              key={c.courseId}
              accessibilityRole="link"
              onPress={() => router.push(`/curso/${c.courseId}`)}
              style={({ pressed }) => [{ gap: 4, paddingVertical: 14, paddingHorizontal: 16, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, backgroundColor: pressed ? cor.fundoSuave : cor.fundo }]}
            >
              {categoriaPt(c.category) ? (
                <Texto v="legenda" suave>
                  {categoriaPt(c.category)}
                </Texto>
              ) : null}
              <Texto forte>{c.title}</Texto>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

