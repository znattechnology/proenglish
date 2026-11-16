/**
 * Teste do nível básico (web: components/pe/acolhimento/TesteBasico.tsx): o requisito para entrar
 * num curso de sector sem ter feito o curso geral. Ecrã inteiro: entrada, perguntas (uma por ecrã,
 * com o tempo a contar) e resultado. O servidor sorteia as perguntas, conta o tempo e dá a nota.
 */
import { router, Stack } from "expo-router";
import { Check, Clock, X } from "lucide-react-native";
import { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, View } from "react-native";
import { mensagemErro } from "@/api/erros";
import {
  type EstadoTesteBasico,
  type TentativaTeste,
  useEntregarTesteBasicoMutation,
  useEstadoTesteBasicoQuery,
  useIniciarTesteBasicoMutation,
} from "@/dominios/cursos/testeBasico";
import { balao, cor, raio } from "@/tema";
import { ACarregar, Aviso, BarraProgresso, Botao, Cabecalho, Dialogo, Ecra, EstadoErro, Numero, Texto, Titulo } from "@/ui";

const MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
function dataHora(iso: string) {
  const d = new Date(iso);
  return `${d.getDate()} de ${MESES[d.getMonth()]}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

const sair = () => (router.canGoBack() ? router.back() : router.replace("/cursos"));
const verCursos = () => router.dismissTo("/cursos");

/** Segundos que faltam até `iso`, actualizados a cada segundo. */
function useFalta(iso: string) {
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, [iso]);
  return Math.max(0, Math.round((new Date(iso).getTime() - agora) / 1000));
}

export default function EcraTesteBasico() {
  const { data, isLoading, isError, error, refetch } = useEstadoTesteBasicoQuery();
  const [iniciar, { isLoading: aIniciar }] = useIniciarTesteBasicoMutation();
  const [resultado, setResultado] = useState<TentativaTeste | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const comecar = async () => {
    setErro(null);
    const r = await iniciar();
    if ("error" in r && r.error) setErro(mensagemErro(r.error, "Não foi possível abrir o teste. Tente outra vez."));
  };

  if (isLoading)
    return (
      <Ecra cabecalho={<Cabecalho titulo="Teste do nível básico" fechar />}>
        <ACarregar linhas={3} rotulo="A abrir o teste" />
      </Ecra>
    );
  if (isError || !data)
    return (
      <Ecra cabecalho={<Cabecalho titulo="Teste do nível básico" fechar />}>
        <EstadoErro erro={error} titulo="Não conseguimos abrir o teste" aoTentar={() => void refetch()} />
      </Ecra>
    );
  if (resultado) return <Resultado t={resultado} estado={data} />;
  if (data.tem_nivel_basico) return <Aprovado />;
  if (data.em_curso?.perguntas) return <Perguntas key={data.em_curso.id} t={data.em_curso} aoEntregar={setResultado} />;
  return <Entrada estado={data} aIniciar={aIniciar} erro={erro} aoComecar={() => void comecar()} />;
}

function Entrada({ estado, aIniciar, erro, aoComecar }: { estado: EstadoTesteBasico; aIniciar: boolean; erro: string | null; aoComecar: () => void }) {
  const r = estado.regras;
  const certasParaPassar = Math.ceil((r.perguntas * r.aprovacao) / 100);
  const rodape = estado.pode_iniciar ? (
    <>
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
      <Botao larguraTotal carregando={aIniciar} onPress={aoComecar}>
        {aIniciar ? "A abrir o teste…" : "Começar o teste"}
      </Botao>
    </>
  ) : (
    <Botao larguraTotal onPress={verCursos}>
      Ver o curso geral
    </Botao>
  );
  return (
    <Ecra cabecalho={<Cabecalho titulo="Teste do nível básico" fechar aoVoltar={sair} />} rodape={rodape} style={{ gap: 20 }}>
      <View style={{ gap: 8 }}>
        <Titulo>Prove que tem o nível básico</Titulo>
        <Texto suave>Os cursos de sector pedem, no mínimo, o nível básico de inglês. Se já o tem, prove-o aqui e inscreva-se logo em qualquer sector.</Texto>
      </View>
      <View style={{ flexDirection: "row", gap: 8 }}>
        <Numero rotulo="Perguntas" valor={r.perguntas} />
        <Numero rotulo="Minutos" valor={r.minutos} />
        <Numero rotulo="Certas para aprovar" valor={certasParaPassar} />
      </View>
      {estado.ultima && estado.ultima.aprovado === false ? (
        <Aviso>
          Na última tentativa acertou {estado.ultima.certas} de {estado.ultima.total}.
        </Aviso>
      ) : null}
      {estado.pode_iniciar ? (
        <View style={{ gap: 10 }}>
          {[
            "São perguntas de escolha, uma de cada vez. Pode voltar atrás e mudar a resposta.",
            "O tempo começa a contar quando abrir o teste e não pára se sair da app.",
            `Se não aprovar, pode repetir ${r.espera_horas} horas depois.`,
          ].map((t) => (
            <View key={t} style={{ flexDirection: "row", gap: 10 }}>
              <Check size={18} color={cor.azulMarca} style={{ marginTop: 4 }} />
              <Texto style={{ flex: 1 }}>{t}</Texto>
            </View>
          ))}
        </View>
      ) : (
        <>
          <Aviso titulo="Ainda não pode repetir o teste">
            <Texto>Pode repetir a partir de {estado.proxima_tentativa_em ? dataHora(estado.proxima_tentativa_em) : "amanhã"}.</Texto>
          </Aviso>
          <Texto suave>Entretanto, o curso geral English Communication Skills leva-o ao nível básico, a falar desde a primeira lição.</Texto>
        </>
      )}
    </Ecra>
  );
}

function Perguntas({ t, aoEntregar }: { t: TentativaTeste; aoEntregar: (r: TentativaTeste) => void }) {
  const perguntas = useMemo(() => t.perguntas ?? [], [t.perguntas]);
  const [indice, setIndice] = useState(0);
  const [respostas, setRespostas] = useState<Record<string, number>>({});
  // As respostas mais recentes, para a entrega automática quando o tempo acaba.
  const ultimas = useRef<Record<string, number>>({});
  const [entregar, { isLoading }] = useEntregarTesteBasicoMutation();
  const [erro, setErro] = useState<string | null>(null);
  const [aSair, setASair] = useState(false);
  const falta = useFalta(t.expira_em);
  const p = perguntas[indice];
  const ultima = indice === perguntas.length - 1;
  const respondidas = Object.keys(respostas).length;
  const porResponder = perguntas.length - respondidas;

  const enviar = async () => {
    setErro(null);
    const r = await entregar({ id: t.id, respostas: ultimas.current });
    if ("data" in r && r.data) return aoEntregar(r.data);
    setErro(mensagemErro("error" in r ? r.error : null, "Não foi possível entregar o teste. Verifique a ligação e tente outra vez."));
  };

  // Tempo esgotado: entrega o que houver (o servidor aceita uns segundos de tolerância).
  useEffect(() => {
    const id = setTimeout(() => void enviar(), Math.max(0, new Date(t.expira_em).getTime() - Date.now()));
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t.expira_em]);

  if (!p) return null;
  const relogio = `${Math.floor(falta / 60)}:${String(falta % 60).padStart(2, "0")}`;
  const poucoTempo = falta <= 60;

  return (
    <Ecra
      cabecalho={
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12, paddingLeft: 12, paddingRight: 20, minHeight: 60 }}>
          <Pressable accessibilityRole="button" accessibilityLabel="Sair do teste" hitSlop={8} onPress={() => setASair(true)} style={{ width: 44, height: 44, alignItems: "center", justifyContent: "center" }}>
            <X size={24} color={cor.tinta} />
          </Pressable>
          <View style={{ flex: 1 }}>
            <BarraProgresso valor={(respondidas / perguntas.length) * 100} rotulo={`${respondidas} de ${perguntas.length} respondidas`} />
          </View>
          <View
            accessible
            accessibilityLabel={`Faltam ${Math.floor(falta / 60)} minutos e ${falta % 60} segundos`}
            style={{ flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 10, paddingVertical: 6, borderRadius: raio.sm, backgroundColor: poucoTempo ? cor.erradoSuave : cor.fundoSuave }}
          >
            <Clock size={16} color={poucoTempo ? cor.errado : cor.tinta} />
            <Texto v="rotulo" numeros cor={poucoTempo ? cor.errado : cor.tinta}>
              {relogio}
            </Texto>
          </View>
        </View>
      }
      rodape={
        <>
          {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
          <View style={{ flexDirection: "row", gap: 12 }}>
            <Botao tipo="secundario" disabled={indice === 0 || isLoading} onPress={() => setIndice((i) => i - 1)}>
              Anterior
            </Botao>
            <View style={{ flex: 1 }}>
              {ultima ? (
                <Botao larguraTotal carregando={isLoading} onPress={() => void enviar()}>
                  {isLoading ? "A entregar…" : "Entregar o teste"}
                </Botao>
              ) : (
                <Botao larguraTotal onPress={() => setIndice((i) => i + 1)}>
                  {respostas[p.id] === undefined ? "Saltar" : "Seguinte"}
                </Botao>
              )}
            </View>
          </View>
        </>
      }
      style={{ gap: 20 }}
    >
      <Stack.Screen options={{ gestureEnabled: false }} />
      <View style={{ gap: 8 }}>
        <Texto v="rotulo" suave numeros>
          Pergunta {indice + 1} de {perguntas.length}
        </Texto>
        <Texto v="tituloM" accessibilityRole="header" accessibilityLanguage="en" style={{ fontSize: 24, lineHeight: 32 }}>
          {p.enunciado}
        </Texto>
      </View>
      <View accessibilityRole="radiogroup" accessibilityLabel="Opções de resposta" style={{ gap: 10 }}>
        {p.opcoes.map((o, i) => {
          const escolhida = respostas[p.id] === i;
          return (
            <Pressable
              key={o}
              accessibilityRole="radio"
              accessibilityState={{ checked: escolhida }}
              accessibilityLanguage="en"
              onPress={() => {
                ultimas.current = { ...ultimas.current, [p.id]: i };
                setRespostas(ultimas.current);
              }}
              style={({ pressed }) => ({
                minHeight: 56,
                flexDirection: "row",
                alignItems: "center",
                gap: 12,
                paddingHorizontal: 16,
                paddingVertical: 12,
                borderRadius: raio.md,
                borderWidth: 2,
                borderColor: escolhida ? cor.azulMarca : cor.linha,
                backgroundColor: escolhida || pressed ? cor.fundoSuave : cor.fundo,
              })}
            >
              <View style={{ width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: escolhida ? cor.azulMarca : cor.linhaForte, alignItems: "center", justifyContent: "center" }}>
                {escolhida ? <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: cor.azulMarca }} /> : null}
              </View>
              <Texto forte={escolhida} style={{ flex: 1, fontSize: 18, lineHeight: 26 }}>
                {o}
              </Texto>
            </Pressable>
          );
        })}
      </View>
      {ultima && porResponder > 0 ? (
        <Texto v="legenda" suave>
          {porResponder === 1 ? "Falta responder a 1 pergunta." : `Faltam ${porResponder} perguntas por responder.`} As que ficarem em branco contam como erradas.
        </Texto>
      ) : null}
      <Dialogo aberto={aSair} aoFechar={() => setASair(false)} titulo="Sair do teste?" texto="O tempo continua a contar. Pode voltar enquanto não acabar; se o tempo acabar sem entregar, a tentativa conta como reprovada.">
        <Botao larguraTotal onPress={() => setASair(false)}>
          Continuar o teste
        </Botao>
        <Botao
          tipo="ligacao"
          larguraTotal
          onPress={() => {
            setASair(false);
            sair();
          }}
        >
          Sair do teste
        </Botao>
      </Dialogo>
    </Ecra>
  );
}

function Resultado({ t, estado }: { t: TentativaTeste; estado: EstadoTesteBasico }) {
  if (t.aprovado) return <Aprovado nota={`${t.certas} de ${t.total}`} />;
  return (
    <Ecra
      cabecalho={<Cabecalho titulo="Resultado do teste" fechar aoVoltar={sair} />}
      rodape={
        <Botao larguraTotal onPress={verCursos}>
          Ver o curso geral
        </Botao>
      }
      style={{ gap: 16 }}
    >
      <View style={[balao.medio, { width: 56, height: 56, alignItems: "center", justifyContent: "center", backgroundColor: cor.erradoSuave }]}>
        <X size={28} color={cor.errado} />
      </View>
      <Titulo>Ainda não chegou ao nível básico</Titulo>
      <Texto v="corpoL" suave>
        Acertou {t.certas} de {t.total}. Para aprovar precisa de {Math.ceil((t.total * estado.regras.aprovacao) / 100)}. Comece pelo curso geral English Communication Skills: quando o concluir, os cursos de sector abrem-se.
      </Texto>
      <Texto v="legenda" suave>
        Pode repetir o teste {estado.regras.espera_horas} horas depois desta tentativa.
      </Texto>
    </Ecra>
  );
}

function Aprovado({ nota }: { nota?: string }) {
  return (
    <Ecra
      cabecalho={<Cabecalho titulo="Teste do nível básico" fechar aoVoltar={sair} />}
      rodape={
        <Botao tipo="realce" larguraTotal onPress={verCursos}>
          Escolher um curso de sector
        </Botao>
      }
      style={{ gap: 16 }}
    >
      <View style={[balao.medio, { width: 56, height: 56, alignItems: "center", justifyContent: "center", backgroundColor: cor.certoSuave }]}>
        <Check size={28} color={cor.certo} />
      </View>
      <Titulo>Tem o nível básico</Titulo>
      <Texto v="corpoL" suave>
        {nota ? `Acertou ${nota}. ` : ""}Já pode inscrever-se em qualquer curso de sector.
      </Texto>
    </Ecra>
  );
}
