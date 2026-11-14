"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, Circle, Loader2, Mic, MicOff, Send } from "lucide-react";
import { Aviso, BalaoFala, Botao } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import { FrasesAlvo, REGRA_FRASES } from "@/components/pe/conversa/FrasesAlvo";
import { reconhecimentoDisponivel, useConversa } from "@/components/pe/conversa/useConversa";
import { disseFrase, type Resumo } from "@/src/domains/student/conversa/api";
import { useComecarConversaLicaoMutation, type ConversaLicao, type Exercicio } from "@/src/domains/student/laboratorio/api";
import type { RespostaExercicio } from "./Exercicios";
import { Enunciado } from "./Partes";

const MIN_FALAS = 2;
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.max(0, s) % 60).padStart(2, "0")}`;

type Fase = { tipo: "inicio" } | { tipo: "viva"; dados: ConversaLicao } | { tipo: "fim"; resumo: Resumo } | { tipo: "bloqueada"; mensagem: string };

/**
 * Conversa curta (1 a 2 minutos) com o tutor no fim da lição, dentro do ecrã da lição.
 * Usa a conversa normal (useConversa): gasta minutos de conversa do dia. Sem minutos ou sem
 * ligação, o aluno salta sem perder nada. Conta quando terminou com pelo menos 2 respostas.
 */
export function ConversaCurta({ ex, bloqueado, aoMudar, aoSaltar }: { ex: Exercicio; bloqueado: boolean; aoMudar: (r: RespostaExercicio) => void; aoSaltar?: () => void }) {
  const [fase, setFase] = useState<Fase>({ tipo: "inicio" });
  const [comecar, { isLoading }] = useComecarConversaLicaoMutation();
  const frases = ex.frases ?? [];

  const abrir = async () => {
    const r = await comecar(ex.id);
    if ("error" in r && r.error) {
      const d = (r.error as { data?: { mensagem?: string } }).data;
      setFase({ tipo: "bloqueada", mensagem: d?.mensagem ?? "Não foi possível começar a conversa agora." });
      return;
    }
    setFase({ tipo: "viva", dados: r.data! });
  };

  const terminou = (resumo: Resumo) => {
    setFase({ tipo: "fim", resumo });
    const falas = resumo.transcricao.filter((f) => f.quem === "aluno").length;
    aoMudar(falas >= MIN_FALAS ? { tipo: "texto", resposta: { sessao_id: resumo.id } } : null);
  };

  const saltar = aoSaltar ? (
    <Botao tipo="ligacao" tamanho="medio" onClick={aoSaltar} disabled={bloqueado}>
      Saltar esta conversa
    </Botao>
  ) : null;

  return (
    <Enunciado titulo="Conversa curta com o tutor">
      <div className="flex flex-col gap-1 border-l-4 border-pe-azul-marca pl-4">
        <span className="text-pe-legenda text-pe-tinta-suave">A situação</span>
        <p className="m-0 text-[17px] leading-7 md:text-[19px]">{ex.pergunta}</p>
      </div>

      {fase.tipo === "viva" ? (
        <Viva dados={fase.dados} frases={frases} aoTerminar={terminou} aoSaltar={aoSaltar} />
      ) : (
        <ListaFrases frases={frases} ditas={fase.tipo === "fim" ? ditasNoResumo(fase.resumo, frases) : undefined} />
      )}

      {fase.tipo === "inicio" ? (
        <div className="flex flex-col gap-4">
          <p className="m-0 text-pe-legenda text-pe-tinta-suave">Cerca de 2 minutos. Conta para os minutos de conversa do seu plano. Responda pelo menos {MIN_FALAS} vezes.</p>
          <div className="flex flex-wrap items-center gap-3">
            <Botao onClick={() => void abrir()} disabled={bloqueado || isLoading}>
              {isLoading ? <Loader2 aria-hidden className="size-5 animate-spin" /> : <Mic aria-hidden className="size-5" />}
              Começar a conversa
            </Botao>
            {saltar}
          </div>
        </div>
      ) : null}

      {fase.tipo === "bloqueada" ? (
        <div className="flex flex-col gap-3">
          <Aviso tipo="neutro">{fase.mensagem} Pode saltar esta conversa: não perde vidas nem pontos.</Aviso>
          <div>{saltar}</div>
        </div>
      ) : null}

      {fase.tipo === "fim" ? <Fim resumo={fase.resumo} aoRepetir={() => setFase({ tipo: "inicio" })} saltar={saltar} /> : null}
    </Enunciado>
  );
}

export function ditasNoResumo(resumo: Resumo, frases: string[]) {
  const usadas = new Set(resumo.objectivos.filter((o) => o.usado || o.com_ajuda).map((o) => o.en));
  return new Set(frases.filter((f) => usadas.has(f)));
}

export function ListaFrases({ frases, ditas, titulo = "Use estas frases da lição" }: { frases: string[]; ditas?: Set<string>; titulo?: string }) {
  if (!frases.length) return null;
  return (
    <div className="flex flex-col gap-2">
      <span className="text-pe-legenda text-pe-tinta-suave">{titulo}</span>
      <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
        {frases.map((f) => {
          const dita = ditas?.has(f);
          return (
            <li key={f} className="flex items-start gap-2.5">
              {dita ? <CheckCircle2 aria-label="Dita" className="mt-0.5 size-5 shrink-0 text-pe-certo" /> : <Circle aria-hidden className="mt-0.5 size-5 shrink-0 text-pe-linha-forte" />}
              <span lang="en" className={cnPe("text-[17px] leading-6", dita && "font-semibold")}>
                {f}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * A conversa a decorrer: falas, frases já ditas, tempo e controlos.
 * As frases-alvo aparecem só em português ("Ver em inglês" mostra-as, mas passam a contar com ajuda).
 * semTexto (exame oral e teste de nível): sem caixa para escrever e sem ajustes durante a conversa.
 */
export function Viva({ dados, frases, aoTerminar, aoSaltar, tituloFrases, semTexto: pedidoSemTexto = false }: { dados: ConversaLicao; frases: string[]; aoTerminar: (r: Resumo) => void; aoSaltar?: () => void; tituloFrases?: string; semTexto?: boolean }) {
  // No modo simulado (desenvolvimento, sem voz real) escreve-se sempre.
  const semTexto = pedidoSemTexto && dados.modo === "vapi";
  const c = useConversa(dados.sessao, dados.modo, dados.chave_publica, { semTexto, semAjustes: pedidoSemTexto });
  const [texto, setTexto] = useState("");
  const fim = useRef<HTMLDivElement>(null);
  const semVoz = dados.modo === "simulado" && !reconhecimentoDisponivel();
  const avisado = useRef(false);

  useEffect(() => {
    if (c.estado === "terminada" && c.resumo && !avisado.current) {
      avisado.current = true;
      aoTerminar(c.resumo);
    }
  }, [c.estado, c.resumo, aoTerminar]);

  const n = c.falas.length;
  const parcial = c.parcial?.texto;
  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [n, parcial]);

  const falasAluno = c.falas.filter((f) => f.quem === "aluno").map((f) => f.texto);
  const chave = falasAluno.join("\n");
  const ditas = useMemo(() => {
    const falas = chave.split("\n");
    return new Set(frases.filter((f) => falas.some((x) => disseFrase(f, x))));
  }, [frases, chave]);

  // O sentido em português de cada frase (vem da sessão: objectivos e frases da situação).
  const comSentido = useMemo(() => {
    const pt = new Map([...(dados.sessao.frases ?? []), ...(dados.sessao.objectivos ?? [])].filter((f) => f.pt).map((f) => [f.en, f.pt]));
    return frases.map((en) => ({ en, pt: pt.get(en) ?? "" }));
  }, [frases, dados.sessao.frases, dados.sessao.objectivos]);

  const restante = dados.sessao.max_segundos - c.segundos;
  const aTerminar = c.estado === "a_terminar" || c.estado === "terminada";
  const estadoTexto =
    c.estado === "a_ligar" ? "A ligar ao tutor…" : aTerminar ? "A guardar a conversa…" : c.tutorAFalar ? "O tutor está a falar" : c.microfone ? "A ouvir" : semVoz && !semTexto ? "Escreva a sua resposta" : "Toque no microfone para falar";

  if (c.estado === "erro") {
    return (
      <div className="flex flex-col gap-3">
        <Aviso tipo="errado">
          {c.erro ?? "A ligação ao tutor falhou."}
          {aoSaltar ? " Pode saltar esta conversa: não perde vidas nem pontos." : ""}
        </Aviso>
        {aoSaltar ? (
          <Botao tipo="secundario" tamanho="medio" className="self-start" onClick={aoSaltar}>
            Saltar esta conversa
          </Botao>
        ) : null}
      </div>
    );
  }

  const enviar = () => {
    if (!texto.trim()) return;
    c.escrever(texto);
    setTexto("");
  };

  return (
    <div className="flex flex-col gap-4">
      {comSentido.length ? (
        <div className="flex flex-col gap-1">
          <span className="text-pe-legenda text-pe-tinta-suave">{tituloFrases ?? "Use estas frases da lição"}</span>
          <FrasesAlvo frases={comSentido} ditas={ditas} reveladas={c.reveladas} aoRevelar={c.revelar} compacta />
          <span className="text-pe-legenda text-pe-tinta-suave">{REGRA_FRASES}</span>
        </div>
      ) : null}

      <div className="flex flex-col gap-3 rounded-pe-md border-[1.5px] border-pe-linha p-3 md:p-4">
        <div className="flex items-center justify-between gap-3 text-pe-legenda">
          <span aria-live="polite" className="text-pe-tinta-suave">
            {estadoTexto}
          </span>
          <span className={cnPe("font-semibold tabular-nums", restante <= 20 ? "text-pe-errado" : "text-pe-tinta")} aria-label={`Faltam ${mmss(restante)}`}>
            {mmss(restante)}
          </span>
        </div>
        <div className="flex max-h-[42vh] min-h-[120px] flex-col gap-2.5 overflow-y-auto">
          {c.falas.map((f) => (
            <BalaoFala key={f.id} quem={f.quem} autor={f.quem === "tutor" ? "Tutor" : "Você"} className="max-w-[88%] px-4 py-3 [&>div]:text-[16px] [&>div]:leading-6">
              <p lang="en" className="m-0">
                {f.texto}
              </p>
            </BalaoFala>
          ))}
          {c.parcial ? (
            <BalaoFala quem={c.parcial.quem} className="max-w-[88%] px-4 py-3 opacity-70 [&>div]:text-[16px]">
              <span>{c.parcial.texto}…</span>
            </BalaoFala>
          ) : null}
          <div ref={fim} />
        </div>
        {c.erro ? (
          <p role="alert" className="m-0 rounded-pe-sm bg-pe-errado-suave px-3 py-2 text-[14px]">
            {c.erro}
          </p>
        ) : null}
        <div className="flex items-center gap-2">
          {semVoz ? null : (
            <button
              type="button"
              onClick={c.alternarMicrofone}
              disabled={c.estado !== "em_curso"}
              aria-pressed={c.microfone}
              aria-label={c.microfone ? "Desligar o microfone" : "Falar"}
              className={cnPe(
                "pe-sobre-marca flex size-12 shrink-0 items-center justify-center rounded-pe-fala text-pe-sobre-marca disabled:opacity-60",
                c.microfone ? "bg-pe-errado" : "bg-pe-azul-marca hover:bg-pe-azul-vivo"
              )}
            >
              {c.microfone ? <MicOff aria-hidden className="size-6" /> : <Mic aria-hidden className="size-6" />}
            </button>
          )}
          {semTexto ? null : (
          <form
            className="flex min-w-0 flex-1 items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              enviar();
            }}
          >
            <input
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => e.stopPropagation()}
              disabled={c.estado !== "em_curso"}
              placeholder="Ou escreva em inglês"
              aria-label="Escrever a resposta"
              lang="en"
              className="h-12 min-w-0 flex-1 rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo px-3 text-[16px] text-pe-tinta"
            />
            <button type="submit" disabled={!texto.trim() || c.estado !== "em_curso"} aria-label="Enviar" className="flex size-12 shrink-0 items-center justify-center rounded-pe-sm text-pe-azul-marca disabled:opacity-40">
              <Send aria-hidden className="size-5" />
            </button>
          </form>
          )}
        </div>
      </div>

      <Botao tipo="secundario" tamanho="medio" className="self-start" onClick={() => void c.terminar()} disabled={aTerminar || c.estado === "a_ligar"}>
        {aTerminar ? "A guardar…" : `Terminar a conversa (${falasAluno.length} ${falasAluno.length === 1 ? "resposta" : "respostas"})`}
      </Botao>
    </div>
  );
}

function Fim({ resumo, aoRepetir, saltar }: { resumo: Resumo; aoRepetir: () => void; saltar: React.ReactNode }) {
  const falas = resumo.transcricao.filter((f) => f.quem === "aluno").length;
  if (falas >= MIN_FALAS) {
    const c = resumo.correccoes[0];
    return (
      <div className="flex flex-col gap-2 rounded-pe-md bg-pe-certo-suave px-4 py-3.5">
        <p className="m-0 font-semibold">Conversa guardada: respondeu {falas} vezes. Carregue em Verificar para continuar.</p>
        {c ? (
          <p className="m-0 text-[15px] leading-[22px]">
            Um ajuste: <s>{c.disse}</s> <span lang="en" className="font-semibold">{c.certo}</span>. {c.porque}
          </p>
        ) : null}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <Aviso tipo="neutro">
        {falas === 0 ? "Não ouvimos nenhuma resposta sua." : "Só respondeu uma vez."} A conversa conta a partir de {MIN_FALAS} respostas.
      </Aviso>
      <div className="flex flex-wrap items-center gap-3">
        <Botao tamanho="medio" onClick={aoRepetir}>
          Tentar outra vez
        </Botao>
        {saltar}
      </div>
    </div>
  );
}
