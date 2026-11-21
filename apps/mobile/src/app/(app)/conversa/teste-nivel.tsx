/**
 * Teste de nível falado: 3 a 4 minutos de conversa com o tutor, que começa fácil e vai subindo.
 * Web: apps/web/components/pe/acolhimento/TesteFalado.tsx (passo 2 da primeira entrada).
 * Não gasta os minutos de conversa do plano.
 *
 * Parâmetros (para o agente CONTA, a partir de /primeira-entrada):
 *   /conversa/teste-nivel?volta=/primeira-entrada
 * No fim volta a `volta` com ?nivel=B1 (nível calculado) ou ?perguntas=1 (o aluno preferiu as
 * 5 perguntas escritas). Quem chamou guarda preferences.nivel. Sem `volta`, só volta atrás.
 */
import { router, useLocalSearchParams } from "expo-router";
import { Mic } from "lucide-react-native";
import { useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { Aviso, Botao, Cabecalho, Ecra, Osso, Texto, Titulo } from "@/ui";
import { balao, cor, fonte } from "@/tema";
import {
  DESCRICAO_NIVEL,
  NOME_NIVEL,
  eNivel,
  erroConversa,
  useConversaComecarDiagnosticoMutation,
  useConversaDiagnosticoQuery,
  useLazyConversaResultadoDiagnosticoQuery,
  type ConversaAberta,
  type Nivel,
  type ResultadoDiagnostico,
} from "@/dominios/conversa/api";
import { vozDisponivel } from "@/componentes/conversa/chamada";
import { PermissaoMicrofone, useMicrofone } from "@/componentes/conversa/PermissaoMicrofone";
import { Viva } from "@/componentes/conversa/Viva";

type Fase = { tipo: "inicio" } | { tipo: "viva"; dados: ConversaAberta } | { tipo: "a_avaliar" } | { tipo: "resultado"; r: ResultadoDiagnostico } | { tipo: "sem_resultado"; mensagem: string };

const COMPETENCIAS: { chave: "falar" | "ouvir" | "gramatica" | "vocabulario"; nome: string }[] = [
  { chave: "falar", nome: "Falar" },
  { chave: "ouvir", nome: "Perceber" },
  { chave: "vocabulario", nome: "Vocabulário" },
  { chave: "gramatica", nome: "Gramática" },
];

const POR_COMPETENCIA: Record<string, Record<Nivel, string>> = {
  ouvir: {
    A1: "Percebe perguntas muito simples, ditas devagar.",
    A2: "Percebe perguntas simples sobre si e o trabalho.",
    B1: "Percebe o essencial de uma conversa de trabalho clara.",
    B2: "Acompanha reuniões e conversas a ritmo normal.",
    C1: "Percebe quase tudo, mesmo com expressões e sotaques.",
    C2: "Percebe tudo, como um falante nativo.",
  },
  gramatica: {
    A1: "Frases muito curtas, com erros frequentes.",
    A2: "Frases simples; os tempos do passado ainda falham.",
    B1: "Frases correctas no dia a dia, com alguns erros.",
    B2: "Usa estruturas variadas com poucos erros.",
    C1: "Frases complexas quase sempre correctas.",
    C2: "Gramática precisa em qualquer situação.",
  },
  vocabulario: {
    A1: "Palavras básicas do dia a dia.",
    A2: "Palavras comuns do trabalho e das rotinas.",
    B1: "Vocabulário suficiente para falar do seu trabalho.",
    B2: "Vocabulário variado da sua área.",
    C1: "Vocabulário rico e preciso, com expressões.",
    C2: "Vocabulário de falante nativo.",
  },
};

function explicacao(chave: string, nivel: Nivel, r: ResultadoDiagnostico) {
  const dada = r.explicacoes[chave as keyof ResultadoDiagnostico["explicacoes"]];
  if (dada) return dada;
  if (chave === "falar") return `${DESCRICAO_NIVEL[nivel]}.`;
  return POR_COMPETENCIA[chave]?.[nivel] ?? "";
}

const espera = (ms: number) => new Promise((ok) => setTimeout(ok, ms));

export default function EcraTesteNivel() {
  const { volta } = useLocalSearchParams<{ volta?: string }>();
  const { data: estado, isLoading, isError, refetch } = useConversaDiagnosticoQuery();
  const [comecar, { isLoading: aComecar }] = useConversaComecarDiagnosticoMutation();
  const [lerResultado] = useLazyConversaResultadoDiagnosticoQuery();
  const [fase, setFase] = useState<Fase>({ tipo: "inicio" });
  const [erroInicio, setErroInicio] = useState<string | null>(null);
  const mic = useMicrofone();
  const minutos = Math.round((estado?.max_segundos ?? 240) / 60);

  const sair = (params: Record<string, string>) => {
    if (volta) router.dismissTo({ pathname: volta as never, params });
    else if (router.canGoBack()) router.back();
    else router.replace("/inicio");
  };
  const preferirPerguntas = () => sair({ perguntas: "1" });

  const abrir = async () => {
    setErroInicio(null);
    if (estado?.modo === "vapi" && !(await mic.garantir())) return;
    try {
      const d = await comecar().unwrap();
      setFase({ tipo: "viva", dados: { sessao: d.sessao, modo: d.modo, chave_publica: d.chave_publica } });
    } catch (e) {
      setErroInicio(erroConversa(e, "Não foi possível ligar ao tutor agora."));
    }
  };

  const terminou = async (id: string) => {
    setFase({ tipo: "a_avaliar" });
    try {
      // O nível sai da chamada confirmada pelo serviço de voz: pode demorar alguns segundos.
      let r = await lerResultado(id).unwrap();
      for (let i = 0; i < 40 && r.estado === "a_avaliar"; i++) {
        await espera(3000);
        r = await lerResultado(id).unwrap();
      }
      if (r.avaliado && eNivel(r.nivel)) setFase({ tipo: "resultado", r });
      else
        setFase({
          tipo: "sem_resultado",
          mensagem:
            r.estado === "nao_ligou"
              ? "A chamada não chegou a ligar."
              : r.estado === "a_avaliar"
                ? "O resultado ainda não chegou. Volte a este ecrã daqui a alguns minutos."
                : "Não ouvimos respostas suficientes para dar um nível. O teste precisa de pelo menos um minuto de conversa.",
        });
    } catch {
      setFase({ tipo: "sem_resultado", mensagem: "Não conseguimos calcular o resultado." });
    }
  };

  const perguntas = (
    <Botao tipo="ligacao" onPress={preferirPerguntas} style={{ alignSelf: "center" }}>
      Prefiro responder a perguntas
    </Botao>
  );
  const cabecalho = <Cabecalho titulo="Teste de nível" fechar={fase.tipo !== "viva"} semVoltar={fase.tipo === "viva" || fase.tipo === "a_avaliar"} />;

  if (fase.tipo === "viva")
    return (
      <Ecra cabecalho={cabecalho}>
        <View style={{ gap: 8 }}>
          <Titulo>Converse com o tutor</Titulo>
          <Texto suave>Responda com calma e diga o máximo que conseguir. As perguntas vão ficando mais difíceis: é normal.</Texto>
        </View>
        <Viva dados={fase.dados} frases={[]} semTexto aoTerminar={(r) => void terminou(r.id)} aoSaltar={preferirPerguntas} />
      </Ecra>
    );

  if (fase.tipo === "a_avaliar")
    return (
      <Ecra cabecalho={cabecalho}>
        <View accessibilityRole="alert" style={{ gap: 16, paddingVertical: 24 }}>
          <ActivityIndicator size="large" color={cor.azulMarca} style={{ alignSelf: "flex-start" }} />
          <Titulo>A ouvir o que disse…</Titulo>
          <Texto suave>Estamos a calcular o seu nível. Demora alguns segundos.</Texto>
        </View>
      </Ecra>
    );

  if (fase.tipo === "resultado") {
    const r = fase.r;
    const nivel = r.nivel as Nivel;
    return (
      <Ecra cabecalho={cabecalho} rodape={<Botao larguraTotal onPress={() => sair({ nivel })}>Ver por onde começar</Botao>}>
        <View style={[balao.grande, { backgroundColor: cor.azulMarca, paddingVertical: 24, paddingHorizontal: 24, gap: 6 }]}>
          <Texto accessibilityRole="header" cor={cor.sobreMarca} style={{ fontFamily: fonte.tituloMedio, fontSize: 22, lineHeight: 28 }}>
            {`O seu nível de fala: ${nivel}`}
          </Texto>
          <Texto v="voz" cor={cor.sobreMarca} style={{ fontSize: 17, lineHeight: 26 }}>
            {`${NOME_NIVEL[nivel]}. ${DESCRICAO_NIVEL[nivel]}.`}
          </Texto>
        </View>
        <View accessibilityLabel="Nível por competência">
          {COMPETENCIAS.map(({ chave, nome }) => {
            const n = r.niveis?.[chave];
            if (!eNivel(n)) return null;
            return (
              <View key={chave} style={{ flexDirection: "row", alignItems: "flex-start", gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderColor: cor.fundoForte }}>
                <View style={{ width: 48, height: 36, alignItems: "center", justifyContent: "center", borderRadius: 6, backgroundColor: n === nivel ? cor.fundoSuave : cor.fundoForte }}>
                  <Texto cor={n === nivel ? cor.azulMarca : cor.tinta} style={{ fontFamily: fonte.titulo, fontSize: 17 }}>
                    {n}
                  </Texto>
                </View>
                <View style={{ flex: 1 }}>
                  <Texto forte style={{ lineHeight: 22 }}>
                    {nome}
                  </Texto>
                  <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
                    {explicacao(chave, n, r)}
                  </Texto>
                </View>
              </View>
            );
          })}
        </View>
        <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
          O tutor e os cursos passam a usar este nível. Vai subindo à medida que conversa.
        </Texto>
      </Ecra>
    );
  }

  if (fase.tipo === "sem_resultado")
    return (
      <Ecra cabecalho={cabecalho}>
        <Titulo>Ainda sem nível</Titulo>
        <Aviso>{`${fase.mensagem} Pode tentar outra vez ou responder a 5 perguntas escritas.`}</Aviso>
        <Botao larguraTotal onPress={() => setFase({ tipo: "inicio" })}>
          Tentar outra vez
        </Botao>
        {perguntas}
      </Ecra>
    );

  const voz = vozDisponivel();
  const indisponivel = isError
    ? "O teste falado não está disponível agora."
    : estado && !estado.disponivel
      ? `Já fez ${estado.limite} testes falados nos últimos 30 dias.`
      : estado?.modo === "vapi" && !voz.disponivel
        ? voz.motivo
        : null;

  return (
    <Ecra
      cabecalho={cabecalho}
      aoActualizar={refetch}
      rodape={
        isLoading ? null : indisponivel ? (
          <Botao larguraTotal onPress={preferirPerguntas}>
            Responder a perguntas
          </Botao>
        ) : (
          <>
            <Botao larguraTotal onPress={() => void abrir()} carregando={aComecar} icone={<Mic size={20} color={cor.sobreMarca} />}>
              Começar a conversa
            </Botao>
            {perguntas}
          </>
        )
      }
    >
      <View style={{ gap: 8 }}>
        <Titulo>Qual é o seu nível a falar?</Titulo>
        <Texto suave>
          {`Uma conversa de ${minutos} minutos com o tutor, em inglês. Começa com perguntas fáceis sobre si e vai subindo: o seu trabalho, um problema que resolveu, uma opinião. No fim mostramos o seu nível em cada competência.`}
        </Texto>
      </View>
      <View style={{ gap: 10 }}>
        {["Não gasta os minutos de conversa do seu plano.", "Não há respostas erradas: o tutor não corrige nem dá notas durante a conversa.", "A conversa não é gravada. Guardamos só o texto do que disse."].map((t) => (
          <View key={t} style={{ flexDirection: "row", gap: 10 }}>
            <View style={[balao.pequeno, { width: 10, height: 10, marginTop: 7, backgroundColor: cor.azulMarca, borderTopLeftRadius: 5, borderTopRightRadius: 5, borderBottomRightRadius: 5 }]} />
            <Texto style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>{t}</Texto>
          </View>
        ))}
      </View>
      {isLoading ? <Osso altura={48} /> : indisponivel ? <Aviso>{`${indisponivel} Responda a 5 perguntas escritas para saber o seu nível.`}</Aviso> : null}
      {erroInicio ? <Aviso tom="erro">{`${erroInicio} Pode responder às perguntas escritas.`}</Aviso> : null}
      <PermissaoMicrofone {...mic.folha} />
    </Ecra>
  );
}
