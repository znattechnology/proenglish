"use client";

import Link from "next/link";
import { useState } from "react";
import { BellOff } from "lucide-react";
import { Aviso, Botao, Interruptor, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { LinhaPagamento, TabelaPlanos } from "@/components/pe/subscricao/Partes";
import {
  dataPt,
  kz,
  mensagemErro,
  useHistoricoQuery,
  useLembretesMutation,
  useMinhaSubscricaoQuery,
  usePlanosQuery,
  vantagens,
  type MinhaSubscricao,
} from "@/src/domains/student/subscricao/api";

export default function PaginaSubscricao() {
  const { data: sub, isLoading, isError, refetch } = useMinhaSubscricaoQuery();
  const { data: planos } = usePlanosQuery();
  const { data: historico } = useHistoricoQuery();

  const pagos = (historico?.payment_history ?? []).filter((p) => (p.status ?? "pago") === "pago");

  return (
    <Pagina>
      <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Subscrição</h1>

      {isError ? (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
          <p className="m-0">Não conseguimos carregar a sua subscrição.</p>
          <Botao tamanho="pequeno" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : isLoading || !sub ? (
        <div aria-busy="true" aria-label="A carregar" className="grid gap-5 lg:grid-cols-[3fr_2fr]">
          <Osso className="h-[280px] rounded-pe-fala" />
          <Osso className="h-[280px] rounded-pe-md" />
        </div>
      ) : (
        <div className="grid items-start gap-5 lg:grid-cols-[3fr_2fr] lg:gap-8">
          <OSeuPlano sub={sub} />
          <HojeAindaTem sub={sub} />
        </div>
      )}

      <section aria-labelledby="titulo-planos" id="planos" className="flex flex-col gap-3 pt-4">
        <h2 id="titulo-planos" className="m-0 font-pe-titulo text-pe-titulo-s">
          Comparar planos
        </h2>
        {planos ? <TabelaPlanos planos={planos} actual={sub?.plan.id} /> : <Osso className="h-[300px] rounded-pe-md" />}
      </section>

      <section aria-labelledby="titulo-pagamentos" className="flex max-w-[760px] flex-col gap-2 pt-4">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id="titulo-pagamentos" className="m-0 font-pe-titulo text-pe-titulo-s">
            Pagamentos
          </h2>
          {pagos.length ? (
            <Link href="/user/billing" className="text-[15px] font-semibold underline-offset-[3px]">
              Ver todos e os recibos
            </Link>
          ) : null}
        </div>
        {!historico ? (
          <Osso className="h-[120px] rounded-pe-md" />
        ) : pagos.length ? (
          <div className="flex flex-col">
            {pagos.slice(0, 3).map((p) => (
              <LinhaPagamento key={p.id} p={p} href={p.receipt_number ? `/user/billing?recibo=${p.receipt_number}` : undefined} />
            ))}
          </div>
        ) : (
          <p className="m-0 text-pe-tinta-suave">Ainda não fez pagamentos. Quando fizer, os recibos ficam aqui.</p>
        )}
      </section>
    </Pagina>
  );
}

function OSeuPlano({ sub }: { sub: MinhaSubscricao }) {
  const [desligar, setDesligar] = useState(false);
  const [lembretes, { isLoading }] = useLembretesMutation();
  const [erro, setErro] = useState<string | null>(null);
  const gratuito = sub.plan.plan_type === "FREE";
  const emTeste = !!sub.em_teste;
  // Datas e regras vêm do servidor (a mesma regra que ele aplica ao aceitar a renovação).
  const [agora] = useState(() => Date.now());
  const terminaEm = sub.termina_em ?? sub.expires_at;
  const activo = !gratuito && !!terminaEm && new Date(terminaEm).getTime() > agora;
  const msFalta = terminaEm ? new Date(terminaEm).getTime() - agora : 0;
  const dias = Math.max(0, Math.ceil(msFalta / 86_400_000));
  const podeRenovar = !gratuito && (sub.pode_renovar ?? !activo);
  const fim = dataPt(terminaEm);
  const anual = sub.periodo === "anual";
  const preco = sub.valor_periodo_kz ?? Number(anual ? sub.plan.yearly_price : sub.plan.monthly_price);

  const mudarLembretes = async (v: boolean) => {
    setErro(null);
    const r = await lembretes(v);
    if ("error" in r && r.error) setErro(mensagemErro(r.error, "Não foi possível guardar. Tente outra vez."));
    else setDesligar(false);
  };

  return (
    <section aria-labelledby="titulo-plano" className="pe-sobre-marca flex flex-col gap-4 rounded-pe-fala bg-pe-azul-marca p-6 text-pe-sobre-marca md:p-8">
      <div className="flex flex-col gap-1">
        <span className="text-[15px] font-semibold">O seu plano</span>
        <h2 id="titulo-plano" className="m-0 font-pe-titulo text-[32px] font-bold leading-[38px] tracking-[-0.015em] md:text-[40px] md:leading-[46px]">
          {sub.plan.name}
        </h2>
        <p className="m-0 text-[16px] leading-6">
          {emTeste
            ? `Em teste até ${dataPt(sub.teste_termina_em ?? terminaEm, { day: "numeric", month: "short" })}. Não pagou nada. Para continuar depois disso, pague com Multicaixa Express; se não pagar, volta ao Gratuito e fica com o progresso.`
            : gratuito
            ? "Grátis, sem prazo. Pode passar para um plano pago quando quiser."
            : !activo
              ? `Terminou a ${fim}. Renove para voltar a ter o ${sub.plan.name}.`
              : sub.termina_hoje
                ? `${kz(preco)} por ${anual ? "ano" : "mês"}. Termina hoje, às ${new Date(terminaEm!).toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" })}.`
                : `${kz(preco)} por ${anual ? "ano" : "mês"}. Válido até ${fim}${podeRenovar ? ` (faltam ${dias} ${dias === 1 ? "dia" : "dias"})` : ""}.`}
        </p>
      </div>
      <ul className="m-0 flex flex-col gap-1.5 pl-5 text-[15px] leading-[22px]">
        {vantagens(sub.plan).map((v) => (
          <li key={v}>{v}</li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-3 pt-1">
        {emTeste ? (
          <Botao asChild tipo="realce">
            <Link href={`/user/upgrade?plan=${sub.plan.plan_type}`}>Pagar agora</Link>
          </Botao>
        ) : gratuito ? (
          <>
            <Botao asChild tipo="realce">
              {/* O teste é do plano que o tem (plano_teste), com os dias desse plano */}
              <Link href={`/user/upgrade?plan=${sub.pode_experimentar && sub.dias_teste && sub.plano_teste ? sub.plano_teste : "PREMIUM"}`}>
                {sub.pode_experimentar && sub.dias_teste && sub.plano_teste ? `Experimentar ${sub.dias_teste} dias grátis` : "Passar para Premium"}
              </Link>
            </Botao>
            <Link href="/user/upgrade?plan=PREMIUM_PLUS" className="font-semibold text-pe-sobre-marca underline underline-offset-[3px] hover:text-pe-realce">
              Ver o Premium Plus
            </Link>
          </>
        ) : (
          <>
            {podeRenovar ? (
              <Botao asChild tipo="realce">
                <Link href={`/user/upgrade?plan=${sub.plan.plan_type}`}>Renovar o {sub.plan.name}</Link>
              </Botao>
            ) : null}
            {sub.plan.plan_type === "PREMIUM" ? (
              <Link href="/user/upgrade?plan=PREMIUM_PLUS" className="font-semibold text-pe-sobre-marca underline underline-offset-[3px] hover:text-pe-realce">
                Passar para Premium Plus
              </Link>
            ) : null}
          </>
        )}
      </div>
      {emTeste ? <p className="m-0 text-pe-legenda">Se pagar agora, o período pago começa no fim do teste: não perde nenhum dia.</p> : null}
      {!gratuito && !emTeste && !podeRenovar && sub.renovavel_a_partir_de ? (
        <p className="m-0 text-pe-legenda">Pode renovar a partir de {dataPt(sub.renovavel_a_partir_de, { day: "numeric", month: "long" })}.</p>
      ) : null}
      {!gratuito && !emTeste && activo && sub.plan.plan_type === "PREMIUM" ? (
        <p className="m-0 text-pe-legenda">Se passar para o Premium Plus, os dias que ainda tem passam a desconto.</p>
      ) : null}

      {!gratuito && !emTeste ? (
        <div className="mt-1 rounded-pe-md bg-pe-fundo p-4 text-pe-tinta">
          <Interruptor
            rotulo="Lembretes de renovação"
            descricao={sub.lembretes_renovacao ? "Avisamos cerca de 3 dias antes e nas últimas 24 horas." : "Não vai receber avisos antes de terminar."}
            ligado={sub.lembretes_renovacao}
            disabled={isLoading}
            aoMudar={(v) => (v ? void mudarLembretes(true) : setDesligar(true))}
          />
          <p className="m-0 pt-3 text-pe-legenda text-pe-tinta-suave">Não há cobranças automáticas. Se não renovar, passa para o Gratuito e fica com o progresso.</p>
          {erro ? (
            <Aviso tipo="errado" className="mt-3">
              {erro}
            </Aviso>
          ) : null}
        </div>
      ) : null}

      <Dialogo
        aberto={desligar}
        aoMudar={setDesligar}
        titulo="Desligar os lembretes?"
        topo={
          <span aria-hidden className="flex size-14 items-center justify-center rounded-[18px_18px_18px_0] bg-pe-fundo-forte text-pe-tinta">
            <BellOff className="size-7" />
          </span>
        }
        descricao={`O ${sub.plan.name} continua até ${fim}, mas não o avisamos antes de terminar. Se não renovar, passa para o Gratuito e fica com o progresso, os pontos e os certificados.`}
      >
        <div className="flex flex-col gap-3">
          <Botao larguraTotal onClick={() => setDesligar(false)}>
            Manter os lembretes
          </Botao>
          <Botao larguraTotal tipo="perigo" disabled={isLoading} onClick={() => void mudarLembretes(false)}>
            {isLoading ? "A guardar…" : "Desligar lembretes"}
          </Botao>
        </div>
      </Dialogo>
    </section>
  );
}

function HojeAindaTem({ sub }: { sub: MinhaSubscricao }) {
  const u = sub.daily_usage;
  const linhas: [string, string][] = [
    [
      "Conversa com o tutor",
      u?.speaking_limit == null ? "Sem limite" : u.speaking_limit > 0 ? `${Math.max(0, u.speaking_limit - u.speaking_minutes_used)} de ${u.speaking_limit} min` : "Não incluída no plano",
    ],
    ["Lições", u?.lessons_limit ? `${Math.max(0, u.lessons_limit - u.lessons_used)} de ${u.lessons_limit}` : "Ilimitadas"],
  ];
  return (
    <section aria-labelledby="titulo-hoje" className="flex flex-col gap-3 rounded-pe-md border border-pe-linha p-6">
      <h2 id="titulo-hoje" className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">
        Hoje ainda tem
      </h2>
      <dl className="m-0 flex flex-col">
        {linhas.map(([dt, dd]) => (
          <div key={dt} className="flex justify-between gap-3 border-b border-pe-linha py-2.5 text-[15px] leading-[22px] last:border-0">
            <dt className="text-pe-tinta-suave">{dt}</dt>
            <dd className="m-0 font-semibold tabular-nums">{dd}</dd>
          </div>
        ))}
      </dl>
      <p className="m-0 text-pe-legenda text-pe-tinta-suave">Os limites diários recomeçam todos os dias.</p>
    </section>
  );
}
