/**
 * As perguntas de um teste de nível (uma por ecrã, com o tempo a contar), usadas no ecrã do teste
 * do nível básico e na colocação da primeira entrada. Web: components/pe/acolhimento/TesteBasico.tsx.
 *
 * Regra do LabTIC: se o aluno sai da app durante o teste, a pergunta em que está é anulada
 * (no servidor, /anular/: conta como errada). Uma anulação por cada saída; ao voltar, vê o aviso.
 * Depois de entregue, deixa de se vigiar.
 *
 * Entrega e anulação usam /student/teste-basico/<id>/, para o teste do nível básico e para o
 * teste de colocação (o servidor sabe de que teste se trata).
 */
import { Stack } from "expo-router";
import { Clock, X } from "lucide-react-native";
import { useEffect, useMemo, useRef, useState } from "react";
import { AppState, Pressable, View } from "react-native";
import { mensagemErro } from "@/api/erros";
import { type TentativaTeste, useAnularPerguntaTesteMutation, useEntregarTesteBasicoMutation } from "@/dominios/cursos/testeBasico";
import { cor, raio } from "@/tema";
import { Aviso, BarraProgresso, Botao, Dialogo, Ecra, Texto } from "@/ui";

/** A regra, para a entrada de cada teste. */
export const REGRA_SAIR_DA_APP = "Se sair da app durante o teste, a pergunta em que está é anulada e conta como errada.";

const MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
export function dataHora(iso: string) {
  const d = new Date(iso);
  return `${d.getDate()} de ${MESES[d.getMonth()]}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** Segundos que faltam até `iso`, actualizados a cada segundo. */
function useFalta(iso: string) {
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, [iso]);
  return Math.max(0, Math.round((new Date(iso).getTime() - agora) / 1000));
}

/**
 * Vigia a saída da app: cada ida para segundo plano chama `aoSair` uma vez; a seguinte só conta
 * depois de o aluno voltar (estado "active"). "inactive" sozinho (centro de controlo, notificações)
 * não conta; "inactive" seguido de "background" conta uma vez.
 */
function useVigiaSaidaDaApp(activo: boolean, aoSair: () => void) {
  const fora = useRef(false);
  const aoSairRef = useRef(aoSair);
  useEffect(() => {
    aoSairRef.current = aoSair;
  }, [aoSair]);

  useEffect(() => {
    if (!activo) return;
    fora.current = false;
    const s = AppState.addEventListener("change", (estado) => {
      if (estado === "background") {
        if (fora.current) return;
        fora.current = true;
        aoSairRef.current();
      } else if (estado === "active") {
        fora.current = false;
      }
    });
    return () => s.remove();
  }, [activo]);
}

export function PerguntasTeste({ t, aoEntregar, aoSair }: { t: TentativaTeste; aoEntregar: (r: TentativaTeste) => void; aoSair: () => void }) {
  const perguntas = useMemo(() => t.perguntas ?? [], [t.perguntas]);
  const [indice, setIndice] = useState(0);
  const [respostas, setRespostas] = useState<Record<string, number>>({});
  // As respostas mais recentes, para a entrega automática quando o tempo acaba.
  const ultimas = useRef<Record<string, number>>({});
  const [entregar, { isLoading }] = useEntregarTesteBasicoMutation();
  const [anularNoServidor] = useAnularPerguntaTesteMutation();
  const [anuladas, setAnuladas] = useState<string[]>(t.anuladas ?? []);
  const [aviso, setAviso] = useState<number | null>(null);
  const [aVigiar, setAVigiar] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [aSair, setASair] = useState(false);
  const falta = useFalta(t.expira_em);
  const p = perguntas[indice];
  const ultima = indice === perguntas.length - 1;
  // As anuladas já não se respondem: contam como tratadas.
  const respondidas = perguntas.filter((q) => respostas[q.id] !== undefined || anuladas.includes(q.id)).length;
  const porResponder = perguntas.length - respondidas;
  const anulada = !!p && anuladas.includes(p.id);

  useVigiaSaidaDaApp(aVigiar, () => {
    if (!p) return;
    setAviso(indice + 1);
    if (anuladas.includes(p.id)) return;
    setAnuladas((a) => [...a, p.id]);
    // A resposta que tivesse dado deixa de contar.
    const resto = { ...ultimas.current };
    delete resto[p.id];
    ultimas.current = resto;
    setRespostas(resto);
    void anularNoServidor({ id: t.id, pergunta: p.id });
  });

  const enviar = async () => {
    setErro(null);
    setAVigiar(false);
    const r = await entregar({ id: t.id, respostas: ultimas.current });
    if ("data" in r && r.data) return aoEntregar(r.data);
    setAVigiar(true);
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
                  {respostas[p.id] === undefined && !anulada ? "Saltar" : "Seguinte"}
                </Botao>
              )}
            </View>
          </View>
        </>
      }
      style={{ gap: 20 }}
    >
      <Stack.Screen options={{ gestureEnabled: false }} />
      {aviso ? (
        <Aviso
          tom="erro"
          accao={
            <Botao tipo="ligacao" tamanho="pequeno" style={{ alignSelf: "flex-start" }} onPress={() => setAviso(null)}>
              Entendi
            </Botao>
          }
        >
          {`Saiu do ecrã do teste: a pergunta ${aviso} foi anulada e conta como errada.`}
        </Aviso>
      ) : null}
      <View style={{ gap: 8 }}>
        <Texto v="rotulo" suave numeros>
          Pergunta {indice + 1} de {perguntas.length}
        </Texto>
        <Texto v="tituloM" accessibilityRole="header" accessibilityLanguage="en" style={{ fontSize: 24, lineHeight: 32 }}>
          {p.enunciado}
        </Texto>
      </View>
      {anulada ? <Aviso>Esta pergunta foi anulada porque saiu do ecrã do teste. Conta como errada.</Aviso> : null}
      <View accessibilityRole="radiogroup" accessibilityLabel="Opções de resposta" accessibilityState={{ disabled: anulada }} style={{ gap: 10, opacity: anulada ? 0.5 : 1 }}>
        {p.opcoes.map((o, i) => {
          const escolhida = respostas[p.id] === i;
          return (
            <Pressable
              key={o}
              accessibilityRole="radio"
              accessibilityState={{ checked: escolhida, disabled: anulada }}
              accessibilityLanguage="en"
              disabled={anulada}
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
            setAVigiar(false);
            aoSair();
          }}
        >
          Sair do teste
        </Botao>
      </Dialogo>
    </Ecra>
  );
}
