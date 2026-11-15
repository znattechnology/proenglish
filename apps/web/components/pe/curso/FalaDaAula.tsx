"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type RefObject } from "react";
import { CheckCircle2, Loader2, MessagesSquare, Mic, Play, Square, Volume2 } from "lucide-react";
import { Aviso, Botao, Etiqueta } from "@/components/pe";
import { falarNoBrowser } from "@/components/pe/conversa/useConversa";
import { ditasNoResumo, ListaFrases, Viva } from "@/components/pe/licao/ConversaCurta";
import { cnPe } from "@/lib/pe";
import type { Resumo } from "@/src/domains/student/conversa/api";
import type { ConversaLicao } from "@/src/domains/student/laboratorio/api";
import { AvisoAnaliseAproximada, PalavrasComNota } from "@/components/pe/fala/Fala";
import { FolhaOferta, OfertaPlano } from "@/components/pe/subscricao/Oferta";
import { ofertaDoErro, type Oferta } from "@/src/domains/student/subscricao/api";
import {
  erroFala,
  useComecarConversaAulaMutation,
  useFalarFraseMutation,
  type AnaliseFrase,
  type EstadoBanco,
  type FalaDaAula,
  type FraseDaAula,
} from "@/src/domains/student/curso/fala";

const REVISAO = "/user/laboratory/review";
const ROTULO_ESTADO: Partial<Record<EstadoBanco, string>> = { com_ajuda: "Já repetiu", sozinho: "Já a diz sozinho" };

/* ------------------------------------------------------------------ */
/* Repetir em voz alta (shadowing)                                     */
/* ------------------------------------------------------------------ */

/**
 * Toca um pedaço do vídeo da aula (do início ao fim da frase) e pára. Devolve a função que deixa
 * de vigiar o fim (também chamada se o aluno pausar o vídeo).
 */
function tocarTrecho(v: HTMLVideoElement, inicio: number, fim: number) {
  const aoTempo = () => {
    if (v.currentTime >= fim) {
      v.pause();
      limpar();
    }
  };
  const limpar = () => {
    v.removeEventListener("timeupdate", aoTempo);
    v.removeEventListener("pause", limpar);
  };
  v.currentTime = inicio;
  v.addEventListener("timeupdate", aoTempo);
  setTimeout(() => v.addEventListener("pause", limpar), 0);
  void v.play().catch(limpar);
  return limpar;
}

type Gravacao = { fraseId: number; estado: "a-gravar" | "a-analisar" } | null;

export function RepetirEmVozAlta({ chapterId, video, dados }: { chapterId: string; video: RefObject<HTMLVideoElement | null>; dados: FalaDaAula }) {
  const frases = dados.frases.filter((f) => f.tipo === "frase");
  const palavras = dados.frases.filter((f) => f.tipo === "palavra");
  const pararTrecho = useRef<(() => void) | null>(null);
  const [gravacao, setGravacao] = useState<Gravacao>(null);
  const [resultados, setResultados] = useState<Record<number, AnaliseFrase["analise"]>>({});
  const [estados, setEstados] = useState<Record<number, EstadoBanco | null>>({});
  const [erro, setErro] = useState<{ fraseId: number; texto: string } | null>(null);
  const [semMicrofone, setSemMicrofone] = useState(false);
  // Limite de análises de pronúncia: o plano que dá mais (a API decide), numa folha.
  const [limite, setLimite] = useState<{ mensagem: string; oferta: Oferta } | null>(null);
  const [falar] = useFalarFraseMutation();
  const gravador = useRef<MediaRecorder | null>(null);
  const inicio = useRef(0);
  const suporta = typeof window === "undefined" || "MediaRecorder" in window;

  useEffect(
    () => () => {
      gravador.current?.stream.getTracks().forEach((t) => t.stop());
      pararTrecho.current?.();
    },
    []
  );

  if (!frases.length && !palavras.length) return null;

  const ouvir = (f: FraseDaAula) => {
    const v = video.current;
    pararTrecho.current?.();
    if (v && f.inicio != null && f.fim != null) pararTrecho.current = tocarTrecho(v, f.inicio, f.fim);
    else falarNoBrowser(f.texto);
  };

  const gravar = async (f: FraseDaAula) => {
    setErro(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      video.current?.pause();
      const rec = new MediaRecorder(stream);
      const pedacos: Blob[] = [];
      rec.ondataavailable = (e) => e.data.size && pedacos.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setGravacao({ fraseId: f.id, estado: "a-analisar" });
        const segundos = Math.round((Date.now() - inicio.current) / 1000);
        const r = await falar({ chapterId, fraseId: f.id, audio: new Blob(pedacos, { type: rec.mimeType || "audio/webm" }), segundos });
        setGravacao(null);
        if ("error" in r && r.error) {
          const e = erroFala(r.error, "Não conseguimos analisar a gravação. Tente outra vez.");
          setErro({ fraseId: f.id, texto: e.mensagem! });
          const oferta = e.codigo === "limite_analises" ? ofertaDoErro(r.error) : null;
          if (oferta) setLimite({ mensagem: e.mensagem!, oferta });
          return;
        }
        setResultados((v) => ({ ...v, [f.id]: r.data!.analise }));
        setEstados((v) => ({ ...v, [f.id]: r.data!.estado }));
      };
      rec.onstart = () => {
        inicio.current = Date.now();
      };
      gravador.current = rec;
      rec.start();
      setGravacao({ fraseId: f.id, estado: "a-gravar" });
    } catch {
      setSemMicrofone(true);
    }
  };
  const parar = () => gravador.current?.state === "recording" && gravador.current.stop();

  return (
    <section aria-labelledby="t-repetir" className="flex flex-col gap-4 border-t border-pe-linha pt-6">
      <div className="flex flex-col gap-1">
        <h2 id="t-repetir" className="m-0 font-pe-titulo text-[22px] font-bold leading-[28px]">
          Repetir em voz alta
        </h2>
        <p className="m-0 max-w-[62ch] text-pe-tinta-suave">Ouça a frase no vídeo e diga-a logo a seguir, com o mesmo ritmo. Depois veja a nota e as palavras a treinar.</p>
      </div>

      {semMicrofone ? <Aviso tipo="info">O navegador não deixou usar o microfone. Permita o microfone nas definições do navegador e toque outra vez em gravar.</Aviso> : null}
      {!suporta ? <Aviso tipo="info">Este navegador não consegue gravar áudio. Experimente no Chrome ou no Safari actualizado.</Aviso> : null}

      <ol className="m-0 grid list-none grid-cols-1 gap-3 p-0 xl:grid-cols-2">
        {frases.map((f) => {
          const estado = estados[f.id] ?? f.estado;
          const aGravar = gravacao?.fraseId === f.id && gravacao.estado === "a-gravar";
          const aAnalisar = gravacao?.fraseId === f.id && gravacao.estado === "a-analisar";
          const outra = gravacao != null && gravacao.fraseId !== f.id;
          const res = resultados[f.id];
          const rotulo = estado ? ROTULO_ESTADO[estado] : undefined;
          return (
            <li key={f.id} className={cnPe("flex flex-col gap-3 rounded-pe-md border-[1.5px] p-4", aGravar ? "border-pe-errado" : "border-pe-linha")}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 flex-col gap-0.5">
                  <p lang="en" className="m-0 font-pe-titulo text-[19px] font-light leading-7">
                    {f.texto}
                  </p>
                  {f.traducao ? <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">{f.traducao}</p> : null}
                </div>
                {rotulo ? (
                  <Etiqueta tipo="certo" className="shrink-0">
                    <CheckCircle2 aria-hidden className="size-4" /> {rotulo}
                  </Etiqueta>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Botao tipo="secundario" tamanho="pequeno" onClick={() => ouvir(f)} disabled={!!gravacao}>
                  {f.inicio != null ? <Play aria-hidden /> : <Volume2 aria-hidden />}
                  {f.inicio != null ? "Ouvir no vídeo" : "Ouvir"}
                </Botao>
                {suporta ? (
                  <Botao
                    tipo={aGravar ? "perigo" : "principal"}
                    tamanho="pequeno"
                    onClick={() => (aGravar ? parar() : void gravar(f))}
                    disabled={outra || aAnalisar}
                    aria-label={aGravar ? `Parar a gravação de "${f.texto}"` : `Gravar "${f.texto}"`}
                  >
                    {aAnalisar ? <Loader2 aria-hidden className="animate-spin" /> : aGravar ? <Square aria-hidden className="fill-current" /> : <Mic aria-hidden />}
                    {aAnalisar ? "A ouvir a gravação…" : aGravar ? "Parar" : res ? "Gravar outra vez" : "Gravar"}
                  </Botao>
                ) : null}
              </div>
              {erro?.fraseId === f.id ? (
                <p role="alert" className="m-0 text-[15px] font-semibold text-pe-errado">
                  {erro.texto}
                </p>
              ) : null}
              {res ? <Resultado frase={f.texto} r={res} /> : null}
            </li>
          );
        })}
      </ol>

      <FolhaOferta aberto={!!limite} aoMudar={(v) => !v && setLimite(null)} titulo="Já usou as análises de pronúncia de hoje" mensagem={limite?.mensagem} oferta={limite?.oferta}>
        <Botao tipo="ligacao" larguraTotal onClick={() => setLimite(null)}>
          Continuar a aula sem gravar
        </Botao>
      </FolhaOferta>

      {palavras.length ? (
        <div className="flex flex-col gap-2">
          <h3 className="m-0 text-[17px] font-semibold leading-6">Palavras da aula</h3>
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
            {palavras.map((p) => (
              <li key={p.id}>
                <button type="button" onClick={() => ouvir(p)} className="inline-flex min-h-11 items-center gap-2 rounded-pe-sm bg-pe-fundo-suave px-3 text-left text-[15px] text-pe-tinta hover:bg-pe-fundo-forte">
                  <Volume2 aria-hidden className="size-4 shrink-0 text-pe-azul-marca" />
                  <span lang="en" className="font-semibold">
                    {p.texto}
                  </span>
                  {p.traducao ? <span className="text-pe-tinta-suave">{p.traducao}</span> : null}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

const soLetras = (t: string) => t.toLowerCase().replace(/[^a-z0-9']/g, "");

function Resultado({ frase, r }: { frase: string; r: AnaliseFrase["analise"] }) {
  const marcar = new Set(r.palavras.flatMap((p) => p.split(/\s+/)).map(soLetras).filter(Boolean));
  const partes = frase.split(/(\s+)/);
  return (
    <div role="status" className={cnPe("flex flex-col gap-1.5 rounded-pe-sm px-3 py-2.5", r.aceite ? "bg-pe-certo-suave" : "bg-pe-fundo-suave")}>
      <p className="m-0 flex items-baseline gap-2">
        <span className="font-pe-titulo text-[26px] font-bold leading-8">{Math.round(r.nota)}</span>
        <span className="text-pe-legenda text-pe-tinta-suave">de 100 na pronúncia</span>
        <span className="ml-auto text-[14px] font-semibold">{r.aceite ? "Repetida com ajuda" : "Tente outra vez"}</span>
      </p>
      <AvisoAnaliseAproximada fonte={r.fonte} />
      {r.detalhe ? (
        <PalavrasComNota detalhe={r.detalhe} />
      ) : marcar.size ? (
        <p lang="en" className="m-0 text-[16px] leading-6">
          {partes.map((p, i) =>
            marcar.has(soLetras(p)) ? (
              <mark key={i} className="rounded-[4px] bg-pe-errado-suave px-0.5 text-inherit underline decoration-pe-errado decoration-2 underline-offset-4">
                {p}
              </mark>
            ) : (
              <span key={i}>{p}</span>
            )
          )}
        </p>
      ) : null}
      {r.mensagem ? <p className="m-0 text-[15px] leading-[22px]">{r.mensagem}</p> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Usar isto numa conversa (3 minutos com o tutor)                      */
/* ------------------------------------------------------------------ */

type Fase = { tipo: "inicio" } | { tipo: "viva"; dados: ConversaLicao } | { tipo: "fim"; resumo: Resumo } | { tipo: "bloqueada"; mensagem: string; oferta?: Oferta | null };

export function ConversaDaAula({ chapterId, dados }: { chapterId: string; dados: FalaDaAula }) {
  const [fase, setFase] = useState<Fase>({ tipo: "inicio" });
  const [comecar, { isLoading }] = useComecarConversaAulaMutation();
  const frases = dados.frases.filter((f) => f.tipo === "frase").map((f) => f.texto);
  if (!frases.length) return null;

  const minutos = Math.max(1, Math.round((dados.conversa.max_segundos || 180) / 60));
  const indisponivel = fase.tipo === "inicio" && !dados.conversa.disponivel ? dados.conversa.mensagem ?? "A conversa não está disponível agora." : null;

  const abrir = async () => {
    const r = await comecar(chapterId);
    if ("error" in r && r.error) {
      setFase({ tipo: "bloqueada", mensagem: erroFala(r.error, "Não foi possível começar a conversa agora.").mensagem!, oferta: ofertaDoErro(r.error) });
      return;
    }
    setFase({ tipo: "viva", dados: r.data! });
  };

  return (
    <section aria-labelledby="t-conversa-aula" className="flex flex-col gap-4 rounded-pe-md border-[1.5px] border-pe-azul-marca p-5 md:p-6">
      <div className="flex items-start gap-3">
        <span aria-hidden className="pe-sobre-marca flex size-11 shrink-0 items-center justify-center rounded-pe-fala bg-pe-azul-marca text-pe-sobre-marca">
          <MessagesSquare className="size-6" />
        </span>
        <div className="flex min-w-0 flex-col gap-1">
          <h2 id="t-conversa-aula" className="m-0 font-pe-titulo text-[22px] font-bold leading-[28px]">
            Usar isto numa conversa
          </h2>
          <p className="m-0 max-w-[62ch] text-pe-tinta-suave">
            {minutos} minutos com o tutor numa situação de trabalho como a do vídeo. Uma frase só fica aprendida quando a diz sozinho, sem o tutor a dizer primeiro.
          </p>
        </div>
      </div>

      {fase.tipo === "viva" ? (
        <Viva dados={fase.dados} frases={frases} tituloFrases="Tente usar estas frases da aula" aoTerminar={(resumo) => setFase({ tipo: "fim", resumo })} />
      ) : (
        <ListaFrases frases={frases} titulo="Tente usar estas frases da aula" ditas={fase.tipo === "fim" ? ditasNoResumo(fase.resumo, frases) : undefined} />
      )}

      {fase.tipo === "inicio" ? (
        indisponivel ? (
          <Indisponivel mensagem={indisponivel} />
        ) : (
          <Botao className="self-start" onClick={() => void abrir()} disabled={isLoading}>
            {isLoading ? <Loader2 aria-hidden className="animate-spin" /> : <Mic aria-hidden />}
            Começar a conversa
          </Botao>
        )
      ) : null}
      {fase.tipo === "bloqueada" ? <Indisponivel mensagem={fase.mensagem} oferta={fase.oferta} /> : null}
      {fase.tipo === "fim" ? <FimConversa resumo={fase.resumo} aoRepetir={() => setFase({ tipo: "inicio" })} /> : null}
    </section>
  );
}

function Indisponivel({ mensagem, oferta }: { mensagem: string; oferta?: Oferta | null }) {
  if (oferta) {
    return (
      <div className="flex max-w-[440px] flex-col gap-4">
        <p className="m-0">{mensagem} Entretanto, pode treinar estas frases na revisão de hoje.</p>
        <OfertaPlano
          oferta={oferta}
          saidas={
            <Botao asChild tipo="ligacao" larguraTotal>
              <Link href={REVISAO}>Fazer a revisão de hoje</Link>
            </Botao>
          }
        />
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <Aviso tipo="neutro">{mensagem} Entretanto, pode treinar estas frases na revisão de hoje.</Aviso>
      <Botao asChild tipo="secundario" tamanho="medio" className="self-start">
        <Link href={REVISAO}>Fazer a revisão de hoje</Link>
      </Botao>
    </div>
  );
}

function FimConversa({ resumo, aoRepetir }: { resumo: Resumo; aoRepetir: () => void }) {
  const falas = resumo.transcricao.filter((f) => f.quem === "aluno").length;
  const sozinho = resumo.objectivos.filter((o) => o.usado).length;
  const c = resumo.correccoes[0];
  return (
    <div className="flex flex-col gap-3">
      <div className={cnPe("flex flex-col gap-2 rounded-pe-md px-4 py-3.5", falas ? "bg-pe-certo-suave" : "bg-pe-fundo-suave")}>
        <p className="m-0 font-semibold">
          {falas === 0
            ? "Não ouvimos nenhuma resposta sua."
            : sozinho
              ? `Disse sozinho ${sozinho} de ${resumo.objectivos.length} frases da aula.`
              : `Respondeu ${falas} ${falas === 1 ? "vez" : "vezes"}. Na próxima, tente usar as frases da aula sem esperar pelo tutor.`}
        </p>
        {c ? (
          <p className="m-0 text-[15px] leading-[22px]">
            Um ajuste: <s>{c.disse}</s>{" "}
            <span lang="en" className="font-semibold">
              {c.certo}
            </span>
            . {c.porque}
          </p>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Botao tamanho="medio" onClick={aoRepetir}>
          Conversar outra vez
        </Botao>
        <Botao asChild tipo="ligacao" tamanho="medio">
          <Link href={`/user/laboratory/speaking/summary/${resumo.id}`}>Ver o resumo completo</Link>
        </Botao>
      </div>
    </div>
  );
}
