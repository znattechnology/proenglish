/**
 * Revisão de hoje (apps/web/components/pe/revisao/**): um exercício de cada vez, servido e corrigido
 * pelo servidor, sem vidas. Os exercícios falados podem saltar-se (sem microfone, análise em baixo):
 * a frase volta amanhã. No fim, o resumo.
 */
import { router } from "expo-router";
import { ArrowUp, CheckCircle2 } from "lucide-react-native";
import { useEffect, useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, type ScrollViewInstance, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { Gravacao } from "@/dominios/laboratorio/gravacao";
import {
  falarRevisao,
  nFrases,
  useResponderRevisaoMutation,
  useSaltarRevisaoMutation,
  useSessaoRevisaoQuery,
  useTerminarRevisaoMutation,
  type ExercicioRevisao,
  type FimRevisao,
  type ResultadoRevisao,
} from "@/dominios/revisao/api";
import { balao, cor, fonte, raio } from "@/tema";
import { Aviso, Botao, Ecra, EstadoErro, Etiqueta, Osso, Texto, Titulo } from "@/ui";
import { BotaoOuvirTexto } from "./Audio";
import { BotaoGravar, useGravador } from "./Gravador";
import { voltarAoTrilho } from "./Jogador";
import { BalaoEnunciado, CabecalhoLicao, corBorda, EmPortugues, Enunciado, estiloOpcao, Linha, PalavrasComNota, Resultado, Rodape, type Visual } from "./Partes";

const ROTULO_ESTADO: Record<string, string> = { vista: "Vista", reconhecida: "Reconhecida", com_ajuda: "Disse com ajuda", sozinho: "Disse sozinho" };

type RespostaRevisao = { tipo: "texto"; valor: string } | { tipo: "audio"; gravacao: Gravacao } | null;
type Fase = { tipo: "responder" } | { tipo: "resultado"; r: ResultadoRevisao } | { tipo: "aviso"; mensagem: string; podeSaltar: boolean };
type Props = { ex: ExercicioRevisao; bloqueado: boolean; visual: Visual; aoMudar: (r: RespostaRevisao) => void; aoSaltar: () => void };

const ESPACO = /_{2,}/;

function Balao({ texto, ouvir, voz }: { texto: string; ouvir?: string | null; voz?: boolean }) {
  return (
    <BalaoEnunciado depois={ouvir ? <BotaoOuvirTexto texto={ouvir} sobreMarca /> : null}>
      <Texto cor={cor.sobreMarca} style={voz ? { fontFamily: fonte.voz, fontSize: 24, lineHeight: 34 } : { fontSize: 20, lineHeight: 30 }}>
        {texto}
      </Texto>
    </BalaoEnunciado>
  );
}

function CampoTexto({ rotulo, linhas, bloqueado, visual, aoMudar }: { rotulo: string; linhas: number; bloqueado: boolean; visual: Visual; aoMudar: (r: RespostaRevisao) => void }) {
  const [texto, setTexto] = useState("");
  const [foco, setFoco] = useState(false);
  return (
    <View style={{ gap: 6 }}>
      <Texto v="rotulo">{rotulo}</Texto>
      <TextInput
        accessibilityLabel={rotulo}
        value={texto}
        editable={!bloqueado}
        multiline={linhas > 1}
        autoCapitalize={linhas > 1 ? "sentences" : "none"}
        autoCorrect={false}
        spellCheck={false}
        onFocus={() => setFoco(true)}
        onBlur={() => setFoco(false)}
        onChangeText={(v) => {
          setTexto(v);
          aoMudar(v.trim() ? { tipo: "texto", valor: v.trim() } : null);
        }}
        style={{
          minHeight: linhas > 1 ? 28 * linhas + 24 : 52,
          paddingHorizontal: 14,
          paddingVertical: 12,
          textAlignVertical: linhas > 1 ? "top" : "center",
          fontFamily: fonte.texto,
          fontSize: 18,
          color: cor.tinta,
          borderWidth: 2,
          borderRadius: raio.sm,
          borderColor: corBorda(visual, foco ? cor.azulMarca : cor.linhaForte),
        }}
      />
    </View>
  );
}

function Escolher({ ex, bloqueado, visual, aoMudar }: Props) {
  const [escolhida, setEscolhida] = useState<string | null>(null);
  return (
    <Enunciado titulo={ex.titulo}>
      {ex.frase_com_espaco ? <Balao texto={ex.frase_com_espaco} /> : ex.texto_en ? <Balao texto={ex.texto_en} ouvir={ex.audio_texto} /> : null}
      <View accessibilityRole="radiogroup" accessibilityLabel="Opções de resposta" style={{ gap: 12 }}>
        {(ex.opcoes ?? []).map((o, i) => {
          const sel = escolhida === o;
          return (
            <Pressable
              key={o}
              accessibilityRole="radio"
              accessibilityState={{ selected: sel, disabled: bloqueado }}
              disabled={bloqueado}
              onPress={() => {
                setEscolhida(o);
                aoMudar({ tipo: "texto", valor: o });
              }}
              style={({ pressed }) => [
                { minHeight: 56, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingVertical: 8, borderRadius: raio.sm, opacity: bloqueado && !sel ? 0.6 : 1 },
                estiloOpcao(sel, visual),
                pressed && !sel ? { backgroundColor: cor.fundoSuave } : null,
              ]}
            >
              <View style={{ width: 28, height: 28, alignItems: "center", justifyContent: "center", borderRadius: raio.sm, borderWidth: 1.5, borderColor: cor.linhaForte }}>
                <Texto v="legenda" forte suave>
                  {i + 1}
                </Texto>
              </View>
              <Texto forte={sel} style={{ flexShrink: 1, fontSize: 18, lineHeight: 24 }}>
                {o}
              </Texto>
            </Pressable>
          );
        })}
      </View>
    </Enunciado>
  );
}

function Completar({ ex, bloqueado, visual, aoMudar }: Props) {
  const [antes, depois = ""] = (ex.frase_com_espaco ?? "").split(ESPACO);
  return (
    <Enunciado titulo={ex.titulo}>
      <BalaoEnunciado>
        <Texto cor={cor.sobreMarca} style={{ fontSize: 20, lineHeight: 34 }}>
          {antes}
          <Texto style={{ fontSize: 20, lineHeight: 34, backgroundColor: cor.realce }}>{" ".repeat(12)}</Texto>
          {depois}
        </Texto>
      </BalaoEnunciado>
      {ex.traducao ? <EmPortugues texto={ex.traducao} /> : null}
      <CampoTexto rotulo="A palavra em falta" linhas={1} bloqueado={bloqueado} visual={visual} aoMudar={aoMudar} />
    </Enunciado>
  );
}

function Traduzir({ ex, bloqueado, visual, aoMudar }: Props) {
  return (
    <Enunciado titulo={ex.titulo}>
      {ex.traducao ? <EmPortugues texto={ex.traducao} /> : null}
      <CampoTexto rotulo="Em inglês" linhas={3} bloqueado={bloqueado} visual={visual} aoMudar={aoMudar} />
    </Enunciado>
  );
}

function Falar({ ex, bloqueado, aoMudar, aoSaltar }: Props) {
  const g = useGravador((gr) => aoMudar(gr ? { tipo: "audio", gravacao: gr } : null));
  return (
    <Enunciado titulo={ex.titulo}>
      <Balao texto={ex.texto_en ?? ""} ouvir={ex.audio_texto ?? ex.texto_en} voz />
      {ex.traducao ? (
        <Texto v="legenda" suave style={{ marginTop: -8 }}>
          {ex.traducao}
        </Texto>
      ) : null}
      <BotaoGravar g={g} bloqueado={bloqueado} aoSaltar={aoSaltar} textoSaltar="Pode saltar este exercício: não perde nada e a frase volta amanhã." />
      {g.estado === "parado" || g.estado === "gravado" ? (
        <Botao tipo="ligacao" disabled={bloqueado} onPress={aoSaltar} style={{ alignSelf: "center" }}>
          Agora não posso falar
        </Botao>
      ) : null}
    </Enunciado>
  );
}

function ExercicioRevisaoUI(props: Props) {
  switch (props.ex.forma) {
    case "escolher":
      return <Escolher {...props} />;
    case "completar":
      return <Completar {...props} />;
    case "traduzir":
      return <Traduzir {...props} />;
    default:
      return <Falar {...props} />;
  }
}

export function Revisao() {
  const { data: sessao, isLoading, isFetching, isError, error, refetch } = useSessaoRevisaoQuery();
  const [responder] = useResponderRevisaoMutation();
  const [saltarNoServidor] = useSaltarRevisaoMutation();
  const [terminar, { isLoading: aTerminar }] = useTerminarRevisaoMutation();
  const ins = useSafeAreaInsets();
  const scroll = useRef<ScrollViewInstance>(null);

  const [i, setI] = useState(0);
  const [resposta, setResposta] = useState<RespostaRevisao>(null);
  const [fase, setFase] = useState<Fase>({ tipo: "responder" });
  const [aVerificar, setAVerificar] = useState(false);
  const [aSaltar, setASaltar] = useState(false);
  const [fim, setFim] = useState<FimRevisao | null>(null);
  const [erroFim, setErroFim] = useState(false);
  const [inicio, setInicio] = useState(() => new Date().toISOString());
  const [tentativa, setTentativa] = useState(0);
  const inicioExercicio = useRef(0);
  useEffect(() => {
    inicioExercicio.current = Date.now();
    scroll.current?.scrollTo({ y: 0, animated: false });
  }, [i]);

  const total = sessao?.exercicios.length ?? 0;
  const ex = sessao?.exercicios[i];

  const acabar = async () => {
    setErroFim(false);
    const r = await terminar({ inicio });
    if ("error" in r && r.error) setErroFim(true);
    else setFim(r.data!);
  };

  const verificar = async () => {
    if (!ex || !resposta || aVerificar) return;
    setAVerificar(true);
    const segundos = Math.round((Date.now() - inicioExercicio.current) / 1000);
    try {
      if (resposta.tipo === "audio") {
        const r = await falarRevisao(ex.id, resposta.gravacao, segundos);
        if (r.error) {
          const e = r.error;
          setFase({
            tipo: "aviso",
            mensagem: e.status === "FETCH_ERROR" ? "Sem ligação ao servidor. Verifique a Internet e tente outra vez." : (e.data?.mensagem ?? "Não conseguimos verificar agora. Tente outra vez."),
            podeSaltar: !!e.data?.pode_saltar || e.status === 404 || e.status === 429 || e.status === 503,
          });
          return;
        }
        setFase({ tipo: "resultado", r: r.data });
        return;
      }
      const r = await responder({ exercicioId: ex.id, forma: ex.forma, resposta: resposta.valor, segundos });
      if ("error" in r && r.error) {
        const e = r.error as { status?: number | string; data?: { mensagem?: string; pode_saltar?: boolean } };
        setFase({ tipo: "aviso", mensagem: e.data?.mensagem ?? "Não conseguimos verificar agora. Verifique a ligação e tente outra vez.", podeSaltar: !!e.data?.pode_saltar || e.status === 404 });
        return;
      }
      setFase({ tipo: "resultado", r: r.data! });
    } finally {
      setAVerificar(false);
    }
  };

  const seguinte = () => {
    setResposta(null);
    setFase({ tipo: "responder" });
    if (i + 1 >= total) void acabar();
    else setI(i + 1);
  };

  // Saltar: o servidor tira-o de hoje sem pontos e a frase volta amanhã. Se falhar, segue na mesma.
  const saltar = async () => {
    if (!ex || aSaltar) return;
    setASaltar(true);
    try {
      if (ex.forma === "ouvir_repetir") await saltarNoServidor({ exercicioId: ex.id });
    } finally {
      setASaltar(false);
    }
    seguinte();
  };

  const outraVez = () => {
    setResposta(null);
    setFase({ tipo: "responder" });
    setTentativa((t) => t + 1);
  };

  const recomecar = () => {
    setFim(null);
    setI(0);
    setResposta(null);
    setFase({ tipo: "responder" });
    setInicio(new Date().toISOString());
    void refetch();
  };

  const sair = () => (router.canGoBack() ? router.back() : voltarAoTrilho());

  if (isLoading || isFetching) return <Esqueleto />;
  if (isError || !sessao) {
    return (
      <Ecra style={{ paddingTop: 48 }}>
        <EstadoErro
          erro={error}
          titulo="Não conseguimos abrir a revisão"
          aoTentar={() => void refetch()}
          outra={
            <Botao tipo="secundario" larguraTotal onPress={sair}>
              Voltar ao laboratório
            </Botao>
          }
        />
      </Ecra>
    );
  }
  if (fim) return <Fim fim={fim} aoRecomecar={recomecar} aoSair={sair} />;
  if (total === 0) return <EmDia aoSair={sair} />;

  const feitos = i + (fase.tipo === "resultado" ? 1 : 0);
  const visual: Visual = fase.tipo === "resultado" ? (fase.r.correcta ? "certo" : "errado") : "livre";
  const r = fase.tipo === "resultado" ? fase.r : null;
  const ultimo = i + 1 >= total;

  return (
    <View style={{ flex: 1, backgroundColor: cor.fundo, paddingTop: ins.top }}>
      <CabecalhoLicao feitos={feitos} total={total} vidas={null} aoSair={sair} rotuloSair="Sair da revisão" contador />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <ScrollView ref={scroll} style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 12, paddingBottom: 24, gap: 20 }} keyboardShouldPersistTaps="handled">
          {ex?.padrao ? (
            <View style={{ alignSelf: "flex-start", backgroundColor: cor.realceSuave, borderRadius: raio.sm, paddingHorizontal: 12, paddingVertical: 6 }}>
              <Texto v="legenda">Treinar um erro frequente: {ex.padrao.descricao}</Texto>
            </View>
          ) : ex?.nova ? (
            <View style={{ alignSelf: "flex-start", backgroundColor: cor.fundoSuave, borderRadius: raio.sm, paddingHorizontal: 12, paddingVertical: 6 }}>
              <Texto v="legenda">Frase nova na revisão</Texto>
            </View>
          ) : null}
          {ex ? <ExercicioRevisaoUI key={`${ex.id}-${tentativa}`} ex={ex} bloqueado={fase.tipo !== "responder" || aSaltar || aVerificar} visual={visual} aoMudar={setResposta} aoSaltar={() => void saltar()} /> : null}
          {erroFim ? (
            <Aviso
              tom="erro"
              accao={
                <Botao tipo="secundario" tamanho="pequeno" onPress={() => void acabar()}>
                  Tentar outra vez
                </Botao>
              }
            >
              Não conseguimos fechar a revisão. As respostas já estão guardadas.
            </Aviso>
          ) : null}
        </ScrollView>
        <Rodape tom={r ? (r.correcta ? "certo" : "errado") : null}>
          {r ? (
            <Resultado
              certo={r.correcta}
              titulo={r.correcta ? (r.analise ? `Certo. ${r.analise.nota} de 100 na pronúncia` : "Certo") : r.analise ? `Ainda não. ${r.analise.nota} de 100 na pronúncia` : "Ainda não"}
            >
              <Texto style={{ lineHeight: 24 }}>
                <Texto suave>{r.correcta ? "A frase: " : "Resposta certa: "}</Texto>
                <Texto forte>{r.texto}</Texto>
              </Texto>
              {r.traducao ? (
                <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
                  {r.traducao}
                </Texto>
              ) : null}
              {r.analise?.detalhe ? <PalavrasComNota detalhe={r.analise.detalhe} /> : r.analise?.palavras.length ? <Linha>Palavras a treinar: {r.analise.palavras.join(", ")}.</Linha> : null}
              {r.explicacao ? <Linha>{r.explicacao}</Linha> : null}
              {r.subiu && r.estado_depois ? (
                <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
                  <ArrowUp size={16} color={cor.tinta} />
                  <Texto forte style={{ fontSize: 15 }}>
                    Subiu para {ROTULO_ESTADO[r.estado_depois].toLowerCase()}
                  </Texto>
                </View>
              ) : null}
              <BotaoOuvirTexto texto={r.texto} rotulo="Ouvir a frase" />
            </Resultado>
          ) : fase.tipo === "aviso" ? (
            <View accessibilityRole="alert">
              <Texto>{fase.mensagem}</Texto>
            </View>
          ) : null}
          {r ? (
            <Botao larguraTotal onPress={seguinte} carregando={aTerminar}>
              {ultimo ? (aTerminar ? "A guardar…" : "Ver o resumo") : "Continuar"}
            </Botao>
          ) : fase.tipo === "aviso" ? (
            <>
              <Botao larguraTotal onPress={outraVez}>
                Tentar outra vez
              </Botao>
              {fase.podeSaltar ? (
                <Botao tipo="secundario" larguraTotal onPress={() => void saltar()} carregando={aSaltar}>
                  Saltar
                </Botao>
              ) : null}
            </>
          ) : (
            <Botao larguraTotal disabled={!resposta || aVerificar || aSaltar} carregando={aVerificar} onPress={() => void verificar()}>
              {aVerificar ? "A verificar…" : "Verificar"}
            </Botao>
          )}
        </Rodape>
      </KeyboardAvoidingView>
    </View>
  );
}

function EmDia({ aoSair }: { aoSair: () => void }) {
  return (
    <Ecra style={{ paddingTop: 48, gap: 20 }}>
      <Etiqueta tom="certo" icone={<CheckCircle2 size={18} color={cor.certo} />}>
        Revisão de hoje
      </Etiqueta>
      <View style={{ gap: 8 }}>
        <Titulo>Está em dia. Volte amanhã</Titulo>
        <Texto suave>Não há frases para rever hoje. As frases novas entram aqui quando as aprende numa lição ou numa conversa com o tutor.</Texto>
      </View>
      <View style={{ gap: 12, marginTop: "auto" }}>
        <Botao larguraTotal onPress={aoSair}>
          Fazer uma lição
        </Botao>
        <Botao tipo="secundario" larguraTotal href="/conversa">
          Falar com o tutor
        </Botao>
      </View>
    </Ecra>
  );
}

function Fim({ fim, aoRecomecar, aoSair }: { fim: FimRevisao; aoRecomecar: () => void; aoSair: () => void }) {
  const falta = Math.max(0, Math.ceil(fim.meta.meta_minutos - fim.meta.minutos_hoje));
  return (
    <Ecra style={{ paddingTop: 48, gap: 28 }}>
      <View style={{ gap: 8 }}>
        <Etiqueta tom="certo" icone={<CheckCircle2 size={18} color={cor.certo} />}>
          Revisão feita
        </Etiqueta>
        <Titulo v="tituloXL">
          Acertou {fim.acertos} de {fim.respondidos}
        </Titulo>
      </View>

      {fim.subiram.length ? (
        <View style={{ gap: 12 }}>
          <Texto v="tituloS" accessibilityRole="header">
            {fim.subiram.length === 1 ? "Uma frase subiu de nível" : `${fim.subiram.length} frases subiram de nível`}
          </Texto>
          {fim.subiram.map((s) => (
            <View key={s.texto} style={{ gap: 2, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, paddingHorizontal: 16, paddingVertical: 12 }}>
              <Texto forte style={{ lineHeight: 24 }}>
                {s.texto}
              </Texto>
              {s.traducao ? (
                <Texto v="legenda" suave>
                  {s.traducao}
                </Texto>
              ) : null}
              <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
                <ArrowUp size={16} color={cor.certo} />
                <Texto v="legenda" cor={cor.certo}>
                  {ROTULO_ESTADO[s.antes]} para {s.depois_rotulo.toLowerCase()}
                </Texto>
              </View>
            </View>
          ))}
          <Texto v="legenda" suave>
            Uma frase só fica aprendida quando a diz sozinho numa conversa com o tutor.
          </Texto>
        </View>
      ) : null}

      <View style={[balao.grande, { backgroundColor: cor.azulMarca, padding: 24, gap: 4 }]}>
        <Texto cor={cor.sobreMarca} style={{ fontFamily: fonte.titulo, fontSize: 22, lineHeight: 28 }}>
          {fim.amanha ? `Amanhã: ${nFrases(fim.amanha)} para rever` : "Amanhã não há frases marcadas"}
        </Texto>
        <Texto cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
          {fim.pontos ? `Ganhou ${fim.pontos} pontos. ` : ""}
          {fim.meta.cumprida ? "A meta de hoje está cumprida." : `Faltam ${falta} min para a meta de hoje (${fim.meta.meta_minutos} min).`}
        </Texto>
      </View>

      <View style={{ gap: 12, marginTop: "auto" }}>
        {fim.restam_hoje ? (
          <Botao tipo="realce" larguraTotal onPress={aoRecomecar}>
            Rever mais {nFrases(fim.restam_hoje)}
          </Botao>
        ) : null}
        <Botao tipo={fim.restam_hoje ? "ligacao" : "principal"} larguraTotal onPress={aoSair}>
          Voltar ao laboratório
        </Botao>
      </View>
    </Ecra>
  );
}

function Esqueleto() {
  const ins = useSafeAreaInsets();
  return (
    <View accessible accessibilityLabel="A carregar a revisão" accessibilityState={{ busy: true }} style={{ flex: 1, backgroundColor: cor.fundo, paddingTop: ins.top + 12, paddingHorizontal: 20, gap: 24 }}>
      <Osso altura={10} raio={999} />
      <Osso altura={28} largura="70%" raio={6} />
      <Osso altura={110} raio={28} />
      <Osso altura={56} raio={6} />
      <Osso altura={56} raio={6} />
    </View>
  );
}
