/**
 * Conversa curta (1 a 2 minutos) com o tutor, exercício "conversa" do leitor de lições do laboratório.
 * Igual a apps/web/components/pe/licao/ConversaCurta.tsx.
 *
 * Para o agente LAB, no ecrã da lição (`ex.modo === "conversa"`):
 *   <ConversaCurta ex={{ id: ex.id, pergunta: ex.pergunta, frases: ex.frases }} bloqueado={bloqueado} aoMudar={setResposta} aoSaltar={saltar} />
 * - aoMudar recebe `{ tipo: "texto", resposta: { sessao_id } }` quando a conversa terminou com pelo
 *   menos 2 respostas (é isso que se manda ao "Verificar"), ou `null` enquanto não conta.
 * - aoSaltar (opcional): o aluno salta a conversa sem perder vidas nem pontos (sem minutos, sem rede…).
 * Gasta minutos de conversa do plano. Pede o microfone antes de ligar.
 */
import { Mic } from "lucide-react-native";
import { type ReactNode, useState } from "react";
import { View } from "react-native";
import { Aviso, Botao, Texto, Titulo } from "@/ui";
import { cor, raio } from "@/tema";
import { erroConversa, useConversaComecarLicaoMutation, type ConversaAberta, type Resumo } from "@/dominios/conversa/api";
import { ListaFrases } from "./Pecas";
import { PermissaoMicrofone, useMicrofone } from "./PermissaoMicrofone";
import { Viva } from "./Viva";
import { OfertaPlano } from "@/componentes/subscricao/Oferta";
import { ofertaDe, type OfertaPlano as Oferta } from "@/dominios/subscricao/api";

export const MIN_FALAS_CONVERSA = 2;

export type RespostaConversaCurta = { tipo: "texto"; resposta: { sessao_id: string } } | null;
export type ExercicioConversa = { id: string; pergunta: string; frases?: string[] | null };

type Fase = { tipo: "inicio" } | { tipo: "viva"; dados: ConversaAberta } | { tipo: "fim"; resumo: Resumo } | { tipo: "bloqueada"; mensagem: string; oferta?: Oferta | null };

export function ditasNoResumo(resumo: Resumo, frases: string[]) {
  const usadas = new Set(resumo.objectivos.filter((o) => o.usado || o.com_ajuda).map((o) => o.en));
  return new Set(frases.filter((f) => usadas.has(f)));
}

export function ConversaCurta({ ex, bloqueado, aoMudar, aoSaltar }: { ex: ExercicioConversa; bloqueado: boolean; aoMudar: (r: RespostaConversaCurta) => void; aoSaltar?: () => void }) {
  const [fase, setFase] = useState<Fase>({ tipo: "inicio" });
  const [comecar, { isLoading }] = useConversaComecarLicaoMutation();
  const mic = useMicrofone();
  const frases = ex.frases ?? [];

  const abrir = async () => {
    if (!(await mic.garantir())) return;
    try {
      setFase({ tipo: "viva", dados: await comecar(ex.id).unwrap() });
    } catch (e) {
      setFase({ tipo: "bloqueada", mensagem: erroConversa(e, "Não foi possível começar a conversa agora."), oferta: ofertaDe(e) });
    }
  };

  const terminou = (resumo: Resumo) => {
    setFase({ tipo: "fim", resumo });
    const falas = resumo.transcricao.filter((f) => f.quem === "aluno").length;
    aoMudar(falas >= MIN_FALAS_CONVERSA ? { tipo: "texto", resposta: { sessao_id: resumo.id } } : null);
  };

  const saltar = aoSaltar ? (
    <Botao tipo="ligacao" tamanho="medio" onPress={aoSaltar} disabled={bloqueado}>
      Saltar esta conversa
    </Botao>
  ) : null;

  return (
    <View style={{ gap: 16 }}>
      <Titulo v="tituloM">Conversa curta com o tutor</Titulo>
      <View style={{ gap: 4, borderLeftWidth: 4, borderColor: cor.azulMarca, paddingLeft: 16 }}>
        <Texto v="legenda" suave>
          A situação
        </Texto>
        <Texto style={{ fontSize: 17, lineHeight: 26 }}>{ex.pergunta}</Texto>
      </View>

      {fase.tipo === "viva" ? (
        <Viva dados={fase.dados} frases={frases} aoTerminar={terminou} aoSaltar={aoSaltar} />
      ) : (
        <ListaFrases frases={frases} ditas={fase.tipo === "fim" ? ditasNoResumo(fase.resumo, frases) : undefined} />
      )}

      {fase.tipo === "inicio" ? (
        <View style={{ gap: 12 }}>
          <Texto v="legenda" suave>
            {`Cerca de 2 minutos. Conta para os minutos de conversa do seu plano. Responda pelo menos ${MIN_FALAS_CONVERSA} vezes.`}
          </Texto>
          <Botao onPress={() => void abrir()} disabled={bloqueado} carregando={isLoading} icone={isLoading ? undefined : <Mic size={20} color={cor.sobreMarca} />} style={{ alignSelf: "flex-start" }}>
            Começar a conversa
          </Botao>
          {saltar}
        </View>
      ) : null}

      {fase.tipo === "bloqueada" ? (
        <View style={{ gap: 12 }}>
          <Aviso>{`${fase.mensagem} Pode saltar esta conversa: não perde vidas nem pontos.`}</Aviso>
          {fase.oferta ? <OfertaPlano oferta={fase.oferta} /> : null}
          {saltar}
        </View>
      ) : null}

      {fase.tipo === "fim" ? <Fim resumo={fase.resumo} aoRepetir={() => setFase({ tipo: "inicio" })} saltar={saltar} /> : null}
      <PermissaoMicrofone {...mic.folha} />
    </View>
  );
}

function Fim({ resumo, aoRepetir, saltar }: { resumo: Resumo; aoRepetir: () => void; saltar: ReactNode }) {
  const falas = resumo.transcricao.filter((f) => f.quem === "aluno").length;
  if (falas >= MIN_FALAS_CONVERSA) {
    const c = resumo.correccoes[0];
    return (
      <View style={{ gap: 8, backgroundColor: cor.certoSuave, borderRadius: raio.md, paddingHorizontal: 16, paddingVertical: 14 }}>
        <Texto forte>{`Conversa guardada: respondeu ${falas} vezes. Carregue em Verificar para continuar.`}</Texto>
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
    );
  }
  return (
    <View style={{ gap: 12 }}>
      <Aviso>{`${falas === 0 ? "Não ouvimos nenhuma resposta sua." : "Só respondeu uma vez."} A conversa conta a partir de ${MIN_FALAS_CONVERSA} respostas.`}</Aviso>
      <Botao tamanho="medio" onPress={aoRepetir} style={{ alignSelf: "flex-start" }}>
        Tentar outra vez
      </Botao>
      {saltar}
    </View>
  );
}
