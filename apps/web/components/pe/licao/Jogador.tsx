"use client";

import Link from "next/link";
import { PedirLembrete } from "@/components/pe/avisos/Avisos";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, Heart, Infinity as InfinitoIcone } from "lucide-react";
import { Botao, Etiqueta, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import {
  useAnalisarPronunciaMutation,
  useSaltarExercicioMutation,
  useConcluirLicaoMutation,
  useEstadoVidasQuery,
  useLicaoParaJogarQuery,
  useRecarregarVidasMutation,
  useResponderMutation,
  useTrilhoQuery,
  type ConclusaoLicao,
} from "@/src/domains/student/laboratorio/api";
import { tempoAte } from "@/components/pe/laboratorio/Trilho";
import { CabecalhoLicao, RodapeLicao, type EstadoRodape } from "./Partes";
import { dicaTeclado, ExercicioUI, type RespostaExercicio } from "./Exercicios";

const ILIMITADAS = 999;

type Fase = { tipo: "responder" } | { tipo: "certo"; explicacao?: string | null } | { tipo: "errado"; dica?: string | null; perdeuVida: boolean };

export function Jogador({ lessonId }: { lessonId: string }) {
  const router = useRouter();
  const { data: licao, isLoading, isError, error: erroLicao, refetch } = useLicaoParaJogarQuery(lessonId);
  const { data: vidasEstado } = useEstadoVidasQuery();
  const [responder] = useResponderMutation();
  const [analisar] = useAnalisarPronunciaMutation();
  const [saltar] = useSaltarExercicioMutation();
  const [concluir, { isLoading: aConcluir }] = useConcluirLicaoMutation();

  const [idx, setIdx] = useState<number | null>(null);
  const [tentativa, setTentativa] = useState(0);
  const [resposta, setResposta] = useState<RespostaExercicio>(null);
  const [fase, setFase] = useState<Fase>({ tipo: "responder" });
  const [aVerificar, setAVerificar] = useState(false);
  const [vidasLocal, setVidas] = useState<number | null>(null);
  const [errouEste, setErrouEste] = useState(false);
  const [certasAPrimeira, setCertasAPrimeira] = useState(0);
  const [respondidos, setRespondidos] = useState(0);
  const [sair, setSair] = useState(false);
  const [semVidas, setSemVidas] = useState(false);
  const [conclusao, setConclusao] = useState<ConclusaoLicao | null>(null);
  const [erroConcluir, setErroConcluir] = useState(false);
  const [limiteAoConcluir, setLimiteAoConcluir] = useState<DadosLimite | null>(null);
  const [inicio] = useState(() => Date.now());
  const [duracao, setDuracao] = useState(0);
  const [pontosInicio, setPontosInicio] = useState<number | null>(null);

  // Começa no primeiro exercício por fazer (retoma uma lição deixada a meio).
  if (licao && idx === null) setIdx(licao.repeticao ? 0 : Math.max(0, licao.exercicios.findIndex((e) => !e.feito)));
  // Os pontos de partida servem para mostrar quantos ganhou no fim.
  if (vidasEstado && pontosInicio === null) setPontosInicio(vidasEstado.points);
  const vidas = vidasLocal ?? (vidasEstado ? (vidasEstado.unlimited ? ILIMITADAS : vidasEstado.current) : null);

  const total = licao?.exercicios.length ?? 0;
  const i = idx ?? 0;
  const ex = licao?.exercicios[i];
  const ilimitadas = (vidas ?? 0) >= ILIMITADAS;
  const repeticao = !!licao?.repeticao;

  const indisponivel = ex?.modo === "indisponivel";

  const verificar = useCallback(async () => {
    if (!ex || !resposta || aVerificar) return;
    setAVerificar(true);
    try {
      if (resposta.tipo === "audio") {
        const r = await analisar({ challengeId: ex.id, frase: ex.frase ?? ex.pergunta, audio: resposta.audio });
        if ("error" in r && r.error) {
          const e = r.error as { status?: number; data?: { codigo?: string; error?: string; pode_saltar?: boolean; token_saltar?: string } };
          if (e.data?.error === "hearts") {
            setVidas(0);
            setSemVidas(true);
            return;
          }
          // A análise de pronúncia não está disponível: o exercício é saltado (sem pontos, sem perder vidas)
          // para a lição não ficar bloqueada.
          if (e.data?.codigo === "analise_indisponivel" && e.data.pode_saltar) {
            const s = await saltar({ challengeId: ex.id, token: e.data.token_saltar });
            if (!("error" in s && s.error)) {
              setFase({ tipo: "certo", explicacao: "A análise da pronúncia não está disponível agora. Saltámos este exercício: não conta pontos nem tira vidas." });
              return;
            }
          }
          setFase({
            tipo: "errado",
            dica: e.status === 429 ? "Já usou as análises de pronúncia de hoje. Amanhã há mais." : "Não conseguimos analisar a gravação agora. Grave outra vez.",
            perdeuVida: false,
          });
          return;
        }
        const d = r.data!;
        if (d.user_progress) setVidas(d.user_progress.hearts);
        if (d.ai_analysis.is_acceptable) {
          setFase({ tipo: "certo", explicacao: d.explicacao ?? d.feedback?.message ?? null });
        } else {
          setFase({ tipo: "errado", dica: d.dica ?? d.feedback?.message ?? null, perdeuVida: !repeticao && !ilimitadas });
          setErrouEste(true);
        }
        return;
      }
      const r = await responder({ challengeId: ex.id, resposta: resposta.resposta });
      if ("error" in r && r.error) {
        const corpo = (r.error as { data?: { error?: string } }).data;
        if (corpo?.error === "hearts") {
          setVidas(0);
          setSemVidas(true);
          return;
        }
        setFase({ tipo: "errado", dica: "Não conseguimos verificar a resposta. Verifique a ligação e tente outra vez.", perdeuVida: false });
        return;
      }
      const d = r.data!;
      if (d.user_progress) setVidas(d.user_progress.hearts);
      if (d.correct) {
        setFase({ tipo: "certo", explicacao: d.explicacao });
      } else {
        const perdeu = (d.heartsUsed ?? 0) > 0;
        setFase({ tipo: "errado", dica: d.dica ?? (d.feedback?.hint ? `Começa por "${d.feedback.hint}"` : null), perdeuVida: perdeu });
        setErrouEste(true);
        if (perdeu && d.user_progress && d.user_progress.hearts <= 0) setSemVidas(true);
      }
    } finally {
      setAVerificar(false);
    }
  }, [ex, resposta, aVerificar, analisar, saltar, responder, repeticao, ilimitadas]);

  const terminar = useCallback(async () => {
    setErroConcluir(false);
    const segundos = Math.round((Date.now() - inicio) / 1000);
    setDuracao(segundos);
    const r = await concluir({ lessonId, segundos });
    if ("error" in r && r.error) {
      const d = (r.error as { data?: DadosLimite }).data;
      if (d?.codigo === "limite_licoes") setLimiteAoConcluir(d);
      else setErroConcluir(true);
      return;
    }
    setConclusao(r.data!);
    try {
      localStorage.setItem("pe_licao_concluida", "1"); // o convite para instalar a app só aparece depois da primeira lição
    } catch {}
  }, [concluir, lessonId, inicio]);

  // contar=false: exercício saltado (indisponível), não entra nas contas do fim da lição.
  const avancar = useCallback((contar: boolean) => {
    if (contar) {
      if (!errouEste) setCertasAPrimeira((n) => n + 1);
      setRespondidos((n) => n + 1);
    }
    setErrouEste(false);
    setResposta(null);
    setFase({ tipo: "responder" });
    if (i + 1 >= total) {
      void terminar();
      return;
    }
    setIdx(i + 1);
    setTentativa((t) => t + 1);
  }, [errouEste, i, total, terminar]);
  const continuar = useCallback(() => avancar(true), [avancar]);

  // Conversa desligada ou escuta sem áudio: o servidor marca o exercício como saltado
  // (sem pontos, sem perder vidas) e passa-se ao seguinte.
  const saltarIndisponivel = useCallback(async () => {
    if (!ex || aVerificar) return;
    setAVerificar(true);
    try {
      const s = await saltar({ challengeId: ex.id });
      if ("error" in s && s.error) {
        setFase({ tipo: "errado", dica: "Não conseguimos continuar agora. Verifique a ligação e tente outra vez.", perdeuVida: false });
        return;
      }
      avancar(false);
    } finally {
      setAVerificar(false);
    }
  }, [ex, aVerificar, saltar, avancar]);
  const accaoVerificar = indisponivel ? saltarIndisponivel : verificar;

  // Escuta sem áudio: salta logo, sem a mostrar (só uma tentativa automática por exercício).
  const saltadoAuto = useRef<string | null>(null);
  useEffect(() => {
    if (!ex || ex.modo !== "indisponivel" || ex.motivo !== "sem_audio" || fase.tipo !== "responder") return;
    if (saltadoAuto.current === ex.id) return;
    saltadoAuto.current = ex.id;
    void saltarIndisponivel();
  }, [ex, fase.tipo, saltarIndisponivel]);

  const tentarOutraVez = useCallback(() => {
    setResposta(null);
    setFase({ tipo: "responder" });
    setTentativa((t) => t + 1);
  }, []);

  // Enter avança: verificar, continuar ou tentar outra vez.
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key !== "Enter" || sair || semVidas || conclusao) return;
      // Numa caixa de texto, Shift+Enter muda de linha; Enter sozinho verifica.
      if (e.target instanceof HTMLTextAreaElement && e.shiftKey) return;
      if (e.target instanceof HTMLButtonElement) return;
      e.preventDefault();
      if (fase.tipo === "responder") void accaoVerificar();
      else if (fase.tipo === "certo") continuar();
      else tentarOutraVez();
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [fase, accaoVerificar, continuar, tentarOutraVez, sair, semVidas, conclusao]);

  const estadoRodape: EstadoRodape = useMemo(() => {
    if (fase.tipo === "certo") return { tipo: "certo", explicacao: fase.explicacao };
    if (fase.tipo === "errado") return { tipo: "errado", dica: fase.dica, perdeuVida: fase.perdeuVida };
    return { tipo: "verificar", pronto: !!resposta || indisponivel, aVerificar };
  }, [fase, resposta, aVerificar, indisponivel]);

  if (isLoading || (licao && idx === null)) return <EsqueletoLicao />;
  const limite = (erroLicao as { data?: DadosLimite } | undefined)?.data;
  if (isError && limite?.codigo === "limite_licoes") return <LimiteLicoes d={limite} />;
  const bloqueio = (erroLicao as { data?: { codigo?: string; mensagem?: string } } | undefined)?.data;
  if (isError && (bloqueio?.codigo === "licao_bloqueada" || bloqueio?.codigo === "plano_insuficiente")) {
    const plano = bloqueio.codigo === "plano_insuficiente";
    return (
      <main className="mx-auto flex max-w-[560px] flex-col items-start gap-4 px-5 py-16">
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9">{plano ? "Esta lição não faz parte do seu plano" : "Esta lição ainda está fechada"}</h1>
        <p className="m-0 text-pe-tinta-suave">{bloqueio.mensagem ?? (plano ? "Passe para um plano com este curso para a abrir." : "Termine as lições anteriores para abrir esta.")}</p>
        <div className="flex flex-wrap gap-3">
          {plano ? (
            <Botao asChild tipo="realce">
              <Link href="/user/upgrade?plan=PREMIUM">Ver os planos</Link>
            </Botao>
          ) : null}
          <Botao asChild tipo={plano ? "secundario" : "principal"}>
            <Link href="/user/laboratory/learn">Voltar ao trilho</Link>
          </Botao>
        </div>
      </main>
    );
  }
  if (limiteAoConcluir) return <LimiteLicoes d={limiteAoConcluir} />;
  if (isError || !licao) {
    return (
      <main className="mx-auto flex max-w-[560px] flex-col items-start gap-4 px-5 py-16">
        <h1 className="m-0 text-pe-titulo-m">Não conseguimos abrir esta lição</h1>
        <p className="m-0 text-pe-tinta-suave">O problema é do nosso lado. O que já fez está guardado.</p>
        <div className="flex gap-3">
          <Botao onClick={() => refetch()}>Tentar outra vez</Botao>
          <Botao asChild tipo="secundario">
            <Link href="/user/laboratory/learn">Voltar ao trilho</Link>
          </Botao>
        </div>
      </main>
    );
  }

  if (conclusao) {
    return <LicaoConcluida licao={licao} conclusao={conclusao} certas={certasAPrimeira} total={respondidos} segundos={duracao} pontosInicio={pontosInicio} />;
  }

  const feitos = i + (fase.tipo === "certo" ? 1 : 0);
  return (
    <div className="flex min-h-dvh flex-col">
      <CabecalhoLicao
        feitos={feitos}
        total={total}
        vidas={repeticao ? null : vidas}
        ilimitadas={ilimitadas}
        aoSair={() => (i > 0 || resposta ? setSair(true) : router.push("/user/laboratory/learn"))}
      />
      {repeticao ? (
        <p className="m-0 bg-pe-fundo-suave px-5 py-2 text-center text-pe-legenda">Prática: esta lição já foi feita, por isso não perde vidas.</p>
      ) : null}
      <main className="flex-1">
        <div className="mx-auto flex max-w-[720px] flex-col gap-6 px-5 py-6 md:px-6 md:py-12">
          {ex ? (
            <ExercicioUI key={`${ex.id}-${tentativa}`} ex={ex} bloqueado={fase.tipo !== "responder"} visual={fase.tipo === "responder" ? "livre" : fase.tipo} aoMudar={setResposta} />
          ) : null}
          {erroConcluir ? (
            <div role="alert" className="flex flex-col gap-3 rounded-pe-md bg-pe-errado-suave px-4 py-3">
              <p className="m-0">Não conseguimos guardar o fim da lição. As respostas já estão guardadas.</p>
              <Botao tipo="secundario" tamanho="pequeno" className="self-start" onClick={() => void terminar()}>
                Tentar outra vez
              </Botao>
            </div>
          ) : null}
        </div>
      </main>
      <RodapeLicao
        estado={estadoRodape}
        dicaTeclado={ex ? dicaTeclado(ex) : undefined}
        aoVerificar={() => void accaoVerificar()}
        textoVerificar={indisponivel ? "Continuar" : undefined}
        aoContinuar={continuar}
        aoTentarOutraVez={tentarOutraVez}
        textoContinuar={i + 1 >= total ? (aConcluir ? "A guardar…" : "Terminar lição") : "Continuar"}
      />

      <Dialogo
        aberto={sair}
        aoMudar={setSair}
        titulo="Sair a meio da lição?"
        descricao={`Já fez ${i} de ${total} exercícios. O que acertou fica guardado e pode continuar depois.`}
      >
        <div className="flex flex-col gap-3">
          <Botao larguraTotal onClick={() => setSair(false)}>
            Continuar a lição
          </Botao>
          <Botao larguraTotal tipo="perigo" onClick={() => router.push("/user/laboratory/learn")}>
            Sair da lição
          </Botao>
        </div>
      </Dialogo>

      <SemVidas aberto={semVidas} aoMudar={setSemVidas} aoRecarregar={(n) => { setVidas(n); setSemVidas(false); }} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sem vidas                                                            */
/* ------------------------------------------------------------------ */
function SemVidas({ aberto, aoMudar, aoRecarregar }: { aberto: boolean; aoMudar: (v: boolean) => void; aoRecarregar: (vidas: number) => void }) {
  const { data: estado, refetch } = useEstadoVidasQuery(undefined, { skip: !aberto });
  const [recarregar, { isLoading }] = useRecarregarVidasMutation();
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => {
    if (aberto) void refetch();
  }, [aberto, refetch]);

  const tempo = tempoAte(estado?.next_heart_at);

  return (
    <Dialogo
      aberto={aberto}
      aoMudar={aoMudar}
      titulo="Ficou sem vidas"
      topo={
        <div role="img" aria-label="0 vidas" className="flex gap-2">
          {[0, 1, 2].map((i) => (
            <Heart key={i} aria-hidden className="size-9 text-pe-linha-forte" />
          ))}
        </div>
      }
      descricao={`${tempo ? `A próxima vida volta daqui a ${tempo}. ` : ""}O que já fez nesta lição fica guardado.`}
    >
      {erro ? <p role="alert" className="m-0 rounded-pe-md bg-pe-errado-suave px-3 py-2 text-[15px]">{erro}</p> : null}
      <div className="flex flex-col gap-3">
        <Botao asChild tipo="realce" larguraTotal>
          <Link href="/user/subscription">
            <InfinitoIcone aria-hidden /> Vidas ilimitadas com o Premium
          </Link>
        </Botao>
        <Botao
          tipo="secundario"
          larguraTotal
          disabled={isLoading || (estado ? !estado.can_refill_with_points : false)}
          onClick={async () => {
            setErro(null);
            const r = await recarregar();
            if ("error" in r && r.error) {
              const c = (r.error as { data?: { error?: string; message?: string } }).data;
              setErro(c?.error === "insufficient_points" ? "Ainda não tem 50 pontos. Pode praticar uma lição já feita para ganhar pontos." : c?.message ?? "Não foi possível recarregar agora.");
              return;
            }
            aoRecarregar(r.data!.hearts);
          }}
        >
          {estado && !estado.can_refill_with_points && estado.points < estado.refill_cost_points
            ? `Recarregar por 50 pontos (tem ${estado.points})`
            : "Recarregar por 50 pontos"}
        </Botao>
        <Botao asChild tipo="ligacao" larguraTotal>
          <Link href="/user/laboratory/learn">Voltar ao trilho</Link>
        </Botao>
      </div>
    </Dialogo>
  );
}

/* ------------------------------------------------------------------ */
/* Lição concluída                                                      */
/* ------------------------------------------------------------------ */
function LicaoConcluida({
  licao,
  conclusao,
  certas,
  total,
  segundos,
  pontosInicio,
}: {
  licao: { id: string; titulo: string; curso: { id: string } };
  conclusao: ConclusaoLicao;
  certas: number;
  total: number;
  segundos: number;
  pontosInicio: number | null;
}) {
  const { data: trilho } = useTrilhoQuery(licao.curso.id);
  const proxima = trilho?.unidades.flatMap((u) => u.licoes).find((l) => l.estado === "actual" && l.id !== licao.id);
  const pontos = pontosInicio !== null ? Math.max(0, conclusao.total_points - pontosInicio) : conclusao.points_awarded;
  const minutos = Math.max(1, Math.round(segundos / 60));
  const metaFalta = Math.max(0, conclusao.daily_goal_minutes - conclusao.minutes_today);

  return (
    <main className="mx-auto flex min-h-dvh max-w-[720px] flex-col gap-7 px-5 pb-8 pt-12 md:min-h-0 md:pt-24">
      <div className="flex flex-col gap-2">
        <Etiqueta tipo="certo">
          <CheckCircle2 aria-hidden className="size-[18px]" /> {conclusao.first_completion ? "Lição concluída" : "Prática concluída"}
        </Etiqueta>
        <h1 className="m-0 font-pe-titulo text-[30px] font-bold leading-9 tracking-[-0.015em] md:text-pe-titulo-l">{licao.titulo}</h1>
      </div>

      <dl className="m-0 grid grid-cols-3 gap-3">
        {[
          ["Certas à primeira", `${certas} de ${total}`],
          ["Tempo", `${minutos} min`],
          ["Seguidos", `${conclusao.streak} ${conclusao.streak === 1 ? "dia" : "dias"}`],
        ].map(([dt, dd]) => (
          <div key={dt} className="flex flex-col gap-0.5 rounded-pe-md bg-pe-fundo-suave px-3 py-3.5">
            <dt className="text-pe-legenda text-pe-tinta-suave">{dt}</dt>
            <dd className="m-0 font-pe-titulo text-[22px] font-bold leading-7 md:text-[24px]">{dd}</dd>
          </div>
        ))}
      </dl>

      <div className="pe-sobre-marca flex flex-col gap-1 rounded-pe-fala bg-pe-azul-marca px-6 py-5 text-pe-sobre-marca">
        <span className="font-pe-titulo text-[22px] font-bold leading-7">+{pontos} pontos</span>
        <span className="text-[15px] leading-[22px]">
          {conclusao.hearts_awarded ? `E recuperou ${conclusao.hearts_awarded} vida. ` : ""}
          {conclusao.goal_just_completed
            ? "Cumpriu a meta de hoje."
            : conclusao.goal_completed
              ? "A meta de hoje já está cumprida."
              : `Faltam ${Math.ceil(metaFalta)} min para a meta de hoje (${conclusao.daily_goal_minutes} min).`}
        </span>
      </div>

      <PedirLembrete sequencia={conclusao.streak} />

      <div className="mt-auto flex flex-col gap-3 md:mt-2 md:flex-row-reverse md:justify-start">
        {proxima ? (
          <Botao asChild tipo="realce" className="md:min-w-[220px]">
            <Link href={`/user/laboratory/learn/lesson/${proxima.id}`}>Próxima lição</Link>
          </Botao>
        ) : null}
        <Botao asChild tipo={proxima ? "ligacao" : "principal"} className="md:min-w-[200px]">
          <Link href="/user/laboratory/learn">Voltar ao trilho</Link>
        </Botao>
      </div>
    </main>
  );
}

type DadosLimite = { codigo?: string; limite?: number; feitas?: number; renova_em?: string };

/** Plano Gratuito: o limite de lições novas do dia foi atingido. Repetir lições continua livre. */
function LimiteLicoes({ d }: { d: DadosLimite }) {
  const n = d.limite ?? 3;
  const renova = d.renova_em ? new Date(d.renova_em) : null;
  return (
    <main className="mx-auto flex max-w-[560px] flex-col items-start gap-5 px-5 py-16">
      <span aria-hidden className="pe-sobre-marca flex size-16 items-center justify-center rounded-[22px_22px_22px_0] bg-pe-azul-marca font-pe-titulo text-[26px] font-bold text-pe-realce">
        {n}
      </span>
      <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9">Já fez as {n} lições de hoje</h1>
      <p className="m-0 text-pe-tinta-suave">
        No plano Gratuito há {n} lições novas por dia
        {renova ? `. Amanhã, a partir das ${renova.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" })}, há mais` : ""}. Pode repetir as lições que já fez, sem limite. O que fez nesta lição fica guardado.
      </p>
      <div className="flex flex-wrap gap-3">
        <Botao asChild tipo="realce">
          <Link href="/user/upgrade?plan=PREMIUM">Passar para o Premium</Link>
        </Botao>
        <Botao asChild tipo="secundario">
          <Link href="/user/laboratory/learn">Voltar ao trilho</Link>
        </Botao>
      </div>
    </main>
  );
}

function EsqueletoLicao() {
  return (
    <div aria-busy="true" aria-label="A carregar a lição" className="flex min-h-dvh flex-col">
      <div className="mx-auto flex w-full max-w-[960px] items-center gap-4 px-4 py-4">
        <Osso className="size-8" />
        <Osso className="h-3 flex-1 rounded-full" />
        <Osso className="h-6 w-10" />
      </div>
      <div className="mx-auto flex w-full max-w-[720px] flex-col gap-5 px-5 py-8">
        <Osso className="h-8 w-2/3" />
        <Osso className="h-28 rounded-pe-fala" />
        <Osso className="h-14" />
        <Osso className="h-14" />
        <Osso className="h-14" />
      </div>
    </div>
  );
}
