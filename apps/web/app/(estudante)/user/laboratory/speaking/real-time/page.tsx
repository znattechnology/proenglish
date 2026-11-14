"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Lock, Target, Volume2 } from "lucide-react";
import { Aviso, Botao, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Conversa } from "@/components/pe/conversa/Conversa";
import { falarNoBrowser } from "@/components/pe/conversa/useConversa";
import { cnPe } from "@/lib/pe";
import {
  NIVEIS_DESCRICAO,
  erroConversa,
  useComecarMutation,
  usePrepararQuery,
  type Correcao,
  type Nivel,
  type NovaSessao,
  type Objectivo,
  type Preparar,
} from "@/src/domains/student/conversa/api";

const CORRECOES: { id: Correcao; nome: string; descricao: string }[] = [
  { id: "suave", nome: "Suave", descricao: "O tutor não interrompe: repete a sua ideia já na forma certa e continua." },
  { id: "directa", nome: "Directa", descricao: "Quando ouve um erro claro, o tutor diz logo o que estava mal e a forma certa." },
];

export default function PaginaConversa() {
  return (
    <Suspense>
      <PrepararOuConversa />
    </Suspense>
  );
}

/** Preparar a conversa e, depois de começar, a conversa em curso (a mesma página). */
function PrepararOuConversa() {
  const { data, isError, refetch } = usePrepararQuery();
  const [sessao, setSessao] = useState<NovaSessao | null>(null);

  if (sessao && data)
    return <Conversa sessao={sessao} modo={data.modo} chavePublica={data.vapi?.public_key ?? null} minutosUsadosHoje={data.quota.minutos_usados} minutosDia={data.quota.minutos_dia} />;

  return (
    <Pagina>
      <div className="flex flex-col gap-1">
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Preparar a conversa</h1>
        <p className="m-0 max-w-[68ch] text-pe-tinta-suave">Escolha a situação. O tutor adapta-se ao nível e à forma de corrigir que preferir.</p>
      </div>
      {isError ? (
        <div role="alert" className="flex max-w-[640px] flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
          <p className="m-0">Não conseguimos preparar a conversa.</p>
          <Botao tamanho="pequeno" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : !data ? (
        <div aria-busy="true" aria-label="A carregar" className="grid gap-6 lg:grid-cols-[3fr_2fr]">
          <Osso className="h-[360px] rounded-pe-md" />
          <Osso className="h-[360px] rounded-pe-md" />
        </div>
      ) : (
        <Formulario p={data} aoComecar={setSessao} />
      )}
    </Pagina>
  );
}

function Formulario({ p, aoComecar }: { p: Preparar; aoComecar: (s: NovaSessao) => void }) {
  const pedida = useSearchParams().get("situacao"); // "Repetir esta conversa" no resumo
  const inicial = p.situacoes.find((s) => s.id === pedida) ?? p.situacoes[0];
  const [situacao, setSituacao] = useState(inicial?.id ?? "");
  // O nível vem do perfil de fala do aluno («O seu nível»); sem perfil, o que o professor sugere.
  // A correcção sugerida pelo professor vem já escolhida. O aluno pode mudar as duas.
  const nivelDe = (s?: Preparar["situacoes"][number]) => p.perfil?.nivel ?? s?.nivel ?? p.preferencias.nivel;
  const [correcao, setCorrecao] = useState<Correcao>(inicial?.correcao ?? p.preferencias.correcao);
  const [nivel, setNivel] = useState<Nivel>(nivelDe(inicial));
  const escolherSituacao = (id: string) => {
    const s = p.situacoes.find((x) => x.id === id);
    setSituacao(id);
    setNivel(nivelDe(s));
    setCorrecao(s?.correcao ?? p.preferencias.correcao);
  };
  const escolhida = p.situacoes.find((s) => s.id === situacao);
  const [area, setArea] = useState(p.preferencias.area);
  const [comecar, { isLoading }] = useComecarMutation();
  const [erro, setErro] = useState<string | null>(null);
  const q = p.quota;
  const nomesArea = p.areas.map((a) => a.nome);

  useEffect(() => {
    // Pede o microfone já, para a conversa não arrancar com um pedido do browser a meio.
    if (p.modo === "vapi") navigator.mediaDevices?.getUserMedia?.({ audio: true }).then((s) => s.getTracks().forEach((t) => t.stop())).catch(() => {});
  }, [p.modo]);

  const bloqueio =
    q.motivo === "plano_sem_tutor"
      ? "A conversa com o tutor não faz parte do seu plano."
      : q.motivo === "teste_expirado"
        ? "O período de experiência da conversa com o tutor terminou."
        : q.motivo === "sem_minutos"
          ? `Já usou os ${q.minutos_dia} minutos de conversa de hoje. Amanhã tem mais.`
          : null;

  return (
    <form
      className="grid items-start gap-8 lg:grid-cols-[3fr_2fr]"
      onSubmit={async (e) => {
        e.preventDefault();
        setErro(null);
        try {
          aoComecar(await comecar({ situacao, nivel, correcao, area }).unwrap());
        } catch (er) {
          setErro(erroConversa(er));
        }
      }}
    >
      <div className="flex min-w-0 flex-col gap-6">
        <fieldset className="m-0 flex min-w-0 flex-col gap-2.5 border-0 p-0">
          <legend className="mb-2.5 p-0 font-pe-titulo text-[18px] font-semibold leading-6">Situação</legend>
          <div className="grid gap-2.5 xl:grid-cols-2">
            {p.situacoes.map((s) => {
              const a = s.id === situacao;
              return (
                <label
                  key={s.id}
                  className={cnPe(
                    "flex cursor-pointer items-center gap-3 rounded-pe-md px-4 py-3.5 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pe-azul-vivo",
                    a ? "border-2 border-pe-azul-marca bg-pe-fundo-suave" : "border border-pe-linha bg-pe-fundo hover:bg-pe-fundo-suave"
                  )}
                >
                  <input type="radio" name="situacao" value={s.id} checked={a} onChange={() => escolherSituacao(s.id)} className="m-0 size-5 shrink-0 accent-pe-azul-marca" />
                  <span className="flex flex-col">
                    <span className="font-semibold leading-[22px]">{s.titulo}</span>
                    <span className="text-[14px] leading-5 text-pe-tinta-suave">
                      {s.descricao} {s.minutos_sugeridos} minutos.
                      {s.curso ? ` Do curso «${s.curso.titulo}».` : ""}
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>
        <Objectivos lista={p.objectivos?.[situacao] ?? []} />
      </div>

      <div className="flex min-w-0 flex-col gap-6 lg:sticky lg:top-8">
        <fieldset className="m-0 flex flex-col gap-2.5 border-0 p-0">
          <legend className="mb-2.5 p-0 font-pe-titulo text-[18px] font-semibold leading-6">Como quer ser corrigido</legend>
          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            {CORRECOES.map((o) => {
              const a = o.id === correcao;
              return (
                <label
                  key={o.id}
                  className={cnPe(
                    "flex cursor-pointer items-start gap-3 rounded-pe-md px-4 py-3.5 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pe-azul-vivo",
                    a ? "border-2 border-pe-azul-marca bg-pe-fundo-suave" : "border border-pe-linha bg-pe-fundo hover:bg-pe-fundo-suave"
                  )}
                >
                  <input type="radio" name="correcao" value={o.id} checked={a} onChange={() => setCorrecao(o.id)} className="m-0 mt-0.5 size-5 shrink-0 accent-pe-azul-marca" />
                  <span className="flex flex-col">
                    <span className="font-semibold leading-[22px]">{o.nome}</span>
                    <span className="text-[14px] leading-5 text-pe-tinta-suave">{o.descricao}</span>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>

        <div className="flex flex-col gap-2.5">
          <h2 id="titulo-nivel" className="m-0 font-pe-titulo text-[18px] font-semibold leading-6">
            O seu nível
          </h2>
          <div role="group" aria-labelledby="titulo-nivel" className="grid grid-cols-6 gap-1.5">
            {p.niveis.map((n) => (
              <button
                key={n}
                type="button"
                aria-pressed={n === nivel}
                onClick={() => setNivel(n)}
                className={cnPe(
                  "min-h-11 rounded-pe-sm font-pe-titulo text-[15px] font-bold",
                  n === nivel ? "border-2 border-pe-azul-marca bg-pe-azul-marca text-pe-sobre-marca" : "border-[1.5px] border-pe-linha-forte bg-pe-fundo text-pe-tinta hover:bg-pe-fundo-suave"
                )}
              >
                {n}
              </button>
            ))}
          </div>
          <span className="text-[14px] leading-5 text-pe-tinta-suave">
            {nivel}: {NIVEIS_DESCRICAO[nivel]}
          </span>
          {p.perfil?.nivel ? (
            <span className="text-[14px] leading-5 text-pe-tinta-suave">
              {nivel === p.perfil.nivel ? "Escolhemos pelas suas últimas conversas e lições." : `Pelas suas conversas e lições, o seu nível é ${p.perfil.nivel}.`}
            </span>
          ) : null}
          {escolhida?.nivel || escolhida?.correcao ? (
            <span className="text-[14px] leading-5 text-pe-tinta-suave">
              O professor sugere {[escolhida.nivel ? `o nível ${escolhida.nivel}` : "", escolhida.correcao ? `a correcção ${escolhida.correcao === "suave" ? "suave" : "directa"}` : ""].filter(Boolean).join(" e ")} para esta situação. Pode mudar.
            </span>
          ) : null}
        </div>

        <div className="flex flex-col gap-2.5">
          <h2 className="m-0 font-pe-titulo text-[18px] font-semibold leading-6">Vocabulário da área</h2>
          <Pilulas opcoes={nomesArea} valor={p.areas.find((a) => a.id === area)?.nome ?? nomesArea[0]} aoMudar={(nome) => setArea(p.areas.find((a) => a.nome === nome)?.id ?? area)} rotulo="Vocabulário da área" />
        </div>

        <div className="flex flex-col gap-3 border-t border-pe-linha pt-5">
          {bloqueio ? (
            <div className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-realce-suave p-4">
              <span className="flex items-start gap-2.5 text-[15px] leading-[22px]">
                <Lock aria-hidden className="mt-0.5 size-5 shrink-0" />
                {bloqueio}
              </span>
              {q.motivo !== "sem_minutos" ? (
                <Botao asChild tipo="realce" tamanho="pequeno">
                  <Link href="/user/upgrade?plan=PREMIUM_PLUS">Ver os planos com tutor</Link>
                </Botao>
              ) : null}
            </div>
          ) : (
            <p className="m-0 text-[15px] leading-[22px]">
              {q.minutos_restantes === null
                ? `Conversas até ${q.max_minutos_sessao} minutos.`
                : `Hoje ainda tem ${q.minutos_restantes} dos ${q.minutos_dia} minutos de conversa. Cada conversa vai até ${Math.min(q.max_minutos_sessao, q.minutos_restantes)} minutos.`}
            </p>
          )}
          {p.modo === "simulado" ? <Aviso tipo="neutro">Modo de ensaio: o tutor responde com um guião, sem chamada de voz real. As notas são indicativas.</Aviso> : null}
          {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
          <Botao type="submit" larguraTotal disabled={!q.pode_comecar || isLoading || !situacao}>
            {isLoading ? "A começar…" : "Começar a conversa"}
          </Botao>
          <Botao asChild tipo="ligacao" tamanho="pequeno" className="self-center">
            <Link href="/user/laboratory/speaking/progress">Ver o seu progresso na conversa</Link>
          </Botao>
        </div>
      </div>
    </form>
  );
}

/** As frases-alvo desta conversa (do perfil de fala): o tutor cria ocasiões para o aluno as dizer. */
function Objectivos({ lista }: { lista: Objectivo[] }) {
  if (!lista.length) return null;
  return (
    <section aria-labelledby="titulo-objectivos" className="flex flex-col gap-2 rounded-pe-md bg-pe-fundo-suave p-4 md:p-5">
      <h2 id="titulo-objectivos" className="m-0 flex items-center gap-2 font-pe-titulo text-[18px] font-semibold leading-6">
        <Target aria-hidden className="size-5 shrink-0 text-pe-azul-marca" />
        Objectivos desta conversa
      </h2>
      <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">Tente dizer estas frases sozinho durante a conversa. O tutor vai dar-lhe ocasiões para as usar.</p>
      <ul className="m-0 flex list-none flex-col p-0">
        {lista.map((o) => (
          <li key={o.en} className="border-b border-pe-fundo-forte last:border-b-0">
            <button type="button" onClick={() => falarNoBrowser(o.en)} aria-label={`Ouvir: ${o.en}${o.pt ? `. ${o.pt}` : ""}`} className="flex min-h-11 w-full items-start gap-3 bg-transparent py-2.5 text-left">
              <Volume2 aria-hidden className="mt-0.5 size-5 shrink-0 text-pe-azul-marca" />
              <span className="flex flex-col">
                <span lang="en" className="font-semibold leading-[22px]">
                  {o.en}
                </span>
                {o.pt ? <span className="text-[14px] leading-5 text-pe-tinta-suave">{o.pt}</span> : null}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
