/**
 * Teste do nível básico (web: components/pe/acolhimento/TesteBasico.tsx): o requisito para entrar
 * num curso de sector sem ter feito o curso geral. Ecrã inteiro: entrada, perguntas (uma por ecrã,
 * com o tempo a contar) e resultado. O servidor sorteia as perguntas, conta o tempo e dá a nota.
 * Sem nível, a API dá o teste do A2. Sair da app durante o teste anula a pergunta (PerguntasTeste).
 */
import { router } from "expo-router";
import { Check, X } from "lucide-react-native";
import { useState } from "react";
import { View } from "react-native";
import { mensagemErro } from "@/api/erros";
import { dataHora, PerguntasTeste, REGRA_SAIR_DA_APP } from "@/componentes/cursos/PerguntasTeste";
import {
  type EstadoTesteBasico,
  type TentativaTeste,
  useEstadoTesteBasicoQuery,
  useIniciarTesteBasicoMutation,
} from "@/dominios/cursos/testeBasico";
import { balao, cor } from "@/tema";
import { ACarregar, Aviso, Botao, Cabecalho, Ecra, EstadoErro, Numero, Texto, Titulo } from "@/ui";

const sair = () => (router.canGoBack() ? router.back() : router.replace("/cursos"));
const verCursos = () => router.dismissTo("/cursos");

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
  if (data.em_curso?.perguntas) return <PerguntasTeste key={data.em_curso.id} t={data.em_curso} aoEntregar={setResultado} aoSair={sair} />;
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
            REGRA_SAIR_DA_APP,
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
