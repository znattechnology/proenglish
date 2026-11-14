/**
 * Progresso a falar (tela ProgressoFala do canvas).
 * Web: apps/web/app/(estudante)/user/laboratory/speaking/progress/page.tsx + components/pe/fala/Fala.tsx (ProgressoDaFala).
 * Conversas com o tutor (/practice/conversa/progresso/) e minutos e ritmo de fala (/student/fala/progresso/).
 */
import { router } from "expo-router";
import { ChevronRight, MessagesSquare, Volume2 } from "lucide-react-native";
import { Pressable, View } from "react-native";
import { BarraProgresso, Botao, BotaoIcone, Cabecalho, Ecra, EstadoErro, EstadoVazio, Etiqueta, Osso, Seccao, Texto } from "@/ui";
import { balao, cor, fonte, raio } from "@/tema";
import { diaMesCurto, duracao, useConversaProgressoQuery, type Progresso } from "@/dominios/conversa/api";
import { minSeg, minutosDe, useFalaProgressoQuery, type ProgressoFala } from "@/dominios/fala/api";
import { MinutosPorSemana } from "@/componentes/conversa/MinutosPorSemana";
import { falar } from "@/componentes/conversa/voz";

const inicioSemana = (iso: string) => diaMesCurto(new Date(`${iso}T12:00:00`));
const traco = (v: number | null, casas = 0) => (v === null ? "—" : v.toFixed(casas).replace(".", ","));

export default function EcraProgressoFala() {
  const conversa = useConversaProgressoQuery();
  const fala = useFalaProgressoQuery();
  const actualizar = () => {
    void conversa.refetch();
    void fala.refetch();
  };
  return (
    <Ecra
      cabecalho={<Cabecalho titulo="Progresso a falar" />}
      aoActualizar={actualizar}
      aActualizar={(conversa.isFetching || fala.isFetching) && !!conversa.data}
      rodape={
        <Botao larguraTotal onPress={() => router.navigate("/conversa")} icone={<MessagesSquare size={20} color={cor.sobreMarca} />}>
          Começar uma conversa
        </Botao>
      }
    >
      {conversa.isError ? (
        <EstadoErro erro={conversa.error} titulo="Não conseguimos carregar o progresso" aoTentar={conversa.refetch} />
      ) : !conversa.data ? (
        <View accessible accessibilityLabel="A carregar" style={{ gap: 16 }}>
          <Osso altura={140} />
          <Osso altura={24} largura="50%" />
          <Osso altura={48} />
          <Osso altura={48} />
          <Osso altura={48} />
        </View>
      ) : !conversa.data.sessoes ? (
        <EstadoVazio
          icone={<MessagesSquare size={26} color={cor.azulMarca} />}
          titulo="Ainda não conversou com o tutor"
          texto="Depois da primeira conversa vê aqui a sua pontuação, o que melhorou e as conversas para rever."
        />
      ) : (
        <Conversas p={conversa.data} />
      )}

      <DaFala dados={fala.data} carregando={fala.isLoading} erro={fala.isError} aoTentar={fala.refetch} />

      {conversa.data?.sessoes ? <Ultimas p={conversa.data} /> : null}
    </Ecra>
  );
}

function Conversas({ p }: { p: Progresso }) {
  const variacao = p.variacao_mes === null ? null : p.variacao_mes === 0 ? "igual ao mês passado" : `${p.variacao_mes > 0 ? "mais" : "menos"} ${Math.abs(p.variacao_mes)} que no mês passado`;
  const competencias = p.por_competencia.filter((a) => a.valor !== null);
  const frases = p.frases_sozinho ?? { total: 0, recentes: [] };
  return (
    <>
      <View style={[balao.grande, { backgroundColor: cor.azulMarca, paddingVertical: 22, paddingHorizontal: 24, gap: 6 }]}>
        <Texto v="legenda" forte cor={cor.sobreMarca}>
          Pontuação média
        </Texto>
        <View style={{ flexDirection: "row", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
          <Texto numeros cor={cor.sobreMarca} style={{ fontFamily: fonte.numero, fontSize: 44, lineHeight: 48 }}>
            {p.media ?? "–"}
          </Texto>
          <Texto cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22, flexShrink: 1 }}>
            {`de 100${variacao ? `, ${variacao}` : ""}`}
          </Texto>
        </View>
        <Texto cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
          {`${p.sessoes} ${p.sessoes === 1 ? "conversa" : "conversas"}, ${duracao(p.minutos)} a falar.`}
        </Texto>
      </View>

      {competencias.length ? (
        <Seccao titulo="Por competência" gap={14}>
          {competencias.map((a) => (
            <View key={a.chave} style={{ gap: 4 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 12 }}>
                <Texto forte style={{ fontSize: 15, lineHeight: 22 }}>
                  {a.nome}
                </Texto>
                <Texto forte numeros style={{ fontSize: 15, lineHeight: 22 }}>
                  {a.valor}
                </Texto>
              </View>
              <BarraProgresso valor={a.valor ?? 0} rotulo={`${a.nome}: ${a.valor} de 100`} altura={10} />
              {a.nota ? (
                <Texto v="legenda" suave>
                  {a.nota}
                </Texto>
              ) : null}
            </View>
          ))}
        </Seccao>
      ) : null}

      <Seccao titulo="Frases que já diz sozinho" gap={8}>
        <View style={{ flexDirection: "row", alignItems: "baseline", gap: 8 }}>
          <Texto numeros style={{ fontFamily: fonte.numero, fontSize: 36, lineHeight: 42 }}>
            {frases.total}
          </Texto>
          <Texto suave style={{ flexShrink: 1 }}>
            {frases.total === 1 ? "frase dita sem ajuda numa conversa" : "frases ditas sem ajuda numa conversa"}
          </Texto>
        </View>
        {frases.recentes.length ? (
          frases.recentes.map((r, i) => (
            <View key={r.texto} style={{ paddingVertical: 10, borderTopWidth: i ? 1 : 0, borderColor: cor.fundoForte }}>
              <Texto forte style={{ lineHeight: 22 }}>
                {r.texto}
              </Texto>
              <Texto v="legenda" suave>
                {[r.traducao, r.dias > 1 ? `Disse em ${r.dias} dias diferentes` : r.ultima_vez ? `Disse a ${diaMesCurto(new Date(r.ultima_vez))}` : ""].filter(Boolean).join(". ")}
              </Texto>
            </View>
          ))
        ) : (
          <Texto suave>Quando disser sozinho uma das frases-objectivo numa conversa, ela aparece aqui.</Texto>
        )}
      </Seccao>

      <Seccao titulo="Erros a trabalhar" gap={10}>
        {p.padroes?.length ? (
          p.padroes.map((e) => (
            <View key={e.chave} style={{ gap: 6, backgroundColor: cor.fundoSuave, borderRadius: raio.md, padding: 16 }}>
              <View style={{ flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                {e.superado ? <Etiqueta tom="certo">Já superado</Etiqueta> : <Etiqueta tom="realce">{e.ocorrencias === 1 ? "1 conversa" : `${e.ocorrencias} conversas`}</Etiqueta>}
                {e.ultima_ocorrencia ? (
                  <Texto v="legenda" suave>
                    {`Última vez a ${diaMesCurto(new Date(e.ultima_ocorrencia))}`}
                  </Texto>
                ) : null}
              </View>
              <Texto style={{ lineHeight: 22 }}>{e.descricao}</Texto>
              {e.errado && e.certo ? (
                <Texto accessibilityLabel={`Disse: ${e.errado}. Forma certa: ${e.certo}`} style={{ fontSize: 15, lineHeight: 22 }}>
                  <Texto suave style={{ fontSize: 15, textDecorationLine: "line-through" }}>
                    {e.errado}
                  </Texto>
                  {" → "}
                  <Texto forte style={{ fontSize: 15 }}>
                    {e.certo}
                  </Texto>
                </Texto>
              ) : null}
            </View>
          ))
        ) : (
          <Texto suave>Ainda não encontrámos erros que se repitam.</Texto>
        )}
      </Seccao>
    </>
  );
}

function DaFala({ dados, carregando, erro, aoTentar }: { dados?: ProgressoFala; carregando: boolean; erro: boolean; aoTentar: () => void }) {
  if (carregando) return <Osso altura={220} />;
  if (erro || !dados)
    return (
      <View accessibilityRole="alert" style={{ gap: 10, backgroundColor: cor.erradoSuave, borderRadius: raio.md, padding: 16 }}>
        <Texto>Não conseguimos carregar os minutos a falar.</Texto>
        <Botao tipo="ligacao" onPress={aoTentar}>
          Tentar outra vez
        </Botao>
      </View>
    );
  const semanas = dados.semanas;
  const total = semanas.reduce((a, s) => a + s.segundos, 0);
  const comMedidas = semanas.filter((s) => s.ppm !== null || s.palavras_por_resposta !== null || s.pausas_por_minuto !== null);
  return (
    <>
      <Seccao titulo="Minutos a falar por semana" gap={12}>
        <Texto suave>{total ? `${minSeg(total)} nas últimas 8 semanas: conversas, lições, revisão e aulas.` : "Ainda não há minutos a falar. Cada conversa e cada gravação contam."}</Texto>
        {semanas.length ? (
          <MinutosPorSemana
            barras={semanas.map((s) => ({ chave: s.inicio, rotulo: s.actual ? "esta" : inicioSemana(s.inicio), rotuloLongo: s.actual ? "Esta semana" : `Semana de ${inicioSemana(s.inicio)}`, minutos: minutosDe(s.segundos), actual: s.actual }))}
            meta={dados.meta_min * 7}
            legendaMeta={`meta da semana, ${dados.meta_min} min por dia`}
          />
        ) : null}
      </Seccao>

      <Seccao titulo="Como fala" gap={8}>
        {comMedidas.length ? (
          <>
            <View style={{ flexDirection: "row", gap: 6, paddingBottom: 6 }}>
              <Texto v="mini" suave style={{ flex: 1.3 }}>
                Semana
              </Texto>
              <Texto v="mini" suave style={{ flex: 1, textAlign: "right" }}>
                Palavras por minuto
              </Texto>
              <Texto v="mini" suave style={{ flex: 1, textAlign: "right" }}>
                Palavras por resposta
              </Texto>
              <Texto v="mini" suave style={{ flex: 1, textAlign: "right" }}>
                Pausas longas por minuto
              </Texto>
            </View>
            {semanas.map((s) => (
              <View
                key={s.inicio}
                accessible
                accessibilityLabel={`${s.actual ? "Esta semana" : `Semana de ${inicioSemana(s.inicio)}`}: ${traco(s.ppm)} palavras por minuto, ${traco(s.palavras_por_resposta, 1)} palavras por resposta, ${traco(s.pausas_por_minuto, 1)} pausas longas por minuto`}
                style={{ flexDirection: "row", gap: 6, paddingVertical: 6, borderTopWidth: 1, borderColor: cor.fundoForte }}
              >
                <Texto v="legenda" forte={s.actual} style={{ flex: 1.3 }}>
                  {s.actual ? "Esta semana" : inicioSemana(s.inicio)}
                </Texto>
                <Texto v="legenda" numeros forte={s.actual} style={{ flex: 1, textAlign: "right" }}>
                  {traco(s.ppm)}
                </Texto>
                <Texto v="legenda" numeros forte={s.actual} style={{ flex: 1, textAlign: "right" }}>
                  {traco(s.palavras_por_resposta, 1)}
                </Texto>
                <Texto v="legenda" numeros forte={s.actual} style={{ flex: 1, textAlign: "right" }}>
                  {traco(s.pausas_por_minuto, 1)}
                </Texto>
              </View>
            ))}
            <Texto v="legenda" suave>
              Mais palavras por minuto e respostas mais longas, com menos pausas longas (mais de 1 segundo), mostram mais fluência.
            </Texto>
          </>
        ) : (
          <Texto suave>Depois de algumas gravações e conversas vê aqui o seu ritmo de fala.</Texto>
        )}
      </Seccao>

      <Seccao titulo="Palavras a treinar" gap={4}>
        {dados.palavras_treinar.length ? (
          dados.palavras_treinar.map((w, i) => (
            <View key={w.palavra} style={{ flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 8, borderTopWidth: i ? 1 : 0, borderColor: cor.fundoForte }}>
              <View style={{ flex: 1 }}>
                <Texto forte style={{ fontSize: 17, lineHeight: 24 }}>
                  {w.palavra}
                </Texto>
                <Texto v="legenda" suave>
                  {`Saiu mal ${w.falhas} de ${w.tentativas} ${w.tentativas === 1 ? "vez" : "vezes"}${w.fonema ? `. Som difícil: /${w.fonema}/` : ""}${w.media !== null ? `. Nota média ${Math.round(w.media)}` : ""}`}
                </Texto>
              </View>
              <BotaoIcone rotulo={`Ouvir: ${w.palavra}`} onPress={() => falar(w.palavra)}>
                <Volume2 size={22} color={cor.azulMarca} />
              </BotaoIcone>
            </View>
          ))
        ) : (
          <Texto suave>Quando uma palavra não sair bem numa gravação, aparece aqui. Também entra na revisão de hoje.</Texto>
        )}
      </Seccao>
    </>
  );
}

function Ultimas({ p }: { p: Progresso }) {
  if (!p.ultimas.length) return null;
  return (
    <Seccao titulo="Últimas conversas" gap={0}>
      {p.ultimas.map((s) => (
        <Pressable
          key={s.id}
          accessibilityRole="link"
          accessibilityLabel={`${s.titulo}, ${diaMesCurto(new Date(s.iniciada_em))}, ${Math.max(1, Math.round(s.minutos))} minutos, ${s.geral ?? "sem nota"}`}
          onPress={() => router.push(`/conversa/resumo/${s.id}`)}
          style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 12, minHeight: 60, paddingVertical: 6, borderBottomWidth: 1, borderColor: cor.fundoForte, backgroundColor: pressed ? cor.fundoSuave : undefined })}
        >
          <View style={{ flex: 1, minWidth: 0 }}>
            <Texto forte numberOfLines={1} style={{ lineHeight: 22 }}>
              {s.titulo}
            </Texto>
            <Texto v="legenda" suave>
              {`${diaMesCurto(new Date(s.iniciada_em))}, ${Math.max(1, Math.round(s.minutos))} min`}
            </Texto>
          </View>
          {s.geral !== null ? (
            <Texto numeros style={{ fontFamily: fonte.numero, fontSize: 20 }}>
              {s.geral}
            </Texto>
          ) : (
            <Texto v="legenda" suave>
              sem nota
            </Texto>
          )}
          <ChevronRight size={18} color={cor.tintaSuave} />
        </Pressable>
      ))}
    </Seccao>
  );
}
