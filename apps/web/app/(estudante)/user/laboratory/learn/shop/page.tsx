"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, Crown, Heart, Zap } from "lucide-react";
import { Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { tempoAte } from "@/components/pe/laboratorio/Trilho";
import { cnPe } from "@/lib/pe";
import { useEstadoVidasQuery, useRecarregarVidasMutation } from "@/src/domains/student/laboratorio/api";
import { kz, usePlanosQuery } from "@/src/domains/student/subscricao/api";

const fmt = (n: number) => n.toLocaleString("pt-PT");

const GANHAR = [
  ["Lição concluída pela primeira vez", "10 pontos"],
  ["Lição repetida", "5 pontos e 1 vida"],
] as const;

export default function Loja() {
  const { data: vidas, isLoading } = useEstadoVidasQuery();
  const { data: planos } = usePlanosQuery();
  const premium = planos?.find((p) => p.plan_type === "PREMIUM");
  const [recarregar, { isLoading: aRecarregar }] = useRecarregarVidasMutation();
  const [mensagem, setMensagem] = useState<{ tipo: "certo" | "errado"; texto: string } | null>(null);

  const cheias = vidas ? vidas.current >= vidas.maximum : false;
  const tempo = vidas && !cheias ? tempoAte(vidas.next_heart_at) : null;

  const aoRecarregar = async () => {
    setMensagem(null);
    const r = await recarregar();
    if ("error" in r && r.error) {
      const c = (r.error as { data?: { error?: string; message?: string } }).data;
      setMensagem({
        tipo: "errado",
        texto:
          c?.error === "insufficient_points"
            ? `Precisa de ${vidas?.refill_cost_points ?? 50} pontos e tem ${fmt(vidas?.points ?? 0)}. Pratique uma lição já feita para ganhar mais.`
            : c?.error === "hearts_full"
              ? "Já tem as vidas todas."
              : c?.message ?? "Não foi possível recarregar agora. Tente outra vez.",
      });
      return;
    }
    setMensagem({ tipo: "certo", texto: `Vidas recarregadas. Gastou ${r.data!.points_spent} pontos.` });
  };

  return (
    <Pagina className="max-w-[960px]">
      <div className="flex flex-col gap-2">
        <Link href="/user/laboratory/learn" className="inline-flex min-h-11 items-center gap-1.5 self-start text-[15px] font-semibold underline-offset-[3px]">
          <ArrowLeft aria-hidden className="size-5" /> Laboratório de prática
        </Link>
        <div className="flex items-center justify-between gap-4">
          <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-[32px] md:leading-[38px] md:tracking-[-0.015em]">Loja</h1>
          {vidas ? (
            <span role="img" aria-label={`${fmt(vidas.points)} pontos`} className="inline-flex items-center gap-1.5 font-semibold tabular-nums">
              <Zap aria-hidden className="size-[22px] fill-pe-realce text-[#c79500]" />
              {fmt(vidas.points)}
            </span>
          ) : null}
        </div>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <section aria-labelledby="titulo-vidas" className="flex flex-col gap-3">
          <h2 id="titulo-vidas" className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">
            Vidas
          </h2>
          {isLoading || !vidas ? (
            <Osso className="h-[180px] rounded-pe-md" />
          ) : vidas.unlimited ? (
            <div className="flex items-center gap-4 rounded-pe-md border border-pe-linha p-5">
              <Heart aria-hidden className="size-8 shrink-0 fill-pe-vida text-pe-vida" />
              <p className="m-0">Tem vidas ilimitadas com o seu plano. Não precisa de recarregar.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-4 rounded-pe-md border border-pe-linha p-5">
              <div className="flex items-center gap-4">
                <div role="img" aria-label={`${vidas.current} de ${vidas.maximum} vidas`} className="flex shrink-0 gap-1">
                  {Array.from({ length: vidas.maximum }, (_, i) => (
                    <Heart key={i} aria-hidden className={cnPe("size-7", i < vidas.current ? "fill-pe-vida text-pe-vida" : "text-pe-linha-forte")} />
                  ))}
                </div>
                <div className="flex min-w-0 flex-col">
                  <span className="font-semibold leading-[22px]">
                    Tem {vidas.current} de {vidas.maximum} vidas
                  </span>
                  <span className="text-pe-legenda text-pe-tinta-suave">{cheias ? "Está tudo cheio." : tempo ? `A próxima volta daqui a ${tempo}.` : "As vidas voltam com o tempo."}</span>
                </div>
              </div>
              <Botao larguraTotal disabled={cheias || aRecarregar} onClick={() => void aoRecarregar()}>
                {aRecarregar ? "A recarregar…" : `Recarregar todas por ${vidas.refill_cost_points} pontos`}
              </Botao>
              {mensagem ? (
                <p role="status" className={cnPe("m-0 rounded-pe-md px-3 py-2 text-[15px]", mensagem.tipo === "certo" ? "bg-pe-certo-suave" : "bg-pe-errado-suave")}>
                  {mensagem.texto}
                </p>
              ) : null}
              {!cheias ? (
                <Link href="/user/laboratory/learn" className="self-start py-1.5 font-semibold underline-offset-[3px]">
                  Ou recupere uma vida a praticar uma lição já feita
                </Link>
              ) : null}
            </div>
          )}
        </section>

        <div className="flex flex-col gap-6">
          <section aria-labelledby="titulo-premium" className="pe-sobre-marca flex flex-col gap-3.5 rounded-pe-fala bg-pe-azul-marca p-6 text-pe-sobre-marca">
            <div className="flex items-center gap-2.5">
              <Crown aria-hidden className="size-6 text-pe-realce" />
              <h2 id="titulo-premium" className="m-0 font-pe-titulo text-[20px] font-bold leading-[26px]">
                Premium
              </h2>
            </div>
            <ul className="m-0 flex list-disc flex-col gap-1.5 pl-5 text-[15px] leading-[22px]">
              <li>Vidas e lições ilimitadas</li>
              {premium?.daily_speaking_minutes ? <li>{premium.daily_speaking_minutes} minutos de conversa com o tutor por dia</li> : null}
              {premium?.certificates ? <li>Certificados de conclusão</li> : null}
            </ul>
            <Botao asChild tipo="realce" tamanho="medio" larguraTotal className="whitespace-normal py-2 text-center">
              <Link href="/user/upgrade?plan=PREMIUM">{premium ? `Subscrever por ${kz(premium.monthly_price)} por mês` : "Ver os planos"}</Link>
            </Botao>
          </section>

          <section aria-labelledby="titulo-ganhar" className="flex flex-col gap-2">
            <h2 id="titulo-ganhar" className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">
              Como ganhar pontos
            </h2>
            <dl className="m-0 flex flex-col">
              {GANHAR.map(([o, q]) => (
                <div key={o} className="flex justify-between gap-3 border-b border-pe-linha py-2.5 text-[15px] leading-[22px]">
                  <dt>{o}</dt>
                  <dd className="m-0 font-semibold tabular-nums">{q}</dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      </div>
    </Pagina>
  );
}
