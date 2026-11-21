"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, Keyboard, Loader2, Mic, MicOff, Send, Volume2 } from "lucide-react";
import { Aviso, BalaoFala, Botao } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import { disseFrase, type NovaSessao } from "@/src/domains/student/conversa/api";
import { FrasesAlvo, REGRA_FRASES } from "./FrasesAlvo";
import { falarNoBrowser, reconhecimentoDisponivel, useConversa, type FalaViva } from "./useConversa";

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/**
 * A conversa em curso. No telemóvel ocupa o ecrã inteiro (sem a barra de baixo);
 * no desktop fica ao lado da barra lateral, com as frases úteis à direita.
 */
export function Conversa({ sessao, modo, chavePublica, minutosUsadosHoje, minutosDia }: { sessao: NovaSessao; modo: "vapi" | "simulado"; chavePublica: string | null; minutosUsadosHoje: number; minutosDia: number | null }) {
  const router = useRouter();
  const c = useConversa(sessao, modo, chavePublica);
  const [aEscrever, setAEscrever] = useState(false);
  const [texto, setTexto] = useState("");
  const fim = useRef<HTMLDivElement>(null);
  const semVoz = modo === "simulado" && !reconhecimentoDisponivel();

  const ultimoAjuste = c.falas[c.falas.length - 1]?.ajuste;
  const textoParcial = c.parcial?.texto;
  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [c.falas.length, textoParcial, ultimoAjuste]);

  useEffect(() => {
    if (c.estado === "terminada" && c.resumo) router.replace(`/user/laboratory/speaking/summary/${c.resumo.id}`);
  }, [c.estado, c.resumo, router]);

  // Barra de espaços liga e desliga o microfone (fora das caixas de texto).
  useEffect(() => {
    const aoPremir = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement;
      if (e.code !== "Space" || e.repeat || alvo.closest("input, textarea, button, a, [contenteditable]")) return;
      e.preventDefault();
      c.alternarMicrofone();
    };
    window.addEventListener("keydown", aoPremir);
    return () => window.removeEventListener("keydown", aoPremir);
  }, [c]);

  const restante = sessao.max_segundos - c.segundos;
  const respostas = c.falas.filter((f) => f.quem === "aluno").length;
  const ajustes = c.falas.filter((f) => f.ajuste).length;
  const minutosHoje = Math.min(minutosDia ?? Infinity, minutosUsadosHoje + Math.floor(c.segundos / 60));
  const aTerminar = c.estado === "a_terminar" || c.estado === "terminada";

  // Objectivos já ditos: só as falas finais do aluno (aproximado; quem decide no fim é o servidor).
  const objectivos = useMemo(() => sessao.objectivos ?? [], [sessao.objectivos]);
  const falasAluno = c.falas.filter((f) => f.quem === "aluno").map((f) => f.texto).join("\n");
  const ditos = useMemo(() => {
    const falas = falasAluno.split("\n");
    return new Set(objectivos.filter((o) => falas.some((f) => disseFrase(o.en, f))).map((o) => o.en));
  }, [objectivos, falasAluno]);
  const chavesObjectivos = new Set(objectivos.map((o) => o.en.toLowerCase()));
  const outrasFrases = sessao.frases.filter((f) => !chavesObjectivos.has(f.en.toLowerCase()));

  const instrucao =
    c.estado === "a_ligar"
      ? "A ligar ao tutor…"
      : aTerminar
        ? "A preparar o resumo…"
        : c.tutorAFalar
          ? "O tutor está a falar"
          : modo === "vapi"
            ? c.microfone
              ? "Responda em inglês. O tutor está a ouvir."
              : "Microfone desligado. Toque para voltar a falar."
            : c.microfone
              ? "A ouvir… pare de falar para enviar"
              : semVoz
                ? "Escreva a resposta em inglês"
                : "Toque no microfone e responda em inglês";

  if (c.estado === "erro") {
    return (
      <div className="mx-auto flex w-full max-w-[640px] flex-col items-start gap-4 px-5 py-10">
        <h1 className="m-0 font-pe-titulo text-[24px] font-bold leading-[30px]">{sessao.situacao.titulo}</h1>
        <Aviso tipo="errado">{c.erro ?? "Não foi possível ligar ao tutor."}</Aviso>
        <Botao onClick={() => window.location.reload()}>Voltar a preparar a conversa</Botao>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-pe-fundo md:static md:z-auto md:mx-auto md:h-dvh md:w-full md:max-w-[1280px] md:flex-row md:gap-8 md:px-10 md:py-8 xl:px-12">
      <section aria-labelledby="titulo-conversa" className="flex min-h-0 min-w-0 flex-1 flex-col md:overflow-hidden md:rounded-pe-md md:border md:border-pe-linha">
        <header className="flex items-center gap-2 border-b border-pe-linha px-4 py-3 md:px-6 md:py-4">
          <button
            type="button"
            onClick={() => void c.terminar()}
            disabled={aTerminar}
            aria-label="Terminar e ver o resumo"
            className="flex size-11 shrink-0 items-center justify-center rounded-pe-sm bg-transparent md:hidden"
          >
            <ChevronLeft aria-hidden className="size-6" />
          </button>
          <div className="flex min-w-0 flex-1 flex-col">
            <h1 id="titulo-conversa" className="m-0 truncate font-pe-titulo text-[18px] font-bold leading-6 md:text-[22px] md:leading-7">
              {sessao.situacao.titulo}
            </h1>
            <span className="text-[14px] leading-5 text-pe-tinta-suave">
              <span className="tabular-nums">{mmss(c.segundos)}</span> de {Math.round(sessao.max_segundos / 60)} min
              <span className="hidden md:inline">
                {minutosDia ? `. Hoje já usou ${minutosHoje} dos ${minutosDia} minutos.` : "."}
              </span>
            </span>
          </div>
          <Botao tipo="secundario" tamanho="pequeno" className="hidden md:inline-flex" disabled={aTerminar} onClick={() => void c.terminar()}>
            {aTerminar ? <Loader2 aria-hidden className="motion-safe:animate-spin" /> : null}
            {aTerminar ? "A guardar" : "Terminar conversa"}
          </Botao>
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-5 md:px-6" aria-live="polite" aria-relevant="additions">
          {c.estado === "a_ligar" ? (
            <p className="m-auto flex items-center gap-2 text-pe-tinta-suave">
              <Loader2 aria-hidden className="size-5 motion-safe:animate-spin" /> A ligar ao tutor. O browser pode pedir acesso ao microfone.
            </p>
          ) : null}
          {c.falas.map((f) => (
            <Linha key={f.id} f={f} />
          ))}
          {c.parcial ? (
            <BalaoFala quem={c.parcial.quem} autor={c.parcial.quem === "tutor" ? "Tutor" : "Você"} className={cnPe("max-w-[85%] opacity-70 md:max-w-[560px]", c.parcial.quem === "aluno" && "[&_span]:text-pe-tinta-suave")}>
              <span aria-hidden>{c.parcial.texto}…</span>
            </BalaoFala>
          ) : null}
          <div ref={fim} />
        </div>

        <footer className="flex flex-col items-center gap-3 bg-pe-fundo-suave px-5 pb-[max(24px,env(safe-area-inset-bottom))] pt-4 md:pb-5">
          {c.erro ? (
            <Aviso tipo="errado" className="w-full max-w-[560px]">
              {c.erro}
            </Aviso>
          ) : null}
          {restante <= 30 && c.estado === "em_curso" ? (
            <Aviso tipo="info" className="w-full max-w-[560px]">
              Faltam {restante} segundos. A conversa termina sozinha e o resumo fica guardado.
            </Aviso>
          ) : null}
          <p className="m-0 text-center font-pe-titulo text-[18px] font-light italic leading-[26px]" role="status">
            {instrucao}
          </p>
          {objectivos.length ? (
            <p className="m-0 text-[14px] leading-5 text-pe-tinta-suave md:hidden">
              Objectivos já ditos: {ditos.size} de {objectivos.length}
            </p>
          ) : null}
          <div className="flex items-center justify-center gap-7">
            <button
              type="button"
              aria-label="Ouvir outra vez"
              onClick={c.ouvirOutraVez}
              disabled={c.estado !== "em_curso"}
              className="flex size-[52px] items-center justify-center rounded-pe-sm border-2 border-pe-azul-marca bg-pe-fundo text-pe-azul-marca disabled:border-pe-linha disabled:text-pe-tinta-suave"
            >
              <Volume2 aria-hidden className="size-[22px]" />
            </button>
            <button
              type="button"
              aria-label={modo === "vapi" ? (c.microfone ? "Desligar o microfone" : "Ligar o microfone") : c.microfone ? "Parar de ouvir" : "Falar"}
              aria-pressed={c.microfone}
              onClick={c.alternarMicrofone}
              disabled={c.estado !== "em_curso" || semVoz}
              className={cnPe(
                "relative flex size-20 items-center justify-center rounded-[28px_28px_28px_0] text-pe-sobre-marca disabled:bg-pe-fundo-forte disabled:text-pe-tinta-suave",
                c.microfone || modo !== "vapi" ? "bg-pe-azul-marca" : "bg-pe-tinta-suave"
              )}
            >
              {c.microfone && !c.tutorAFalar ? <span aria-hidden className="absolute inset-0 rounded-[inherit] ring-4 ring-pe-realce motion-safe:animate-pulse" /> : null}
              {c.microfone || modo !== "vapi" ? <Mic aria-hidden className="size-[34px]" /> : <MicOff aria-hidden className="size-[34px]" />}
            </button>
            <button
              type="button"
              aria-label="Escrever em vez de falar"
              aria-expanded={aEscrever || semVoz}
              onClick={() => setAEscrever((v) => !v)}
              disabled={c.estado !== "em_curso"}
              className={cnPe(
                "flex size-[52px] items-center justify-center rounded-pe-sm border-2 border-pe-azul-marca disabled:border-pe-linha disabled:text-pe-tinta-suave",
                aEscrever ? "bg-pe-azul-marca text-pe-sobre-marca" : "bg-pe-fundo text-pe-azul-marca"
              )}
            >
              <Keyboard aria-hidden className="size-[22px]" />
            </button>
          </div>
          {(aEscrever || semVoz) && c.estado === "em_curso" ? (
            <form
              className="flex w-full max-w-[560px] gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                c.escrever(texto);
                setTexto("");
              }}
            >
              <label htmlFor="resposta-escrita" className="sr-only">
                Resposta em inglês
              </label>
              <input
                id="resposta-escrita"
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
                lang="en"
                autoComplete="off"
                placeholder="Write your answer…"
                autoFocus
                className="h-12 min-w-0 flex-1 rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo px-3.5 text-[16px]"
              />
              <Botao type="submit" tamanho="medio" disabled={!texto.trim()} aria-label="Enviar">
                <Send aria-hidden />
              </Botao>
            </form>
          ) : (
            <span className="hidden text-[14px] leading-5 text-pe-tinta-suave md:block">Também pode usar a barra de espaços para o microfone.</span>
          )}
        </footer>
      </section>

      <aside aria-label="Ajuda para a conversa" className="hidden w-[320px] shrink-0 flex-col gap-6 overflow-y-auto md:flex lg:w-[360px]">
        {objectivos.length ? (
          <section aria-labelledby="titulo-objectivos" className="flex flex-col gap-2 rounded-pe-md border-2 border-pe-azul-marca p-4">
            <h2 id="titulo-objectivos" className="m-0 font-pe-titulo text-pe-titulo-s">
              Objectivos desta conversa
            </h2>
            <p className="m-0 text-[14px] leading-5 text-pe-tinta-suave" aria-live="polite">
              Já disse {ditos.size} de {objectivos.length}. {REGRA_FRASES}
            </p>
            <FrasesAlvo frases={objectivos} ditas={ditos} reveladas={c.reveladas} aoRevelar={c.revelar} />
          </section>
        ) : null}
        {outrasFrases.length ? (
          <section aria-labelledby="titulo-frases" className="flex flex-col gap-3">
            <h2 id="titulo-frases" className="m-0 font-pe-titulo text-pe-titulo-s">
              {objectivos.length ? "Outras frases que pode usar" : "Frases que pode usar"}
            </h2>
            <FrasesAlvo frases={outrasFrases} ditas={new Set()} reveladas={c.reveladas} aoRevelar={c.revelar} />
          </section>
        ) : null}
        <section aria-labelledby="titulo-nesta" className="flex flex-col gap-1.5 rounded-pe-md bg-pe-fundo-suave p-5">
          <h2 id="titulo-nesta" className="m-0 text-[17px] font-semibold leading-6">
            Nesta conversa
          </h2>
          <p className="m-0 text-[15px] leading-[22px]">
            {respostas === 0 ? "Ainda não respondeu." : `${respostas} ${respostas === 1 ? "resposta dada" : "respostas dadas"}, ${ajustes} ${ajustes === 1 ? "ajuste" : "ajustes"}.`}
          </p>
          <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">No fim recebe um resumo com as frases a rever.</p>
        </section>
      </aside>
    </div>
  );
}

function Linha({ f }: { f: FalaViva }) {
  const tutor = f.quem === "tutor";
  return (
    <>
      <BalaoFala quem={f.quem} autor={tutor ? "Tutor" : "Você"} className={cnPe("max-w-[85%] md:max-w-[560px]", !tutor && "[&>span]:text-pe-tinta-suave")}>
        <p lang="en" className="m-0">
          {f.texto}
        </p>
      </BalaoFala>
      {f.ajuste ? (
        <div className="flex max-w-[85%] flex-col gap-1.5 self-end rounded-pe-md bg-pe-realce-suave px-4 py-3 md:max-w-[560px]">
          <span className="text-[14px] font-semibold leading-5">Um ajuste</span>
          <span className="text-[15px] leading-[22px]">
            {f.ajuste.porque}{" "}
            <span lang="en" className="font-semibold">
              {f.ajuste.certo}
            </span>
          </span>
          <button
            type="button"
            onClick={() => falarNoBrowser(f.ajuste!.certo)}
            className="min-h-11 self-start bg-transparent px-1 text-[15px] font-semibold text-pe-azul-marca underline underline-offset-[3px]"
          >
            Ouvir a frase certa
          </button>
        </div>
      ) : null}
    </>
  );
}
