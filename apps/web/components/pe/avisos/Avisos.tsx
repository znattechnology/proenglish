"use client";

import { useEffect, useState } from "react";
import { BellRing } from "lucide-react";
import { Aviso, Botao, Interruptor } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import {
  cancelarPushLocal,
  pushSuportado,
  subscreverPush,
  useAvisosQuery,
  useMudarAvisosMutation,
  useRegistarPushMutation,
  useRetirarPushMutation,
  type Avisos,
} from "@/src/domains/student/avisos/api";

const HORAS = ["07:00", "12:30", "19:00", "21:00"];

const iphoneSemApp = () => {
  if (typeof window === "undefined") return false;
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
  const instalada = window.matchMedia("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return ios && !instalada;
};

type EstadoPermissao = "sem_suporte" | "default" | "granted" | "denied";
const permissaoActual = (): EstadoPermissao => (pushSuportado() ? (Notification.permission as EstadoPermissao) : "sem_suporte");

/** Liga as notificações push neste browser e regista-as no servidor. */
export function useLigarPush(a: Avisos | undefined) {
  const [registar] = useRegistarPushMutation();
  // A permissão só existe no browser; no servidor a secção ainda mostra o esqueleto (sem `a`).
  const [permissao, setPermissao] = useState<EstadoPermissao>(permissaoActual);
  // Autorizar não chega: é preciso uma subscrição push deste browser registada no servidor.
  const [subscrito, setSubscrito] = useState<boolean | null>(null);
  useEffect(() => {
    if (!pushSuportado()) return;
    let vivo = true;
    navigator.serviceWorker.ready
      .then((r) => r.pushManager.getSubscription())
      .then((s) => vivo && setSubscrito(!!s))
      .catch(() => vivo && setSubscrito(false));
    return () => {
      vivo = false;
    };
  }, []);
  const ligar = async () => {
    if (!a?.push.disponivel || !a.push.chave_publica) return false;
    let sub = await subscreverPush(a.push.chave_publica).catch(() => null);
    setPermissao(permissaoActual());
    if (!sub) return false;
    try {
      await registar(sub).unwrap();
    } catch (e) {
      // A subscrição deste browser pertence a outra conta: faz-se uma nova para esta.
      if ((e as { status?: number })?.status !== 409) throw e;
      await cancelarPushLocal();
      sub = await subscreverPush(a.push.chave_publica).catch(() => null);
      if (!sub) return false;
      await registar(sub).unwrap();
    }
    setSubscrito(true);
    return true;
  };
  return { permissao, subscrito, setSubscrito, ligar };
}

/** Secção "Avisos" das definições. */
export function SeccaoAvisos() {
  const { data: a, isError } = useAvisosQuery();
  const [mudar, { isLoading }] = useMudarAvisosMutation();
  const [retirar] = useRetirarPushMutation();
  const { permissao, subscrito, setSubscrito, ligar } = useLigarPush(a);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const guardar = async (m: Parameters<typeof mudar>[0]) => {
    setErro(null);
    try {
      await mudar(m).unwrap();
    } catch {
      setErro("Não foi possível guardar. Tente outra vez.");
    }
  };

  if (isError)
    return (
      <section id="avisos" className="rounded-pe-md border border-pe-linha p-5 md:p-6">
        <p className="m-0">Não conseguimos carregar os avisos.</p>
      </section>
    );

  return (
    <section id="avisos" aria-labelledby="titulo-avisos" className="flex scroll-mt-8 flex-col gap-4 rounded-pe-md border border-pe-linha p-5 md:p-6">
      <h2 id="titulo-avisos" className="m-0 font-pe-titulo text-pe-titulo-s">
        Avisos
      </h2>
      {!a ? (
        <div aria-busy="true" className="h-40 rounded-pe-md bg-pe-fundo-suave" />
      ) : (
        <>
          <div className="flex flex-col gap-3">
            <Interruptor
              rotulo="Lembrete da meta diária"
              descricao="Um aviso por dia, à hora que escolher, só se ainda não tiver praticado."
              ligado={a.lembrete.ligado}
              disabled={isLoading}
              aoMudar={async (v) => {
                setAviso(null);
                await guardar({ lembrete: { ligado: v } });
                if (v && a.push.disponivel && permissao === "default") {
                  const ok = await ligar().catch(() => false);
                  if (!ok) setAviso("Sem autorização para notificações, o lembrete aparece só dentro da app.");
                }
              }}
            />
            {a.lembrete.ligado ? (
              <div className="flex flex-col gap-2">
                <span id="rotulo-hora" className="font-semibold leading-[22px]">
                  Hora do lembrete
                </span>
                <div role="radiogroup" aria-labelledby="rotulo-hora" className="flex flex-wrap gap-2">
                  {Array.from(new Set([...HORAS, a.lembrete.hora])).sort().map((h) => (
                    <button
                      key={h}
                      type="button"
                      role="radio"
                      aria-checked={a.lembrete.hora === h}
                      disabled={isLoading}
                      onClick={() => guardar({ lembrete: { hora: h } })}
                      className={cnPe(
                        "min-h-11 min-w-[80px] rounded-full px-4 text-[15px] font-semibold tabular-nums",
                        a.lembrete.hora === h ? "bg-pe-azul-marca text-pe-sobre-marca" : "border-[1.5px] border-pe-linha-forte bg-pe-fundo text-pe-tinta hover:bg-pe-fundo-suave"
                      )}
                    >
                      {h}
                    </button>
                  ))}
                  <label className="flex min-h-11 items-center gap-2 rounded-full border-[1.5px] border-pe-linha-forte px-3 text-[15px]">
                    <span className="text-pe-tinta-suave">Outra</span>
                    <input
                      type="time"
                      step={900}
                      defaultValue={a.lembrete.hora}
                      onBlur={(e) => e.target.value && e.target.value !== a.lembrete.hora && guardar({ lembrete: { hora: e.target.value } })}
                      className="bg-transparent font-semibold tabular-nums"
                      aria-label="Outra hora para o lembrete"
                    />
                  </label>
                </div>
                <span className="text-pe-legenda text-pe-tinta-suave">Hora de Angola. O lembrete sai no quarto de hora escolhido.</span>
              </div>
            ) : null}
          </div>

          <div className="flex flex-col">
            <span className="pb-1 pt-2 font-semibold leading-[22px]">O que quer receber</span>
            <Interruptor rotulo="Meta diária e dias seguidos" ligado={a.tipos.meta} disabled={isLoading} aoMudar={(v) => guardar({ tipos: { meta: v } })} />
            <Interruptor rotulo="Liga semanal e conquistas" ligado={a.tipos.liga} disabled={isLoading} aoMudar={(v) => guardar({ tipos: { liga: v } })} />
            <Interruptor rotulo="Certificados" ligado={a.tipos.certificados} disabled={isLoading} aoMudar={(v) => guardar({ tipos: { certificados: v } })} />
            <Interruptor rotulo="Aulas novas nos seus cursos" ligado={a.tipos.cursos} disabled={isLoading} aoMudar={(v) => guardar({ tipos: { cursos: v } })} />
            <Interruptor rotulo="Subscrição e recibos" descricao="Pagamentos e fim do plano. Não se podem desligar. Os lembretes antes da renovação estão em Estudo e renovação." ligado disabled aoMudar={() => {}} />
          </div>

          <div className="flex flex-col gap-2 rounded-pe-md bg-pe-fundo-suave p-4">
            <span className="flex items-center gap-2 font-semibold leading-[22px]">
              <BellRing aria-hidden className="size-5 text-pe-azul-marca" /> Notificações neste aparelho
            </span>
            {!a.push.disponivel ? (
              <span className="text-[15px] leading-[22px] text-pe-tinta-suave">As notificações fora da app ainda não estão disponíveis. Os avisos aparecem em Notificações.</span>
            ) : permissao === "sem_suporte" ? (
              <span className="text-[15px] leading-[22px] text-pe-tinta-suave">
                {iphoneSemApp() ? "No iPhone, as notificações só funcionam com a app instalada no ecrã principal." : "Este browser não recebe notificações. Os avisos aparecem em Notificações."}
              </span>
            ) : permissao === "denied" ? (
              <span className="text-[15px] leading-[22px] text-pe-tinta-suave">O browser está a bloquear as notificações deste site. Pode desbloquear nas definições do browser, no cadeado ao lado do endereço.</span>
            ) : permissao === "granted" && subscrito ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-[15px] leading-[22px]">Ligadas neste aparelho.</span>
                <Botao
                  tipo="ligacao"
                  tamanho="pequeno"
                  onClick={async () => {
                    const endpoint = await cancelarPushLocal();
                    if (endpoint) await retirar(endpoint);
                    setSubscrito(false);
                    setAviso("Desligámos as notificações neste aparelho.");
                  }}
                >
                  Desligar neste aparelho
                </Botao>
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-[15px] leading-[22px] text-pe-tinta-suave">Receba os avisos mesmo com a app fechada.</span>
                <Botao
                  tamanho="pequeno"
                  onClick={async () => {
                    setAviso(null);
                    const ok = await ligar().catch(() => false);
                    setAviso(ok ? "Notificações ligadas neste aparelho." : "Sem autorização, os avisos ficam só em Notificações.");
                  }}
                >
                  Ligar neste aparelho
                </Botao>
              </div>
            )}
          </div>
          {aviso ? <Aviso tipo="info">{aviso}</Aviso> : null}
          {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
        </>
      )}
    </section>
  );
}

const CHAVE_PEDIDO = "pe_lembrete_pedido";

/**
 * Pedido de lembrete no fim de uma lição, quando a pessoa chega aos 3 dias seguidos.
 * Só aparece uma vez, e só se as notificações ainda não foram pedidas.
 */
export function PedirLembrete({ sequencia }: { sequencia: number }) {
  const { data: a } = useAvisosQuery(undefined, { skip: sequencia < 3 });
  const [mudar, { isLoading }] = useMudarAvisosMutation();
  const { ligar } = useLigarPush(a);
  const [hora, setHora] = useState("19:00");
  const [jaPedido, setJaPedido] = useState(() => {
    try {
      return typeof window !== "undefined" && localStorage.getItem(CHAVE_PEDIDO) === "1";
    } catch {
      return false;
    }
  });

  if (sequencia < 3 || !a || a.lembrete.ligado || jaPedido) return null;
  const fechar = () => {
    try {
      localStorage.setItem(CHAVE_PEDIDO, "1");
    } catch {}
    setJaPedido(true);
  };

  return (
    <section aria-labelledby="titulo-lembrete" className="flex w-full flex-col gap-4 rounded-[24px_24px_24px_0] border border-pe-linha bg-pe-fundo p-5 text-left">
      <h2 id="titulo-lembrete" className="m-0 font-pe-titulo text-[20px] font-bold leading-[26px]">
        Quer um lembrete para não perder os dias seguidos?
      </h2>
      <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">Um aviso por dia, à hora que escolher, só se ainda não tiver praticado.</p>
      <div role="radiogroup" aria-label="Hora do lembrete" className="flex flex-wrap gap-2">
        {["19:00", "07:00", "12:30", "21:00"].map((h) => (
          <button
            key={h}
            type="button"
            role="radio"
            aria-checked={hora === h}
            onClick={() => setHora(h)}
            className={cnPe(
              "min-h-11 min-w-[76px] rounded-full px-4 text-[15px] font-semibold tabular-nums",
              hora === h ? "bg-pe-azul-marca text-pe-sobre-marca" : "border-[1.5px] border-pe-linha-forte bg-pe-fundo text-pe-tinta"
            )}
          >
            {h}
          </button>
        ))}
      </div>
      {iphoneSemApp() ? <p className="m-0 text-[14px] leading-5 text-pe-tinta-suave">No iPhone, o aviso só chega com a app instalada no ecrã principal. Sem ela, aparece em Notificações.</p> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Botao
          disabled={isLoading}
          onClick={async () => {
            await mudar({ lembrete: { ligado: true, hora } }).unwrap().catch(() => null);
            if (a.push.disponivel) await ligar().catch(() => false);
            fechar();
          }}
        >
          Ligar o lembrete
        </Botao>
        <Botao tipo="ligacao" tamanho="pequeno" onClick={fechar}>
          Agora não
        </Botao>
      </div>
    </section>
  );
}
