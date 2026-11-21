/**
 * Estatísticas (canvas: Estatisticas; web: user/analytics/page.tsx).
 */
import { ChevronRight } from "lucide-react-native";
import { useState } from "react";
import { Pressable, View } from "react-native";
import { router } from "expo-router";
import { Segmentos } from "@/componentes/perfil/Campos";
import { duracao, useEstatisticasPeriodoQuery, type Estatisticas, type PeriodoEstatisticas } from "@/dominios/estatisticas/api";
import { dataPt } from "@/dominios/subscricao/api";
import { cor, raio } from "@/tema";
import { ACarregar, BarraProgresso, Botao, Cabecalho, Ecra, EstadoErro, Texto } from "@/ui";

const PERIODOS: { valor: PeriodoEstatisticas; nome: string }[] = [
  { valor: "7", nome: "7 dias" },
  { valor: "30", nome: "30 dias" },
  { valor: "tudo", nome: "Tudo" },
];
const CRITERIOS: Record<string, string> = { fluencia: "Fluência", pronuncia: "Pronúncia", gramatica: "Gramática", vocabulario: "Vocabulário" };

export default function EcraEstatisticas() {
  const [periodo, setPeriodo] = useState<PeriodoEstatisticas>("7");
  const { data, isFetching, isError, error, refetch } = useEstatisticasPeriodoQuery(periodo);

  return (
    <Ecra cabecalho={<Cabecalho titulo="Estatísticas" />} aoActualizar={() => refetch()} aActualizar={isFetching && !!data} style={{ gap: 20 }}>
      <Segmentos rotulo="Período" opcoes={PERIODOS} valor={periodo} aoMudar={setPeriodo} />
      {isError && !data ? (
        <EstadoErro erro={error} titulo="Não conseguimos calcular as estatísticas" aoTentar={() => refetch()} />
      ) : !data ? (
        <ACarregar linhas={3} altura={120} rotulo="A carregar as estatísticas" />
      ) : (
        <View style={{ gap: 24, opacity: isFetching ? 0.6 : 1 }} accessibilityState={{ busy: isFetching }}>
          <Conteudo e={data} tudo={periodo === "tudo"} />
        </View>
      )}
    </Ecra>
  );
}

function comparacao(variacao: number | null, tudo: boolean) {
  if (variacao === null || tudo) return null;
  if (variacao === 0) return "igual ao período anterior";
  return `${variacao > 0 ? "mais" : "menos"} ${Math.abs(variacao)} que no período anterior`;
}

function Titulo2({ children }: { children: string }) {
  return (
    <Texto accessibilityRole="header" style={{ fontFamily: "Montserrat_600SemiBold", fontSize: 18, lineHeight: 24 }}>
      {children}
    </Texto>
  );
}

function Conteudo({ e, tudo }: { e: Estatisticas; tudo: boolean }) {
  const numeros = [
    { nome: "Tempo de estudo", valor: duracao(e.tempo_estudo.minutos), nota: `${e.dias_meta_cumprida} de ${e.dias} dias com a meta cumprida` },
    { nome: "Lições concluídas", valor: String(e.licoes_concluidas.total), nota: comparacao(e.licoes_concluidas.variacao, tudo) ?? "lições do laboratório" },
    { nome: "Dias seguidos", valor: String(e.sequencia.atual), nota: `o seu recorde é ${e.sequencia.maior}` },
    {
      nome: "Respostas certas",
      valor: e.respostas.percentagem === null ? "–" : `${e.respostas.percentagem}%`,
      nota: e.respostas.total ? `${e.respostas.certas} de ${e.respostas.total} perguntas` : "ainda sem respostas neste período",
    },
  ];
  const tipos = e.por_tipo_exercicio.filter((t) => t.total > 0).sort((a, b) => (b.percentagem ?? 0) - (a.percentagem ?? 0));
  const conv = e.conversacao;
  const criterios = Object.entries(conv.criterios ?? {}).filter(([, v]) => v !== null) as [string, number][];

  return (
    <>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
        {numeros.map((n) => (
          <View
            key={n.nome}
            accessible
            accessibilityLabel={`${n.nome}: ${n.valor}. ${n.nota}`}
            style={{ flexBasis: "47%", flexGrow: 1, backgroundColor: cor.fundoSuave, borderRadius: raio.md, paddingVertical: 14, paddingHorizontal: 16 }}
          >
            <Texto v="legenda" suave>
              {n.nome}
            </Texto>
            <Texto v="tituloM" numeros style={{ fontSize: 24, lineHeight: 32 }}>
              {n.valor}
            </Texto>
            <Texto v="mini" suave style={{ fontSize: 13, lineHeight: 18 }}>
              {n.nota}
            </Texto>
          </View>
        ))}
      </View>

      <View style={{ gap: 12 }}>
        <Titulo2>Minutos de estudo por dia</Titulo2>
        {e.minutos_por_dia.some((d) => d.minutos > 0) ? (
          <MinutosPorDia dias={e.minutos_por_dia} meta={e.meta_diaria_minutos} />
        ) : (
          <Texto suave>Ainda não estudou neste período.</Texto>
        )}
        <Texto v="legenda" suave>
          {duracao(e.tempo_estudo.por_tipo.licoes)} no laboratório, {duracao(e.tempo_estudo.por_tipo.videos)} a ver aulas e {duracao(e.tempo_estudo.por_tipo.conversacao)} a conversar com o tutor.
        </Texto>
        <Botao tipo="ligacao" tamanho="pequeno" href="/definicoes">
          Mudar a meta diária
        </Botao>
      </View>

      <View style={{ gap: 10 }}>
        <Titulo2>Respostas certas por tipo</Titulo2>
        {tipos.length ? (
          tipos.map((t) => (
            <View key={t.tipo} style={{ gap: 4 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 12 }}>
                <Texto v="legenda" style={{ flex: 1, fontSize: 15, lineHeight: 22 }} numberOfLines={1}>
                  {t.rotulo}
                </Texto>
                <Texto v="rotulo" numeros>
                  {t.percentagem}%
                </Texto>
              </View>
              <BarraProgresso valor={t.percentagem ?? 0} rotulo={`${t.rotulo}: ${t.certas} de ${t.total} certas`} altura={10} />
            </View>
          ))
        ) : (
          <Texto suave>Faça lições no laboratório para ver aqui onde acerta mais.</Texto>
        )}
      </View>

      <View style={{ gap: 12 }}>
        <Titulo2>Conversa com o tutor</Titulo2>
        {conv.sessoes ? (
          <>
            <View style={{ flexDirection: "row", alignItems: "baseline", gap: 6 }}>
              <Texto v="tituloXL" numeros>
                {conv.pontuacao_media ?? "–"}
              </Texto>
              <Texto suave>de 100, em média</Texto>
            </View>
            <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
              {conv.sessoes} {conv.sessoes === 1 ? "conversa" : "conversas"}, {duracao(conv.minutos)} a falar. Melhor nota: {conv.melhor_pontuacao}.
            </Texto>
            {criterios.map(([k, v]) => (
              <View key={k} style={{ gap: 4 }}>
                <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <Texto v="legenda" style={{ fontSize: 15 }}>
                    {CRITERIOS[k] ?? k}
                  </Texto>
                  <Texto v="rotulo" numeros>
                    {v}
                  </Texto>
                </View>
                <BarraProgresso valor={v} rotulo={`${CRITERIOS[k] ?? k}: ${v} de 100`} />
              </View>
            ))}
            {conv.ultima_sessao?.resumo ? (
              <View style={{ backgroundColor: cor.fundoSuave, borderRadius: raio.md, padding: 16, gap: 4 }}>
                <Texto v="legenda" suave>
                  Última conversa, {dataPt(conv.ultima_sessao.data, "diaMes")}
                </Texto>
                <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
                  {conv.ultima_sessao.resumo}
                </Texto>
              </View>
            ) : null}
          </>
        ) : (
          <>
            <Texto suave>Ainda não conversou com o tutor neste período.</Texto>
            <Botao tipo="secundario" tamanho="pequeno" href="/conversa" style={{ alignSelf: "flex-start" }}>
              Conversar com o tutor
            </Botao>
          </>
        )}
      </View>

      <View style={{ gap: 10 }}>
        <Ligacao titulo="Ver o progresso na conversa" href="/conversa/progresso" />
        <Ligacao titulo="Ver as notas dos cursos" href="/notas" />
      </View>
    </>
  );
}

function Ligacao({ titulo, href }: { titulo: string; href: string }) {
  return (
    <Pressable
      accessibilityRole="link"
      onPress={() => router.push(href)}
      style={({ pressed }) => ({
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        minHeight: 56,
        paddingHorizontal: 16,
        borderWidth: 1,
        borderColor: cor.linha,
        borderRadius: raio.md,
        backgroundColor: pressed ? cor.fundoSuave : cor.fundo,
      })}
    >
      <Texto forte>{titulo}</Texto>
      <ChevronRight size={20} color={cor.tintaSuave} />
    </Pressable>
  );
}

/** Barras de minutos por dia com a linha tracejada da meta (a amarelo, como no canvas). */
function MinutosPorDia({ dias, meta }: { dias: Estatisticas["minutos_por_dia"]; meta: number }) {
  const [activo, setActivo] = useState<number | null>(null);
  const altura = 150;
  const maximo = Math.max(meta * 1.25, ...dias.map((d) => d.minutos), 1);
  const yMeta = (meta / maximo) * altura;
  const muitos = dias.length > 14;
  const cumpridos = dias.filter((d) => d.minutos >= meta).length;
  const sel = activo !== null ? dias[activo] : null;
  return (
    <View style={{ gap: 6 }}>
      <Texto v="mini" suave style={{ minHeight: 18, fontSize: 13 }} accessibilityLiveRegion="polite">
        {sel ? `${dataPt(sel.data, "diaMes")}: ${sel.minutos} min${sel.minutos >= meta ? ", meta cumprida" : ""}` : `${cumpridos} de ${dias.length} dias com a meta de ${meta} min cumprida. Toque numa barra.`}
      </Texto>
      <View style={{ height: altura, flexDirection: "row", alignItems: "flex-end", gap: muitos ? 2 : 10, borderBottomWidth: 1, borderColor: cor.linha }}>
        <View pointerEvents="none" style={{ position: "absolute", left: 0, right: 0, bottom: yMeta, borderTopWidth: 2, borderStyle: "dashed", borderColor: cor.realce }} />
        <View pointerEvents="none" style={{ position: "absolute", right: 0, bottom: yMeta + 4, backgroundColor: cor.fundo, paddingLeft: 4 }}>
          <Texto v="mini" suave>
            meta {meta}
          </Texto>
        </View>
        {dias.map((d, i) => {
          const h = d.minutos ? Math.max(3, (d.minutos / maximo) * altura) : 3;
          return (
            <Pressable
              key={d.data}
              accessibilityRole="button"
              accessibilityLabel={`${dataPt(d.data, "diaMes")}: ${d.minutos} minutos${d.minutos >= meta ? ", meta cumprida" : ""}`}
              onPress={() => setActivo(activo === i ? null : i)}
              style={{ flex: 1, height: "100%", justifyContent: "flex-end" }}
            >
              <View
                style={{
                  height: h,
                  borderTopLeftRadius: muitos ? 2 : 6,
                  borderTopRightRadius: muitos ? 2 : 6,
                  backgroundColor: d.minutos === 0 ? cor.fundoForte : d.minutos >= meta ? cor.azulMarca : cor.azulVivo,
                  opacity: activo !== null && activo !== i ? 0.5 : 1,
                }}
              />
            </Pressable>
          );
        })}
      </View>
      {muitos ? (
        <View style={{ flexDirection: "row", justifyContent: "space-between" }} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <Texto v="mini" suave>
            {dataPt(dias[0].data, "curta")}
          </Texto>
          <Texto v="mini" suave>
            {dataPt(dias[dias.length - 1].data, "curta")}
          </Texto>
        </View>
      ) : (
        <View style={{ flexDirection: "row", gap: 10 }} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          {dias.map((d) => (
            <Texto key={d.data} v="mini" suave centro numberOfLines={1} style={{ flex: 1 }}>
              {d.dia_semana}
            </Texto>
          ))}
        </View>
      )}
    </View>
  );
}
