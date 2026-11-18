/**
 * Primeira entrada (web app/(licao)/user/primeira-entrada/page.tsx):
 * 1. o que quer aprender (inglês geral ou de uma área) e a meta diária;
 * 2. o nível em que começa o English Communication Skills, de A1 a C1: o A1 entra logo; outro
 *    nível pede um teste escrito com perguntas dos níveis abaixo, feito aqui mesmo (TODO: o início
 *    do teste de colocação espera o novo contrato da API; ver iniciarTesteColocacao);
 * 3. o curso onde ficou inscrito.
 * Quem decide o nível e faz a inscrição é o servidor (/student/colocacao/), que também guarda
 * { nivel, acolhimento: "concluido" } nas preferências.
 */
import { router, Stack } from "expo-router";
import { BookOpen, Briefcase, Check, Fuel, Globe, Landmark, Laptop, Lock, Scale, Stethoscope } from "lucide-react-native";
import { type ComponentType, useState } from "react";
import { Pressable, View } from "react-native";
import { mensagemErro } from "@/api/erros";
import { dataHora, PerguntasTeste, REGRA_SAIR_DA_APP } from "@/componentes/cursos/PerguntasTeste";
import { type Preferencias, usePeGuardarPreferenciasMutation, usePeMetaQuery, usePeMudarMetaMutation } from "@/dominios/conta/api";
import { AREA_GERAL, AREAS, METAS, rotuloArea } from "@/dominios/conta/primeiraEntrada";
import { type NivelColocacao, type NivelDisponivel, type ResultadoColocacao, testeNecessario, useColocacaoQuery, useColocarMutation, useIniciarTesteColocacaoMutation } from "@/dominios/cursos/colocacao";
import type { TentativaTeste } from "@/dominios/cursos/testeBasico";
import { primeiroNome, useSessao } from "@/sessao/ContextoSessao";
import { ACarregar, Aviso, Botao, Cartao, Ecra, Numero, Osso, Texto, Titulo } from "@/ui";
import { balao, cor, fonte, raio } from "@/tema";


type IconeLucide = ComponentType<{ size?: number; color?: string }>;
const ICONES: Record<string, IconeLucide> = {
  [AREA_GERAL]: Globe,
  "Industry English": Fuel,
  "Financial English": Landmark,
  "Business English": Briefcase,
  "Medical English": Stethoscope,
  "Legal English": Scale,
  "Technical English": Laptop,
};

const ERRO_GUARDAR = "Não foi possível guardar. Tente outra vez.";

export default function PrimeiraEntrada() {
  const { utilizador } = useSessao();
  const pref = (utilizador?.preferences ?? {}) as Preferencias;
  const [passo, setPasso] = useState<1 | 2 | 3>(1);
  const [area, setArea] = useState<string | null>(null);
  const { data: metaGuardada } = usePeMetaQuery();
  const [metaEscolhida, setMeta] = useState<number | null>(null);
  const meta = metaEscolhida ?? metaGuardada?.daily_goal_minutes ?? 10;
  const [guardar, { isLoading: aGuardar }] = usePeGuardarPreferenciasMutation();
  const [mudarMeta, { isLoading: aMudarMeta }] = usePeMudarMetaMutation();
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<{ r: ResultadoColocacao; tentativa: TentativaTeste | null } | null>(null);
  const areaEscolhida = area ?? pref.area ?? null;

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

  return (
    <>
      <Stack.Screen options={{ gestureEnabled: false }} />
      {passo === 1 ? (
        <Ecra
          cabecalho={<Progresso passo={1} />}
          style={{ gap: 22, paddingTop: 8 }}
          rodape={
            <>
              <Texto v="legenda" suave>
                A seguir: escolha o nível em que quer começar.
              </Texto>
              {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
              <Botao larguraTotal disabled={!areaEscolhida} carregando={aGuardar || aMudarMeta} onPress={() => void continuarPasso1()}>
                {aGuardar || aMudarMeta ? "A guardar…" : "Continuar"}
              </Botao>
              {!areaEscolhida ? (
                <Texto v="legenda" suave centro>
                  Escolha o que quer aprender para continuar.
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
      ) : passo === 2 || !resultado ? (
        <EscolherNivel
          aoColocar={(r, tentativa) => {
            setResultado({ r, tentativa });
            setPasso(3);
          }}
        />
      ) : (
        <Pronto r={resultado.r} tentativa={resultado.tentativa} area={areaEscolhida} />
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
        O que quer aprender?
      </Titulo>
      <View accessibilityRole="radiogroup" accessibilityLabel="O que quer aprender" style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
        {AREAS.map((a) => {
          const sel = a.valor === valor;
          const geral = a.valor === AREA_GERAL;
          const Icone = ICONES[a.valor] ?? BookOpen;
          const rotulo = rotuloArea(a);
          return (
            <Pressable
              key={a.valor}
              accessibilityRole="radio"
              accessibilityState={{ checked: sel }}
              accessibilityLabel={geral ? `${rotulo}. English Communication Skills, para qualquer profissão` : rotulo}
              onPress={() => aoMudar(a.valor)}
              style={({ pressed }) => ({
                width: geral ? "100%" : "48%",
                flexGrow: 1,
                flexDirection: geral ? "row" : "column",
                alignItems: geral ? "center" : "flex-start",
                gap: geral ? 12 : 8,
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
              <View style={{ flex: geral ? 1 : undefined, gap: 2 }}>
                <Texto forte={sel || geral} style={{ lineHeight: 22 }}>
                  {rotulo}
                </Texto>
                {geral ? (
                  <Texto v="legenda" suave>
                    <Texto v="legenda" suave accessibilityLanguage="en">
                      English Communication Skills
                    </Texto>
                    , para qualquer profissão
                  </Texto>
                ) : null}
              </View>
            </Pressable>
          );
        })}
      </View>
      <Texto v="legenda" suave>
        Todos começam pelo inglês geral. Os cursos de cada área abrem-se a partir do nível básico (A2).
      </Texto>
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

/**
 * Entra sem fazer teste: A1, níveis anteriores já provados, ou já fez o teste de colocação há menos
 * de 24 horas (o servidor coloca-o pelo resultado desse teste).
 */
const entraSemTeste = (n: NivelDisponivel, espera: string | null) => n.pode_entrar || !!espera;

/** Passo 2: o nível em que começa. O teste de colocação, quando é preciso, faz-se aqui mesmo. */
function EscolherNivel({ aoColocar }: { aoColocar: (r: ResultadoColocacao, tentativa: TentativaTeste | null) => void }) {
  const { actualizarUtilizador } = useSessao();
  const { data, isLoading, isError, refetch } = useColocacaoQuery();
  const [colocar, { isLoading: aColocar }] = useColocarMutation();
  const [escolhido, setEscolhido] = useState<NivelColocacao | null>(null);
  const [emTeste, setEmTeste] = useState<NivelDisponivel | null>(null);
  // O teste entregue, enquanto o servidor guarda o nível (ou se falhar, para tentar outra vez).
  const [entregue, setEntregue] = useState<TentativaTeste | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const aplicar = async (nivel: NivelColocacao, tentativa: TentativaTeste | null) => {
    setErro(null);
    try {
      const r = await colocar(nivel).unwrap();
      void actualizarUtilizador();
      aoColocar(r, tentativa);
    } catch (e) {
      // O servidor pede o teste: abre-se a entrada do teste de colocação.
      const n = data?.niveis.find((x) => x.nivel === nivel);
      if (testeNecessario(e) && n) {
        setEntregue(null);
        setEmTeste(n);
      } else setErro(mensagemErro(e, "Não foi possível guardar o nível. Tente outra vez."));
    }
  };

  const cabecalho = <Progresso passo={2} />;
  // Um teste de colocação a meio retoma-se logo (o tempo continua a contar).
  const aMeio = data?.em_curso?.perguntas ? data.em_curso : null;
  const noTeste = emTeste ?? (aMeio ? data?.niveis.find((n) => n.nivel === aMeio.para) ?? null : null);

  if (noTeste && entregue)
    return (
      <Ecra
        cabecalho={cabecalho}
        style={{ gap: 20, paddingTop: 8 }}
        rodape={
          erro ? (
            <Botao larguraTotal carregando={aColocar} onPress={() => void aplicar(noTeste.nivel, entregue)}>
              Tentar outra vez
            </Botao>
          ) : undefined
        }
      >
        <Titulo>Teste entregue</Titulo>
        {erro ? <Aviso tom="erro">{erro}</Aviso> : <ACarregar linhas={2} rotulo="A guardar o seu nível" />}
      </Ecra>
    );
  if (noTeste && data)
    return (
      <TesteDeColocacao
        n={noTeste}
        aMeio={aMeio}
        aoVoltar={() => setEmTeste(null)}
        aoEntregar={(t) => {
          setEntregue(t);
          void aplicar(noTeste.nivel, t);
        }}
      />
    );
  if (isLoading)
    return (
      <Ecra cabecalho={cabecalho} style={{ gap: 12, paddingTop: 8 }}>
        <Osso altura={36} />
        {[0, 1, 2, 3, 4].map((i) => (
          <Osso key={i} altura={96} />
        ))}
      </Ecra>
    );
  if (isError || !data)
    return (
      <Ecra cabecalho={cabecalho} style={{ gap: 16, paddingTop: 8 }}>
        <Titulo>Não conseguimos carregar os níveis</Titulo>
        <Botao onPress={() => void refetch()}>Tentar outra vez</Botao>
      </Ecra>
    );

  const sel = data.niveis.find((n) => n.nivel === escolhido) ?? null;
  const espera = data.proxima_tentativa_em;
  const textoBotao = !sel
    ? "Escolha um nível"
    : aColocar
      ? "A guardar…"
      : entraSemTeste(sel, espera)
        ? sel.pode_entrar
          ? `Começar no ${sel.nivel}`
          : "Continuar"
        : "Fazer o teste de colocação";

  return (
    <Ecra
      cabecalho={cabecalho}
      style={{ gap: 20, paddingTop: 8 }}
      rodape={
        <>
          {sel && !sel.pode_entrar && espera ? (
            <Aviso>{`Já fez o teste de colocação. Pode repeti-lo a partir de ${dataHora(espera)}; até lá, começa no nível que esse teste mostrou.`}</Aviso>
          ) : null}
          {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
          <Botao
            larguraTotal
            disabled={!sel}
            carregando={aColocar}
            onPress={() => {
              if (!sel) return;
              if (entraSemTeste(sel, espera)) void aplicar(sel.nivel, null);
              else setEmTeste(sel);
            }}
          >
            {textoBotao}
          </Botao>
        </>
      }
    >
      <View style={{ gap: 8 }}>
        <Titulo>Em que nível quer começar?</Titulo>
        <Texto suave>
          {`No A1 começa logo. Para outro nível, faz um teste escrito de 30 perguntas com todos os níveis abaixo do que escolheu: começa no nível a seguir ao último em que acertar ${data.regras.aprovacao}%, a contar do A1.`}
        </Texto>
      </View>
      <View accessibilityRole="radiogroup" accessibilityLabel="Níveis" style={{ gap: 10 }}>
        {data.niveis.map((n) => {
          const activo = n.nivel === escolhido;
          const aberto = n.pode_entrar;
          const estado =
            n.niveis_teste.length === 0 ? "Começa logo" : n.pode_entrar ? "Já tem os níveis anteriores" : `Teste de ${n.perguntas} perguntas: ${n.niveis_teste.join(", ")}`;
          return (
            <Pressable
              key={n.nivel}
              accessibilityRole="radio"
              accessibilityState={{ checked: activo }}
              accessibilityLabel={`${n.nivel}, ${n.nome}. ${n.descricao}. ${estado}`}
              onPress={() => setEscolhido(n.nivel)}
              style={({ pressed }) => ({
                flexDirection: "row",
                alignItems: "flex-start",
                gap: 14,
                paddingHorizontal: 14,
                paddingVertical: 14,
                borderRadius: raio.md,
                borderWidth: activo ? 2 : 1.5,
                borderColor: activo ? cor.azulMarca : cor.linha,
                backgroundColor: activo || pressed ? cor.fundoSuave : cor.fundo,
              })}
            >
              <View style={[balao.pequeno, { width: 48, height: 48, borderTopLeftRadius: 16, borderTopRightRadius: 16, borderBottomRightRadius: 16, alignItems: "center", justifyContent: "center", backgroundColor: activo ? cor.azulMarca : cor.fundoForte }]}>
                <Texto cor={activo ? cor.sobreMarca : cor.azulMarca} style={{ fontFamily: fonte.titulo, fontSize: 18, lineHeight: 22 }}>
                  {n.nivel}
                </Texto>
              </View>
              <View style={{ flex: 1, gap: 2 }}>
                <Texto forte style={{ lineHeight: 22 }}>
                  {n.nome}
                </Texto>
                <Texto v="legenda" suave>
                  {n.descricao}
                </Texto>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 4 }}>
                  {aberto ? <Check size={16} color={cor.certo} /> : <Lock size={16} color={cor.azulMarca} />}
                  <Texto v="legenda" forte cor={aberto ? cor.certo : cor.azulMarca}>
                    {estado}
                  </Texto>
                </View>
              </View>
            </Pressable>
          );
        })}
      </View>
    </Ecra>
  );
}

/** O teste de colocação, aqui mesmo: as regras e depois as perguntas. */
function TesteDeColocacao({ n, aMeio, aoVoltar, aoEntregar }: { n: NivelDisponivel; aMeio: TentativaTeste | null; aoVoltar: () => void; aoEntregar: (t: TentativaTeste) => void }) {
  const [iniciar, { isLoading: aIniciar }] = useIniciarTesteColocacaoMutation();
  const [tentativa, setTentativa] = useState<TentativaTeste | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const cabecalho = <Progresso passo={2} />;
  const aDecorrer = tentativa ?? aMeio;

  if (aDecorrer?.perguntas) return <PerguntasTeste key={aDecorrer.id} t={aDecorrer} aoEntregar={aoEntregar} aoSair={aoVoltar} />;

  return (
    <Ecra
      cabecalho={cabecalho}
      style={{ gap: 20, paddingTop: 8 }}
      rodape={
        <>
          {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
          <Botao
            larguraTotal
            carregando={aIniciar}
            onPress={async () => {
              setErro(null);
              try {
                setTentativa(await iniciar(n.nivel).unwrap());
              } catch (e) {
                setErro(mensagemErro(e, "Não foi possível abrir o teste. Tente outra vez."));
              }
            }}
          >
            {aIniciar ? "A abrir o teste…" : "Começar o teste"}
          </Botao>
          <Botao tipo="ligacao" tamanho="medio" style={{ alignSelf: "center" }} onPress={aoVoltar}>
            Escolher outro nível
          </Botao>
        </>
      }
    >
      <View style={{ gap: 8 }}>
        <Titulo>{`Teste para começar no ${n.nivel}`}</Titulo>
        <Texto suave>
          {`O teste tem perguntas de ${n.niveis_teste.join(", ")}. Cada nível conta em separado: começa no nível a seguir ao último em que acertar 70%, a contar do A1. Se acertar em todos, começa no ${n.nivel}.`}
        </Texto>
      </View>
      <View style={{ flexDirection: "row", gap: 8 }}>
        <Numero rotulo="Perguntas" valor={n.perguntas} />
        <Numero rotulo="Minutos" valor={n.minutos} />
        <Numero rotulo="Certas em cada nível" valor="70%" />
      </View>
      <View style={{ gap: 10 }}>
        {[
          "São perguntas de escolha, uma de cada vez. Pode voltar atrás e mudar a resposta.",
          "O tempo começa a contar quando abrir o teste e não pára se sair da app.",
          "Só pode repetir o teste 24 horas depois.",
        ].map((t) => (
          <View key={t} style={{ flexDirection: "row", gap: 10 }}>
            <Check size={18} color={cor.azulMarca} style={{ marginTop: 4 }} />
            <Texto style={{ flex: 1 }}>{t}</Texto>
          </View>
        ))}
      </View>
      <Aviso tom="realce" titulo="Fique na app até entregar">
        <Texto>{REGRA_SAIR_DA_APP}</Texto>
      </Aviso>
    </Ecra>
  );
}

/** Passo 3: o nível e o curso onde ficou inscrito. */
function Pronto({ r, tentativa, area }: { r: ResultadoColocacao; tentativa: TentativaTeste | null; area: string | null }) {
  const sector = !!area && area !== AREA_GERAL;
  const nomeArea = AREAS.find((a) => a.valor === area)?.nome;
  const temBasico = ["B1", "B2", "C1"].includes(r.nivel);
  const resultado = tentativa?.resultado ? Object.entries(tentativa.resultado) : [];

  let texto: string | null = null;
  if (r.no_nivel_escolhido) texto = tentativa ? "Passou em todos os níveis do teste." : null;
  else texto = `Escolheu o ${r.escolhido}, mas o teste mostrou que o melhor é começar no ${r.nivel}. Pode repetir o teste daqui a 24 horas para subir.`;

  return (
    <Ecra
      cabecalho={<Progresso passo={3} />}
      style={{ gap: 24, paddingTop: 8 }}
      rodape={
        <Botao tipo="ligacao" larguraTotal onPress={() => router.dismissTo("/inicio")}>
          Ir para o início
        </Botao>
      }
    >
      <View style={{ gap: 8 }}>
        <Titulo>{`Começa no ${r.nivel}`}</Titulo>
        {texto ? <Texto suave>{texto}</Texto> : null}
      </View>

      {resultado.length ? (
        <View accessibilityLabel="Resultado por nível" style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {resultado.map(([nivel, x]) => (
            <View key={nivel} style={{ flexBasis: "47%", flexGrow: 1, gap: 2, paddingHorizontal: 14, paddingVertical: 10, borderRadius: raio.md, backgroundColor: x?.aprovado ? cor.certoSuave : cor.fundoSuave }}>
              <Texto style={{ fontFamily: fonte.titulo, fontSize: 18, lineHeight: 22 }}>{nivel}</Texto>
              <Texto v="legenda" numeros>{`${x?.certas} de ${x?.total} certas`}</Texto>
              <Texto v="legenda" forte>{x?.aprovado ? "Passou" : "Não passou"}</Texto>
            </View>
          ))}
        </View>
      ) : null}

      {r.curso ? (
        <Cartao style={{ gap: 10, padding: 20 }}>
          <Texto v="legenda" forte suave>
            O seu curso
          </Texto>
          <Titulo v="tituloS">{r.curso.titulo}</Titulo>
          {r.inscrito ? (
            <>
              <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
                Já está inscrito. Comece pela primeira vídeo-aula com a professora Luena.
              </Texto>
              <Botao tipo="realce" larguraTotal onPress={() => router.replace(`/curso/${r.curso!.id}`)}>
                Começar o curso
              </Botao>
              {r.curso_pratica ? (
                <Botao tipo="secundario" larguraTotal onPress={() => router.dismissTo("/praticar")}>
                  Abrir o laboratório
                </Botao>
              ) : null}
            </>
          ) : r.motivo === "plano" ? (
            <>
              <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
                Este curso faz parte dos planos pagos. Escolha um plano para se inscrever.
              </Texto>
              <Botao larguraTotal onPress={() => router.replace("/planos")}>
                Ver os planos
              </Botao>
            </>
          ) : (
            <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
              Não foi possível fazer a inscrição agora. Pode inscrever-se a partir da página do curso.
            </Texto>
          )}
        </Cartao>
      ) : (
        <Aviso>{`O curso do nível ${r.nivel} está a ser preparado. O seu nível ficou guardado: quando o curso abrir, aparece no início.`}</Aviso>
      )}

      {sector && nomeArea ? (
        <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
          {temBasico
            ? `Já tem o nível básico: pode também inscrever-se nos cursos de ${nomeArea}.`
            : `Os cursos de ${nomeArea} abrem-se quando chegar ao nível básico (A2 concluído ou o teste do A2).`}
        </Texto>
      ) : null}
    </Ecra>
  );
}
