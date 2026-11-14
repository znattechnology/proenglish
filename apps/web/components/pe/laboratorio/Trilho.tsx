"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Flame, Heart, RotateCcw, Star, Trophy, Zap } from "lucide-react";
import { BarraProgresso, Botao, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { cnPe } from "@/lib/pe";
import type { EstadoVidas, Sequencia, Trilho as TTrilho } from "@/src/domains/student/laboratorio/api";

const ILIMITADAS = 999;
const fmt = (n: number) => n.toLocaleString("pt-PT");

/** Tempo até à próxima vida, por extenso curto: "2 h 40 min". */
export function tempoAte(iso: string | null | undefined) {
  if (!iso) return null;
  const falta = Math.max(0, new Date(iso).getTime() - Date.now());
  const h = Math.floor(falta / 3_600_000);
  const m = Math.ceil((falta % 3_600_000) / 60_000);
  return h ? `${h} h ${m} min` : `${m} min`;
}

/* ------------------------------------------------------------------ */
/* Contadores: curso, dias seguidos, pontos, vidas                      */
/* ------------------------------------------------------------------ */
export function Contadores({ curso, sequencia, vidas, className }: { curso?: string; sequencia?: Sequencia; vidas?: EstadoVidas; className?: string }) {
  const ilimitadas = !!vidas?.unlimited || (vidas?.current ?? 0) >= ILIMITADAS;
  return (
    <div className={cnPe("flex items-center justify-between gap-2 md:flex-wrap md:gap-x-4", className)}>
      {curso ? (
        <Link
          href="/user/laboratory/learn/courses"
          className="inline-flex min-h-11 min-w-0 items-center rounded-pe-sm bg-pe-fundo-suave px-3 text-[15px] font-semibold text-pe-tinta no-underline hover:bg-pe-fundo-forte hover:text-pe-tinta md:px-3.5 md:text-[16px]"
        >
          <span className="truncate">{curso}</span>
        </Link>
      ) : null}
      <span role="img" aria-label={`${sequencia?.current_streak ?? 0} dias seguidos`} className="inline-flex items-center gap-1 font-semibold">
        <Flame aria-hidden className={cnPe("size-[22px]", sequencia?.practiced_today ? "fill-pe-realce text-[#c79500]" : "text-pe-tinta-suave")} />
        {sequencia?.current_streak ?? 0}
      </span>
      <span role="img" aria-label={`${fmt(vidas?.points ?? 0)} pontos`} className="inline-flex items-center gap-1 font-semibold tabular-nums">
        <Zap aria-hidden className="size-[22px] fill-pe-realce text-[#c79500]" />
        {fmt(vidas?.points ?? 0)}
      </span>
      <Link
        href="/user/laboratory/learn/shop"
        aria-label={ilimitadas ? "Vidas ilimitadas. Abrir a loja" : `${vidas?.current ?? 0} de ${vidas?.maximum ?? 3} vidas. Abrir a loja`}
        className="inline-flex min-h-11 items-center gap-1 font-semibold text-pe-tinta no-underline hover:text-pe-tinta"
      >
        <Heart aria-hidden className="size-[22px] fill-pe-vida text-pe-vida" />
        {ilimitadas ? "∞" : vidas?.current ?? 0}
      </Link>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Trilho: unidades com a faixa e os discos em serpentina              */
/* ------------------------------------------------------------------ */
const DESVIOS = [0, 1, 1.7, 1, 0, -1, -1.7, -1];

type Licao = TTrilho["unidades"][number]["licoes"][number];

export function TrilhoLicoes({ trilho }: { trilho: TTrilho }) {
  const [praticar, setPraticar] = useState<Licao | null>(null);
  let indiceGlobal = 0;
  return (
    <>
      <div className="flex flex-col gap-2">
        {trilho.unidades.map((u) => {
          const aberta = u.licoes.some((l) => l.estado !== "bloqueada");
          return (
            <section key={u.id} aria-labelledby={`unidade-${u.id}`} className="flex flex-col gap-2 pb-6">
              <header
                className={cnPe(
                  "flex items-center justify-between gap-3 px-[18px] py-3.5 md:px-6 md:py-5",
                  aberta ? "pe-sobre-marca rounded-pe-fala bg-pe-azul-marca text-pe-sobre-marca" : "rounded-pe-md bg-pe-fundo-suave text-pe-tinta-suave"
                )}
              >
                <div className="flex min-w-0 flex-col">
                  <span className="text-[14px] font-semibold leading-5">Unidade {u.ordem}</span>
                  <h2 id={`unidade-${u.id}`} className="m-0 font-pe-titulo text-[19px] font-bold leading-6 md:text-[22px] md:leading-7">
                    {u.titulo}
                  </h2>
                  {u.descricao ? <p className="m-0 mt-1 hidden text-[15px] leading-[22px] md:block">{u.descricao}</p> : null}
                </div>
              </header>
              <ol className="m-0 flex list-none flex-col items-center gap-[18px] p-0 pt-3.5 md:gap-5">
                {u.licoes.map((l, i) => {
                  const desvio = DESVIOS[indiceGlobal++ % 8];
                  return (
                    <li key={l.id} className="flex flex-col items-center [--passo:40px] md:[--passo:52px]" style={{ transform: `translateX(calc(var(--passo) * ${desvio}))` }}>
                      <No licao={l} ultima={i === u.licoes.length - 1} aoPraticar={() => setPraticar(l)} />
                    </li>
                  );
                })}
              </ol>
            </section>
          );
        })}
      </div>
      <PraticarDeNovo licao={praticar} aoFechar={() => setPraticar(null)} />
    </>
  );
}

function No({ licao, ultima, aoPraticar }: { licao: Licao; ultima: boolean; aoPraticar: () => void }) {
  const { estado } = licao;
  const nome = { feita: "concluída, praticar outra vez", actual: "lição actual", bloqueada: "por abrir" }[estado];
  const Icone = estado === "feita" ? Check : ultima ? Trophy : Star;
  const disco = cnPe(
    "flex size-[68px] items-center justify-center rounded-full no-underline md:size-[76px] [&_svg]:size-8 md:[&_svg]:size-9",
    estado === "feita" && "bg-pe-azul-marca text-pe-sobre-marca shadow-[0_6px_0_#00003d] hover:bg-pe-azul-vivo",
    estado === "actual" && "bg-pe-realce text-pe-tinta shadow-[0_6px_0_#c79500]",
    estado === "bloqueada" && "cursor-not-allowed bg-pe-fundo-forte text-pe-tinta-suave shadow-[0_6px_0_#cfd2e6]"
  );
  const rotulo = `${licao.titulo}, ${nome}`;

  if (estado === "actual") {
    const pct = licao.exercicios ? (100 * licao.exercicios_feitos) / licao.exercicios : 0;
    return (
      <>
        <div className="pe-sobre-marca mb-1 flex max-w-[220px] flex-col items-start rounded-[18px_18px_18px_0] bg-pe-azul-marca px-4 py-2 text-pe-sobre-marca">
          <span className="font-pe-titulo text-[15px] font-bold leading-5">{licao.exercicios_feitos ? "Continuar" : "Começar"}</span>
          <span className="text-[13px] leading-[18px]">{licao.titulo}</span>
        </div>
        <div className="flex size-[98px] items-center justify-center rounded-full md:size-[108px]" style={{ background: `conic-gradient(var(--pe-azul-vivo, #2f46e8) ${pct}%, #e3e5f4 0)` }}>
          <div className="box-border flex size-[84px] items-start justify-center rounded-full bg-pe-fundo pt-[5px] md:size-[94px] md:pt-1.5">
            <Link href={`/user/laboratory/learn/lesson/${licao.id}`} aria-label={rotulo} className={disco}>
              <Icone aria-hidden />
            </Link>
          </div>
        </div>
      </>
    );
  }
  return (
    <div className="pb-1.5">
      {estado === "feita" ? (
        <button type="button" aria-label={rotulo} title={licao.titulo} onClick={aoPraticar} className={disco}>
          <Icone aria-hidden strokeWidth={3} />
        </button>
      ) : (
        <span role="img" aria-label={rotulo} title={licao.titulo} className={disco}>
          <Icone aria-hidden />
        </span>
      )}
    </div>
  );
}

function PraticarDeNovo({ licao, aoFechar }: { licao: Licao | null; aoFechar: () => void }) {
  return (
    <Dialogo
      aberto={!!licao}
      aoMudar={(v) => !v && aoFechar()}
      titulo="Praticar outra vez"
      topo={
        <span aria-hidden className="pe-sobre-marca flex size-16 items-center justify-center rounded-[22px_22px_22px_0] bg-pe-azul-marca text-pe-sobre-marca">
          <RotateCcw className="size-8" />
        </span>
      }
      descricao={licao ? `Já concluiu "${licao.titulo}". Ao repetir uma lição ganha pontos e recupera uma vida, e não perde nenhuma se errar.` : undefined}
    >
      <dl className="m-0 grid grid-cols-2 gap-3">
        <div className="flex flex-col rounded-pe-md bg-pe-fundo-suave px-3.5 py-3">
          <dt className="text-pe-legenda text-pe-tinta-suave">Por lição repetida</dt>
          <dd className="m-0 font-semibold">5 pontos</dd>
        </div>
        <div className="flex flex-col rounded-pe-md bg-pe-fundo-suave px-3.5 py-3">
          <dt className="text-pe-legenda text-pe-tinta-suave">Vidas</dt>
          <dd className="m-0 font-semibold">Recupera 1</dd>
        </div>
      </dl>
      <div className="flex flex-col gap-3">
        {licao ? (
          <Botao asChild larguraTotal>
            <Link href={`/user/laboratory/learn/lesson/${licao.id}`}>Começar a prática</Link>
          </Botao>
        ) : null}
        <Botao tipo="ligacao" larguraTotal onClick={aoFechar}>
          Agora não
        </Botao>
      </div>
    </Dialogo>
  );
}

/* ------------------------------------------------------------------ */
/* Coluna lateral do desktop                                           */
/* ------------------------------------------------------------------ */
export function MetaDeHoje({ sequencia }: { sequencia?: Sequencia }) {
  if (!sequencia) return <Osso className="h-[120px] rounded-pe-md" />;
  const pct = Math.min(100, (100 * sequencia.minutes_today) / Math.max(1, sequencia.daily_goal_minutes));
  return (
    <section className="flex flex-col gap-3 rounded-pe-md border border-pe-linha p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">Meta de hoje</h2>
        <span className={cnPe("text-pe-legenda", sequencia.goal_completed ? "font-semibold text-pe-certo" : "tabular-nums text-pe-tinta-suave")}>
          {sequencia.goal_completed ? "Cumprida" : `${Math.floor(sequencia.minutes_today)} de ${sequencia.daily_goal_minutes} min`}
        </span>
      </div>
      <BarraProgresso valor={pct} rotulo="Minutos praticados hoje" cor={sequencia.goal_completed ? "certo" : undefined} altura={12} />
      <p className="m-0 text-pe-legenda text-pe-tinta-suave">
        {sequencia.current_streak
          ? `${sequencia.current_streak} ${sequencia.current_streak === 1 ? "dia seguido" : "dias seguidos"}. O seu recorde é ${sequencia.longest_streak}.`
          : "Pratique hoje para começar uma sequência de dias."}
      </p>
    </section>
  );
}

export function CartaoVidas({ vidas }: { vidas?: EstadoVidas }) {
  if (!vidas) return <Osso className="h-[150px] rounded-pe-md" />;
  if (vidas.unlimited) {
    return (
      <section className="flex flex-col gap-2 rounded-pe-md bg-pe-fundo-suave p-6">
        <h2 className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">Vidas</h2>
        <p className="m-0 text-[15px] leading-[22px]">Tem vidas ilimitadas com o seu plano. Pode errar à vontade.</p>
      </section>
    );
  }
  const tempo = vidas.current < vidas.maximum ? tempoAte(vidas.next_heart_at) : null;
  return (
    <section className="flex flex-col gap-3 rounded-pe-md bg-pe-fundo-suave p-6">
      <h2 className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">Vidas</h2>
      <p className="m-0 text-[15px] leading-[22px]">
        Tem {vidas.current} de {vidas.maximum} vidas.{tempo ? ` A próxima volta daqui a ${tempo}.` : ""}
      </p>
      {vidas.licoes_hoje?.limite ? (
        <p className="m-0 text-[15px] leading-[22px]">
          Lições novas hoje: <strong className="tabular-nums">{Math.min(vidas.licoes_hoje.feitas, vidas.licoes_hoje.limite)} de {vidas.licoes_hoje.limite}</strong>. Repetir lições não conta.
        </p>
      ) : null}
      <div className="flex flex-wrap gap-3">
        {vidas.current < vidas.maximum ? (
          <Botao asChild tipo="secundario" tamanho="pequeno">
            <Link href="/user/laboratory/learn/shop">Recarregar por {vidas.refill_cost_points} pontos</Link>
          </Botao>
        ) : null}
        <Botao asChild tipo="ligacao" tamanho="pequeno">
          <Link href="/user/subscription">Vidas e lições ilimitadas no Premium</Link>
        </Botao>
      </div>
    </section>
  );
}

export function EsqueletoTrilho() {
  return (
    <div aria-busy="true" aria-label="A carregar o trilho" className="flex flex-col items-center gap-5">
      <Osso className="h-[76px] w-full rounded-pe-fala" />
      {[0, 1, 1.7, 1, 0].map((d, i) => (
        <Osso key={i} className="size-[68px] rounded-full" style={{ transform: `translateX(${d * 40}px)` }} />
      ))}
    </div>
  );
}
