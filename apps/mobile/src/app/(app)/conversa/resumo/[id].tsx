/**
 * Resumo de uma conversa com o tutor (tela ResumoConversa do canvas).
 * Web: apps/web/app/(estudante)/user/laboratory/speaking/summary/[sessionId]/page.tsx.
 * Enquanto a conversa é avaliada no servidor, volta a perguntar de 4 em 4 segundos.
 */
import { ASeguir } from "@/componentes/cursos/Percurso";
import { useProximoPassoQuery } from "@/dominios/cursos/api";
import { router, useLocalSearchParams } from "expo-router";
import { CheckCircle2, Circle, Mic } from "lucide-react-native";
import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { Botao, Cabecalho, Ecra, EstadoErro, Etiqueta, Osso, Seccao, Texto } from "@/ui";
import { balao, cor, fonte, raio } from "@/tema";
import { COMPETENCIAS, quandoFoi, useConversaResumoQuery, type Ajuste, type PadraoConversa, type Resumo } from "@/dominios/conversa/api";
import { Bolha } from "@/componentes/conversa/Pecas";

const voltar = () => (router.canGoBack() ? router.back() : router.replace("/conversa/progresso"));

export default function EcraResumoConversa() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data, isError, error, refetch, isFetching } = useConversaResumoQuery(id);
  const aAvaliar = data?.estado === "a_avaliar";
  useEffect(() => {
    if (!aAvaliar) return;
    const t = setInterval(() => void refetch(), 4000);
    return () => clearInterval(t);
  }, [aAvaliar, refetch]);

  const minutos = data?.minutos_cobrados ?? 0;
  const cabecalho = (
    <Cabecalho
      titulo={data?.situacao.titulo ?? "Resumo da conversa"}
      subtitulo={data ? `${quandoFoi(data.iniciada_em)}, ${minutos ? `${minutos} min com o tutor` : "sem minutos contados"}` : undefined}
      aoVoltar={voltar}
    />
  );

  if (isError)
    return (
      <Ecra cabecalho={cabecalho}>
        <EstadoErro erro={error} titulo="Não encontrámos esta conversa" aoTentar={refetch} outra={<Botao tipo="secundario" larguraTotal href="/conversa/progresso" substituir>Ver o progresso a falar</Botao>} />
      </Ecra>
    );
  if (!data)
    return (
      <Ecra cabecalho={cabecalho}>
        <View accessible accessibilityLabel="A carregar" style={{ gap: 16 }}>
          <Osso altura={96} />
          <View style={{ flexDirection: "row", gap: 8 }}>
            {[0, 1, 2, 3].map((i) => (
              <Osso key={i} altura={64} style={{ flex: 1 }} />
            ))}
          </View>
          <Osso altura={120} />
          <Osso altura={120} />
        </View>
      </Ecra>
    );
  return (
    <Ecra cabecalho={cabecalho} aoActualizar={refetch} aActualizar={isFetching && !aAvaliar}>
      <Conteudo r={data} />
    </Ecra>
  );
}

function Conteudo({ r }: { r: Resumo }) {
  const [verTudo, setVerTudo] = useState(false);
  const notas = r.notas ? (["fluencia", "gramatica", "pronuncia", "vocabulario"] as const).filter((k) => r.notas![k] !== null).map((k) => ({ k, nome: COMPETENCIAS[k], valor: Math.round(r.notas![k] as number) })) : [];
  const geral = r.notas?.geral ?? null;
  const repetir = r.situacao.id ? `/conversa?situacao=${encodeURIComponent(r.situacao.id)}` : "/conversa";
  // O passo seguinte do percurso do curso a que esta conversa pertence (se pertencer a algum).
  const { data: seguinte } = useProximoPassoQuery(r.situacao.id ? { situacao: r.situacao.id } : undefined, { refetchOnMountOrArgChange: true });

  return (
    <>
      {geral !== null ? (
        <View accessible accessibilityLabel={`Nota geral: ${Math.round(geral)} de 100`} style={[balao.grande, { backgroundColor: cor.azulMarca, paddingVertical: 20, paddingHorizontal: 24, flexDirection: "row", alignItems: "baseline", gap: 10 }]}>
          <Texto numeros cor={cor.sobreMarca} style={{ fontFamily: fonte.numero, fontSize: 44, lineHeight: 48 }}>
            {Math.round(geral)}
          </Texto>
          <Texto cor={cor.sobreMarca} style={{ flex: 1 }}>
            de 100 nesta conversa
          </Texto>
        </View>
      ) : null}

      {notas.length ? (
        <View style={{ flexDirection: "row", gap: 8 }}>
          {notas.map((n) => (
            <View key={n.k} accessible accessibilityLabel={`${n.nome}: ${n.valor}`} style={{ flex: 1, minWidth: 0, alignItems: "center", backgroundColor: cor.fundoSuave, borderRadius: raio.md, paddingVertical: 10, paddingHorizontal: 4 }}>
              <Texto numeros style={{ fontFamily: fonte.numero, fontSize: 22, lineHeight: 28 }}>
                {n.valor}
              </Texto>
              <Texto v="mini" suave centro numberOfLines={1} adjustsFontSizeToFit>
                {n.nome}
              </Texto>
            </View>
          ))}
        </View>
      ) : (
        <SemNotas r={r} />
      )}

      {r.fala ? (
        <View style={{ flexDirection: "row", gap: 12, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, paddingHorizontal: 16, paddingVertical: 12 }}>
          <Mic size={20} color={cor.azulMarca} style={{ marginTop: 3 }} />
          <View style={{ flex: 1 }}>
            <Texto style={{ fontSize: 17, lineHeight: 26 }}>{r.fala.frase}</Texto>
            {r.fala.fonte === "estimado" ? (
              <Texto v="legenda" suave>
                Tempo estimado pelas palavras que disse.
              </Texto>
            ) : null}
          </View>
        </View>
      ) : null}

      {r.resumo ? <Texto style={{ fontSize: 17, lineHeight: 26 }}>{r.resumo}</Texto> : null}

      <Objectivos r={r} />

      <Seccao titulo="Correcções" gap={10}>
        {r.correccoes.length ? (
          r.correccoes.map((c, i) => (
            <View key={i} style={{ borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, paddingVertical: 14, paddingHorizontal: 16, gap: 6 }}>
              <Texto accessibilityLabel={`Disse: ${c.disse}`} cor={cor.errado} style={{ fontSize: 15, lineHeight: 22, textDecorationLine: "line-through" }}>
                {c.disse}
              </Texto>
              <Texto accessibilityLabel={`Forma certa: ${c.certo}`} forte style={{ fontSize: 17, lineHeight: 24 }}>
                <Texto forte style={{ fontSize: 17, lineHeight: 24, backgroundColor: cor.realce }}>{` ${c.certo} `}</Texto>
              </Texto>
              <Texto v="legenda" suave>
                {c.porque}
              </Texto>
            </View>
          ))
        ) : (
          <Texto suave>{notas.length ? "Nenhuma correcção nesta conversa." : "Sem correcções."}</Texto>
        )}
      </Seccao>

      {r.padroes?.length ? (
        <Seccao titulo="Erros a trabalhar" gap={10}>
          {r.padroes.map((p) => (
            <View key={p.chave} style={{ gap: 6, backgroundColor: cor.fundoSuave, borderRadius: raio.md, padding: 16 }}>
              <EstadoPadrao estado={p.estado} />
              <Texto style={{ lineHeight: 22 }}>{p.descricao}</Texto>
              <Exemplo errado={p.errado} certo={p.certo} />
            </View>
          ))}
        </Seccao>
      ) : null}

      {r.palavras_bem_usadas.length ? (
        <Seccao titulo="Palavras novas que usou bem" gap={10}>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {r.palavras_bem_usadas.map((p) => (
              <View key={p} style={{ backgroundColor: cor.certoSuave, borderRadius: raio.sm, paddingHorizontal: 12, paddingVertical: 4 }}>
                <Texto forte cor={cor.certo}>
                  {p}
                </Texto>
              </View>
            ))}
          </View>
        </Seccao>
      ) : null}

      {verTudo ? (
        <Seccao titulo="A conversa" gap={12}>
          {r.transcricao_provisoria ? (
            <Texto v="legenda" suave>
              Transcrição provisória: a versão final chega quando a chamada for confirmada.
            </Texto>
          ) : null}
          {r.transcricao.length ? (
            r.transcricao.map((f, i) => (
              <Bolha key={i} quem={f.quem} compacta>
                {f.quem === "aluno" ? <ComErros texto={f.texto} correccoes={r.correccoes} /> : f.texto}
              </Bolha>
            ))
          ) : (
            <Texto suave>Não ficou registada nenhuma fala nesta conversa.</Texto>
          )}
        </Seccao>
      ) : null}

      {seguinte ? <ASeguir proximo={seguinte} /> : null}

      <View style={{ gap: 10, paddingTop: 4 }}>
        <Botao tipo={seguinte ? "secundario" : "principal"} larguraTotal onPress={() => router.navigate(repetir)}>
          {r.situacao.id ? "Repetir esta conversa" : "Nova conversa"}
        </Botao>
        <Botao tipo="secundario" larguraTotal tamanho="medio" onPress={() => setVerTudo((v) => !v)} accessibilityState={{ expanded: verTudo }}>
          {verTudo ? "Esconder a conversa" : "Ler a conversa toda"}
        </Botao>
        <Botao tipo="ligacao" href="/conversa/progresso" style={{ alignSelf: "center" }}>
          Progresso a falar
        </Botao>
      </View>
    </>
  );
}

function SemNotas({ r }: { r: Resumo }) {
  const [titulo, texto] =
    r.estado === "em_curso"
      ? ["Esta conversa ainda não terminou", "Volte daqui a pouco para ver o resumo."]
      : r.estado === "a_avaliar"
        ? ["A avaliar a conversa…", "Demora uns segundos. Este ecrã actualiza-se sozinho."]
        : r.estado === "nao_ligou"
          ? ["A chamada não chegou a ligar", "Não gastou minutos. Pode tentar outra vez quando quiser."]
          : ["Conversa curta demais para dar notas", "Responda pelo menos a algumas perguntas do tutor para receber notas e correcções. Os minutos contam na mesma para o seu dia."];
  return (
    <View style={{ gap: 4, backgroundColor: cor.fundoSuave, borderRadius: raio.md, padding: 20 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        {r.estado === "a_avaliar" ? <ActivityIndicator color={cor.azulMarca} /> : null}
        <Texto forte style={{ fontSize: 17, lineHeight: 24, flex: 1 }}>
          {titulo}
        </Texto>
      </View>
      <Texto suave accessibilityLiveRegion="polite">
        {texto}
      </Texto>
    </View>
  );
}

/** Marca, na fala do aluno, o trecho que foi corrigido. */
function ComErros({ texto, correccoes }: { texto: string; correccoes: Ajuste[] }) {
  const baixo = texto.toLowerCase();
  const c = correccoes.find((x) => x.disse && baixo.includes(x.disse.toLowerCase().replace(/[.!?]+$/, "")));
  if (!c) return <Texto>{texto}</Texto>;
  const alvo = c.disse.replace(/[.!?]+$/, "");
  const i = baixo.indexOf(alvo.toLowerCase());
  return (
    <Texto>
      {texto.slice(0, i)}
      <Texto style={{ backgroundColor: cor.erradoSuave, textDecorationLine: "underline", textDecorationStyle: "dashed", textDecorationColor: cor.errado }}>{texto.slice(i, i + alvo.length)}</Texto>
      {texto.slice(i + alvo.length)}
    </Texto>
  );
}

function Objectivos({ r }: { r: Resumo }) {
  const lista = r.objectivos ?? [];
  if (!lista.length) return null;
  const avaliada = r.estado === "avaliada";
  const ditas = lista.filter((o) => o.usado).length;
  return (
    <Seccao titulo="Objectivos" gap={8}>
      <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
        {!avaliada
          ? "Vemos que frases disse quando a conversa for avaliada."
          : ditas === lista.length
            ? "Disse todas as frases sozinho. Ficam como aprendidas."
            : ditas
              ? `Disse ${ditas} de ${lista.length} frases sozinho. Essas ficam como aprendidas.`
              : "Ainda não disse estas frases sozinho. Tente na próxima conversa."}
      </Texto>
      {lista.map((o, i) => (
        <View key={o.en} style={{ flexDirection: "row", gap: 10, paddingVertical: 10, borderTopWidth: i ? 1 : 0, borderColor: cor.fundoForte }}>
          <View style={{ marginTop: 2 }}>{o.usado ? <CheckCircle2 size={20} color={cor.certo} /> : <Circle size={20} color={cor.tintaSuave} />}</View>
          <View style={{ flex: 1 }}>
            <Texto forte style={{ lineHeight: 22 }}>
              {o.en}
            </Texto>
            {o.pt ? (
              <Texto v="legenda" suave>
                {o.pt}
              </Texto>
            ) : null}
            {avaliada ? (
              <Texto v="legenda" forte={o.usado} cor={o.usado ? cor.certo : cor.tintaSuave}>
                {o.usado ? "Disse sozinho" : o.com_ajuda ? "Disse logo a seguir ao tutor: ainda não conta" : "Ainda não disse"}
              </Texto>
            ) : null}
          </View>
        </View>
      ))}
    </Seccao>
  );
}

function EstadoPadrao({ estado }: { estado: PadraoConversa["estado"] }) {
  if (estado === "superado") return <Etiqueta tom="certo">Já superado</Etiqueta>;
  if (estado === "recorrente") return <Etiqueta tom="realce">Repete-se</Etiqueta>;
  return <Etiqueta>Novo</Etiqueta>;
}

function Exemplo({ errado, certo }: { errado: string; certo: string }) {
  if (!errado || !certo) return null;
  return (
    <Texto accessibilityLabel={`Disse: ${errado}. Forma certa: ${certo}`} style={{ fontSize: 15, lineHeight: 22 }}>
      <Texto suave style={{ fontSize: 15, textDecorationLine: "line-through", textDecorationColor: cor.errado }}>
        {errado}
      </Texto>
      {" → "}
      <Texto forte style={{ fontSize: 15 }}>
        {certo}
      </Texto>
    </Texto>
  );
}
