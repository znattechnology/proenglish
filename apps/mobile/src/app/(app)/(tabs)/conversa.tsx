/**
 * Separador "Conversa": preparar a conversa com o tutor (tela PrepararConversa do canvas).
 * Web: apps/web/app/(estudante)/user/laboratory/speaking/real-time/page.tsx (formulário).
 * Escolher a situação, a forma de corrigir, o nível e a área; os minutos do plano; começar.
 */
import { router, useLocalSearchParams } from "expo-router";
import { Clock, Lock, Mic, Target, TrendingUp, Volume2 } from "lucide-react-native";
import { type ReactNode, useState } from "react";
import { Pressable, View } from "react-native";
import { Aviso, Botao, BotaoIcone, Cabecalho, Ecra, EstadoErro, EstadoVazio, Osso, Pilulas, Texto } from "@/ui";
import { cor, raio } from "@/tema";
import {
  NIVEIS_DESCRICAO,
  erroConversa,
  useConversaComecarMutation,
  useConversaPrepararQuery,
  type Correcao,
  type Nivel,
  type Objectivo,
  type Preparar,
} from "@/dominios/conversa/api";
import { vozDisponivel } from "@/componentes/conversa/chamada";
import { EscolherNivel, OpcaoCartao } from "@/componentes/conversa/Pecas";
import { PermissaoMicrofone, useMicrofone } from "@/componentes/conversa/PermissaoMicrofone";
import { guardarSessao } from "@/componentes/conversa/sessoesAbertas";
import { falar } from "@/componentes/conversa/voz";
import { FolhaOferta } from "@/componentes/subscricao/Oferta";
import { ofertaDe, type OfertaPlano } from "@/dominios/subscricao/api";

const CORRECOES: { id: Correcao; nome: string; descricao: string }[] = [
  { id: "suave", nome: "Suave", descricao: "O tutor não interrompe: repete a sua ideia já na forma certa e continua." },
  { id: "directa", nome: "Directa", descricao: "Quando ouve um erro claro, o tutor diz logo o que estava mal e a forma certa." },
];

export default function SeparadorConversa() {
  const { situacao } = useLocalSearchParams<{ situacao?: string }>();
  const { data, isError, error, refetch, isFetching } = useConversaPrepararQuery();
  const cabecalho = (
    <Cabecalho
      semVoltar
      titulo="Preparar a conversa"
      subtitulo="Conversa com o tutor"
      direita={
        <BotaoIcone rotulo="Progresso a falar" href="/conversa/progresso">
          <TrendingUp size={24} color={cor.tinta} />
        </BotaoIcone>
      }
    />
  );

  if (isError)
    return (
      <Ecra cabecalho={cabecalho} aoActualizar={refetch} aActualizar={isFetching}>
        <EstadoErro erro={error} titulo="Não conseguimos preparar a conversa" aoTentar={refetch} />
      </Ecra>
    );
  if (!data)
    return (
      <Ecra cabecalho={cabecalho}>
        <View accessible accessibilityLabel="A carregar" style={{ gap: 12 }}>
          <Osso altura={24} largura="40%" />
          <Osso altura={72} />
          <Osso altura={72} />
          <Osso altura={72} />
          <Osso altura={44} />
        </View>
      </Ecra>
    );
  if (!data.situacoes.length)
    return (
      <Ecra cabecalho={cabecalho} aoActualizar={refetch} aActualizar={isFetching}>
        <EstadoVazio titulo="Ainda não há situações para conversar" texto="Quando houver situações de conversa para o seu nível, aparecem aqui. Entretanto, pratique no laboratório." accao={<Botao href="/praticar">Ir praticar</Botao>} />
      </Ecra>
    );
  return <Formulario key={situacao ?? "-"} p={data} pedida={situacao} cabecalho={cabecalho} aoActualizar={refetch} aActualizar={isFetching} />;
}

function Formulario({ p, pedida, cabecalho, aoActualizar, aActualizar }: { p: Preparar; pedida?: string; cabecalho: ReactNode; aoActualizar: () => void; aActualizar: boolean }) {
  const inicial = p.situacoes.find((s) => s.id === pedida) ?? p.situacoes[0];
  // O nível vem do perfil de fala do aluno; sem perfil, o que o professor sugere. O aluno pode mudar.
  const nivelDe = (s?: Preparar["situacoes"][number]) => p.perfil?.nivel ?? s?.nivel ?? p.preferencias.nivel;
  const [situacao, setSituacao] = useState(inicial?.id ?? "");
  const [correcao, setCorrecao] = useState<Correcao>(inicial?.correcao ?? p.preferencias.correcao);
  const [nivel, setNivel] = useState<Nivel>(nivelDe(inicial));
  const [area, setArea] = useState(p.preferencias.area);
  const [comecar, { isLoading }] = useConversaComecarMutation();
  const [erro, setErro] = useState<string | null>(null);
  // 403 sem_minutos / plano_sem_tutor / teste_expirado ao criar a sessão, com o plano que resolve.
  const [limite, setLimite] = useState<{ mensagem: string; oferta: OfertaPlano } | null>(null);
  const mic = useMicrofone();
  const escolhida = p.situacoes.find((s) => s.id === situacao);
  const q = p.quota;
  const voz = vozDisponivel();
  const semVoz = p.modo === "vapi" && !voz.disponivel ? voz.motivo : null;

  const escolherSituacao = (id: string) => {
    const s = p.situacoes.find((x) => x.id === id);
    setSituacao(id);
    setNivel(nivelDe(s));
    setCorrecao(s?.correcao ?? p.preferencias.correcao);
  };

  const bloqueio =
    q.motivo === "plano_sem_tutor"
      ? "A conversa com o tutor não faz parte do seu plano."
      : q.motivo === "teste_expirado"
        ? "O período de experiência da conversa com o tutor terminou."
        : q.motivo === "sem_minutos"
          ? `Já usou os ${q.minutos_dia} minutos de conversa de hoje. Amanhã tem mais.`
          : null;

  const abrir = async () => {
    setErro(null);
    if (p.modo === "vapi" && !(await mic.garantir())) return;
    try {
      const sessao = await comecar({ situacao, nivel, correcao, area }).unwrap();
      guardarSessao({ sessao, modo: p.modo, chavePublica: p.vapi?.public_key ?? null, minutosUsadosHoje: q.minutos_usados, minutosDia: q.minutos_dia });
      router.push(`/conversa/sessao?id=${encodeURIComponent(sessao.id)}`);
    } catch (e) {
      const oferta = ofertaDe(e);
      if (oferta) setLimite({ mensagem: erroConversa(e), oferta });
      else setErro(erroConversa(e));
    }
  };

  const areas = p.areas.map((a) => ({ valor: a.id, nome: a.nome }));
  const rodape = (
    <>
      {bloqueio ? null : (
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <Clock size={18} color={cor.tinta} />
          <Texto v="legenda" style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>
            {q.minutos_restantes === null
              ? `Conversas até ${q.max_minutos_sessao} minutos.`
              : `Hoje ainda tem ${q.minutos_restantes} dos ${q.minutos_dia} minutos de conversa.`}
          </Texto>
        </View>
      )}
      <Botao
        larguraTotal
        onPress={() => void abrir()}
        disabled={!q.pode_comecar || !situacao || !!semVoz}
        carregando={isLoading}
        icone={<Mic size={20} color={!q.pode_comecar || !situacao || semVoz ? cor.tintaSuave : cor.sobreMarca} />}
      >
        {isLoading ? "A começar…" : "Começar a conversa"}
      </Botao>
    </>
  );

  return (
    <Ecra cabecalho={cabecalho} rodape={rodape} aoActualizar={aoActualizar} aActualizar={aActualizar} style={{ gap: 28 }}>
      <View accessibilityRole="radiogroup" accessibilityLabel="Situação" style={{ gap: 10 }}>
        <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
          Situação
        </Texto>
        {p.situacoes.map((s) => (
          <OpcaoCartao
            key={s.id}
            titulo={s.titulo}
            descricao={`${s.descricao} ${s.minutos_sugeridos} minutos.${s.curso ? ` Do curso «${s.curso.titulo}».` : ""}`.trim()}
            escolhida={s.id === situacao}
            aoEscolher={() => escolherSituacao(s.id)}
          />
        ))}
      </View>

      <Objectivos lista={p.objectivos?.[situacao] ?? []} />

      <View style={{ gap: 10 }}>
        <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
          O seu nível
        </Texto>
        <EscolherNivel niveis={p.niveis} valor={nivel} aoMudar={(n) => setNivel(n as Nivel)} />
        <Texto v="legenda" suave>{`${nivel}: ${NIVEIS_DESCRICAO[nivel]}`}</Texto>
        {p.perfil?.nivel ? (
          <Texto v="legenda" suave>
            {nivel === p.perfil.nivel ? "Escolhemos pelas suas últimas conversas e lições." : `Pelas suas conversas e lições, o seu nível é ${p.perfil.nivel}.`}
          </Texto>
        ) : null}
        {escolhida?.nivel || escolhida?.correcao ? (
          <Texto v="legenda" suave>
            {`O professor sugere ${[escolhida.nivel ? `o nível ${escolhida.nivel}` : "", escolhida.correcao ? `a correcção ${escolhida.correcao}` : ""].filter(Boolean).join(" e ")} para esta situação. Pode mudar.`}
          </Texto>
        ) : null}
      </View>

      {areas.length ? (
        <View style={{ gap: 10 }}>
          <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
            Vocabulário da área
          </Texto>
          <Pilulas opcoes={areas} valor={area} aoMudar={setArea} rotulo="Vocabulário da área" />
        </View>
      ) : null}

      <View accessibilityRole="radiogroup" accessibilityLabel="Como quer ser corrigido" style={{ gap: 10 }}>
        <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
          Como quer ser corrigido
        </Texto>
        {CORRECOES.map((o) => (
          <OpcaoCartao key={o.id} titulo={o.nome} descricao={o.descricao} escolhida={o.id === correcao} aoEscolher={() => setCorrecao(o.id)} />
        ))}
      </View>

      {bloqueio ? (
        <View style={{ gap: 12, backgroundColor: cor.realceSuave, borderRadius: raio.md, padding: 16 }}>
          <View style={{ flexDirection: "row", gap: 10 }}>
            <Lock size={20} color={cor.tinta} style={{ marginTop: 1 }} />
            <Texto style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>{bloqueio}</Texto>
          </View>
          {/* A quota (GET) não traz oferta: só a ligação para os planos. */}
          <Botao tipo="secundario" tamanho="pequeno" href="/planos" style={{ alignSelf: "flex-start" }}>
            Ver os planos
          </Botao>
        </View>
      ) : null}
      {semVoz ? <Aviso titulo="Sem voz nesta versão">{semVoz}</Aviso> : null}
      {p.modo === "simulado" ? <Aviso>Modo de ensaio: o tutor responde com um guião, sem chamada de voz real. Escreva as respostas em inglês e o telemóvel lê as do tutor. As notas são indicativas.</Aviso> : null}
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}

      <Botao tipo="ligacao" href="/conversa/progresso" style={{ alignSelf: "center" }}>
        Ver o seu progresso na conversa
      </Botao>
      <PermissaoMicrofone {...mic.folha} />
      {limite ? (
        <FolhaOferta aberto aoFechar={() => setLimite(null)} titulo="Sem minutos de conversa" mensagem={limite.mensagem} oferta={limite.oferta}>
          <Botao tipo="ligacao" larguraTotal onPress={() => setLimite(null)}>
            Agora não
          </Botao>
        </FolhaOferta>
      ) : null}
    </Ecra>
  );
}

/** As frases-alvo desta conversa: o tutor cria ocasiões para o aluno as dizer. */
function Objectivos({ lista }: { lista: Objectivo[] }) {
  if (!lista.length) return null;
  return (
    <View style={{ gap: 8, backgroundColor: cor.fundoSuave, borderRadius: raio.md, padding: 16 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <Target size={20} color={cor.azulMarca} />
        <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
          Objectivos desta conversa
        </Texto>
      </View>
      <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
        Tente dizer estas frases sozinho durante a conversa. O tutor vai dar-lhe ocasiões para as usar.
      </Texto>
      {lista.map((o, i) => (
        <Pressable
          key={o.en}
          accessibilityRole="button"
          accessibilityLabel={`Ouvir: ${o.en}${o.pt ? `. ${o.pt}` : ""}`}
          onPress={() => falar(o.en)}
          style={({ pressed }) => ({ flexDirection: "row", gap: 12, minHeight: 44, paddingVertical: 10, borderTopWidth: i ? 1 : 0, borderColor: cor.fundoForte, opacity: pressed ? 0.7 : 1 })}
        >
          <Volume2 size={20} color={cor.azulMarca} style={{ marginTop: 2 }} />
          <View style={{ flex: 1 }}>
            <Texto forte style={{ lineHeight: 22 }}>
              {o.en}
            </Texto>
            {o.pt ? (
              <Texto v="legenda" suave>
                {o.pt}
              </Texto>
            ) : null}
          </View>
        </Pressable>
      ))}
    </View>
  );
}
