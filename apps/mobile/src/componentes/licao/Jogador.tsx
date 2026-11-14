/**
 * O leitor de lições (apps/web/components/pe/licao/Jogador.tsx) no telemóvel: a fila de exercícios
 * (os errados voltam ao fim), vidas, verificar/continuar, saltar o que não se pode fazer, sair com
 * confirmação, sem vidas e o fim da lição. Telas Licao*.dc.html, SairLicao, SemVidas e Concluida.
 */
import { router, Stack, usePreventRemove } from "expo-router";
import { CheckCircle2, Heart, Infinity as Infinito } from "lucide-react-native";
import { useEffect, useMemo, useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, type ScrollViewInstance, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  ILIMITADAS,
  tempoAte,
  useConcluirLicaoMutation,
  useEstadoVidasQuery,
  useLabTrilhoQuery,
  useLicaoParaJogarQuery,
  useRecarregarVidasMutation,
  useResponderExercicioMutation,
  useSaltarExercicioMutation,
  type ConclusaoLicao,
  type LicaoParaJogar,
  type ResultadoResponder,
} from "@/dominios/laboratorio/api";
import { analisarPronuncia, responderEmVoz, type ErroGravacao } from "@/dominios/laboratorio/gravacao";
import { balao, cor, fonte, raio } from "@/tema";
import { Aviso, Botao, Dialogo, Ecra, Etiqueta, Numero, Osso, Texto, Titulo } from "@/ui";
import { ExercicioUI, seSalta, type RespostaExercicio, type ResultadoFala } from "./Exercicios";
import { CabecalhoLicao, RodapeLicao, type EstadoRodape } from "./Partes";

type Fase =
  | { tipo: "responder" }
  | { tipo: "certo"; explicacao?: string | null }
  /** repetir: falha técnica (grava-se já outra vez); senão o exercício volta no fim da lição. */
  | { tipo: "errado"; dica?: string | null; perdeuVida: boolean; solucao?: string | null; explicacao?: string | null; repetir?: boolean; falado?: boolean };

/** Respostas da gravação que pedem para gravar outra vez (silêncio, ficheiro recusado ou grande demais). */
const GRAVAR_OUTRA_VEZ = new Set(["sem_fala", "gravacao_invalida", "gravacao_grande"]);

type DadosLimite = { codigo?: string; limite?: number; feitas?: number; renova_em?: string; mensagem?: string };

/** Segundos desde um instante (fora dos componentes: o compilador do React não o vê como render). */
function segundosDesde(t: number) {
  return Math.round((Date.now() - t) / 1000);
}

export const voltarAoTrilho = () => router.dismissTo("/praticar");

/** Começa no primeiro exercício por fazer; a conversa curta fica sempre no fim. */
function filaInicial(licao: LicaoParaJogar) {
  const inicio = licao.repeticao ? 0 : Math.max(0, licao.exercicios.findIndex((e) => !e.feito));
  const porFazer = licao.exercicios.slice(inicio).filter((e) => licao.repeticao || !e.feito);
  const resto = porFazer.length ? porFazer : licao.exercicios;
  return [...resto.filter((e) => e.modo !== "conversa"), ...resto.filter((e) => e.modo === "conversa")].map((e) => e.id);
}

export function Jogador({ lessonId }: { lessonId: string }) {
  const { data: licao, isLoading, isError, error: erroLicao, refetch } = useLicaoParaJogarQuery(lessonId);
  const { data: vidasEstado } = useEstadoVidasQuery();
  const [responder] = useResponderExercicioMutation();
  const [saltar] = useSaltarExercicioMutation();
  const [concluir, { isLoading: aConcluir }] = useConcluirLicaoMutation();

  const [fila, setFila] = useState<string[] | null>(null);
  const [pos, setPos] = useState(0);
  const [tentativa, setTentativa] = useState(0);
  const [resposta, setResposta] = useState<RespostaExercicio>(null);
  const [fase, setFase] = useState<Fase>({ tipo: "responder" });
  const [fala, setFala] = useState<ResultadoFala | null>(null);
  const [avaliacao, setAvaliacao] = useState<ResultadoResponder | null>(null);
  const [aVerificar, setAVerificar] = useState(false);
  const [vidasLocal, setVidas] = useState<number | null>(null);
  const [errados, setErrados] = useState<ReadonlySet<string>>(() => new Set());
  const [acertados, setAcertados] = useState<ReadonlySet<string>>(() => new Set());
  const [saltados, setSaltados] = useState<ReadonlySet<string>>(() => new Set());
  const [sair, setSair] = useState(false);
  const [semVidas, setSemVidas] = useState(false);
  const [conclusao, setConclusao] = useState<ConclusaoLicao | null>(null);
  const [erroConcluir, setErroConcluir] = useState(false);
  const [limiteAoConcluir, setLimiteAoConcluir] = useState<DadosLimite | null>(null);
  const [inicio] = useState(() => Date.now());
  const [duracao, setDuracao] = useState(0);
  const [pontosInicio, setPontosInicio] = useState<number | null>(null);
  const scroll = useRef<ScrollViewInstance>(null);
  const ins = useSafeAreaInsets();

  if (licao && fila === null) setFila(filaInicial(licao));
  if (vidasEstado && pontosInicio === null) setPontosInicio(vidasEstado.points);
  const vidas = vidasLocal ?? (vidasEstado ? (vidasEstado.unlimited ? ILIMITADAS : vidasEstado.current) : null);

  const total = useMemo(() => new Set(fila ?? []).size, [fila]);
  const ex = licao?.exercicios.find((e) => e.id === fila?.[pos]);
  const ultimo = !!fila && pos + 1 >= fila.length;
  const ilimitadas = (vidas ?? 0) >= ILIMITADAS;
  const repeticao = !!licao?.repeticao;
  const salta = !!ex && seSalta(ex);

  // Sair a meio pede confirmação (botão X, gesto de voltar e botão de trás do Android).
  const aMeio = !!licao && !conclusao && (pos > 0 || !!resposta || acertados.size > 0);
  const largar = usePreventRemove(aMeio, () => setSair(true));

  const marcarErrado = (id: string) => setErrados((s) => new Set(s).add(id));

  const errou = (perdeu: boolean, heartsRestantes: number | undefined, extra: Omit<Extract<Fase, { tipo: "errado" }>, "tipo" | "perdeuVida">) => {
    setFase({ tipo: "errado", perdeuVida: perdeu, ...extra });
    if (ex) marcarErrado(ex.id);
    if (perdeu && heartsRestantes !== undefined && heartsRestantes <= 0) setSemVidas(true);
  };
  const acertou = (explicacao?: string | null) => {
    setFase({ tipo: "certo", explicacao: explicacao ?? null });
    if (ex) setAcertados((a) => new Set(a).add(ex.id));
  };

  // Falha técnica numa gravação: salta com o token (sem pontos nem vidas) ou grava outra vez.
  const falhaGravacao = async (e: ErroGravacao, limite: string) => {
    if (!ex) return;
    if (e.data?.error === "hearts") {
      setVidas(0);
      setSemVidas(true);
      return;
    }
    if (e.data?.codigo === "analise_indisponivel" && e.data.pode_saltar) {
      const s = await saltar({ challengeId: ex.id, token: e.data.token_saltar });
      if (!("error" in s && s.error)) {
        setFase({ tipo: "certo", explicacao: "A análise da gravação não está disponível agora. Saltámos este exercício: não conta pontos nem tira vidas." });
        setSaltados((a) => new Set(a).add(ex.id));
        return;
      }
    }
    setFase({
      tipo: "errado",
      dica:
        e.status === 429
          ? limite
          : e.status === "FETCH_ERROR"
            ? "Sem ligação ao servidor. Verifique a Internet e grave outra vez."
            : GRAVAR_OUTRA_VEZ.has(e.data?.codigo ?? "") && e.data?.mensagem
              ? e.data.mensagem
              : "Não conseguimos analisar a gravação agora. Grave outra vez.",
      perdeuVida: false,
      repetir: true,
    });
  };

  const verificar = async () => {
    if (!ex || !resposta || aVerificar) return;
    setAVerificar(true);
    try {
      if (resposta.tipo === "audio" && ex.modo === "responder") {
        const r = await responderEmVoz(ex.id, resposta.gravacao);
        if (r.error) return void (await falhaGravacao(r.error, "Já usou as análises com IA de hoje. Amanhã há mais."));
        const d = r.data;
        if (d.user_progress) setVidas(d.user_progress.hearts);
        setAvaliacao(d);
        if (d.aceite) acertou(d.explicacao);
        // Uma resposta falada não aceite nunca tira vidas (o servidor decide; heartsUsed é sempre 0).
        else errou(false, d.user_progress?.hearts, { dica: d.dica ?? null, falado: true });
        return;
      }

      if (resposta.tipo === "audio") {
        const r = await analisarPronuncia(ex.id, ex.frase ?? ex.pergunta, resposta.gravacao);
        if (r.error) return void (await falhaGravacao(r.error, "Já usou as análises de pronúncia de hoje. Amanhã há mais."));
        const d = r.data;
        if (d.user_progress) setVidas(d.user_progress.hearts);
        setFala({ nota: d.ai_analysis.overall_score, palavras: d.feedback?.problematic_words ?? [], mensagem: d.feedback?.message ?? null, detalhe: d.detalhe ?? null, fonte: d.ai_analysis.fonte ?? null });
        if (d.ai_analysis.is_acceptable) acertou(d.explicacao);
        // Uma gravação não aceite nunca tira vidas (o reconhecimento de fala pode errar com o sotaque).
        else errou(false, d.user_progress?.hearts, { dica: d.dica ?? null, falado: true });
        return;
      }

      const r = await responder({ challengeId: ex.id, resposta: resposta.resposta });
      if ("error" in r && r.error) {
        const corpo = (r.error as { data?: { codigo?: string; error?: string; mensagem?: string } }).data;
        if (corpo?.error === "hearts") {
          setVidas(0);
          setSemVidas(true);
          return;
        }
        const dica = corpo?.codigo === "conversa_incompleta" && corpo.mensagem ? corpo.mensagem : "Não conseguimos verificar a resposta. Verifique a ligação e tente outra vez.";
        setFase({ tipo: "errado", dica, perdeuVida: false, repetir: true });
        return;
      }
      const d = r.data!;
      if (d.user_progress) setVidas(d.user_progress.hearts);
      if (d.correct) acertou(d.explicacao);
      else errou((d.heartsUsed ?? 0) > 0, d.user_progress?.hearts, { dica: d.dica ?? null, solucao: d.solucao ?? null, explicacao: d.explicacao ?? null });
    } finally {
      setAVerificar(false);
    }
  };

  const terminar = async () => {
    setErroConcluir(false);
    const segundos = segundosDesde(inicio);
    setDuracao(segundos);
    const r = await concluir({ lessonId, segundos });
    if ("error" in r && r.error) {
      const d = (r.error as { data?: DadosLimite }).data;
      if (d?.codigo === "limite_licoes") setLimiteAoConcluir(d);
      else setErroConcluir(true);
      return;
    }
    setConclusao(r.data!);
  };

  // Passa ao exercício seguinte; voltar=true põe o actual no fim (errou).
  const avancar = (voltar: boolean) => {
    if (!fila || !ex) return;
    const nova = voltar ? [...fila, ex.id] : fila;
    setResposta(null);
    setFala(null);
    setAvaliacao(null);
    setFase({ tipo: "responder" });
    if (pos + 1 >= nova.length) {
      void terminar();
      return;
    }
    if (voltar) setFila(nova);
    setPos(pos + 1);
    setTentativa((t) => t + 1);
    scroll.current?.scrollTo({ y: 0, animated: false });
  };
  const continuar = () => avancar(fase.tipo === "errado" && !fase.repetir);

  // Exercícios que não se podem fazer: o servidor marca-os como saltados (sem pontos, sem perder vidas).
  const saltarExercicio = async () => {
    if (!ex || aVerificar) return;
    setAVerificar(true);
    try {
      const s = await saltar({ challengeId: ex.id });
      if ("error" in s && s.error) {
        setFase({ tipo: "errado", dica: "Não conseguimos continuar agora. Verifique a ligação e tente outra vez.", perdeuVida: false, repetir: true });
        return;
      }
      setSaltados((a) => new Set(a).add(ex.id));
      avancar(false);
    } finally {
      setAVerificar(false);
    }
  };

  // Escuta sem áudio: salta logo, sem a mostrar (uma tentativa automática por exercício).
  const saltadoAuto = useRef<string | null>(null);
  const exId = ex?.id;
  const semAudio = ex?.modo === "indisponivel" && ex.motivo === "sem_audio";
  useEffect(() => {
    if (!exId || !semAudio || fase.tipo !== "responder" || saltadoAuto.current === exId) return;
    saltadoAuto.current = exId;
    void saltarExercicio();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- só quando muda o exercício
  }, [exId, semAudio, fase.tipo]);

  const tentarOutraVez = () => {
    setResposta(null);
    setFala(null);
    setAvaliacao(null);
    setFase({ tipo: "responder" });
    setTentativa((t) => t + 1);
  };

  const sairJa = () => {
    setSair(false);
    largar();
    voltarAoTrilho();
  };

  const estadoRodape: EstadoRodape =
    fase.tipo === "certo" ? { tipo: "certo", explicacao: fase.explicacao } : fase.tipo === "errado" ? fase : { tipo: "verificar", pronto: !!resposta || salta, aVerificar };

  const opcoesEcra = <Stack.Screen options={{ gestureEnabled: !aMeio }} />;

  if (isLoading || (licao && fila === null)) return <EsqueletoLicao />;
  const dadosErro = (erroLicao as { data?: DadosLimite } | undefined)?.data;
  if (isError && dadosErro?.codigo === "limite_licoes") return <LimiteLicoes d={dadosErro} />;
  if (isError && (dadosErro?.codigo === "licao_bloqueada" || dadosErro?.codigo === "plano_insuficiente")) {
    const plano = dadosErro.codigo === "plano_insuficiente";
    return (
      <Ecra cabecalho={null} style={{ paddingTop: 48 }}>
        <View style={{ gap: 12 }}>
          <Titulo>{plano ? "Esta lição não faz parte do seu plano" : "Esta lição ainda está fechada"}</Titulo>
          <Texto suave>{dadosErro.mensagem ?? (plano ? "Passe para um plano com este curso para a abrir." : "Termine as lições anteriores para abrir esta.")}</Texto>
        </View>
        <View style={{ gap: 12, marginTop: "auto" }}>
          {plano ? (
            <Botao tipo="realce" larguraTotal href="/planos">
              Ver os planos
            </Botao>
          ) : null}
          <Botao tipo={plano ? "secundario" : "principal"} larguraTotal onPress={voltarAoTrilho}>
            Voltar ao trilho
          </Botao>
        </View>
      </Ecra>
    );
  }
  if (limiteAoConcluir) return <LimiteLicoes d={limiteAoConcluir} />;
  if (isError || !licao) {
    return (
      <Ecra style={{ paddingTop: 48 }}>
        <View style={{ gap: 12 }}>
          <Titulo v="tituloM">Não conseguimos abrir esta lição</Titulo>
          <Texto suave>Verifique a ligação à Internet. O que já fez está guardado.</Texto>
        </View>
        <View style={{ gap: 12, marginTop: "auto" }}>
          <Botao larguraTotal onPress={() => void refetch()}>
            Tentar outra vez
          </Botao>
          <Botao tipo="secundario" larguraTotal onPress={voltarAoTrilho}>
            Voltar ao trilho
          </Botao>
        </View>
      </Ecra>
    );
  }

  if (conclusao) {
    // "À primeira": acertados sem nenhum erro antes (os saltados não contam).
    const certas = [...acertados].filter((id) => !errados.has(id)).length;
    return <LicaoConcluida licao={licao} conclusao={conclusao} certas={certas} total={acertados.size} segundos={duracao} pontosInicio={pontosInicio} />;
  }

  const feitos = Math.min(total, acertados.size + saltados.size);
  const aRever = !!ex && errados.has(ex.id) && fase.tipo === "responder";
  const textoContinuar = ultimo && !(fase.tipo === "errado" && !fase.repetir) ? (aConcluir ? "A guardar…" : "Terminar lição") : "Continuar";

  return (
    <View style={{ flex: 1, backgroundColor: cor.fundo, paddingTop: ins.top }}>
      {opcoesEcra}
      <CabecalhoLicao feitos={feitos} total={total} vidas={repeticao ? null : vidas} ilimitadas={ilimitadas} aoSair={() => (aMeio ? setSair(true) : voltarAoTrilho())} />
      {repeticao ? (
        <View style={{ backgroundColor: cor.fundoSuave, paddingHorizontal: 20, paddingVertical: 8 }}>
          <Texto v="legenda" centro>
            Prática: esta lição já foi feita, por isso não perde vidas.
          </Texto>
        </View>
      ) : null}
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <ScrollView ref={scroll} style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 12, paddingBottom: 24, gap: 20 }} keyboardShouldPersistTaps="handled">
          {aRever ? (
            <View style={{ alignSelf: "flex-start", backgroundColor: cor.realceSuave, borderRadius: raio.sm, paddingHorizontal: 12, paddingVertical: 4 }}>
              <Texto v="legenda" forte>
                Para rever: errou este exercício antes
              </Texto>
            </View>
          ) : null}
          {ex ? (
            <ExercicioUI
              key={`${ex.id}-${tentativa}`}
              ex={ex}
              bloqueado={fase.tipo !== "responder" || aVerificar}
              visual={fase.tipo === "responder" ? "livre" : fase.tipo}
              aoMudar={setResposta}
              fala={fala}
              avaliacao={avaliacao}
              aoSaltar={ex.modo === "conversa" ? () => void saltarExercicio() : undefined}
            />
          ) : null}
          {erroConcluir ? (
            <Aviso
              tom="erro"
              accao={
                <Botao tipo="secundario" tamanho="pequeno" onPress={() => void terminar()}>
                  Tentar outra vez
                </Botao>
              }
            >
              Não conseguimos guardar o fim da lição. As respostas já estão guardadas.
            </Aviso>
          ) : null}
        </ScrollView>
        <RodapeLicao
          estado={estadoRodape}
          aoVerificar={() => void (salta ? saltarExercicio() : verificar())}
          textoVerificar={salta ? "Continuar" : "Verificar"}
          textoPorResponder={ex?.modo === "conversa" ? "Termine a conversa para verificar" : ex?.modo === "pares" ? "Ligue todos os pares" : ex?.tipo === "TRUE_FALSE" ? "Escolha uma resposta" : undefined}
          aoContinuar={continuar}
          aoTentarOutraVez={tentarOutraVez}
          textoContinuar={textoContinuar}
        />
      </KeyboardAvoidingView>

      <Dialogo
        aberto={sair}
        aoFechar={() => setSair(false)}
        titulo="Sair a meio da lição?"
        texto={`Já acertou ${acertados.size} de ${total} exercícios. O que acertou fica guardado e pode continuar depois.`}
      >
        <Botao larguraTotal onPress={() => setSair(false)}>
          Continuar a lição
        </Botao>
        <Botao larguraTotal tipo="perigo" onPress={sairJa}>
          Sair da lição
        </Botao>
      </Dialogo>

      <SemVidas
        aberto={semVidas}
        aoFechar={() => setSemVidas(false)}
        aoSair={() => {
          setSemVidas(false);
          largar();
          voltarAoTrilho();
        }}
        aoRecarregar={(n) => {
          setVidas(n);
          setSemVidas(false);
        }}
      />
    </View>
  );
}

/* ------------------------------------------------------------------ */
/* Sem vidas (tela SemVidas)                                            */
/* ------------------------------------------------------------------ */
function SemVidas({ aberto, aoFechar, aoSair, aoRecarregar }: { aberto: boolean; aoFechar: () => void; aoSair: () => void; aoRecarregar: (vidas: number) => void }) {
  const { data: estado, refetch } = useEstadoVidasQuery(undefined, { skip: !aberto });
  const [recarregar, { isLoading }] = useRecarregarVidasMutation();
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => {
    if (aberto) void refetch();
  }, [aberto, refetch]);
  const tempo = tempoAte(estado?.next_heart_at);
  const custo = estado?.refill_cost_points ?? 50;
  const max = estado?.maximum ?? 3;

  return (
    <Dialogo aberto={aberto} aoFechar={aoFechar} titulo="Ficou sem vidas" texto={`${tempo ? `A próxima vida volta daqui a ${tempo}. ` : ""}O seu progresso nesta lição fica guardado.`}>
      <View accessible accessibilityLabel={`0 de ${max} vidas`} style={{ flexDirection: "row", gap: 8 }}>
        {Array.from({ length: max }, (_, i) => (
          <Heart key={i} size={34} color={cor.linhaForte} />
        ))}
      </View>
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
      <Botao tipo="realce" larguraTotal icone={<Infinito size={20} color={cor.tinta} />} href="/planos">
        Vidas ilimitadas com o Premium
      </Botao>
      <Botao
        tipo="secundario"
        larguraTotal
        carregando={isLoading}
        disabled={estado ? !estado.can_refill_with_points : false}
        onPress={async () => {
          setErro(null);
          const r = await recarregar();
          if ("error" in r && r.error) {
            const c = (r.error as { data?: { error?: string; message?: string } }).data;
            setErro(c?.error === "insufficient_points" ? `Ainda não tem ${custo} pontos. Pode praticar uma lição já feita para ganhar pontos.` : (c?.message ?? "Não foi possível recarregar agora."));
            return;
          }
          aoRecarregar(r.data!.hearts);
        }}
      >
        {estado && !estado.can_refill_with_points && estado.points < custo ? `Recarregar por ${custo} pontos (tem ${estado.points})` : `Recarregar por ${custo} pontos`}
      </Botao>
      <Botao tipo="ligacao" larguraTotal onPress={aoSair}>
        Voltar ao trilho
      </Botao>
    </Dialogo>
  );
}

/* ------------------------------------------------------------------ */
/* Lição concluída (tela Concluida)                                     */
/* ------------------------------------------------------------------ */
function LicaoConcluida({ licao, conclusao, certas, total, segundos, pontosInicio }: { licao: LicaoParaJogar; conclusao: ConclusaoLicao; certas: number; total: number; segundos: number; pontosInicio: number | null }) {
  const { data: trilho } = useLabTrilhoQuery(licao.curso.id);
  const proxima = trilho?.unidades.flatMap((u) => u.licoes).find((l) => l.estado === "actual" && l.id !== licao.id);
  const pontos = pontosInicio !== null ? Math.max(0, conclusao.total_points - pontosInicio) : conclusao.points_awarded;
  const minutos = Math.max(1, Math.round(segundos / 60));
  const metaFalta = Math.max(0, conclusao.daily_goal_minutes - conclusao.minutes_today);

  return (
    <Ecra style={{ paddingTop: 48, gap: 28 }}>
      <Stack.Screen options={{ gestureEnabled: true }} />
      <View style={{ gap: 8 }}>
        <Etiqueta tom="certo" icone={<CheckCircle2 size={18} color={cor.certo} />}>
          {conclusao.first_completion ? "Lição concluída" : "Prática concluída"}
        </Etiqueta>
        <Titulo v="tituloXL">{licao.titulo}</Titulo>
      </View>

      <View style={{ flexDirection: "row", gap: 12 }}>
        <Numero rotulo="À primeira" valor={`${certas} de ${total}`} />
        <Numero rotulo="Tempo" valor={`${minutos} min`} />
        <Numero rotulo="Seguidos" valor={`${conclusao.streak} ${conclusao.streak === 1 ? "dia" : "dias"}`} />
      </View>

      <View style={[balao.grande, { backgroundColor: cor.azulMarca, padding: 24, gap: 4 }]}>
        <Texto cor={cor.sobreMarca} style={{ fontFamily: fonte.titulo, fontSize: 22, lineHeight: 28 }}>
          +{pontos} pontos
        </Texto>
        <Texto cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
          {conclusao.hearts_awarded ? `E recuperou ${conclusao.hearts_awarded} vida. ` : ""}
          {conclusao.goal_just_completed
            ? "Cumpriu a meta de hoje."
            : conclusao.goal_completed
              ? "A meta de hoje já está cumprida."
              : `Faltam ${Math.ceil(metaFalta)} min para a meta de hoje (${conclusao.daily_goal_minutes} min).`}
        </Texto>
      </View>

      <View style={{ marginTop: "auto", gap: 12 }}>
        {proxima ? (
          <Botao tipo="realce" larguraTotal onPress={() => router.replace(`/licao/${proxima.id}`)}>
            Próxima lição
          </Botao>
        ) : null}
        <Botao tipo={proxima ? "ligacao" : "principal"} larguraTotal onPress={voltarAoTrilho}>
          Voltar ao trilho
        </Botao>
      </View>
    </Ecra>
  );
}

/** Plano Gratuito: o limite de lições novas do dia foi atingido. Repetir lições continua livre. */
function LimiteLicoes({ d }: { d: DadosLimite }) {
  const n = d.limite ?? 3;
  const renova = d.renova_em ? new Date(d.renova_em) : null;
  const hora = renova ? `${String(renova.getHours()).padStart(2, "0")}:${String(renova.getMinutes()).padStart(2, "0")}` : null;
  return (
    <Ecra style={{ paddingTop: 48, gap: 20 }}>
      <View style={{ width: 64, height: 64, borderTopLeftRadius: 22, borderTopRightRadius: 22, borderBottomRightRadius: 22, borderBottomLeftRadius: 0, alignItems: "center", justifyContent: "center", backgroundColor: cor.azulMarca }}>
        <Texto cor={cor.realce} style={{ fontFamily: fonte.titulo, fontSize: 26, lineHeight: 32 }}>
          {n}
        </Texto>
      </View>
      <View style={{ gap: 8 }}>
        <Titulo>Já fez as {n} lições de hoje</Titulo>
        <Texto suave>
          No plano Gratuito há {n} lições novas por dia{hora ? `. Amanhã, a partir das ${hora}, há mais` : ""}. Pode repetir as lições que já fez, sem limite. O que fez nesta lição fica guardado.
        </Texto>
      </View>
      <View style={{ gap: 12, marginTop: "auto" }}>
        <Botao tipo="realce" larguraTotal href="/planos">
          Passar para o Premium
        </Botao>
        <Botao tipo="secundario" larguraTotal onPress={voltarAoTrilho}>
          Voltar ao trilho
        </Botao>
      </View>
    </Ecra>
  );
}

function EsqueletoLicao() {
  const ins = useSafeAreaInsets();
  return (
    <View accessible accessibilityLabel="A carregar a lição" accessibilityState={{ busy: true }} style={{ flex: 1, backgroundColor: cor.fundo, paddingTop: ins.top + 12, paddingHorizontal: 20, gap: 24 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
        <Osso altura={28} largura={28} raio={6} />
        <View style={{ flex: 1 }}>
          <Osso altura={10} raio={999} />
        </View>
        <Osso altura={22} largura={36} raio={6} />
      </View>
      <Osso altura={28} largura="70%" raio={6} />
      <Osso altura={110} raio={28} />
      <Osso altura={56} raio={6} />
      <Osso altura={56} raio={6} />
      <Osso altura={56} raio={6} />
    </View>
  );
}
