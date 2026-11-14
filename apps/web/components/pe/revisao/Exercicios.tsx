"use client";

import { useEffect, useRef, useState } from "react";
import { Mic, Square, Volume2 } from "lucide-react";
import { cnPe } from "@/lib/pe";
import { falarNoBrowser } from "@/components/pe/conversa/useConversa";
import type { ExercicioRevisao } from "@/src/domains/student/revisao/api";
import { MAX_SEGUNDOS_GRAVACAO, MENSAGEM_SEM_GRAVACAO, motivoSemGravacao, type EstadoMicrofone } from "@/components/pe/fala/gravacao";

export type RespostaRevisao = { tipo: "texto"; valor: string } | { tipo: "audio"; audio: Blob } | null;
export type Visual = "livre" | "certo" | "errado";

type Props = {
  ex: ExercicioRevisao;
  bloqueado: boolean;
  visual: Visual;
  aoMudar: (r: RespostaRevisao) => void;
  /** Exercícios falados: saltar quando não se consegue gravar (sem pontos; a frase volta amanhã). */
  aoSaltar?: () => void;
};

const ESPACO = /_{2,}/;

/** Lê a frase em inglês com a voz do browser (en-GB), como na conversa com o tutor. */
export function BotaoOuvirFrase({ texto, sobreMarca = false, rotulo = "Ouvir" }: { texto: string; sobreMarca?: boolean; rotulo?: string }) {
  return (
    <button
      type="button"
      onClick={() => falarNoBrowser(texto)}
      className={cnPe(
        "inline-flex min-h-11 items-center gap-2 self-start bg-transparent p-0 text-[15px] font-semibold underline underline-offset-[3px]",
        sobreMarca ? "text-pe-sobre-marca" : "text-pe-azul-marca"
      )}
    >
      <Volume2 aria-hidden className="size-5" />
      {rotulo}
    </button>
  );
}

function Titulo({ children }: { children: React.ReactNode }) {
  return <h1 className="m-0 text-[22px] font-bold leading-7 md:text-pe-titulo-m">{children}</h1>;
}

function Balao({ children, ouvir }: { children: React.ReactNode; ouvir?: string | null }) {
  return (
    <div className="pe-sobre-marca flex max-w-[560px] flex-col gap-1.5 self-start rounded-pe-fala bg-pe-azul-marca px-6 py-4 text-pe-sobre-marca md:px-7 md:py-5">
      <p className="m-0 text-[20px] leading-[30px] md:text-[24px] md:leading-9">{children}</p>
      {ouvir ? <BotaoOuvirFrase texto={ouvir} sobreMarca /> : null}
    </div>
  );
}

function EmPortugues({ texto }: { texto: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-pe-md bg-pe-fundo-suave px-4 py-3">
      <span className="text-pe-legenda text-pe-tinta-suave">Em português</span>
      <p className="m-0 text-[19px] leading-7 md:text-[21px]">{texto}</p>
    </div>
  );
}

function corBorda(visual: Visual) {
  return visual === "certo" ? "border-pe-certo" : visual === "errado" ? "border-pe-errado" : "border-pe-linha-forte";
}

/* Escolher: o significado de uma frase (itens) ou a forma certa (padrões de erro). */
function Escolher({ ex, bloqueado, visual, aoMudar }: Props) {
  const [escolhida, setEscolhida] = useState<string | null>(null);
  const opcoes = ex.opcoes ?? [];
  const escolher = (o: string) => {
    if (bloqueado) return;
    setEscolhida(o);
    aoMudar({ tipo: "texto", valor: o });
  };
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (bloqueado || e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const n = Number(e.key);
      if (n >= 1 && n <= opcoes.length) escolher(opcoes[n - 1]);
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  });
  return (
    <div className="flex flex-col gap-5 md:gap-7">
      <Titulo>{ex.titulo}</Titulo>
      {ex.frase_com_espaco ? <Balao>{ex.frase_com_espaco}</Balao> : ex.texto_en ? <Balao ouvir={ex.audio_texto}>{ex.texto_en}</Balao> : null}
      <div role="radiogroup" aria-label="Opções de resposta" className={cnPe("grid grid-cols-1 gap-3", opcoes.length > 3 && "md:grid-cols-2")}>
        {opcoes.map((o, i) => {
          const sel = escolhida === o;
          return (
            <button
              key={o}
              type="button"
              role="radio"
              aria-checked={sel}
              disabled={bloqueado && !sel}
              onClick={() => escolher(o)}
              className={cnPe(
                "flex min-h-[60px] items-center gap-3 rounded-pe-sm border-2 px-4 py-2 text-left text-[17px] leading-6 text-pe-tinta disabled:opacity-60 md:text-[19px] md:leading-[26px]",
                sel && visual === "certo"
                  ? "border-pe-certo bg-pe-certo-suave font-semibold"
                  : sel && visual === "errado"
                    ? "border-pe-errado bg-pe-errado-suave font-semibold"
                    : sel
                      ? "border-pe-azul-marca bg-pe-fundo-suave font-semibold"
                      : "border-pe-linha-forte bg-pe-fundo hover:bg-pe-fundo-suave"
              )}
            >
              <span aria-hidden className="flex size-7 shrink-0 items-center justify-center rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo text-[14px] font-semibold text-pe-tinta-suave">
                {i + 1}
              </span>
              <span className="min-w-0">{o}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* Completar: a frase com uma palavra em branco, escrita dentro da frase. */
function Completar({ ex, bloqueado, visual, aoMudar }: Props) {
  const [texto, setTexto] = useState("");
  const campo = useRef<HTMLInputElement>(null);
  useEffect(() => campo.current?.focus(), []);
  const [antes, depois = ""] = (ex.frase_com_espaco ?? "").split(ESPACO);
  return (
    <div className="flex flex-col gap-5 md:gap-7">
      <Titulo>{ex.titulo}</Titulo>
      <p className="m-0 text-[20px] leading-[44px] md:text-[24px] md:leading-[52px]">
        {antes}
        <input
          ref={campo}
          aria-label="Palavra em falta"
          value={texto}
          disabled={bloqueado}
          onChange={(e) => {
            setTexto(e.target.value);
            aoMudar(e.target.value.trim() ? { tipo: "texto", valor: e.target.value.trim() } : null);
          }}
          autoCapitalize="none"
          autoComplete="off"
          spellCheck={false}
          className={cnPe("mx-1 inline-block h-11 w-40 rounded-pe-sm border-2 bg-pe-fundo px-3 align-middle text-[17px] text-pe-tinta", corBorda(visual))}
        />
        {depois}
      </p>
      {ex.traducao ? <EmPortugues texto={ex.traducao} /> : null}
    </div>
  );
}

/* Traduzir: do português para o inglês. */
function Traduzir({ ex, bloqueado, visual, aoMudar }: Props) {
  const [texto, setTexto] = useState("");
  const campo = useRef<HTMLTextAreaElement>(null);
  useEffect(() => campo.current?.focus(), []);
  return (
    <div className="flex flex-col gap-5 md:gap-7">
      <Titulo>{ex.titulo}</Titulo>
      {ex.traducao ? <EmPortugues texto={ex.traducao} /> : null}
      <label className="flex flex-col gap-1.5">
        <span className="text-pe-rotulo">Em inglês</span>
        <textarea
          ref={campo}
          rows={3}
          value={texto}
          disabled={bloqueado}
          onChange={(e) => {
            setTexto(e.target.value);
            aoMudar(e.target.value.trim() ? { tipo: "texto", valor: e.target.value.trim() } : null);
          }}
          autoCapitalize="sentences"
          autoComplete="off"
          spellCheck={false}
          className={cnPe("w-full resize-none rounded-pe-sm border-2 bg-pe-fundo px-3 py-2.5 text-[17px] leading-6 text-pe-tinta", corBorda(visual))}
        />
      </label>
    </div>
  );
}

/* Ouvir e repetir: grava a frase (como o exercício Falar das lições). */
function Falar({ ex, bloqueado, aoMudar, aoSaltar }: Props) {
  const [estado, setEstado] = useState<EstadoMicrofone>(() =>
    typeof window !== "undefined" && (!("MediaRecorder" in window) || !navigator.mediaDevices?.getUserMedia) ? "sem-suporte" : "parado"
  );
  const gravador = useRef<MediaRecorder | null>(null);
  const pedacos = useRef<Blob[]>([]);
  const limite = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (limite.current) clearTimeout(limite.current);
      gravador.current?.stream.getTracks().forEach((t) => t.stop());
    },
    []
  );

  const comecar = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      pedacos.current = [];
      rec.ondataavailable = (e) => e.data.size && pedacos.current.push(e.data);
      rec.onstop = () => {
        if (limite.current) clearTimeout(limite.current);
        stream.getTracks().forEach((t) => t.stop());
        setEstado("gravado");
        aoMudar({ tipo: "audio", audio: new Blob(pedacos.current, { type: rec.mimeType || "audio/webm" }) });
      };
      gravador.current = rec;
      window.speechSynthesis?.cancel();
      rec.start();
      limite.current = setTimeout(() => rec.state === "recording" && rec.stop(), MAX_SEGUNDOS_GRAVACAO * 1000);
      setEstado("a-gravar");
      aoMudar(null);
    } catch (e) {
      setEstado(motivoSemGravacao(e));
    }
  };
  const parar = () => gravador.current?.state === "recording" && gravador.current.stop();
  const semGravar = estado === "sem-permissao" || estado === "sem-microfone" || estado === "sem-suporte";

  return (
    <div className="flex flex-col gap-5 md:gap-7">
      <Titulo>{ex.titulo}</Titulo>
      <Balao ouvir={ex.audio_texto}>
        <span className="font-pe-titulo font-light italic">{ex.texto_en}</span>
      </Balao>
      {ex.traducao ? <p className="m-0 -mt-2 text-pe-legenda text-pe-tinta-suave">{ex.traducao}</p> : null}
      <div className="flex flex-col items-center gap-3 pt-2">
        {semGravar ? (
          <div role="alert" className="flex max-w-[460px] flex-col items-center gap-3 rounded-pe-md bg-pe-realce-suave px-4 py-3 text-center text-[15px]">
            <p className="m-0">
              {MENSAGEM_SEM_GRAVACAO[estado]} {aoSaltar ? "Pode saltar este exercício: não perde nada e a frase volta amanhã." : null}
            </p>
            {aoSaltar ? (
              <button
                type="button"
                disabled={bloqueado}
                onClick={aoSaltar}
                className="min-h-11 bg-transparent px-2 font-semibold text-pe-azul-marca underline underline-offset-[3px] disabled:opacity-60"
              >
                Saltar este exercício
              </button>
            ) : null}
          </div>
        ) : null}
        {estado !== "sem-suporte" ? (
          <button
            type="button"
            disabled={bloqueado}
            onClick={estado === "a-gravar" ? parar : comecar}
            aria-label={estado === "a-gravar" ? "Parar a gravação" : "Gravar"}
            className={cnPe(
              "pe-sobre-marca flex size-20 items-center justify-center rounded-pe-fala text-pe-sobre-marca disabled:opacity-60",
              estado === "a-gravar" ? "bg-pe-errado" : "bg-pe-azul-marca hover:bg-pe-azul-vivo"
            )}
          >
            {estado === "a-gravar" ? <Square aria-hidden className="size-8 fill-current" /> : <Mic aria-hidden className="size-9" />}
          </button>
        ) : null}
        <span aria-live="polite" className="text-pe-legenda text-pe-tinta-suave">
          {estado === "a-gravar"
            ? `A gravar… toque para parar (no máximo ${MAX_SEGUNDOS_GRAVACAO} segundos)`
            : estado === "gravado"
              ? "Gravado. Pode verificar ou gravar outra vez."
              : semGravar
                ? ""
                : "Toque para gravar"}
        </span>
      </div>
    </div>
  );
}

export function ExercicioRevisaoUI(props: Props) {
  switch (props.ex.forma) {
    case "escolher":
      return <Escolher {...props} />;
    case "completar":
      return <Completar {...props} />;
    case "traduzir":
      return <Traduzir {...props} />;
    default:
      return <Falar {...props} />;
  }
}
