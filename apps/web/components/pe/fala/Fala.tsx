"use client";

import Link from "next/link";
import { useState } from "react";
import { Mic } from "lucide-react";
import { cnPe } from "@/lib/pe";
import { Aviso, BarraProgresso, Osso } from "@/components/pe";
import { MinutosPorDia } from "@/components/pe/estatisticas/MinutosPorDia";
import { BotaoOuvirFrase } from "@/components/pe/revisao/Exercicios";
import {
  minSeg,
  minutos,
  useMudarMetaFalaMutation,
  useProgressoFalaQuery,
  useResumoFalaQuery,
  type DetalhePronuncia,
  type DiaFala,
  type ProgressoFala,
} from "@/src/domains/student/fala/api";

const diaCurto = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-PT", { weekday: "short" }).replace(".", "");
const diaLongo = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-PT", { weekday: "long", day: "numeric", month: "long" });

/* ------------------------------------------------------------------ */
/* Notas por palavra (avaliação detalhada)                             */
/* ------------------------------------------------------------------ */

function nivel(nota: number | null, erro: string) {
  if (erro === "Omission") return { classe: "bg-pe-errado-suave text-pe-tinta-suave line-through decoration-pe-errado", texto: "não se ouviu" };
  if (nota === null) return { classe: "", texto: "" };
  if (nota >= 80) return { classe: "text-pe-certo", texto: `${nota} de 100, bem` };
  if (nota >= 60) return { classe: "bg-pe-realce-suave", texto: `${nota} de 100, quase` };
  return { classe: "bg-pe-errado-suave underline decoration-pe-errado decoration-2 underline-offset-4", texto: `${nota} de 100, a treinar` };
}

/**
 * A frase com cada palavra pela sua nota: verde (bem), amarelo (quase), vermelho sublinhado
 * (a treinar). A nota de cada palavra vai também em texto, para quem não distingue as cores.
 */
export function PalavrasComNota({ detalhe, className }: { detalhe: DetalhePronuncia; className?: string }) {
  return (
    <div className={cnPe("flex flex-col gap-1.5", className)}>
      <p lang="en" className="m-0 flex flex-wrap gap-x-1.5 gap-y-1 text-[17px] leading-7">
        {detalhe.palavras.map((p, i) => {
          const n = nivel(p.nota, p.erro_tipo);
          return (
            <span key={`${p.palavra}-${i}`} className={cnPe("rounded-[4px] px-0.5 font-semibold", n.classe)}>
              {p.palavra}
              {n.texto ? <span className="sr-only"> ({n.texto})</span> : null}
            </span>
          );
        })}
      </p>
      <p aria-hidden className="m-0 flex flex-wrap gap-x-3 text-[13px] leading-[18px] text-pe-tinta-suave">
        <span><span className="font-semibold text-pe-certo">verde</span> bem</span>
        <span><span className="rounded-[3px] bg-pe-realce-suave px-1 font-semibold">amarelo</span> quase</span>
        <span><span className="rounded-[3px] bg-pe-errado-suave px-1 font-semibold">vermelho</span> a treinar</span>
      </p>
      {detalhe.dica ? <p className="m-0 text-[15px] leading-[22px]">{detalhe.dica}</p> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Últimos 7 dias (painel)                                             */
/* ------------------------------------------------------------------ */

function SemanaEmBarras({ dias, metaMin }: { dias: DiaFala[]; metaMin: number }) {
  const altura = 64;
  const maximo = Math.max(metaMin * 60, ...dias.map((d) => d.segundos), 1);
  const yMeta = Math.min(altura, ((metaMin * 60) / maximo) * altura);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="relative" style={{ height: altura }}>
        <div aria-hidden className="absolute inset-x-0 border-t border-dashed border-pe-linha-forte" style={{ bottom: yMeta }} />
        <ol aria-label="Minutos a falar nos últimos 7 dias" className="absolute inset-0 m-0 grid list-none grid-cols-7 items-end gap-2 p-0">
          {dias.map((d) => {
            const h = d.segundos ? Math.max(4, (d.segundos / maximo) * altura) : 0;
            return (
              <li key={d.dia} className="flex h-full items-end justify-center">
                <span className="sr-only">
                  {diaLongo(d.dia)}{d.hoje ? " (hoje)" : ""}: {d.segundos ? minSeg(d.segundos) : "não falou"}
                </span>
                <span
                  aria-hidden
                  className={cnPe("block w-full max-w-[22px] rounded-t-[4px]", d.hoje ? "bg-pe-azul-marca" : "bg-pe-azul-vivo/45")}
                  style={{ height: h }}
                />
              </li>
            );
          })}
        </ol>
      </div>
      <div aria-hidden className="grid grid-cols-7 gap-2 border-t border-pe-linha pt-1 text-center text-[12px] leading-4 text-pe-tinta-suave">
        {dias.map((d) => (
          <span key={d.dia} className={cnPe(d.hoje && "font-semibold text-pe-tinta")}>
            {d.hoje ? "hoje" : diaCurto(d.dia)}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Meta de fala: escolher 3, 5, 10 ou 15 minutos                       */
/* ------------------------------------------------------------------ */

export function EscolherMetaFala({ actual, opcoes, id = "meta-fala", rotulo = "Meta de fala por dia" }: { actual?: number; opcoes: number[]; id?: string; rotulo?: string }) {
  const [mudar, { isLoading }] = useMudarMetaFalaMutation();
  const [erro, setErro] = useState<string | null>(null);
  return (
    <div className="flex flex-col gap-2">
      <span id={id} className="font-semibold leading-[22px]">
        {rotulo}
      </span>
      <div role="radiogroup" aria-labelledby={id} className="flex flex-wrap gap-2">
        {opcoes.map((m) => (
          <button
            key={m}
            type="button"
            role="radio"
            aria-checked={actual === m}
            disabled={isLoading || actual === undefined}
            onClick={async () => {
              setErro(null);
              const r = await mudar(m);
              if ("error" in r && r.error) setErro("Não foi possível mudar a meta. Tente outra vez.");
            }}
            className={cnPe(
              "min-h-11 min-w-[68px] rounded-full px-4 text-[15px] font-semibold tabular-nums",
              actual === m ? "bg-pe-azul-marca text-pe-sobre-marca" : "border-[1.5px] border-pe-linha-forte bg-pe-fundo text-pe-tinta hover:bg-pe-fundo-suave"
            )}
          >
            {m} min
          </button>
        ))}
      </div>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Resumo do painel                                                    */
/* ------------------------------------------------------------------ */

/**
 * Topo do painel: quanto o aluno falou (frase feita só com dados reais), a meta de fala de hoje
 * e os últimos 7 dias. A meta de estudo (dias seguidos) continua nas definições.
 */
export function ResumoFala() {
  const { data, isLoading, isError } = useResumoFalaQuery();
  const [aMudar, setAMudar] = useState(false);
  if (isLoading) return <Osso className="h-[148px] rounded-pe-md" />;
  if (isError || !data) return null;
  const { hoje, semana } = data;
  const vazio = semana.segundos === 0;
  const faltam = Math.max(0, hoje.meta_min * 60 - hoje.segundos);

  return (
    <section aria-labelledby="titulo-fala" className="grid gap-5 rounded-pe-md border border-pe-linha p-5 md:grid-cols-[minmax(0,1.4fr)_minmax(260px,1fr)] md:gap-8 md:p-6">
      <div className="flex min-w-0 flex-col gap-3">
        <h2 id="titulo-fala" className="m-0 flex items-center gap-2 text-[15px] font-semibold leading-5 text-pe-tinta-suave">
          <Mic aria-hidden className="size-[18px] text-pe-azul-marca" />A sua fala
        </h2>
        <p className="m-0 font-pe-titulo text-[20px] font-semibold leading-7 md:text-[22px] md:leading-[30px]">{data.frase}</p>
        {vazio ? (
          <Link href="/user/laboratory/speaking/real-time" className="self-start text-[15px] font-semibold">
            Falar com o tutor
          </Link>
        ) : (
          <Link href="/user/laboratory/speaking/progress" className="self-start text-[15px] font-semibold">
            Ver o progresso da fala
          </Link>
        )}
      </div>

      <div className="flex min-w-0 flex-col gap-4">
        <div className="flex flex-col gap-2">
          <p className="m-0 flex items-baseline justify-between gap-3">
            <span className="font-semibold">Hoje</span>
            <span className="tabular-nums text-pe-tinta-suave">
              <span className="font-pe-titulo text-[22px] font-bold text-pe-tinta">{minutos(hoje.segundos)}</span> de {hoje.meta_min} min a falar
            </span>
          </p>
          <BarraProgresso valor={hoje.percentagem} altura={10} cor={hoje.cumprida ? "certo" : "marca"} rotulo={`Meta de fala de hoje: ${hoje.percentagem}%`} />
          <p className="m-0 text-pe-legenda text-pe-tinta-suave">
            {hoje.cumprida ? "Meta de fala cumprida." : hoje.segundos ? `Faltam ${minSeg(faltam)}.` : "Conta o tempo em que fala: conversas, lições, revisão e aulas."}{" "}
            <button type="button" onClick={() => setAMudar((v) => !v)} aria-expanded={aMudar} className="bg-transparent p-0 font-semibold text-pe-azul-marca underline underline-offset-[3px]">
              Mudar a meta
            </button>
          </p>
          {aMudar ? <EscolherMetaFala actual={hoje.meta_min} opcoes={data.metas_validas} id="meta-fala-painel" /> : null}
        </div>
        <SemanaEmBarras dias={semana.dias} metaMin={hoje.meta_min} />
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Progresso da fala (página de progresso)                             */
/* ------------------------------------------------------------------ */

const inicioSemana = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-PT", { day: "numeric", month: "short" }).replace(".", "");
const traco = (v: number | null, casas = 0) => (v === null ? "—" : v.toLocaleString("pt-PT", { maximumFractionDigits: casas }));

/**
 * Quanto fala por semana (últimas 8), como fala (palavras por minuto, tamanho das respostas,
 * pausas longas) e as palavras que ainda não saem bem. Só números medidos ou calculados a partir
 * das gravações e conversas: sem dados, um traço.
 */
export function ProgressoDaFala() {
  const { data, isLoading, isError, refetch } = useProgressoFalaQuery();
  if (isLoading) return <Osso className="h-[320px] rounded-pe-md" />;
  if (isError || !data) {
    return (
      <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
        <p className="m-0">Não conseguimos carregar os minutos a falar.</p>
        <button type="button" onClick={() => refetch()} className="bg-transparent p-0 font-semibold text-pe-azul-marca underline">
          Tentar outra vez
        </button>
      </div>
    );
  }
  const semanas = data.semanas;
  const total = semanas.reduce((a, s) => a + s.segundos, 0);
  const comMedidas = semanas.filter((s) => s.ppm !== null || s.palavras_por_resposta !== null || s.pausas_por_minuto !== null);
  return (
    <div className="grid items-start gap-8 lg:grid-cols-[3fr_2fr]">
      <section aria-labelledby="titulo-semanas" className="flex min-w-0 flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h2 id="titulo-semanas" className="m-0 font-pe-titulo text-pe-titulo-s">
            Minutos a falar por semana
          </h2>
          <p className="m-0 text-pe-tinta-suave">
            {total
              ? `${minSeg(total)} nas últimas 8 semanas: conversas, lições, revisão e aulas.`
              : "Ainda não há minutos a falar. Cada conversa e cada gravação contam."}
          </p>
        </div>
        <MinutosPorDia
          dias={semanas.map((s) => ({ data: s.inicio, minutos: minutos(s.segundos), rotulo: s.actual ? "esta" : inicioSemana(s.inicio) }))}
          meta={data.meta_min * 7}
          legendaMeta={`meta da semana: ${data.meta_min} min por dia`}
          rotuloLongo={(iso) => `Semana de ${inicioSemana(iso)}`}
          descricao="Minutos a falar por semana"
          cabecalho="Semana"
        />

        <h3 className="m-0 mt-2 text-[17px] font-semibold leading-6">Como fala</h3>
        {comMedidas.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[320px] border-collapse text-left text-[15px]">
              <thead>
                <tr className="text-[14px] leading-5 text-pe-tinta-suave">
                  <th scope="col" className="py-1.5 pr-2 font-normal">Semana</th>
                  <th scope="col" className="py-1.5 pr-2 text-right font-normal">Palavras por minuto</th>
                  <th scope="col" className="py-1.5 pr-2 text-right font-normal">Palavras por resposta</th>
                  <th scope="col" className="py-1.5 text-right font-normal">Pausas longas por minuto</th>
                </tr>
              </thead>
              <tbody>
                {semanas.map((s) => (
                  <tr key={s.inicio} className={cnPe("border-t border-pe-fundo-forte tabular-nums", s.actual && "font-semibold")}>
                    <td className="py-1.5 pr-2">{s.actual ? "Esta semana" : inicioSemana(s.inicio)}</td>
                    <td className="py-1.5 pr-2 text-right">{traco(s.ppm)}</td>
                    <td className="py-1.5 pr-2 text-right">{traco(s.palavras_por_resposta, 1)}</td>
                    <td className="py-1.5 text-right">{traco(s.pausas_por_minuto, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="m-0 mt-2 text-pe-legenda text-pe-tinta-suave">
              Mais palavras por minuto e respostas mais longas, com menos pausas longas (mais de 1 segundo), mostram mais fluência.
            </p>
          </div>
        ) : (
          <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4 text-pe-tinta-suave">Depois de algumas gravações e conversas vê aqui o seu ritmo de fala.</p>
        )}
      </section>

      <PalavrasATreinar p={data} />
    </div>
  );
}

function PalavrasATreinar({ p }: { p: ProgressoFala }) {
  const lista = p.palavras_treinar;
  return (
    <section aria-labelledby="titulo-palavras" className="flex min-w-0 flex-col gap-3">
      <h2 id="titulo-palavras" className="m-0 font-pe-titulo text-pe-titulo-s">
        Palavras a treinar
      </h2>
      {lista.length ? (
        <ul className="m-0 flex list-none flex-col p-0">
          {lista.map((w) => (
            <li key={w.palavra} className="flex items-center gap-3 border-b border-pe-fundo-forte py-2.5 last:border-b-0">
              <span className="flex min-w-0 flex-1 flex-col">
                <span lang="en" className="text-[17px] font-semibold leading-6">
                  {w.palavra}
                </span>
                <span className="text-[14px] leading-5 text-pe-tinta-suave">
                  {`Saiu mal ${w.falhas} de ${w.tentativas} ${w.tentativas === 1 ? "vez" : "vezes"}`}
                  {w.fonema ? `. Som difícil: /${w.fonema}/` : ""}
                  {w.media !== null ? `. Nota média ${Math.round(w.media)}` : ""}
                </span>
              </span>
              <BotaoOuvirFrase texto={w.palavra} rotulo="Ouvir" />
            </li>
          ))}
        </ul>
      ) : (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4 text-pe-tinta-suave">
          Quando uma palavra não sair bem numa gravação, aparece aqui. Também entra na revisão de hoje.
        </p>
      )}
    </section>
  );
}
