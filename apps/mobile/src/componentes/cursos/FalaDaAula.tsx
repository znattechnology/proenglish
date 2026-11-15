/**
 * Falar depois do vídeo de uma aula (web components/pe/curso/FalaDaAula.tsx):
 * "Repetir em voz alta" (ouvir a frase no vídeo, gravar, ver a nota) e "Usar isto numa conversa"
 * (abre a conversa de 3 minutos do agente da conversa em /conversa/aula).
 */
import { RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder } from "expo-audio";
import { useEventListener } from "expo";
import { router } from "expo-router";
import * as Speech from "expo-speech";
import type { VideoPlayer } from "expo-video";
import { CheckCircle2, MessagesSquare, Mic, Play, Square, Volume2 } from "lucide-react-native";
import { useEffect, useRef, useState } from "react";
import { Linking, Pressable, View } from "react-native";
import { pedir } from "@/api/base";
import { agora, tocarDesde } from "./leitor";
import type { AnaliseFrase, AnaliseGravacao, EstadoBanco, FalaDaAula, FraseDaAula } from "@/dominios/cursos/api";
import { ofertaDe, type OfertaPlano } from "@/dominios/subscricao/api";
import { Aviso, Botao, Etiqueta, Texto } from "@/ui";
import { FolhaOferta } from "@/componentes/subscricao/Oferta";
import { AvisoAnaliseAproximada } from "@/componentes/licao/Partes";
import { balao, cor, fonte, raio } from "@/tema";

const ROTULO_ESTADO: Partial<Record<EstadoBanco, string>> = { com_ajuda: "Já repetiu", sozinho: "Já a diz sozinho" };

type Gravacao = { fraseId: number; estado: "a-gravar" | "a-analisar" } | null;

/** Ouve uma frase: o pedaço do vídeo onde ela é dita ou, sem tempos, a voz do telemóvel. */
function useOuvir(player: VideoPlayer) {
  const fim = useRef<number | null>(null);
  useEventListener(player, "timeUpdate", ({ currentTime }) => {
    if (fim.current != null && currentTime >= fim.current) {
      fim.current = null;
      player.pause();
    }
  });
  useEventListener(player, "playingChange", ({ isPlaying }) => {
    if (!isPlaying) fim.current = null;
  });
  return (f: FraseDaAula) => {
    if (f.inicio != null && f.fim != null) {
      tocarDesde(player, f.inicio);
      // Depois do salto, para não ser apanhado pelo "pause" que limpa o fim.
      setTimeout(() => (fim.current = f.fim), 0);
    } else {
      Speech.stop();
      Speech.speak(f.texto, { language: "en-US", rate: 0.9 });
    }
  };
}

export function RepetirEmVozAlta({ chapterId, player, dados }: { chapterId: string; player: VideoPlayer; dados: FalaDaAula }) {
  const frases = dados.frases.filter((f) => f.tipo === "frase");
  const palavras = dados.frases.filter((f) => f.tipo === "palavra");
  const gravador = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [gravacao, setGravacao] = useState<Gravacao>(null);
  const [resultados, setResultados] = useState<Record<number, AnaliseGravacao>>({});
  const [estados, setEstados] = useState<Record<number, EstadoBanco | null>>({});
  const [erro, setErro] = useState<{ fraseId: number; texto: string } | null>(null);
  const [semMicrofone, setSemMicrofone] = useState(false);
  // 429 limite_analises: o plano que dá mais análises de pronúncia.
  const [limite, setLimite] = useState<{ mensagem: string; oferta: OfertaPlano } | null>(null);
  const inicio = useRef(0);
  const ouvir = useOuvir(player);

  useEffect(
    () => () => {
      Speech.stop();
    },
    []
  );

  if (!frases.length && !palavras.length) return null;

  const gravar = async (f: FraseDaAula) => {
    setErro(null);
    const p = await requestRecordingPermissionsAsync();
    if (!p.granted) {
      setSemMicrofone(true);
      return;
    }
    setSemMicrofone(false);
    try {
      player.pause();
      Speech.stop();
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await gravador.prepareToRecordAsync();
      gravador.record();
      inicio.current = agora();
      setGravacao({ fraseId: f.id, estado: "a-gravar" });
    } catch {
      setErro({ fraseId: f.id, texto: "Não foi possível começar a gravar. Tente outra vez." });
    }
  };

  const parar = async (f: FraseDaAula) => {
    setGravacao({ fraseId: f.id, estado: "a-analisar" });
    try {
      await gravador.stop();
    } finally {
      // Sem modo de gravação, o vídeo volta a tocar pelo altifalante.
      await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true }).catch(() => {});
    }
    const uri = gravador.uri;
    if (!uri) {
      setGravacao(null);
      setErro({ fraseId: f.id, texto: "A gravação ficou vazia. Tente outra vez." });
      return;
    }
    const segundos = Math.round((agora() - inicio.current) / 1000);
    const corpo = new FormData();
    // React Native envia o ficheiro a partir do uri (o tipo m4a é aceite pela API).
    corpo.append("audio", { uri, name: "gravacao.m4a", type: "audio/mp4" } as unknown as Blob);
    corpo.append("segundos", String(segundos));
    try {
      const r = await pedir<AnaliseFrase & { mensagem?: string }>(`/student/video-courses/chapters/${chapterId}/frases/${f.id}/falar/`, { method: "POST", body: corpo });
      if (!r.ok) {
        const texto = r.data?.mensagem ?? "Não conseguimos analisar a gravação. Tente outra vez.";
        setErro({ fraseId: f.id, texto });
        const oferta = r.status === 429 ? ofertaDe(r.data) : undefined;
        if (oferta) setLimite({ mensagem: texto, oferta });
        return;
      }
      setResultados((v) => ({ ...v, [f.id]: r.data.analise }));
      setEstados((v) => ({ ...v, [f.id]: r.data.estado }));
    } catch {
      setErro({ fraseId: f.id, texto: "Sem ligação ao servidor. Verifique a Internet e tente outra vez." });
    } finally {
      setGravacao(null);
    }
  };

  return (
    <View style={{ gap: 16 }}>
      <View style={{ gap: 4 }}>
        <Texto v="tituloM" accessibilityRole="header">
          Repetir em voz alta
        </Texto>
        <Texto suave>Ouça a frase no vídeo e diga-a logo a seguir, com o mesmo ritmo. Depois veja a nota e as palavras a treinar.</Texto>
      </View>

      {semMicrofone ? (
        <Aviso titulo="Sem acesso ao microfone" accao={<Botao tipo="ligacao" tamanho="pequeno" onPress={() => Linking.openSettings()}>Abrir as definições</Botao>}>
          Para gravar, permita o microfone ao ProEnglish nas definições do telemóvel e toque outra vez em Gravar.
        </Aviso>
      ) : null}

      {frases.map((f) => {
        const estado = estados[f.id] ?? f.estado;
        const aGravar = gravacao?.fraseId === f.id && gravacao.estado === "a-gravar";
        const aAnalisar = gravacao?.fraseId === f.id && gravacao.estado === "a-analisar";
        const outra = gravacao != null && gravacao.fraseId !== f.id;
        const res = resultados[f.id];
        const rotulo = estado ? ROTULO_ESTADO[estado] : undefined;
        return (
          <View key={f.id} style={{ gap: 12, padding: 16, borderWidth: 1.5, borderColor: aGravar ? cor.errado : cor.linha, borderRadius: raio.md }}>
            <View style={{ gap: 2 }}>
              {rotulo ? (
                <Etiqueta tom="certo" icone={<CheckCircle2 size={16} color={cor.certo} />}>
                  {rotulo}
                </Etiqueta>
              ) : null}
              <Texto v="voz" style={{ fontSize: 19, lineHeight: 28 }}>
                {f.texto}
              </Texto>
              {f.traducao ? (
                <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
                  {f.traducao}
                </Texto>
              ) : null}
            </View>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
              <Botao
                tipo="secundario"
                tamanho="pequeno"
                disabled={!!gravacao}
                onPress={() => ouvir(f)}
                icone={f.inicio != null ? <Play size={18} color={gravacao ? cor.tintaSuave : cor.azulMarca} /> : <Volume2 size={18} color={gravacao ? cor.tintaSuave : cor.azulMarca} />}
              >
                {f.inicio != null ? "Ouvir no vídeo" : "Ouvir"}
              </Botao>
              <Botao
                tipo={aGravar ? "perigo" : "principal"}
                tamanho="pequeno"
                disabled={outra}
                carregando={aAnalisar}
                accessibilityLabel={aGravar ? `Parar a gravação de "${f.texto}"` : `Gravar "${f.texto}"`}
                onPress={() => (aGravar ? void parar(f) : void gravar(f))}
                icone={aAnalisar ? undefined : aGravar ? <Square size={16} color={cor.errado} fill={cor.errado} /> : <Mic size={18} color={outra ? cor.tintaSuave : cor.sobreMarca} />}
              >
                {aAnalisar ? "A ouvir a gravação…" : aGravar ? "Parar" : res ? "Gravar outra vez" : "Gravar"}
              </Botao>
            </View>
            {erro?.fraseId === f.id ? (
              <Texto accessibilityRole="alert" forte cor={cor.errado} style={{ fontSize: 15 }}>
                {erro.texto}
              </Texto>
            ) : null}
            {res ? <Resultado frase={f.texto} r={res} /> : null}
          </View>
        );
      })}

      {palavras.length ? (
        <View style={{ gap: 8 }}>
          <Texto v="tituloXS" accessibilityRole="header">
            Palavras da aula
          </Texto>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {palavras.map((p) => (
              <Pressable
                key={p.id}
                accessibilityRole="button"
                accessibilityLabel={`Ouvir ${p.texto}${p.traducao ? `, ${p.traducao}` : ""}`}
                onPress={() => ouvir(p)}
                style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44, paddingHorizontal: 12, borderRadius: raio.sm, backgroundColor: pressed ? cor.fundoForte : cor.fundoSuave })}
              >
                <Volume2 size={16} color={cor.azulMarca} />
                <Texto forte style={{ fontSize: 15 }}>
                  {p.texto}
                </Texto>
                {p.traducao ? (
                  <Texto suave style={{ fontSize: 15 }}>
                    {p.traducao}
                  </Texto>
                ) : null}
              </Pressable>
            ))}
          </View>
        </View>
      ) : null}

      {limite ? (
        <FolhaOferta aberto aoFechar={() => setLimite(null)} titulo="Já usou as análises de hoje" mensagem={limite.mensagem} oferta={limite.oferta}>
          <Botao tipo="ligacao" larguraTotal onPress={() => setLimite(null)}>
            Continuar a aula
          </Botao>
        </FolhaOferta>
      ) : null}
    </View>
  );
}

const soLetras = (t: string) => t.toLowerCase().replace(/[^a-z0-9']/g, "");

function nivelPalavra(nota: number | null, erro: string) {
  if (erro === "Omission") return { fundo: cor.erradoSuave, cor: cor.tintaSuave, riscado: true, texto: "não se ouviu" };
  if (nota === null) return { fundo: undefined, cor: cor.tinta, texto: "" };
  if (nota >= 80) return { fundo: undefined, cor: cor.certo, texto: `${nota} de 100, bem` };
  if (nota >= 60) return { fundo: cor.realceSuave, cor: cor.tinta, texto: `${nota} de 100, quase` };
  return { fundo: cor.erradoSuave, cor: cor.tinta, sublinhado: true, texto: `${nota} de 100, a treinar` };
}

function Resultado({ frase, r }: { frase: string; r: AnaliseGravacao }) {
  const marcar = new Set(r.palavras.flatMap((p) => p.split(/\s+/)).map(soLetras).filter(Boolean));
  return (
    <View accessibilityLiveRegion="polite" style={{ gap: 6, padding: 12, borderRadius: raio.sm, backgroundColor: r.aceite ? cor.certoSuave : cor.fundoSuave }}>
      <View style={{ flexDirection: "row", alignItems: "baseline", gap: 8 }}>
        <Texto numeros style={{ fontFamily: fonte.numero, fontSize: 26, lineHeight: 32 }}>
          {Math.round(r.nota)}
        </Texto>
        <Texto v="legenda" suave style={{ flex: 1 }}>
          de 100 na pronúncia
        </Texto>
        <Texto v="legenda" forte>
          {r.aceite ? "Repetida com ajuda" : "Tente outra vez"}
        </Texto>
      </View>
      <AvisoAnaliseAproximada fonte={r.fonte} />
      {r.detalhe?.palavras?.length ? (
        <View style={{ gap: 6 }}>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
            {r.detalhe.palavras.map((p, i) => {
              const n = nivelPalavra(p.nota, p.erro_tipo);
              return (
                <Texto
                  key={`${p.palavra}-${i}`}
                  forte
                  accessibilityLabel={n.texto ? `${p.palavra}, ${n.texto}` : p.palavra}
                  cor={n.cor}
                  style={{
                    fontSize: 17,
                    lineHeight: 26,
                    paddingHorizontal: 2,
                    borderRadius: 4,
                    backgroundColor: n.fundo,
                    textDecorationLine: n.riscado ? "line-through" : n.sublinhado ? "underline" : "none",
                    textDecorationColor: cor.errado,
                  }}
                >
                  {p.palavra}
                </Texto>
              );
            })}
          </View>
          <Texto v="mini" suave importantForAccessibility="no">
            verde: bem · amarelo: quase · vermelho: a treinar
          </Texto>
          {r.detalhe.dica ? <Texto style={{ fontSize: 15, lineHeight: 22 }}>{r.detalhe.dica}</Texto> : null}
        </View>
      ) : marcar.size ? (
        <Texto style={{ fontSize: 16, lineHeight: 24 }}>
          {frase.split(/(\s+)/).map((p, i) =>
            marcar.has(soLetras(p)) ? (
              <Texto key={i} style={{ backgroundColor: cor.erradoSuave, textDecorationLine: "underline", textDecorationColor: cor.errado }}>
                {p}
              </Texto>
            ) : (
              p
            )
          )}
        </Texto>
      ) : null}
      {r.mensagem ? <Texto style={{ fontSize: 15, lineHeight: 22 }}>{r.mensagem}</Texto> : null}
    </View>
  );
}

/** "Usar isto numa conversa": as frases da aula e a entrada para a conversa de 3 minutos com o tutor. */
export function UsarNumaConversa({ chapterId, courseId, titulo, dados }: { chapterId: string; courseId: string; titulo: string; dados: FalaDaAula }) {
  const frases = dados.frases.filter((f) => f.tipo === "frase").map((f) => f.texto);
  if (!frases.length) return null;
  const minutos = Math.max(1, Math.round((dados.conversa.max_segundos || 180) / 60));
  const indisponivel = !dados.conversa.disponivel ? (dados.conversa.mensagem ?? "A conversa não está disponível agora.") : null;
  return (
    <View style={{ gap: 16, padding: 20, borderWidth: 1.5, borderColor: cor.azulMarca, borderRadius: raio.md }}>
      <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 12 }}>
        <View style={[balao.medio, { width: 44, height: 44, alignItems: "center", justifyContent: "center", backgroundColor: cor.azulMarca }]}>
          <MessagesSquare size={24} color={cor.sobreMarca} />
        </View>
        <View style={{ flex: 1, gap: 4 }}>
          <Texto v="tituloM" accessibilityRole="header">
            Usar isto numa conversa
          </Texto>
          <Texto suave>{minutos} minutos com o tutor numa situação de trabalho como a do vídeo. Uma frase só fica aprendida quando a diz sozinho, sem o tutor a dizer primeiro.</Texto>
        </View>
      </View>
      <View style={{ gap: 6 }}>
        <Texto v="rotulo">Tente usar estas frases da aula</Texto>
        {frases.map((f, i) => (
          <Texto key={i} v="voz" style={{ fontSize: 18, lineHeight: 26 }}>
            {f}
          </Texto>
        ))}
      </View>
      {indisponivel ? (
        <View style={{ gap: 12 }}>
          <Aviso>{`${indisponivel} Entretanto, pode treinar estas frases na revisão de hoje.`}</Aviso>
          <Botao tipo="secundario" tamanho="medio" href="/revisao">
            Fazer a revisão de hoje
          </Botao>
        </View>
      ) : (
        <Botao
          icone={<Mic size={20} color={cor.sobreMarca} />}
          onPress={() =>
            router.push(`/conversa/aula?capitulo=${encodeURIComponent(chapterId)}&curso=${encodeURIComponent(courseId)}&titulo=${encodeURIComponent(titulo)}`)
          }
        >
          Começar a conversa
        </Botao>
      )}
    </View>
  );
}
