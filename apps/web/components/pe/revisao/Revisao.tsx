"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, CheckCircle2, X, XCircle } from "lucide-react";
import { BarraProgresso, Botao, Etiqueta, Osso } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import {
  nFrases,
  useFalarRevisaoMutation,
  useResponderRevisaoMutation,
  useSaltarRevisaoMutation,
  useSessaoRevisaoQuery,
  useTerminarRevisaoMutation,
  type FimRevisao,
  type ResultadoRevisao,
} from "@/src/domains/student/revisao/api";
import { BotaoOuvirFrase, ExercicioRevisaoUI, type RespostaRevisao } from "./Exercicios";
import { AvisoAnaliseAproximada, PalavrasComNota } from "@/components/pe/fala/Fala";
import { FolhaOferta } from "@/components/pe/subscricao/Oferta";
import { ofertaDoErro, type Oferta } from "@/src/domains/student/subscricao/api";

const VOLTAR = "/user/laboratory/learn";

const ROTULO_ESTADO: Record<string, string> = {
  vista: "Vista",
  reconhecida: "Reconhecida",
  com_ajuda: "Disse com ajuda",
  sozinho: "Disse sozinho",
};

type Fase =
  | { tipo: "responder" }
  | { tipo: "resultado"; r: ResultadoRevisao }
  | { tipo: "aviso"; mensagem: string; podeSaltar: boolean };

/** A revisão de hoje: um exercício de cada vez, sem vidas; no fim, o resumo. */
export function Revisao() {
  const router = useRouter();
  const { data: sessao, isLoading, isFetching, isError, refetch } = useSessaoRevisaoQuery();
  const [responder] = useResponderRevisaoMutation();
  const [saltarNoServidor] = useSaltarRevisaoMutation();
  const [falar] = useFalarRevisaoMutation();
  const [terminar, { isLoading: aTerminar }] = useTerminarRevisaoMutation();

  const [i, setI] = useState(0);
  const [resposta, setResposta] = useState<RespostaRevisao>(null);
  const [fase, setFase] = useState<Fase>({ tipo: "responder" });
  const [aVerificar, setAVerificar] = useState(false);
  const [fim, setFim] = useState<FimRevisao | null>(null);
  const [erroFim, setErroFim] = useState(false);
  const [inicio, setInicio] = useState(() => new Date().toISOString());
  const [tentativa, setTentativa] = useState(0);
  // Limite de análises de pronúncia: o plano que dá mais (a API decide), numa folha.
  const [limite, setLimite] = useState<{ mensagem: string; oferta: Oferta } | null>(null);
  const inicioExercicio = useRef(0);
  useEffect(() => {
    inicioExercicio.current = Date.now();
  }, [i]);

  const total = sessao?.exercicios.length ?? 0;
  const ex = sessao?.exercicios[i];

  const acabar = useCallback(async () => {
    setErroFim(false);
    const r = await terminar({ inicio });
    if ("error" in r && r.error) setErroFim(true);
    else setFim(r.data!);
  }, [terminar, inicio]);

  const verificar = useCallback(async () => {
    if (!ex || !resposta || aVerificar) return;
    setAVerificar(true);
    const segundos = Math.round((Date.now() - inicioExercicio.current) / 1000);
    try {
      const r =
        resposta.tipo === "audio"
          ? await falar({ exercicioId: ex.id, audio: resposta.audio, segundos })
          : await responder({ exercicioId: ex.id, forma: ex.forma, resposta: resposta.valor, segundos });
      if ("error" in r && r.error) {
        const e = r.error as { status?: number | string; data?: { codigo?: string; mensagem?: string; pode_saltar?: boolean } };
        const mensagem = e.data?.mensagem ?? "Não conseguimos verificar agora. Verifique a ligação e tente outra vez.";
        setFase({ tipo: "aviso", mensagem, podeSaltar: !!e.data?.pode_saltar || e.status === 404 });
        const oferta = e.data?.codigo === "limite_analises" ? ofertaDoErro(r.error) : null;
        if (oferta) setLimite({ mensagem, oferta });
        return;
      }
      setFase({ tipo: "resultado", r: r.data! });
    } finally {
      setAVerificar(false);
    }
  }, [ex, resposta, aVerificar, falar, responder]);

  const seguinte = useCallback(() => {
    setResposta(null);
    setFase({ tipo: "responder" });
    if (i + 1 >= total) void acabar();
    else setI(i + 1);
  }, [i, total, acabar]);

  // Saltar (sem microfone, sem análises, análise em baixo): o servidor tira-o de hoje sem pontos e a
  // frase volta amanhã. Se o pedido falhar, segue na mesma (a frase fica para hoje).
  const [aSaltar, setASaltar] = useState(false);
  const saltar = useCallback(async () => {
    if (!ex || aSaltar) return;
    setASaltar(true);
    try {
      if (ex.forma === "ouvir_repetir") await saltarNoServidor({ exercicioId: ex.id });
    } finally {
      setASaltar(false);
    }
    seguinte();
  }, [ex, aSaltar, saltarNoServidor, seguinte]);

  const outraVez = useCallback(() => {
    setResposta(null);
    setFase({ tipo: "responder" });
    setTentativa((t) => t + 1);
  }, []);

  // "Rever mais": uma sessão nova com o que ainda está para hoje.
  const recomecar = useCallback(() => {
    setFim(null);
    setI(0);
    setResposta(null);
    setFase({ tipo: "responder" });
    setInicio(new Date().toISOString());
    void refetch();
  }, [refetch]);

  // Enter: verificar ou continuar.
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key !== "Enter" || fim) return;
      if (e.target instanceof HTMLTextAreaElement && e.shiftKey) return;
      if (e.target instanceof HTMLButtonElement) return;
      e.preventDefault();
      if (fase.tipo === "responder") void verificar();
      else if (fase.tipo === "resultado") seguinte();
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [fase, verificar, seguinte, fim]);

  // Também ao recarregar ("Rever mais"): nunca mostrar o exercício antigo enquanto chega a sessão nova.
  if (isLoading || isFetching) return <Esqueleto />;
  if (isError || !sessao) {
    return (
      <main className="mx-auto flex max-w-[560px] flex-col items-start gap-4 px-5 py-16">
        <h1 className="m-0 text-pe-titulo-m">Não conseguimos abrir a revisão</h1>
        <p className="m-0 text-pe-tinta-suave">O problema é do nosso lado. As suas frases estão guardadas.</p>
        <div className="flex flex-wrap gap-3">
          <Botao onClick={() => refetch()}>Tentar outra vez</Botao>
          <Botao asChild tipo="secundario">
            <Link href={VOLTAR}>Voltar ao laboratório</Link>
          </Botao>
        </div>
      </main>
    );
  }
  if (fim) return <Fim fim={fim} aoRecomecar={recomecar} />;
  if (total === 0) return <EmDia />;

  const feitos = i + (fase.tipo === "resultado" ? 1 : 0);
  const visual = fase.tipo === "resultado" ? (fase.r.correcta ? "certo" : "errado") : "livre";

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b border-pe-linha">
        <div className="mx-auto flex max-w-[960px] items-center gap-3 px-4 py-3 md:gap-5 md:px-6 md:py-4">
          <button
            type="button"
            onClick={() => router.push(VOLTAR)}
            aria-label="Sair da revisão"
            className="flex size-11 shrink-0 items-center justify-center rounded-pe-sm text-pe-tinta hover:bg-pe-fundo-suave"
          >
            <X aria-hidden className="size-6" />
          </button>
          <BarraProgresso valor={(100 * feitos) / total} rotulo={`Exercício ${Math.min(i + 1, total)} de ${total}`} altura={12} className="flex-1" />
          <span className="shrink-0 text-[15px] tabular-nums text-pe-tinta-suave">
            {Math.min(i + 1, total)} de {total}
          </span>
        </div>
      </header>
      <main className="flex-1">
        <div className="mx-auto flex max-w-[720px] flex-col gap-6 px-5 py-6 md:px-6 md:py-12">
          {ex?.padrao ? (
            <p className="m-0 self-start rounded-pe-sm bg-pe-realce-suave px-3 py-1.5 text-pe-legenda">Treinar um erro frequente: {ex.padrao.descricao}</p>
          ) : ex?.nova ? (
            <p className="m-0 self-start rounded-pe-sm bg-pe-fundo-suave px-3 py-1.5 text-pe-legenda">Frase nova na revisão</p>
          ) : null}
          {ex ? <ExercicioRevisaoUI
              key={`${ex.id}-${tentativa}`}
              ex={ex}
              bloqueado={fase.tipo !== "responder" || aSaltar}
              visual={visual}
              aoMudar={setResposta}
              aoSaltar={() => void saltar()}
            /> : null}
          {erroFim ? (
            <div role="alert" className="flex flex-col gap-3 rounded-pe-md bg-pe-errado-suave px-4 py-3">
              <p className="m-0">Não conseguimos fechar a revisão. As respostas já estão guardadas.</p>
              <Botao tipo="secundario" tamanho="pequeno" className="self-start" onClick={() => void acabar()}>
                Tentar outra vez
              </Botao>
            </div>
          ) : null}
        </div>
      </main>
      <Rodape
        fase={fase}
        pronto={!!resposta}
        aVerificar={aVerificar || aTerminar || aSaltar}
        ultimo={i + 1 >= total}
        aoVerificar={() => void verificar()}
        aoContinuar={seguinte}
        aoSaltar={() => void saltar()}
        aoTentar={outraVez}
      />
      <FolhaOferta aberto={!!limite} aoMudar={(v) => !v && setLimite(null)} titulo="Já usou as análises de pronúncia de hoje" mensagem={limite?.mensagem} oferta={limite?.oferta}>
        <Botao
          tipo="ligacao"
          larguraTotal
          onClick={() => {
            setLimite(null);
            void saltar();
          }}
        >
          Saltar este exercício
        </Botao>
      </FolhaOferta>
    </div>
  );
}

function Rodape({
  fase,
  pronto,
  aVerificar,
  ultimo,
  aoVerificar,
  aoContinuar,
  aoSaltar,
  aoTentar,
}: {
  fase: Fase;
  pronto: boolean;
  aVerificar: boolean;
  ultimo: boolean;
  aoVerificar: () => void;
  aoContinuar: () => void;
  aoSaltar: () => void;
  aoTentar: () => void;
}) {
  const r = fase.tipo === "resultado" ? fase.r : null;
  const certo = !!r?.correcta;
  const errado = !!r && !r.correcta;
  const textoContinuar = ultimo ? (aVerificar ? "A guardar…" : "Ver o resumo") : "Continuar";
  return (
    <footer
      className={cnPe(
        "border-t motion-safe:transition-colors",
        certo ? "border-transparent bg-pe-certo-suave" : errado ? "border-transparent bg-pe-errado-suave" : "border-pe-linha bg-pe-fundo"
      )}
    >
      <div className="mx-auto flex max-w-[960px] flex-col gap-3 px-5 pb-5 pt-4 md:flex-row md:items-center md:justify-between md:gap-8 md:px-6 md:py-5">
        {r ? (
          <div role="status" aria-live="assertive" className="flex min-w-0 gap-3">
            {certo ? <CheckCircle2 aria-hidden className="mt-0.5 size-7 shrink-0 text-pe-certo md:size-8" /> : <XCircle aria-hidden className="mt-0.5 size-7 shrink-0 text-pe-errado md:size-8" />}
            <div className="flex min-w-0 flex-col gap-1">
              <span className={cnPe("font-pe-titulo text-[18px] font-bold leading-6 md:text-pe-titulo-s", certo ? "text-pe-certo" : "text-pe-errado")}>
                {certo ? (r.analise ? `Certo. ${r.analise.nota} de 100 na pronúncia` : "Certo") : r.analise ? `Ainda não. ${r.analise.nota} de 100 na pronúncia` : "Ainda não"}
              </span>
              <AvisoAnaliseAproximada fonte={r.analise?.fonte} />
              <span className="text-[16px] leading-6">
                <span className="text-pe-tinta-suave">{certo ? "A frase: " : "Resposta certa: "}</span>
                <span className="font-semibold">{r.texto}</span>
              </span>
              {r.traducao ? <span className="text-[15px] leading-[22px] text-pe-tinta-suave">{r.traducao}</span> : null}
              {r.analise?.detalhe ? (
                <PalavrasComNota detalhe={r.analise.detalhe} />
              ) : r.analise?.palavras.length ? (
                <span className="text-[15px] leading-[22px]">Palavras a treinar: {r.analise.palavras.join(", ")}.</span>
              ) : null}
              {r.explicacao ? <span className="text-[15px] leading-[22px]">{r.explicacao}</span> : null}
              {r.subiu && r.estado_depois ? (
                <span className="inline-flex items-center gap-1 text-[15px] font-semibold">
                  <ArrowUp aria-hidden className="size-4" /> Subiu para {ROTULO_ESTADO[r.estado_depois].toLowerCase()}
                </span>
              ) : r.desceu ? (
                <span className="inline-flex items-start gap-1 text-[15px] font-semibold leading-[22px]">
                  <ArrowDown aria-hidden className="mt-[3px] size-4 shrink-0" /> Voltou a «disse com ajuda»: falhou-a em dois dias seguidos. Diga-a sozinho numa conversa para a recuperar.
                </span>
              ) : null}
              <BotaoOuvirFrase texto={r.texto} rotulo="Ouvir a frase" />
            </div>
          </div>
        ) : fase.tipo === "aviso" ? (
          <p role="alert" className="m-0 text-[16px] leading-6">{fase.mensagem}</p>
        ) : (
          <p className="m-0 hidden text-pe-legenda text-pe-tinta-suave md:block">Sem vidas na revisão: uma frase errada volta mais cedo para a treinar.</p>
        )}
        <div className="flex flex-col gap-2 md:shrink-0 md:flex-row-reverse">
          {r ? (
            <Botao larguraTotal className="md:w-auto md:min-w-[200px]" onClick={aoContinuar} disabled={aVerificar} autoFocus>
              {textoContinuar}
            </Botao>
          ) : fase.tipo === "aviso" ? (
            <>
              <Botao larguraTotal className="md:w-auto md:min-w-[180px]" onClick={aoTentar}>
                Tentar outra vez
              </Botao>
              {fase.podeSaltar ? (
                <Botao tipo="secundario" larguraTotal className="md:w-auto md:min-w-[160px]" onClick={aoSaltar} disabled={aVerificar}>
                  Saltar
                </Botao>
              ) : null}
            </>
          ) : (
            <Botao larguraTotal className="md:w-auto md:min-w-[200px]" disabled={!pronto || aVerificar} onClick={aoVerificar}>
              {aVerificar ? "A verificar…" : "Verificar"}
            </Botao>
          )}
        </div>
      </div>
    </footer>
  );
}

/** Nada para rever hoje. */
function EmDia() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-[560px] flex-col items-start gap-5 px-5 pb-8 pt-16 md:min-h-0 md:pt-24">
      <Etiqueta tipo="certo">
        <CheckCircle2 aria-hidden className="size-[18px]" /> Revisão de hoje
      </Etiqueta>
      <h1 className="m-0 font-pe-titulo text-[30px] font-bold leading-9">Está em dia. Volte amanhã</h1>
      <p className="m-0 text-pe-tinta-suave">
        Não há frases para rever hoje. As frases novas entram aqui quando as aprende numa lição ou numa conversa com o tutor.
      </p>
      <div className="flex flex-col gap-3 self-stretch md:flex-row md:self-start">
        <Botao asChild>
          <Link href={VOLTAR}>Fazer uma lição</Link>
        </Botao>
        <Botao asChild tipo="secundario">
          <Link href="/user/laboratory/speaking/real-time">Falar com o tutor</Link>
        </Botao>
      </div>
    </main>
  );
}

/** Resumo do fim: acertos, frases que subiram de nível e o que fica para amanhã. */
function Fim({ fim, aoRecomecar }: { fim: FimRevisao; aoRecomecar: () => void }) {
  const falta = Math.max(0, Math.ceil(fim.meta.meta_minutos - fim.meta.minutos_hoje));
  return (
    <main className="mx-auto flex min-h-dvh max-w-[720px] flex-col gap-7 px-5 pb-8 pt-12 md:min-h-0 md:pt-20">
      <div className="flex flex-col gap-2">
        <Etiqueta tipo="certo">
          <CheckCircle2 aria-hidden className="size-[18px]" /> Revisão feita
        </Etiqueta>
        <h1 className="m-0 font-pe-titulo text-[30px] font-bold leading-9 tracking-[-0.015em] md:text-pe-titulo-l">
          Acertou {fim.acertos} de {fim.respondidos}
        </h1>
      </div>

      {fim.subiram.length ? (
        <section aria-labelledby="titulo-subiram" className="flex flex-col gap-3">
          <h2 id="titulo-subiram" className="m-0 text-pe-titulo-s">
            {fim.subiram.length === 1 ? "Uma frase subiu de nível" : `${fim.subiram.length} frases subiram de nível`}
          </h2>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {fim.subiram.map((s) => (
              <li key={s.texto} className="flex flex-col gap-0.5 rounded-pe-md border border-pe-linha px-4 py-3">
                <span className="font-semibold leading-6">{s.texto}</span>
                {s.traducao ? <span className="text-pe-legenda text-pe-tinta-suave">{s.traducao}</span> : null}
                <span className="inline-flex items-center gap-1 text-pe-legenda text-pe-certo">
                  <ArrowUp aria-hidden className="size-4" /> {ROTULO_ESTADO[s.antes]} para {s.depois_rotulo.toLowerCase()}
                </span>
              </li>
            ))}
          </ul>
          <p className="m-0 text-pe-legenda text-pe-tinta-suave">Uma frase só fica aprendida quando a diz sozinho numa conversa com o tutor.</p>
        </section>
      ) : null}

      {fim.desceram?.length ? (
        <section aria-labelledby="titulo-desceram" className="flex flex-col gap-3">
          <h2 id="titulo-desceram" className="m-0 text-pe-titulo-s">
            {fim.desceram.length === 1 ? "Uma frase para recuperar" : `${fim.desceram.length} frases para recuperar`}
          </h2>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {fim.desceram.map((s) => (
              <li key={s.texto} className="flex flex-col gap-0.5 rounded-pe-md border border-pe-linha px-4 py-3">
                <span lang="en" className="font-semibold leading-6">{s.texto}</span>
                {s.traducao ? <span className="text-pe-legenda text-pe-tinta-suave">{s.traducao}</span> : null}
                <span className="inline-flex items-center gap-1 text-pe-legenda">
                  <ArrowDown aria-hidden className="size-4" /> {ROTULO_ESTADO[s.antes]} para {s.depois_rotulo.toLowerCase()}
                </span>
              </li>
            ))}
          </ul>
          <p className="m-0 text-pe-legenda text-pe-tinta-suave">Falhou-as em dois dias seguidos. Diga-as outra vez sozinho numa conversa e voltam a contar como aprendidas.</p>
        </section>
      ) : null}

      <div className="pe-sobre-marca flex flex-col gap-1 rounded-pe-fala bg-pe-azul-marca px-6 py-5 text-pe-sobre-marca">
        <span className="font-pe-titulo text-[22px] font-bold leading-7">
          {fim.amanha ? `Amanhã: ${nFrases(fim.amanha)} para rever` : "Amanhã não há frases marcadas"}
        </span>
        <span className="text-[15px] leading-[22px]">
          {fim.pontos ? `Ganhou ${fim.pontos} pontos. ` : ""}
          {fim.meta.cumprida ? "A meta de hoje está cumprida." : `Faltam ${falta} min para a meta de hoje (${fim.meta.meta_minutos} min).`}
        </span>
      </div>

      <div className="mt-auto flex flex-col gap-3 md:mt-2 md:flex-row-reverse md:justify-start">
        {fim.restam_hoje ? (
          <Botao tipo="realce" className="md:min-w-[220px]" onClick={aoRecomecar}>
            Rever mais {nFrases(fim.restam_hoje)}
          </Botao>
        ) : null}
        <Botao asChild tipo={fim.restam_hoje ? "ligacao" : "principal"} className="md:min-w-[200px]">
          <Link href={VOLTAR}>Voltar ao laboratório</Link>
        </Botao>
      </div>
    </main>
  );
}

function Esqueleto() {
  return (
    <div aria-busy="true" aria-label="A carregar a revisão" className="flex min-h-dvh flex-col">
      <div className="mx-auto flex w-full max-w-[960px] items-center gap-4 px-4 py-4">
        <Osso className="size-8" />
        <Osso className="h-3 flex-1 rounded-full" />
      </div>
      <div className="mx-auto flex w-full max-w-[720px] flex-col gap-5 px-5 py-8">
        <Osso className="h-8 w-2/3" />
        <Osso className="h-28 rounded-pe-fala" />
        <Osso className="h-14" />
        <Osso className="h-14" />
      </div>
    </div>
  );
}
