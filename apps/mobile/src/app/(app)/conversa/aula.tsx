/**
 * "Usar isto numa conversa": 3 minutos com o tutor numa situação de trabalho como a da aula,
 * a tentar usar as frases da aula. Web: ConversaDaAula em apps/web/components/pe/curso/FalaDaAula.tsx.
 *
 * Parâmetros (para o agente CURSOS, a partir da aula em vídeo):
 *   /conversa/aula?capitulo=<chapterId>&titulo=<título da aula (opcional)>
 * Lê as frases e a disponibilidade em GET /student/video-courses/chapters/<id>/fala/
 * e começa em POST .../chapters/<id>/conversa/ (gasta minutos de conversa do plano).
 */
import { router, useLocalSearchParams } from "expo-router";
import { MessagesSquare, Mic } from "lucide-react-native";
import { useState } from "react";
import { View } from "react-native";
import { Aviso, Botao, Cabecalho, Ecra, EstadoErro, EstadoVazio, Osso, Texto, Titulo } from "@/ui";
import { balao, cor, raio } from "@/tema";
import { erroConversa, useConversaComecarAulaMutation, useConversaFalaDaAulaQuery, type ConversaAberta, type Resumo } from "@/dominios/conversa/api";
import { ditasNoResumo } from "@/componentes/conversa/ConversaCurta";
import { ListaFrases } from "@/componentes/conversa/Pecas";
import { PermissaoMicrofone, useMicrofone } from "@/componentes/conversa/PermissaoMicrofone";
import { Viva } from "@/componentes/conversa/Viva";

type Fase = { tipo: "inicio" } | { tipo: "viva"; dados: ConversaAberta } | { tipo: "fim"; resumo: Resumo } | { tipo: "bloqueada"; mensagem: string };

const TITULO_FRASES = "Tente usar estas frases da aula";

export default function EcraConversaDaAula() {
  const { capitulo, titulo } = useLocalSearchParams<{ capitulo?: string; titulo?: string }>();
  const { data, isLoading, isError, error, refetch, isFetching } = useConversaFalaDaAulaQuery(capitulo ?? "", { skip: !capitulo });
  const [fase, setFase] = useState<Fase>({ tipo: "inicio" });
  const [comecar, { isLoading: aComecar }] = useConversaComecarAulaMutation();
  const mic = useMicrofone();
  const cabecalho = <Cabecalho titulo="Usar isto numa conversa" subtitulo={titulo || undefined} fechar={fase.tipo !== "viva"} semVoltar={fase.tipo === "viva"} />;

  if (!capitulo)
    return (
      <Ecra cabecalho={cabecalho}>
        <EstadoVazio titulo="Falta escolher a aula" texto="Abra uma aula em vídeo e toque em «Usar isto numa conversa»." accao={<Botao href="/cursos" substituir>Ver os meus cursos</Botao>} />
      </Ecra>
    );
  if (isError)
    return (
      <Ecra cabecalho={cabecalho}>
        <EstadoErro erro={error} titulo="Não conseguimos abrir as frases da aula" aoTentar={refetch} />
      </Ecra>
    );
  if (isLoading || !data)
    return (
      <Ecra cabecalho={cabecalho}>
        <View accessible accessibilityLabel="A carregar" style={{ gap: 12 }}>
          <Osso altura={64} />
          <Osso altura={24} largura="70%" />
          <Osso altura={24} largura="80%" />
          <Osso altura={24} largura="60%" />
        </View>
      </Ecra>
    );

  const frases = data.frases.filter((f) => f.tipo === "frase").map((f) => f.texto);
  if (!frases.length)
    return (
      <Ecra cabecalho={cabecalho} aoActualizar={refetch} aActualizar={isFetching}>
        <EstadoVazio
          icone={<MessagesSquare size={26} color={cor.azulMarca} />}
          titulo="Esta aula ainda não tem frases"
          texto="Quando o professor aprovar as frases da aula, pode usá-las numa conversa com o tutor. Entretanto, converse sobre o que quiser."
          accao={<Botao onPress={() => router.navigate("/conversa")}>Preparar uma conversa</Botao>}
        />
      </Ecra>
    );

  const minutos = Math.max(1, Math.round((data.conversa.max_segundos || 180) / 60));
  const indisponivel = fase.tipo === "inicio" && !data.conversa.disponivel ? data.conversa.mensagem ?? "A conversa não está disponível agora." : null;

  const abrir = async () => {
    if (!(await mic.garantir())) return;
    try {
      setFase({ tipo: "viva", dados: await comecar(capitulo).unwrap() });
    } catch (e) {
      setFase({ tipo: "bloqueada", mensagem: erroConversa(e, "Não foi possível começar a conversa agora.") });
    }
  };

  return (
    <Ecra cabecalho={cabecalho} aoActualizar={fase.tipo === "inicio" ? refetch : undefined} aActualizar={isFetching}>
      <View style={{ flexDirection: "row", gap: 12 }}>
        <View style={[balao.pequeno, { width: 44, height: 44, alignItems: "center", justifyContent: "center", backgroundColor: cor.azulMarca }]}>
          <MessagesSquare size={24} color={cor.sobreMarca} />
        </View>
        <View style={{ flex: 1, gap: 4 }}>
          <Titulo v="tituloM">Usar isto numa conversa</Titulo>
          <Texto suave>{`${minutos} minutos com o tutor numa situação de trabalho como a do vídeo. Uma frase só fica aprendida quando a diz sozinho, sem o tutor a dizer primeiro.`}</Texto>
        </View>
      </View>

      {fase.tipo === "viva" ? (
        <Viva dados={fase.dados} frases={frases} tituloFrases={TITULO_FRASES} aoTerminar={(resumo) => setFase({ tipo: "fim", resumo })} />
      ) : (
        <ListaFrases frases={frases} titulo={TITULO_FRASES} ditas={fase.tipo === "fim" ? ditasNoResumo(fase.resumo, frases) : undefined} />
      )}

      {fase.tipo === "inicio" ? (
        indisponivel ? (
          <Indisponivel mensagem={indisponivel} />
        ) : (
          <Botao larguraTotal onPress={() => void abrir()} carregando={aComecar} icone={<Mic size={20} color={cor.sobreMarca} />}>
            Começar a conversa
          </Botao>
        )
      ) : null}
      {fase.tipo === "bloqueada" ? <Indisponivel mensagem={fase.mensagem} /> : null}
      {fase.tipo === "fim" ? <Fim resumo={fase.resumo} aoRepetir={() => setFase({ tipo: "inicio" })} /> : null}
      <PermissaoMicrofone {...mic.folha} />
    </Ecra>
  );
}

function Indisponivel({ mensagem }: { mensagem: string }) {
  return (
    <View style={{ gap: 12 }}>
      <Aviso>{`${mensagem} Entretanto, pode treinar estas frases na revisão de hoje.`}</Aviso>
      <Botao tipo="secundario" href="/revisao" larguraTotal>
        Fazer a revisão de hoje
      </Botao>
    </View>
  );
}

function Fim({ resumo, aoRepetir }: { resumo: Resumo; aoRepetir: () => void }) {
  const falas = resumo.transcricao.filter((f) => f.quem === "aluno").length;
  const sozinho = resumo.objectivos.filter((o) => o.usado).length;
  const c = resumo.correccoes[0];
  return (
    <View style={{ gap: 12 }}>
      <View style={{ gap: 8, borderRadius: raio.md, paddingHorizontal: 16, paddingVertical: 14, backgroundColor: falas ? cor.certoSuave : cor.fundoSuave }}>
        <Texto forte>
          {falas === 0
            ? "Não ouvimos nenhuma resposta sua."
            : sozinho
              ? `Disse sozinho ${sozinho} de ${resumo.objectivos.length} frases da aula.`
              : `Respondeu ${falas} ${falas === 1 ? "vez" : "vezes"}. Na próxima, tente usar as frases da aula sem esperar pelo tutor.`}
        </Texto>
        {c ? (
          <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
            Um ajuste: <Texto v="legenda" style={{ fontSize: 15, textDecorationLine: "line-through" }}>{c.disse}</Texto>{" "}
            <Texto v="legenda" forte style={{ fontSize: 15 }}>
              {c.certo}
            </Texto>
            . {c.porque}
          </Texto>
        ) : null}
      </View>
      <Botao larguraTotal onPress={aoRepetir}>
        Conversar outra vez
      </Botao>
      <Botao tipo="secundario" larguraTotal href={`/conversa/resumo/${resumo.id}`}>
        Ver o resumo completo
      </Botao>
    </View>
  );
}
