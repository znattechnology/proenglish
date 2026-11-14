"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import { cnPe } from "@/lib/pe";
import type { Exercicio, Resposta } from "@/src/domains/student/laboratorio/api";
import { BalaoEnunciado, BotaoOuvir, Enunciado } from "./Partes";

export type RespostaExercicio = { tipo: "texto"; resposta: Resposta } | { tipo: "audio"; audio: Blob } | null;
export type EstadoVisual = "livre" | "certo" | "errado";

type Props = {
  ex: Exercicio;
  bloqueado: boolean;
  visual: EstadoVisual;
  aoMudar: (r: RespostaExercicio) => void;
};

const ESPACO = /_{2,}|\[\s*\]/g;

/** Estilo de uma opção conforme o estado (escolhida, certa, errada). */
function estiloOpcao(escolhida: boolean, visual: EstadoVisual) {
  if (escolhida && visual === "certo") return "border-2 border-pe-certo bg-pe-certo-suave font-semibold";
  if (escolhida && visual === "errado") return "border-2 border-pe-errado bg-pe-errado-suave font-semibold";
  if (escolhida) return "border-2 border-pe-azul-marca bg-pe-fundo-suave font-semibold";
  return "border-2 border-pe-linha-forte bg-pe-fundo hover:bg-pe-fundo-suave";
}

function Numero({ n }: { n: number }) {
  return (
    <span aria-hidden className="flex size-7 shrink-0 items-center justify-center rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo text-[14px] font-semibold text-pe-tinta-suave">
      {n}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Escolha: SELECT, ASSIST, TRUE_FALSE e escolha em TRANSLATION/LISTENING */
/* ------------------------------------------------------------------ */
function Escolha({ ex, bloqueado, visual, aoMudar }: Props) {
  const [id, setId] = useState<string | null>(null);
  const opcoes = ex.opcoes ?? [];
  const comImagens = opcoes.some((o) => o.imagem);
  const vf = ex.tipo === "TRUE_FALSE";

  const escolher = (oid: string) => {
    if (bloqueado) return;
    setId(oid);
    const o = opcoes.find((x) => x.id === oid)!;
    // TRANSLATION valida texto mesmo quando é de escolha.
    aoMudar({ tipo: "texto", resposta: ex.tipo === "TRANSLATION" ? { text_answer: o.texto } : { selected_option: oid } });
  };

  // Teclas 1 a 9 escolhem a opção (desktop).
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (bloqueado || e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const n = Number(e.key);
      if (n >= 1 && n <= opcoes.length) escolher(opcoes[n - 1].id);
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  });

  const titulo = vf ? ex.instrucao || "Verdadeiro ou falso?" : comImagens || ex.tipo === "ASSIST" ? ex.pergunta : ex.instrucao || "Escolha a melhor resposta";
  const mostraBalao = !(comImagens || ex.tipo === "ASSIST");

  return (
    <Enunciado titulo={titulo}>
      {mostraBalao ? <BalaoEnunciado audio={ex.audio}>{ex.pergunta}</BalaoEnunciado> : null}
      <div
        role="radiogroup"
        aria-label="Opções de resposta"
        className={cnPe(
          "grid gap-3",
          comImagens || vf ? "grid-cols-2" : "grid-cols-1",
          comImagens && "md:grid-cols-4",
          !comImagens && !vf && opcoes.length > 3 && "md:grid-cols-2"
        )}
      >
        {opcoes.map((o, i) => {
          const sel = id === o.id;
          return (
            <button
              key={o.id}
              type="button"
              role="radio"
              aria-checked={sel}
              disabled={bloqueado && !sel}
              onClick={() => escolher(o.id)}
              className={cnPe(
                "rounded-pe-sm text-left text-[17px] leading-6 text-pe-tinta disabled:opacity-60 md:text-[19px] md:leading-[26px]",
                comImagens ? "flex flex-col gap-2 rounded-pe-md p-2.5 text-center" : "flex min-h-[60px] items-center gap-3 px-4 py-2",
                vf && "min-h-[72px] justify-center text-center font-semibold",
                estiloOpcao(sel, visual)
              )}
            >
              {comImagens ? (
                o.imagem ? (
                  // eslint-disable-next-line @next/next/no-img-element -- imagens do professor (URL externo)
                  <img src={o.imagem} alt="" className="h-28 w-full rounded-pe-sm bg-pe-fundo-forte object-cover md:h-32" />
                ) : (
                  <span aria-hidden className="h-28 w-full rounded-pe-sm bg-pe-fundo-forte md:h-32" />
                )
              ) : vf ? null : (
                <Numero n={i + 1} />
              )}
              <span className="min-w-0">{o.texto}</span>
            </button>
          );
        })}
      </div>
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Banco de palavras: FILL_BLANK com alternativas                       */
/* ------------------------------------------------------------------ */
function Banco({ ex, bloqueado, visual, aoMudar }: Props) {
  const espacos = Math.max(1, ex.espacos ?? 1);
  // Um lugar por espaço (null = vazio): tirar uma palavra não puxa as seguintes para a esquerda.
  const [cheios, setCheios] = useState<(string | null)[]>(() => Array(espacos).fill(null));
  const opcoes = ex.opcoes ?? [];
  const textoDe = (id: string) => opcoes.find((o) => o.id === id)?.texto ?? "";
  const preenchidos = cheios.filter(Boolean).length;

  const atualizar = (novo: (string | null)[]) => {
    setCheios(novo);
    if (novo.every(Boolean)) {
      const textos = (novo as string[]).map(textoDe);
      aoMudar({ tipo: "texto", resposta: espacos > 1 ? { text_answers: textos } : { text_answer: textos[0] } });
    } else aoMudar(null);
  };
  const tirar = (i: number) => atualizar(cheios.map((c, j) => (j === i ? null : c)));
  const por = (id: string) => {
    const livre = cheios.indexOf(null);
    if (livre < 0) return;
    atualizar(cheios.map((c, j) => (j === livre ? id : c)));
  };

  const partes = ex.pergunta.split(ESPACO);
  const corEspaco = visual === "certo" ? "bg-pe-certo-suave text-pe-certo" : visual === "errado" ? "bg-pe-errado-suave text-pe-errado" : "bg-pe-realce text-pe-tinta";

  return (
    <Enunciado titulo={ex.instrucao || "Complete a frase"}>
      <BalaoEnunciado audio={ex.audio}>
        {partes.map((p, i) => (
          <span key={i}>
            {p}
            {i < partes.length - 1 ? (
              cheios[i] ? (
                <button
                  type="button"
                  disabled={bloqueado}
                  onClick={() => tirar(i)}
                  aria-label={`Tirar ${textoDe(cheios[i]!)}`}
                  className={cnPe("mx-1 rounded-[2px] px-3 font-semibold", corEspaco)}
                >
                  {textoDe(cheios[i]!)}
                </button>
              ) : (
                <span aria-label="espaço por preencher" className="mx-1 inline-block w-20 border-b-2 border-dashed border-pe-realce align-baseline md:w-24">
                  &nbsp;
                </span>
              )
            ) : null}
          </span>
        ))}
      </BalaoEnunciado>
      <div role="group" aria-label="Palavras" className="flex flex-wrap gap-2.5">
        {opcoes.map((o) => {
          const usada = cheios.includes(o.id);
          return (
            <button
              key={o.id}
              type="button"
              disabled={bloqueado || usada || preenchidos >= espacos}
              onClick={() => por(o.id)}
              className={cnPe(
                "min-h-12 rounded-pe-sm border-2 px-4 text-[17px] font-semibold",
                usada ? "border-pe-fundo-forte bg-pe-fundo-forte text-transparent" : "border-pe-linha-forte bg-pe-fundo text-pe-tinta hover:bg-pe-fundo-suave disabled:opacity-60"
              )}
            >
              {o.texto}
            </button>
          );
        })}
      </div>
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Escrever: TRANSLATION, ditado (LISTENING) e FILL_BLANK sem alternativas */
/* ------------------------------------------------------------------ */
function Escrever({ ex, bloqueado, visual, aoMudar }: Props) {
  const n = Math.max(1, ex.espacos ?? 1);
  const [textos, setTextos] = useState<string[]>(Array(n).fill(""));
  const primeiro = useRef<HTMLTextAreaElement & HTMLInputElement>(null);
  useEffect(() => primeiro.current?.focus(), []);

  const mudar = (i: number, v: string) => {
    const novo = textos.map((t, j) => (j === i ? v : t));
    setTextos(novo);
    const cheios = novo.every((t) => t.trim());
    aoMudar(cheios ? { tipo: "texto", resposta: n > 1 ? { text_answers: novo.map((t) => t.trim()) } : { text_answer: novo[0].trim() } } : null);
  };
  const borda = visual === "certo" ? "border-pe-certo" : visual === "errado" ? "border-pe-errado" : "border-pe-linha-forte";
  const campo = cnPe("w-full rounded-pe-sm border-2 bg-pe-fundo px-3 text-[17px] text-pe-tinta", borda);

  if (ex.tipo === "TRANSLATION") {
    return (
      <Enunciado titulo={ex.instrucao || "Escreva em inglês"}>
        <div className="flex flex-col gap-1 rounded-pe-md bg-pe-fundo-suave px-4 py-3">
          <span className="text-pe-legenda text-pe-tinta-suave">Em português</span>
          <p className="m-0 text-[19px] leading-7 md:text-[21px]">{ex.pergunta}</p>
        </div>
        <label className="flex flex-col gap-1.5">
          <span className="text-pe-rotulo">A sua tradução</span>
          <textarea
            ref={primeiro}
            rows={3}
            value={textos[0]}
            disabled={bloqueado}
            onChange={(e) => mudar(0, e.target.value)}
            autoCapitalize="sentences"
            spellCheck={false}
            className={cnPe(campo, "resize-none py-2.5 leading-6")}
          />
        </label>
      </Enunciado>
    );
  }

  if (ex.tipo === "LISTENING") {
    return (
      <Enunciado titulo={ex.pergunta || "Escreva o que ouve"}>
        {ex.audio ? <BotaoOuvir src={ex.audio} grande rotulo="Ouvir a frase" /> : (
          <p className="m-0 rounded-pe-md bg-pe-realce-suave px-4 py-3 text-[15px]">O áudio deste exercício ainda não está disponível. Avise o professor do curso.</p>
        )}
        <label className="flex flex-col gap-1.5">
          <span className="text-pe-rotulo">O que ouviu</span>
          <input ref={primeiro} value={textos[0]} disabled={bloqueado} onChange={(e) => mudar(0, e.target.value)} spellCheck={false} className={cnPe(campo, "h-12")} />
        </label>
      </Enunciado>
    );
  }

  // FILL_BLANK sem alternativas: campos dentro da frase.
  const partes = ex.pergunta.split(ESPACO);
  return (
    <Enunciado titulo={ex.instrucao || "Complete a frase"}>
      <p className="m-0 text-[20px] leading-[44px] md:text-[24px] md:leading-[52px]">
        {partes.map((p, i) => (
          <span key={i}>
            {p}
            {i < partes.length - 1 ? (
              <input
                ref={i === 0 ? primeiro : undefined}
                aria-label={`Espaço ${i + 1}`}
                value={textos[i] ?? ""}
                disabled={bloqueado}
                onChange={(e) => mudar(i, e.target.value)}
                spellCheck={false}
                className={cnPe(campo, "mx-1 inline-block h-11 w-36 align-middle")}
              />
            ) : null}
          </span>
        ))}
      </p>
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Ordenar a frase                                                      */
/* ------------------------------------------------------------------ */
function Ordenar({ ex, bloqueado, visual, aoMudar }: Props) {
  const palavras = ex.palavras ?? [];
  const [ordem, setOrdem] = useState<string[]>([]);
  const textoDe = (id: string) => palavras.find((p) => p.id === id)?.texto ?? "";
  const atualizar = (novo: string[]) => {
    setOrdem(novo);
    aoMudar(novo.length === palavras.length ? { tipo: "texto", resposta: { ordered_options: novo } } : null);
  };
  const borda = visual === "certo" ? "border-pe-certo bg-pe-certo-suave" : visual === "errado" ? "border-pe-errado bg-pe-errado-suave" : "border-pe-linha-forte";
  return (
    <Enunciado titulo={ex.instrucao || "Ponha as palavras por ordem"}>
      <div className="flex flex-col gap-1 rounded-pe-md bg-pe-fundo-suave px-4 py-3">
        <span className="text-pe-legenda text-pe-tinta-suave">Em português</span>
        <p className="m-0 text-[19px] leading-7">{ex.pergunta}</p>
      </div>
      <div className={cnPe("flex min-h-[76px] flex-wrap content-start gap-2 rounded-pe-md border-2 border-dashed p-3", borda)} aria-label="A sua frase" role="group">
        {ordem.length === 0 ? <span className="self-center text-pe-legenda text-pe-tinta-suave">Toque nas palavras pela ordem certa.</span> : null}
        {ordem.map((id, i) => (
          <button
            key={id}
            type="button"
            disabled={bloqueado}
            onClick={() => atualizar(ordem.filter((_, j) => j !== i))}
            className="pe-sobre-marca min-h-11 rounded-pe-sm bg-pe-azul-marca px-3.5 text-[17px] font-semibold text-pe-sobre-marca"
          >
            {textoDe(id)}
          </button>
        ))}
      </div>
      <div role="group" aria-label="Palavras" className="flex flex-wrap gap-2">
        {palavras.map((p) => {
          const usada = ordem.includes(p.id);
          return (
            <button
              key={p.id}
              type="button"
              disabled={bloqueado || usada}
              onClick={() => atualizar([...ordem, p.id])}
              className={cnPe(
                "min-h-11 rounded-pe-sm border-2 px-3.5 text-[17px] font-semibold",
                usada ? "border-pe-fundo-forte bg-pe-fundo-forte text-transparent" : "border-pe-linha-forte bg-pe-fundo text-pe-tinta hover:bg-pe-fundo-suave"
              )}
            >
              {p.texto}
            </button>
          );
        })}
      </div>
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Ligar pares                                                          */
/* ------------------------------------------------------------------ */
function Pares({ ex, bloqueado, visual, aoMudar }: Props) {
  const esquerda = ex.esquerda ?? [];
  const direita = ex.direita ?? [];
  const [pares, setPares] = useState<Record<string, string>>({});
  const [aberto, setAberto] = useState<string | null>(null);
  const usados = useMemo(() => new Set(Object.values(pares)), [pares]);

  const atualizar = (novo: Record<string, string>) => {
    setPares(novo);
    aoMudar(Object.keys(novo).length === esquerda.length ? { tipo: "texto", resposta: { paired_options: novo } } : null);
  };
  const tocarEsquerda = (id: string) => {
    if (bloqueado) return;
    if (pares[id]) {
      const { [id]: _, ...resto } = pares;
      atualizar(resto);
      return;
    }
    setAberto(aberto === id ? null : id);
  };
  const tocarDireita = (texto: string) => {
    if (bloqueado || !aberto || usados.has(texto)) return;
    atualizar({ ...pares, [aberto]: texto });
    setAberto(null);
  };
  const numeroDoPar = (id: string) => Object.keys(pares).indexOf(id) + 1;
  const parDaDireita = (t: string) => Object.entries(pares).find(([, v]) => v === t)?.[0];
  const corPar = visual === "certo" ? "border-pe-certo bg-pe-certo-suave" : visual === "errado" ? "border-pe-errado bg-pe-errado-suave" : "border-pe-azul-marca bg-pe-fundo-suave";

  return (
    <Enunciado titulo={ex.pergunta || "Ligue cada palavra à tradução"}>
      <p className="m-0 -mt-3 text-pe-legenda text-pe-tinta-suave md:-mt-5">
        {Object.keys(pares).length} de {esquerda.length} pares ligados. Toque numa palavra e depois na tradução.
      </p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        <span className="text-pe-legenda font-semibold text-pe-tinta-suave">Inglês</span>
        <span className="text-pe-legenda font-semibold text-pe-tinta-suave">Português</span>
        {Array.from({ length: Math.max(esquerda.length, direita.length) }).map((_, i) => {
          const e = esquerda[i];
          const d = direita[i];
          const ligadoD = d !== undefined ? parDaDireita(d) : undefined;
          return [
            e ? (
              <button
                key={`e-${e.id}`}
                type="button"
                aria-pressed={aberto === e.id}
                onClick={() => tocarEsquerda(e.id)}
                className={cnPe(
                  "flex min-h-12 items-center justify-between gap-2 rounded-pe-sm border-2 px-3 text-left text-[16px] font-semibold",
                  pares[e.id] ? corPar : aberto === e.id ? "border-pe-azul-vivo bg-pe-fundo-suave" : "border-pe-linha-forte bg-pe-fundo hover:bg-pe-fundo-suave"
                )}
              >
                {e.texto}
                {pares[e.id] ? <span className="text-pe-legenda text-pe-tinta-suave">{numeroDoPar(e.id)}</span> : null}
              </button>
            ) : <span key={`e-${i}`} />,
            d !== undefined ? (
              <button
                key={`d-${d}`}
                type="button"
                disabled={bloqueado || (!!ligadoD && aberto === null)}
                onClick={() => tocarDireita(d)}
                className={cnPe(
                  "flex min-h-12 items-center justify-between gap-2 rounded-pe-sm border-2 px-3 text-left text-[16px]",
                  ligadoD ? corPar : "border-pe-linha-forte bg-pe-fundo hover:bg-pe-fundo-suave"
                )}
              >
                {d}
                {ligadoD ? <span className="text-pe-legenda text-pe-tinta-suave">{numeroDoPar(ligadoD)}</span> : null}
              </button>
            ) : <span key={`d-${i}`} />,
          ];
        })}
      </div>
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Falar: grava a frase e envia para análise de pronúncia               */
/* ------------------------------------------------------------------ */
function Falar({ ex, bloqueado, aoMudar }: Props) {
  // Só é montado no browser (a lição carrega depois dos dados), por isso pode ver-se já o suporte.
  const [estado, setEstado] = useState<"parado" | "a-gravar" | "gravado" | "sem-permissao" | "sem-suporte">(() =>
    typeof window !== "undefined" && !("MediaRecorder" in window) ? "sem-suporte" : "parado"
  );
  const gravador = useRef<MediaRecorder | null>(null);
  const pedacos = useRef<Blob[]>([]);

  useEffect(() => () => gravador.current?.stream.getTracks().forEach((t) => t.stop()), []);

  const comecar = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      pedacos.current = [];
      rec.ondataavailable = (e) => e.data.size && pedacos.current.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const audio = new Blob(pedacos.current, { type: rec.mimeType || "audio/webm" });
        setEstado("gravado");
        aoMudar({ tipo: "audio", audio });
      };
      gravador.current = rec;
      rec.start();
      setEstado("a-gravar");
      aoMudar(null);
    } catch {
      setEstado("sem-permissao");
    }
  };
  const parar = () => gravador.current?.state === "recording" && gravador.current.stop();

  return (
    <Enunciado titulo={ex.instrucao || "Diga esta frase em voz alta"}>
      <BalaoEnunciado audio={ex.audio}>
        <span className="font-pe-titulo font-light italic">{ex.frase}</span>
      </BalaoEnunciado>
      <div className="flex flex-col items-center gap-3 pt-2">
        {estado === "sem-permissao" ? (
          <p role="alert" className="m-0 max-w-[420px] rounded-pe-md bg-pe-realce-suave px-4 py-3 text-center text-[15px]">
            O navegador não deixou usar o microfone. Permita o microfone nas definições do navegador e volte a tocar em gravar.
          </p>
        ) : null}
        {estado === "sem-suporte" ? (
          <p role="alert" className="m-0 rounded-pe-md bg-pe-realce-suave px-4 py-3 text-center text-[15px]">Este navegador não consegue gravar áudio. Experimente no Chrome ou no Safari actualizado.</p>
        ) : (
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
        )}
        <span aria-live="polite" className="text-pe-legenda text-pe-tinta-suave">
          {estado === "a-gravar" ? "A gravar… toque para parar" : estado === "gravado" ? "Gravado. Pode verificar ou gravar outra vez." : "Toque para gravar"}
        </span>
      </div>
    </Enunciado>
  );
}

/* ------------------------------------------------------------------ */
/* Indisponível: conversa (desligada) e escuta sem áudio. O aluno salta. */
/* ------------------------------------------------------------------ */
function Indisponivel({ ex }: Props) {
  const conversa = ex.motivo === "conversa";
  return (
    <Enunciado titulo={conversa ? "Conversa com o tutor" : "Exercício de escuta"}>
      <p className="m-0 rounded-pe-md bg-pe-fundo-suave px-4 py-3 text-pe-tinta-suave">
        {conversa
          ? "A conversa dentro da lição não está disponível por agora. Pode continuar: este exercício não conta pontos nem tira vidas."
          : "Este exercício de escuta ainda não tem áudio. Pode continuar: não conta pontos nem tira vidas."}
      </p>
    </Enunciado>
  );
}

export function ExercicioUI(props: Props) {
  switch (props.ex.modo) {
    case "escolha":
      return <Escolha {...props} />;
    case "banco":
      return <Banco {...props} />;
    case "escrever":
      return <Escrever {...props} />;
    case "ordenar":
      return <Ordenar {...props} />;
    case "pares":
      return <Pares {...props} />;
    case "falar":
      return <Falar {...props} />;
    default:
      return <Indisponivel {...props} />;
  }
}

/** Dica de teclado para o rodapé no desktop. */
export function dicaTeclado(ex: Exercicio) {
  if (ex.modo === "escolha") return `No teclado: 1 a ${ex.opcoes?.length ?? 4} para escolher, Enter para verificar.`;
  if (ex.modo === "escrever") return "Escreva a resposta e carregue em Enter.";
  if (ex.modo === "falar") return "Grave, ouça o modelo se precisar, e depois verifique.";
  if (ex.modo === "indisponivel") return "Carregue em Enter para continuar.";
  return "Tab para andar entre as palavras, Enter para escolher.";
}
