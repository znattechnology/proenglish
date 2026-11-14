/**
 * Catálogo de cursos (canvas CursosMovel; web user/courses/explore/page.tsx): procura sem acentos,
 * filtro por área e a lista. Usado no separador Cursos ("Explorar") e em /cursos/explorar.
 */
import { Search } from "lucide-react-native";
import { useMemo, useState } from "react";
import { ScrollView, TextInput, View } from "react-native";
import { categoriaPt, useCatalogoCursosQuery, useMeusCursosQuery } from "@/dominios/cursos/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { Botao, EstadoErro, Pilulas, Texto } from "@/ui";
import { cor, fonte, raio } from "@/tema";
import { CartaoCursoCatalogo, EsqueletoCursos } from "./Pecas";

const TODAS = "Todas";

/** Sem acentos nem maiúsculas, para a procura encontrar "inglês" escrito "ingles". */
function normal(t: string) {
  return t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function useCatalogo() {
  const { utilizador } = useSessao();
  const catalogo = useCatalogoCursosQuery();
  const meus = useMeusCursosQuery(utilizador?.id ?? "", { skip: !utilizador });
  return { catalogo, meus };
}

export function ExplorarCursos() {
  const { catalogo, meus } = useCatalogo();
  const { data, isLoading, isError, error, refetch } = catalogo;
  const [procura, setProcura] = useState("");
  const [area, setArea] = useState(TODAS);

  const inscritos = useMemo(() => new Set((meus.data ?? []).map((c) => c.courseId)), [meus.data]);
  const areas = useMemo(() => {
    const unicas = Array.from(new Set((data?.cursos ?? []).map((c) => categoriaPt(c.category)).filter(Boolean) as string[]));
    return [TODAS, ...unicas.sort((a, b) => a.localeCompare(b, "pt"))];
  }, [data]);

  const visiveis = useMemo(() => {
    const q = normal(procura.trim());
    return (data?.cursos ?? []).filter((c) => {
      if (area !== TODAS && categoriaPt(c.category) !== area) return false;
      if (!q) return true;
      return normal(`${c.title} ${c.description ?? ""} ${categoriaPt(c.category) ?? ""}`).includes(q);
    });
  }, [data, procura, area]);

  return (
    <View style={{ gap: 14 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, height: 48, paddingHorizontal: 12, borderWidth: 1.5, borderColor: cor.linhaForte, borderRadius: raio.sm }}>
        <Search size={18} color={cor.tintaSuave} />
        <TextInput
          accessibilityLabel="Procurar um curso"
          value={procura}
          onChangeText={setProcura}
          placeholder="Procurar: reuniões, emails, atendimento"
          placeholderTextColor={cor.tintaSuave}
          returnKeyType="search"
          clearButtonMode="while-editing"
          style={{ flex: 1, height: "100%", fontFamily: fonte.texto, fontSize: 16, color: cor.tinta }}
        />
      </View>
      {areas.length > 2 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -20 }} contentContainerStyle={{ paddingHorizontal: 20 }}>
          <View style={{ flexDirection: "row" }}>
            <PilulasLinha opcoes={areas} valor={area} aoMudar={setArea} />
          </View>
        </ScrollView>
      ) : null}

      {isLoading ? (
        <EsqueletoCursos linhas={4} />
      ) : isError ? (
        <EstadoErro titulo="Não conseguimos carregar os cursos" erro={error} aoTentar={refetch} />
      ) : visiveis.length === 0 ? (
        <View style={{ gap: 12, alignItems: "flex-start" }}>
          <Texto>
            {procura.trim()
              ? `Nenhum curso com "${procura.trim()}"${area !== TODAS ? ` em ${area}` : ""}.`
              : area !== TODAS
                ? `Ainda não há cursos em ${area}.`
                : "Ainda não há cursos publicados. Volte em breve."}
          </Texto>
          {procura.trim() || area !== TODAS ? (
            <Botao
              tipo="secundario"
              tamanho="pequeno"
              onPress={() => {
                setProcura("");
                setArea(TODAS);
              }}
            >
              Ver todos os cursos
            </Botao>
          ) : null}
        </View>
      ) : (
        <>
          <Texto v="legenda" suave accessibilityLiveRegion="polite">
            {visiveis.length} {visiveis.length === 1 ? "curso" : "cursos"}
          </Texto>
          <View style={{ gap: 12 }}>
            {visiveis.map((c) => (
              <CartaoCursoCatalogo key={c.courseId} curso={c} inscrito={inscritos.has(c.courseId)} />
            ))}
          </View>
        </>
      )}
    </View>
  );
}

/** As pílulas do sistema numa só linha (deslocam-se na horizontal). */
function PilulasLinha({ opcoes, valor, aoMudar }: { opcoes: string[]; valor: string; aoMudar: (v: string) => void }) {
  return (
    <View style={{ flexWrap: "nowrap" }}>
      <Pilulas rotulo="Área profissional" opcoes={opcoes.map((o) => ({ valor: o, nome: o }))} valor={valor} aoMudar={aoMudar} />
    </View>
  );
}
