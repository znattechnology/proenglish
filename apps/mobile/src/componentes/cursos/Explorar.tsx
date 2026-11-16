/**
 * Catálogo de cursos (canvas CursosMovel; web user/courses/explore/page.tsx): todos os cursos
 * publicados, em vídeo e do laboratório, com procura sem acentos e filtro por área.
 * Sem procura nem filtro, separa o curso geral dos cursos de sector (que pedem o nível básico).
 * Usado no separador Cursos e em /cursos/explorar.
 */
import { Search } from "lucide-react-native";
import { useMemo, useState } from "react";
import { ScrollView, TextInput, View } from "react-native";
import { categoriaPt, useCatalogoCursosQuery, useMeusCursosQuery, type CursoVideo } from "@/dominios/cursos/api";
import { useEstadoTesteBasicoQuery } from "@/dominios/cursos/testeBasico";
import { idCursoActivo, useCursosPraticaQuery, useProgressoPraticaQuery, type CursoPratica } from "@/dominios/laboratorio/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { Botao, EstadoErro, Pilulas, Texto } from "@/ui";
import { cor, fonte, raio } from "@/tema";
import { AvisoNivelBasico } from "./NivelBasico";
import { CartaoCursoCatalogo, CartaoCursoPratica, EsqueletoCursos } from "./Pecas";

const TODAS = "Todas";

/** Sem acentos nem maiúsculas, para a procura encontrar "inglês" escrito "ingles". */
function normal(t: string) {
  return t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

type Item = { chave: string; area?: string; deSector: boolean; texto: string } & ({ tipo: "video"; curso: CursoVideo } | { tipo: "pratica"; curso: CursoPratica });

export function useCatalogo() {
  const { utilizador } = useSessao();
  const catalogo = useCatalogoCursosQuery();
  const meus = useMeusCursosQuery(utilizador?.id ?? "", { skip: !utilizador });
  const pratica = useCursosPraticaQuery();
  const teste = useEstadoTesteBasicoQuery();
  /** Volta a ler tudo o que o catálogo mostra (puxar para actualizar). */
  const actualizar = () => Promise.allSettled([catalogo.refetch(), utilizador ? meus.refetch() : null, pratica.refetch(), teste.refetch()]);
  return { catalogo, meus, pratica, teste, actualizar };
}

export function ExplorarCursos() {
  const { catalogo, meus, pratica, teste } = useCatalogo();
  const progresso = useProgressoPraticaQuery();
  const [procura, setProcura] = useState("");
  const [area, setArea] = useState(TODAS);
  const cursoPratica = idCursoActivo(progresso.data?.active_course);
  // Sem saber ainda o estado do teste não se fecha nada: a API é que decide ao inscrever.
  const faltaBasico = teste.data ? !teste.data.tem_nivel_basico : false;

  const inscritos = useMemo(() => new Set((meus.data ?? []).map((c) => c.courseId)), [meus.data]);
  const itens = useMemo<Item[]>(() => {
    const videos: Item[] = (catalogo.data?.cursos ?? []).map((c) => ({
      tipo: "video",
      curso: c,
      chave: `v-${c.courseId}`,
      area: categoriaPt(c.category),
      deSector: !!c.de_sector,
      texto: normal(`${c.title} ${c.description ?? ""} ${categoriaPt(c.category) ?? ""}`),
    }));
    const praticas: Item[] = (pratica.data ?? []).map((c) => ({
      tipo: "pratica",
      curso: c,
      chave: `p-${c.id}`,
      area: categoriaPt(c.category),
      deSector: !!c.de_sector,
      texto: normal(`${c.title} ${c.description ?? ""} ${categoriaPt(c.category) ?? ""}`),
    }));
    return [...videos, ...praticas];
  }, [catalogo.data, pratica.data]);

  const areas = useMemo(() => {
    const unicas = Array.from(new Set(itens.map((i) => i.area).filter(Boolean) as string[]));
    return [TODAS, ...unicas.sort((a, b) => a.localeCompare(b, "pt"))];
  }, [itens]);

  const q = normal(procura.trim());
  const visiveis = itens.filter((i) => (area === TODAS || i.area === area) && (!q || i.texto.includes(q)));
  const gerais = visiveis.filter((i) => !i.deSector);
  const sectores = visiveis.filter((i) => i.deSector);
  const aFiltrar = !!q || area !== TODAS;

  const cartao = (i: Item) =>
    i.tipo === "video" ? (
      <CartaoCursoCatalogo key={i.chave} curso={i.curso} inscrito={inscritos.has(i.curso.courseId)} bloqueado={faltaBasico && i.deSector && !inscritos.has(i.curso.courseId)} />
    ) : (
      <CartaoCursoPratica key={i.chave} curso={i.curso} actual={i.curso.id === cursoPratica} />
    );

  // O catálogo de vídeo manda no estado do ecrã; se o do laboratório falhar, mostra-se o resto.
  const aCarregar = catalogo.isLoading || (pratica.isLoading && !catalogo.data?.cursos.length);
  const comErro = catalogo.isError && pratica.isError;

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

      {aCarregar ? (
        <EsqueletoCursos linhas={4} />
      ) : comErro ? (
        <EstadoErro titulo="Não conseguimos carregar os cursos" erro={catalogo.error} aoTentar={() => (void catalogo.refetch(), void pratica.refetch())} />
      ) : visiveis.length === 0 ? (
        <View style={{ gap: 12, alignItems: "flex-start" }}>
          <Texto>
            {procura.trim()
              ? `Nenhum curso com "${procura.trim()}"${area !== TODAS ? ` em ${area}` : ""}.`
              : area !== TODAS
                ? `Ainda não há cursos em ${area}.`
                : "Ainda não há cursos publicados. Volte em breve."}
          </Texto>
          {aFiltrar ? (
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
      ) : aFiltrar ? (
        <>
          <Texto v="legenda" suave accessibilityLiveRegion="polite">
            {visiveis.length} {visiveis.length === 1 ? "curso" : "cursos"}
          </Texto>
          {faltaBasico && sectores.length ? <AvisoNivelBasico /> : null}
          <View style={{ gap: 12 }}>{visiveis.map(cartao)}</View>
        </>
      ) : (
        <>
          {gerais.length ? (
            <Grupo titulo="Curso geral" texto="Inglês para o dia-a-dia e para o trabalho, do básico ao avançado. É por aqui que se chega ao nível básico.">
              {gerais.map(cartao)}
            </Grupo>
          ) : null}
          {sectores.length ? (
            <Grupo titulo="Cursos de sector" texto="O inglês da sua área: as reuniões, os relatórios e as conversas do seu trabalho.">
              {faltaBasico ? <AvisoNivelBasico semCursoGeral={!gerais.length} /> : null}
              {sectores.map(cartao)}
            </Grupo>
          ) : null}
        </>
      )}
      {catalogo.isError !== pratica.isError && !aCarregar ? (
        <Texto v="legenda" suave>
          {pratica.isError ? "Não conseguimos carregar os cursos do laboratório." : "Não conseguimos carregar os cursos em vídeo."} Puxe para baixo para tentar outra vez.
        </Texto>
      ) : null}
    </View>
  );
}

function Grupo({ titulo, texto, children }: { titulo: string; texto: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: 12, marginTop: 6 }}>
      <View style={{ gap: 2 }}>
        <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
          {titulo}
        </Texto>
        <Texto v="legenda" suave>
          {texto}
        </Texto>
      </View>
      {children}
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
