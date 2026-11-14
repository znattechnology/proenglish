/**
 * Primeira entrada (PrimeiraEntrada.dc.html; web app/(licao)/user/primeira-entrada/page.tsx):
 * 1. área e meta diária; 2. nível — o teste falado com o tutor (/conversa/teste-nivel, do agente
 * CONVERSA) ou, em alternativa, 5 perguntas escritas; 3. o curso por onde começar.
 *
 * Volta do teste falado: o ecrã do teste chama `router.dismissTo("/primeira-entrada?nivel=B1")` (aberto com `?volta=/primeira-entrada`).
 * Recebido o `nivel`, guardamos { nivel, acolhimento: "concluido" } e passamos ao passo 3.
 */
import { router, Stack, useFocusEffect, useLocalSearchParams } from "expo-router";
import { BookOpen, Briefcase, Check, Fuel, Globe, Landmark, Laptop, Mic, Scale, Stethoscope } from "lucide-react-native";
import { type ComponentType, useCallback, useEffect, useRef, useState } from "react";
import { Pressable, View } from "react-native";
import { mensagemErro } from "@/api/erros";
import {
  type Preferencias,
  usePeCursosPraticaQuery,
  usePeCursosVideoDaAreaQuery,
  usePeEscolherCursoPraticaMutation,
  usePeGuardarPreferenciasMutation,
  usePeMetaQuery,
  usePeMudarMetaMutation,
} from "@/dominios/conta/api";
import { type NivelCefr, OPCOES_NIVEL, eNivel, nivelDoTeste, nomeCompletoNivel, sugerirPorNivel } from "@/dominios/conta/niveis";
import { AREAS, METAS, PERGUNTAS } from "@/dominios/conta/primeiraEntrada";
import { primeiroNome, useSessao } from "@/sessao/ContextoSessao";
import { Aviso, BalaoFala, Botao, Cartao, Ecra, Osso, Texto, Titulo } from "@/ui";
import { balao, cor, fonte, raio } from "@/tema";

type IconeLucide = ComponentType<{ size?: number; color?: string }>;
const ICONES: Record<string, IconeLucide> = {
  "Industry English": Fuel,
  "Financial English": Landmark,
  "Business English": Briefcase,
  "Medical English": Stethoscope,
  "Legal English": Scale,
  "Technical English": Laptop,
  "General English": Globe,
};

const ERRO_GUARDAR = "Não foi possível guardar. Tente outra vez.";

export default function PrimeiraEntrada() {
  const p = useLocalSearchParams<{ nivel?: string; perguntas?: string }>();
  const { utilizador, actualizarUtilizador } = useSessao();
  const pref = (utilizador?.preferences ?? {}) as Preferencias;
  const [passo, setPasso] = useState<1 | 2 | 3>(1);
  const [area, setArea] = useState<string | null>(null);
  const { data: metaGuardada } = usePeMetaQuery();
  const [metaEscolhida, setMeta] = useState<number | null>(null);
  const meta = metaEscolhida ?? metaGuardada?.daily_goal_minutes ?? 10;
  const [nivel, setNivel] = useState<NivelCefr | null>(null);
  const [porPerguntas, setPorPerguntas] = useState(false);
  const [guardar, { isLoading: aGuardar }] = usePeGuardarPreferenciasMutation();
  const [mudarMeta, { isLoading: aMudarMeta }] = usePeMudarMetaMutation();
  const [erro, setErro] = useState<string | null>(null);
  const areaEscolhida = area ?? pref.area ?? null;
  const abriuTeste = useRef(false);
  const nivelTratado = useRef<string | null>(null);

  // Volta do teste falado com ?perguntas=1: a pessoa preferiu as perguntas escritas.
  useFocusEffect(
    useCallback(() => {
      if (p.perguntas !== "1") return;
      setPasso(2);
      setPorPerguntas(true);
    }, [p.perguntas])
  );

  const terminarTeste = useCallback(
    async (n: NivelCefr) => {
      setErro(null);
      try {
        await guardar({ nivel: n, acolhimento: "concluido" }).unwrap();
        setNivel(n);
        setPasso(3);
        void actualizarUtilizador();
      } catch (e) {
        setPasso(2);
        setErro(mensagemErro(e, ERRO_GUARDAR));
      }
    },
    [guardar, actualizarUtilizador]
  );

  // Volta do teste falado com ?nivel=XX.
  useEffect(() => {
    const n = p.nivel?.toUpperCase();
    if (!eNivel(n) || nivelTratado.current === n) return;
    nivelTratado.current = n;
    void terminarTeste(n);
  }, [p.nivel, terminarTeste]);

  // Se o teste falado guardou ele próprio o nível, ao voltar passa-se ao passo 3.
  useFocusEffect(
    useCallback(() => {
      if (abriuTeste.current) void actualizarUtilizador();
    }, [actualizarUtilizador])
  );
  useEffect(() => {
    if (abriuTeste.current && passo === 2 && pref.acolhimento === "concluido" && eNivel(pref.nivel)) {
      setNivel(pref.nivel);
      setPasso(3);
    }
  }, [pref.acolhimento, pref.nivel, passo]);

  const continuarPasso1 = async () => {
    if (!areaEscolhida) return;
    setErro(null);
    try {
      await Promise.all([guardar({ area: areaEscolhida }).unwrap(), mudarMeta(meta).unwrap()]);
      setPasso(2);
    } catch (e) {
      setErro(mensagemErro(e, ERRO_GUARDAR));
    }
  };

  const cabecalho = <Progresso passo={passo} />;

  return (
    <>
      <Stack.Screen options={{ gestureEnabled: false }} />
      {passo === 1 ? (
        <Ecra
          cabecalho={cabecalho}
          style={{ gap: 22, paddingTop: 8 }}
          rodape={
            <>
              <Texto v="legenda" suave>
                A seguir: uma conversa curta com o tutor para saber o seu nível. Depois começa a primeira lição.
              </Texto>
              {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
              <Botao larguraTotal disabled={!areaEscolhida} carregando={aGuardar || aMudarMeta} onPress={() => void continuarPasso1()}>
                {aGuardar || aMudarMeta ? "A guardar…" : "Continuar"}
              </Botao>
              {!areaEscolhida ? (
                <Texto v="legenda" suave centro>
                  Escolha a área para continuar.
                </Texto>
              ) : null}
            </>
          }
        >
          <Titulo v="tituloM" style={{ fontSize: 24, lineHeight: 30 }}>
            {`${primeiroNome(utilizador?.name) ? `Olá, ${primeiroNome(utilizador?.name)}. ` : "Olá. "}Vamos preparar o seu curso.`}
          </Titulo>
          <EscolherArea valor={areaEscolhida} aoMudar={setArea} />
          <EscolherMeta valor={meta} aoMudar={setMeta} />
        </Ecra>
      ) : passo === 2 ? (
        <Ecra cabecalho={cabecalho} style={{ gap: 24, paddingTop: 8 }}>
          {porPerguntas ? (
            <Perguntas aoTerminar={(n) => void terminarTeste(n)} erro={erro} aGuardar={aGuardar} aoPreferirConversa={() => setPorPerguntas(false)} />
          ) : (
            <TesteFalado
              erro={erro}
              aoComecar={() => {
                abriuTeste.current = true;
                router.push("/conversa/teste-nivel?volta=/primeira-entrada");
              }}
              aoPreferirPerguntas={() => setPorPerguntas(true)}
            />
          )}
        </Ecra>
      ) : (
        <Ecra cabecalho={cabecalho} style={{ gap: 24, paddingTop: 8 }}>
          <Pronto area={areaEscolhida} nivel={nivel ?? "B1"} />
        </Ecra>
      )}
    </>
  );
}

/** "Passo 1 de 3" e as três barras. */
function Progresso({ passo }: { passo: number }) {
  return (
    <View style={{ paddingHorizontal: 20, paddingTop: 24, paddingBottom: 8, gap: 8 }}>
      <Texto v="rotulo" suave>{`Passo ${passo} de 3`}</Texto>
      <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={{ flexDirection: "row", gap: 6 }}>
        {[1, 2, 3].map((n) => (
          <View key={n} style={{ flex: 1, height: 6, borderRadius: raio.pilula, backgroundColor: n <= passo ? cor.azulVivo : cor.fundoForte }} />
        ))}
      </View>
    </View>
  );
}

function EscolherArea({ valor, aoMudar }: { valor: string | null; aoMudar: (v: string) => void }) {
  return (
    <View style={{ gap: 12 }}>
      <Titulo v="tituloXS" style={{ fontFamily: fonte.tituloMedio, fontSize: 18, lineHeight: 24 }}>
        Em que área trabalha?
      </Titulo>
      <View accessibilityRole="radiogroup" accessibilityLabel="Área" style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
        {AREAS.map((a) => {
          const sel = a.valor === valor;
          const Icone = ICONES[a.valor] ?? BookOpen;
          return (
            <Pressable
              key={a.valor}
              accessibilityRole="radio"
              accessibilityState={{ checked: sel }}
              accessibilityLabel={a.nome}
              onPress={() => aoMudar(a.valor)}
              style={({ pressed }) => ({
                width: "48%",
                flexGrow: 1,
                gap: 8,
                padding: 14,
                borderRadius: raio.md,
                borderWidth: sel ? 2 : 1.5,
                borderColor: sel ? cor.azulMarca : cor.linha,
                backgroundColor: sel || pressed ? cor.fundoSuave : cor.fundo,
              })}
            >
              <View style={[balao.pequeno, { width: 40, height: 40, borderTopLeftRadius: 14, borderTopRightRadius: 14, borderBottomRightRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: sel ? cor.azulMarca : cor.fundoForte }]}>
                <Icone size={22} color={sel ? cor.sobreMarca : cor.tinta} />
              </View>
              <Texto forte={sel} style={{ lineHeight: 22 }}>
                {a.nome}
              </Texto>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function EscolherMeta({ valor, aoMudar }: { valor: number; aoMudar: (v: number) => void }) {
  return (
    <View style={{ gap: 12 }}>
      <Titulo v="tituloXS" style={{ fontFamily: fonte.tituloMedio, fontSize: 18, lineHeight: 24 }}>
        Quanto tempo por dia?
      </Titulo>
      <View accessibilityRole="radiogroup" accessibilityLabel="Meta diária" style={{ flexDirection: "row", gap: 8 }}>
        {METAS.map((m) => {
          const sel = m.min === valor;
          return (
            <Pressable
              key={m.min}
              accessibilityRole="radio"
              accessibilityState={{ checked: sel }}
              accessibilityLabel={`${m.min} minutos, ${m.nome}`}
              onPress={() => aoMudar(m.min)}
              style={({ pressed }) => ({
                flex: 1,
                minHeight: 60,
                alignItems: "center",
                justifyContent: "center",
                paddingVertical: 10,
                paddingHorizontal: 4,
                borderRadius: raio.sm,
                borderWidth: sel ? 2 : 1.5,
                borderColor: sel ? cor.azulMarca : cor.linhaForte,
                backgroundColor: sel ? cor.azulMarca : pressed ? cor.fundoSuave : cor.fundo,
              })}
            >
              <Texto numeros cor={sel ? cor.sobreMarca : cor.tinta} style={{ fontFamily: fonte.titulo, fontSize: 17, lineHeight: 22 }}>
                {`${m.min} min`}
              </Texto>
              <Texto v="mini" cor={sel ? cor.sobreMarca : cor.tinta} style={{ fontSize: 13, lineHeight: 18 }}>
                {m.nome}
              </Texto>
            </Pressable>
          );
        })}
      </View>
      <Texto v="legenda" suave>
        Pode mudar isto nas definições.
      </Texto>
    </View>
  );
}

/** Passo 2, caminho principal: abre o teste de nível falado (ecrã do agente CONVERSA). */
function TesteFalado({ erro, aoComecar, aoPreferirPerguntas }: { erro: string | null; aoComecar: () => void; aoPreferirPerguntas: () => void }) {
  return (
    <>
      <View style={{ gap: 8 }}>
        <Titulo>Qual é o seu nível a falar?</Titulo>
        <Texto suave>
          Uma conversa curta com o tutor, em inglês. Começa com perguntas fáceis sobre si e vai subindo: o seu trabalho, um problema que resolveu, uma opinião. No fim mostramos o seu nível em cada competência.
        </Texto>
      </View>
      <View style={{ gap: 10 }}>
        {[
          "Não gasta os minutos de conversa do seu plano.",
          "Não há respostas erradas: o tutor não corrige nem dá notas durante a conversa.",
          "A conversa não é gravada. Guardamos só o texto do que disse.",
        ].map((t) => (
          <View key={t} style={{ flexDirection: "row", gap: 10 }}>
            <Check size={18} color={cor.certo} style={{ marginTop: 3 }} />
            <Texto v="legenda" style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>
              {t}
            </Texto>
          </View>
        ))}
      </View>
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
      <View style={{ gap: 8, marginTop: "auto" }}>
        <Botao larguraTotal icone={<Mic size={20} color={cor.sobreMarca} />} onPress={aoComecar}>
          Começar a conversa
        </Botao>
        <Botao tipo="ligacao" tamanho="medio" style={{ alignSelf: "center" }} onPress={aoPreferirPerguntas}>
          Prefiro responder a perguntas
        </Botao>
      </View>
    </>
  );
}

/** Passo 2, alternativa: 5 perguntas escritas, ou escolher o nível à mão. */
function Perguntas({ aoTerminar, erro, aGuardar, aoPreferirConversa }: { aoTerminar: (n: NivelCefr) => void; erro: string | null; aGuardar: boolean; aoPreferirConversa: () => void }) {
  const [i, setI] = useState(0);
  const [respostas, setRespostas] = useState<boolean[]>([]);
  const [escolha, setEscolha] = useState<number | null>(null);
  const [escolherAMao, setEscolherAMao] = useState(false);
  const p = PERGUNTAS[i];
  const ultima = i === PERGUNTAS.length - 1;

  const seguinte = (acertou: boolean) => {
    const novas = [...respostas];
    novas[i] = acertou;
    setRespostas(novas);
    setEscolha(null);
    if (ultima) aoTerminar(nivelDoTeste(novas.filter(Boolean).length));
    else setI(i + 1);
  };

  if (escolherAMao)
    return (
      <>
        <Titulo>Qual é o seu nível de inglês?</Titulo>
        <View style={{ gap: 10 }}>
          {OPCOES_NIVEL.map((n) => (
            <Pressable
              key={n.valor}
              accessibilityRole="button"
              disabled={aGuardar}
              onPress={() => aoTerminar(n.valor)}
              style={({ pressed }) => ({ minHeight: 56, paddingVertical: 10, paddingHorizontal: 16, gap: 2, borderRadius: raio.sm, borderWidth: 2, borderColor: cor.azulMarca, backgroundColor: pressed ? cor.fundoSuave : cor.fundo })}
            >
              <Texto forte cor={cor.azulMarca}>
                {n.nome}
              </Texto>
              <Texto v="legenda" suave>
                {n.descricao}
              </Texto>
            </Pressable>
          ))}
        </View>
        {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
        <Botao tipo="ligacao" onPress={() => setEscolherAMao(false)}>
          Fazer as perguntas
        </Botao>
      </>
    );

  return (
    <>
      <View style={{ gap: 8 }}>
        <Titulo>Complete a frase</Titulo>
        <Texto suave>{`Pergunta ${i + 1} de ${PERGUNTAS.length}. Não há problema em errar: serve só para escolher por onde começa.`}</Texto>
      </View>
      <BalaoFala>
        <Texto v="voz" cor={cor.sobreMarca} style={{ fontSize: 24, lineHeight: 34 }}>
          {p.frase[0]}
          <Texto v="voz" cor={cor.sobreMarca} style={{ fontFamily: fonte.textoForte, fontSize: 24, lineHeight: 34, fontStyle: "normal", textDecorationLine: "underline", textDecorationColor: cor.realce }}>
            {escolha === null ? "   " : ` ${p.opcoes[escolha]} `}
          </Texto>
          {p.frase[1]}
        </Texto>
      </BalaoFala>
      <View accessibilityRole="radiogroup" accessibilityLabel="Opções" style={{ gap: 10 }}>
        {p.opcoes.map((o, k) => {
          const sel = escolha === k;
          return (
            <Pressable
              key={o}
              accessibilityRole="radio"
              accessibilityState={{ checked: sel }}
              accessibilityLanguage="en"
              onPress={() => setEscolha(k)}
              style={({ pressed }) => ({
                minHeight: 52,
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                paddingHorizontal: 16,
                borderRadius: raio.sm,
                borderWidth: sel ? 2 : 1.5,
                borderColor: sel ? cor.azulMarca : cor.linhaForte,
                backgroundColor: sel || pressed ? cor.fundoSuave : cor.fundo,
              })}
            >
              {sel ? <Check size={16} color={cor.tinta} /> : null}
              <Texto forte style={{ fontSize: 17 }}>
                {o}
              </Texto>
            </Pressable>
          );
        })}
      </View>
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
      <View style={{ gap: 4 }}>
        <Botao larguraTotal disabled={escolha === null} carregando={aGuardar} onPress={() => escolha !== null && seguinte(escolha === p.certa)}>
          {ultima ? "Ver o meu nível" : "Seguinte"}
        </Botao>
        <Botao tipo="ligacao" tamanho="pequeno" style={{ alignSelf: "center" }} disabled={aGuardar} onPress={() => seguinte(false)}>
          Não sei
        </Botao>
      </View>
      <View style={{ flexDirection: "row", flexWrap: "wrap", columnGap: 24 }}>
        <Botao tipo="ligacao" tamanho="pequeno" onPress={() => setEscolherAMao(true)}>
          Já sei o meu nível
        </Botao>
        <Botao tipo="ligacao" tamanho="pequeno" onPress={aoPreferirConversa}>
          Fazer o teste a falar
        </Botao>
      </View>
    </>
  );
}

/** Passo 3: o nível e o curso por onde começar. */
function Pronto({ area, nivel }: { area: string | null; nivel: NivelCefr }) {
  const { data: videos, isLoading: aCarregarVideo } = usePeCursosVideoDaAreaQuery(area);
  const { data: praticas, isLoading: aCarregarPratica, isError: erroPratica, refetch } = usePeCursosPraticaQuery();
  const [escolher, { isLoading: aEscolher }] = usePeEscolherCursoPraticaMutation();
  const [erro, setErro] = useState<string | null>(null);

  const daArea = (praticas ?? []).filter((c) => c.category === area);
  const pratica = sugerirPorNivel(daArea, nivel) ?? sugerirPorNivel(praticas ?? [], nivel);
  const video = sugerirPorNivel(videos ?? [], nivel);

  return (
    <>
      <View style={{ gap: 8 }}>
        <Titulo>{`O seu nível: ${nomeCompletoNivel(nivel)}`}</Titulo>
        <Texto suave>Escolhemos o curso por onde começar. Pode mudar de nível e de área nas definições.</Texto>
      </View>

      {aCarregarPratica ? (
        <Osso altura={170} />
      ) : erroPratica ? (
        <Aviso tom="erro" accao={<Botao tipo="ligacao" tamanho="pequeno" onPress={() => void refetch()}>Tentar outra vez</Botao>}>
          Não conseguimos carregar os cursos de prática.
        </Aviso>
      ) : pratica ? (
        <Cartao style={{ gap: 10, padding: 20 }}>
          <Texto v="legenda" forte suave>
            Laboratório de prática
          </Texto>
          <Titulo v="tituloS">{pratica.title}</Titulo>
          <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
            Lições de 5 minutos com exercícios de ouvir, falar e escrever.
          </Texto>
          {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
          <Botao
            tipo="realce"
            larguraTotal
            carregando={aEscolher}
            onPress={async () => {
              setErro(null);
              try {
                await escolher(pratica.id).unwrap();
                router.dismissTo("/praticar");
              } catch {
                setErro("Não foi possível abrir o curso. Tente outra vez.");
              }
            }}
          >
            {aEscolher ? "A preparar…" : "Começar a primeira lição"}
          </Botao>
        </Cartao>
      ) : null}

      {aCarregarVideo ? null : video ? (
        <Cartao suave style={{ padding: 20 }}>
          <Texto v="legenda" forte suave>
            Curso em vídeo da sua área
          </Texto>
          <Texto forte style={{ fontSize: 18, lineHeight: 24 }}>
            {video.title}
          </Texto>
          <Botao tipo="ligacao" href={`/curso/${video.courseId}`}>
            Ver o curso
          </Botao>
        </Cartao>
      ) : null}

      <Botao tipo="ligacao" style={{ marginTop: "auto" }} onPress={() => router.dismissTo("/inicio")}>
        Ir para o início
      </Botao>
    </>
  );
}
