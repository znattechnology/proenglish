"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { skipToken } from "@reduxjs/toolkit/query/react";
import { CalendarClock, CheckCircle2, Gift, LockKeyhole, Smartphone, XCircle } from "lucide-react";
import { Aviso, BarraProgresso, Botao, Etiqueta, Osso } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import {
  codigoErro,
  dataPt,
  kz,
  mensagemErro,
  periodoDoPlano,
  precoPlano,
  telefoneLegivel,
  useCancelarPagamentoMutation,
  useCriarPagamentoMutation,
  useMinhaSubscricaoQuery,
  usePagamentoQuery,
  usePlanosQuery,
  useOrcamentoQuery,
  useAtivarSemPagamentoMutation,
  useIniciarTesteMutation,
  vantagens,
  type Orcamento,
  type Pagamento,
  type Periodo,
  type Plano,
  type TesteIniciado,
  type TipoPlano,
} from "@/src/domains/student/subscricao/api";
import { CabecalhoCheckout, ResumoCompra } from "./Partes";

/**
 * Checkout por Multicaixa Express. O estado vive no endereço
 * (?plan=PREMIUM&periodo=mensal&pagamento=<id>), por isso recarregar a página retoma o pagamento.
 */
export function Checkout() {
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const tipo = (params.get("plan") ?? "").toUpperCase() as TipoPlano | "";
  const periodoPedido: Periodo = params.get("periodo") === "anual" ? "anual" : "mensal";
  const pagamentoId = params.get("pagamento");
  const [teste, setTeste] = useState<TesteIniciado | null>(null);

  const { data: planos, isError: erroPlanos } = usePlanosQuery();
  const { data: sub } = useMinhaSubscricaoQuery();
  const plano = planos?.find((p) => p.plan_type === tipo && p.plan_type !== "FREE");
  // Um plano sem preço anual paga-se sempre ao mês.
  const periodo: Periodo = plano ? periodoDoPlano(plano, periodoPedido) : periodoPedido;
  const cod = useCodigo();
  // O servidor calcula tudo: preço, código, crédito dos dias já pagos e o que fica a pagar.
  const { data: orcamento, isError: erroOrcamento, refetch: refazerOrcamento } = useOrcamentoQuery(plano && !pagamentoId ? { plano: plano.plan_type, periodo, codigo: cod.codigo } : skipToken);

  const irPara = (mudancas: Record<string, string | null>) => {
    const novo = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(mudancas)) {
      if (v === null) novo.delete(k);
      else novo.set(k, v);
    }
    router.replace(`${caminho}?${novo.toString()}`, { scroll: false });
  };

  if (erroPlanos) {
    return (
      <>
        <CabecalhoCheckout passo={1} />
        <main className="mx-auto flex max-w-[640px] flex-col items-start gap-4 px-5 py-12">
          <h1 className="m-0 text-pe-titulo-m">Não conseguimos carregar os planos</h1>
          <Botao onClick={() => location.reload()}>Tentar outra vez</Botao>
        </main>
      </>
    );
  }
  if (!planos) return <EsqueletoCheckout />;

  if (!plano) {
    return (
      <EscolherPlano
        planos={planos}
        actual={sub?.plan.id}
        emTeste={!!sub?.em_teste}
        periodo={periodo}
        aoEscolher={(p, per) => irPara({ plan: p.plan_type, periodo: periodoDoPlano(p, per) })}
      />
    );
  }

  if (teste) return <TesteComecou teste={teste} plano={plano} />;

  if (pagamentoId) {
    return (
      <AcompanharPagamento
        id={pagamentoId}
        plano={plano}
        periodo={periodo}
        aoRecomecar={() => irPara({ pagamento: null })}
        aoNovoPagamento={(id) => irPara({ pagamento: id })}
      />
    );
  }


  return (
    <>
      <CabecalhoCheckout passo={2} />
      <main className="mx-auto flex max-w-[1080px] flex-col gap-8 px-5 pb-16 pt-6 md:flex-row md:items-start md:gap-10 md:px-6 md:pt-10">
        <section className="flex min-w-0 flex-col gap-6 md:flex-[3_1_460px]">
          <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-[34px] tracking-[-0.01em] md:text-[32px] md:leading-10">Pagamento</h1>
          {erroOrcamento ? (
            <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
              <p className="m-0">Não conseguimos calcular o preço.</p>
              <Botao tamanho="pequeno" onClick={() => refazerOrcamento()}>
                Tentar outra vez
              </Botao>
            </div>
          ) : !orcamento ? (
            <Osso className="h-[260px] rounded-pe-md" />
          ) : !orcamento.pode_comprar ? (
            <div className="flex flex-col items-start gap-4">
              <Aviso tipo="neutro">{orcamento.motivo_bloqueio ?? "Este plano não está disponível agora."}</Aviso>
              <Botao asChild tipo="secundario">
                <Link href="/user/subscription">Voltar à subscrição</Link>
              </Botao>
            </div>
          ) : (
            <>
              {orcamento.pode_experimentar && orcamento.dias_teste > 0 ? <OfertaTeste plano={plano} dias={orcamento.dias_teste} aoComecar={setTeste} focar={params.get("teste") === "1"} /> : null}
              {orcamento.operacao === "conversao_teste" && orcamento.teste_termina_em ? (
                <Aviso tipo="neutro">
                  Está a experimentar o {plano.name} até {dataPt(orcamento.teste_termina_em, { day: "numeric", month: "long" })}. Se pagar agora, o período pago só começa no fim do teste: não perde
                  nenhum dia.
                </Aviso>
              ) : null}
              <FormularioPagamento
              plano={plano}
              periodo={periodo}
              orcamento={orcamento}
              codigo={orcamento.codigo?.codigo ?? null}
              aoMudarPeriodo={(p) => irPara({ periodo: p })}
              aoCriado={(id) => irPara({ pagamento: id })}
              />
            </>
          )}
        </section>
        <ResumoComCodigo plano={plano} periodo={periodo} orcamento={orcamento} cod={cod} aoMudarPlano={() => irPara({ plan: null, pagamento: null, codigo: null })} className="md:sticky md:top-8 md:flex-[2_1_320px]" />
      </main>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Teste grátis: só para quem nunca experimentou nem pagou              */
/* ------------------------------------------------------------------ */
function OfertaTeste({ plano, dias, aoComecar, focar = false }: { plano: Plano; dias: number; aoComecar: (t: TesteIniciado) => void; focar?: boolean }) {
  const [iniciar, { isLoading }] = useIniciarTesteMutation();
  // Vindo de "Experimentar N dias grátis" (oferta num limite): vai direito ao número.
  const campo = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!focar || !campo.current) return;
    campo.current.scrollIntoView({ block: "center" });
    campo.current.focus({ preventScroll: true });
  }, [focar]);
  const [erro, setErro] = useState<{ campo?: boolean; texto: string } | null>(null);
  const [telefone, setTelefone] = useState(() => {
    try {
      return telefoneLegivel(sessionStorage.getItem("pe-telefone-mcx") ?? "");
    } catch {
      return "";
    }
  });
  const digitos = telefone.replace(/\D/g, "").replace(/^244/, "");

  const comecar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^9\d{8}$/.test(digitos)) {
      setErro({ campo: true, texto: "Escreva os 9 dígitos do número, a começar por 9. Por exemplo: 923 456 789." });
      return;
    }
    setErro(null);
    const r = await iniciar({ plano: plano.plan_type, telefone: digitos });
    if ("error" in r && r.error) {
      const codigo = codigoErro(r.error) ?? "";
      return setErro({ campo: codigo.startsWith("telefone"), texto: mensagemErro(r.error, "Não foi possível começar o teste. Tente outra vez.") });
    }
    try {
      sessionStorage.setItem("pe-telefone-mcx", digitos);
    } catch {
      /* sem armazenamento */
    }
    aoComecar(r.data!);
  };

  return (
    <form onSubmit={comecar} noValidate aria-labelledby="titulo-teste" className="flex flex-col gap-4 rounded-pe-md border-2 border-pe-certo bg-pe-certo-suave p-5">
      <div className="flex items-start gap-3">
        <span aria-hidden className="flex size-10 shrink-0 items-center justify-center rounded-[14px_14px_14px_0] bg-pe-fundo text-pe-certo">
          <Gift className="size-5" />
        </span>
        <div className="flex flex-col gap-1">
          <h2 id="titulo-teste" className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">
            Experimente o {plano.name} {dias} dias grátis
          </h2>
          <p className="m-0 text-[15px] leading-[22px]">
            Não paga nada agora. No fim do teste, pague com Multicaixa Express para continuar. Se não pagar, a conta volta ao Gratuito e o seu progresso fica guardado.
          </p>
        </div>
      </div>
      <div className="flex max-w-[480px] flex-col gap-1">
        <label htmlFor="telefone-teste" className="text-pe-rotulo">
          Número com Multicaixa Express
        </label>
        <div
          className={cnPe(
            "flex h-12 overflow-hidden rounded-pe-sm border-[1.5px] bg-pe-fundo focus-within:outline focus-within:outline-[3px] focus-within:outline-offset-2 focus-within:outline-pe-azul-vivo",
            erro?.campo ? "border-pe-errado" : "border-pe-linha-forte"
          )}
        >
          <span className="flex items-center border-r border-pe-linha bg-pe-fundo-suave px-3 font-semibold">+244</span>
          <input
            id="telefone-teste"
            ref={campo}
            type="tel"
            inputMode="numeric"
            autoComplete="tel-national"
            placeholder="923 456 789"
            value={telefone}
            onChange={(e) => setTelefone(telefoneLegivel(e.target.value))}
            aria-invalid={erro?.campo ? true : undefined}
            aria-describedby={erro?.campo ? "erro-teste" : "ajuda-teste"}
            className="min-w-0 flex-1 border-0 bg-pe-fundo px-3 text-[16px] text-pe-tinta outline-none"
          />
        </div>
        {erro?.campo ? (
          <p id="erro-teste" role="alert" className="m-0 text-pe-legenda font-semibold text-pe-errado">
            {erro.texto}
          </p>
        ) : (
          <p id="ajuda-teste" className="m-0 text-pe-legenda text-pe-tinta-suave">
            Cada número só dá direito a um teste grátis. Não cobramos nada agora; é o número que vai usar para pagar quando quiser continuar.
          </p>
        )}
      </div>
      {erro && !erro.campo ? <Aviso tipo="errado">{erro.texto}</Aviso> : null}
      <Botao type="submit" tipo="secundario" className="w-full md:w-auto md:self-start" disabled={isLoading}>
        {isLoading ? "A começar o teste…" : `Experimentar ${dias} dias grátis`}
      </Botao>
      <p className="m-0 text-pe-legenda text-pe-tinta-suave">Ou pague já abaixo, se preferir.</p>
    </form>
  );
}

function TesteComecou({ teste, plano }: { teste: TesteIniciado; plano: Plano }) {
  const fim = dataPt(teste.teste_termina_em, { day: "numeric", month: "long" });
  return (
    <>
      <CabecalhoCheckout passo={3} />
      <main className="mx-auto flex max-w-[640px] flex-col items-start gap-5 px-5 py-12">
        <span aria-hidden className="flex size-14 items-center justify-center rounded-[18px_18px_18px_0] bg-pe-certo-suave text-pe-certo">
          <CalendarClock className="size-7" />
        </span>
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-[34px] md:text-[32px] md:leading-10" role="status">
          O seu teste do {plano.name} começou
        </h1>
        <p className="m-0 text-[17px] leading-[26px]">
          Tem o {plano.name} grátis até {fim}. Dois dias antes do fim, avisamos para pagar com Multicaixa Express. Se não pagar, a conta volta ao Gratuito e o seu progresso fica guardado.
        </p>
        <div className="flex flex-wrap gap-3">
          <Botao asChild>
            <Link href="/user/dashboard">Começar a aprender</Link>
          </Botao>
          <Botao asChild tipo="secundario">
            <Link href="/user/subscription">Ver a subscrição</Link>
          </Botao>
        </div>
      </main>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Passo 1: escolher o plano                                            */
/* ------------------------------------------------------------------ */
function EscolherPlano({
  planos,
  actual,
  emTeste,
  periodo,
  aoEscolher,
}: {
  planos: Plano[];
  actual?: string;
  emTeste: boolean;
  periodo: Periodo;
  aoEscolher: (p: Plano, per: Periodo) => void;
}) {
  const [per, setPer] = useState<Periodo>(periodo);
  const pagos = planos.filter((p) => p.plan_type !== "FREE");
  const desconto = Math.max(...pagos.map((p) => p.yearly_discount_percentage || 0));
  return (
    <>
      <CabecalhoCheckout passo={1} />
      <main className="mx-auto flex max-w-[1080px] flex-col gap-6 px-5 pb-16 pt-6 md:px-6 md:pt-10">
        <div className="flex flex-col gap-2">
          <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-[34px] md:text-[32px] md:leading-10">Escolha o plano</h1>
          <p className="m-0 text-pe-tinta-suave">Paga em kwanzas com Multicaixa Express. Não há cobranças automáticas.</p>
        </div>
        <SeletorPeriodo valor={per} aoMudar={setPer} desconto={desconto} />
        <ul className="m-0 grid list-none gap-4 p-0 md:grid-cols-2">
          {pagos.map((p) => {
            const eActual = p.id === actual;
            // Sem preço anual mostra-se o preço mensal, nunca "por ano".
            const perPlano = periodoDoPlano(p, per);
            const rotulo = eActual && emTeste ? `Pagar o ${p.name}` : eActual || p.so_renovacao ? `Renovar o ${p.name}` : `Escolher ${p.name}`;
            return (
              <li key={p.id} className={cnPe("flex flex-col gap-4 rounded-pe-md border p-6", p.is_most_popular ? "border-2 border-pe-azul-marca" : "border-pe-linha")}>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="m-0 font-pe-titulo text-[22px] font-bold leading-7">{p.name}</h2>
                  {eActual ? <Etiqueta tipo="marca">O seu plano</Etiqueta> : p.is_most_popular ? <Etiqueta tipo="realce">O mais escolhido</Etiqueta> : null}
                </div>
                <p className="m-0">
                  <span className="font-pe-titulo text-[30px] font-bold tabular-nums">{kz(precoPlano(p, perPlano))}</span>{" "}
                  <span className="text-pe-tinta-suave">{perPlano === "anual" ? "por ano" : "por mês"}</span>
                </p>
                {per === "anual" && perPlano === "mensal" ? <p className="-mt-2 m-0 text-pe-legenda text-pe-tinta-suave">Este plano só tem pagamento mensal.</p> : null}
                {p.so_renovacao ? <p className="-mt-2 m-0 text-pe-legenda text-pe-tinta-suave">Já não está à venda, mas pode continuar com ele.</p> : null}
                <ul className="m-0 flex flex-col gap-1.5 pl-5 text-[15px] leading-[22px]">
                  {vantagens(p).map((v) => (
                    <li key={v}>{v}</li>
                  ))}
                </ul>
                {p.pode_experimentar && p.dias_teste ? (
                  <p className="m-0 inline-flex items-center gap-2 text-[15px] font-semibold text-pe-certo">
                    <Gift aria-hidden className="size-4 shrink-0" />
                    Pode experimentar {p.dias_teste} dias grátis antes de pagar
                  </p>
                ) : null}
                <Botao className="mt-auto" tipo={p.is_most_popular ? "principal" : "secundario"} onClick={() => aoEscolher(p, per)}>
                  {rotulo}
                </Botao>
              </li>
            );
          })}
        </ul>
        <Link href="/user/subscription" className="self-start font-semibold underline-offset-[3px]">
          Voltar à subscrição
        </Link>
      </main>
    </>
  );
}

function SeletorPeriodo({ valor, aoMudar, desconto }: { valor: Periodo; aoMudar: (p: Periodo) => void; desconto: number }) {
  const opcoes: [Periodo, string][] = [
    ["mensal", "Mensal"],
    ["anual", desconto ? `Anual, poupa ${Math.round(desconto)}%` : "Anual"],
  ];
  return (
    <div role="radiogroup" aria-label="Período" className="inline-flex w-fit rounded-pe-sm bg-pe-fundo-suave p-1">
      {opcoes.map(([v, nome]) => (
        <button
          key={v}
          type="button"
          role="radio"
          aria-checked={valor === v}
          onClick={() => aoMudar(v)}
          className={cnPe("min-h-11 rounded-[4px] px-4 text-[15px] font-semibold", valor === v ? "bg-pe-azul-marca text-pe-sobre-marca" : "text-pe-tinta hover:bg-pe-fundo-forte")}
        >
          {nome}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Código promocional: guardado no endereço para chegar ao pagamento    */
/* ------------------------------------------------------------------ */
type Codigo = ReturnType<typeof useCodigo>;

/** O código vive no endereço; o servidor diz no orçamento se é válido (erro_codigo) e quanto desconta. */
function useCodigo() {
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const codigo = params.get("codigo")?.toUpperCase() ?? null;
  const mudar = (c: string | null) => {
    const novo = new URLSearchParams(params.toString());
    if (c) novo.set("codigo", c);
    else novo.delete("codigo");
    router.replace(`${caminho}?${novo.toString()}`, { scroll: false });
  };
  return { codigo, aplicar: (c: string) => mudar(c), remover: () => mudar(null) };
}

function ResumoComCodigo({
  plano,
  periodo,
  orcamento,
  cod,
  aoMudarPlano,
  className,
}: {
  plano: Plano;
  periodo: Periodo;
  orcamento?: Orcamento;
  cod: Codigo;
  aoMudarPlano: () => void;
  className?: string;
}) {
  const [texto, setTexto] = useState("");
  const [aberto, setAberto] = useState(false);
  const erro = orcamento?.erro_codigo?.mensagem ?? null;
  const valido = orcamento?.codigo?.codigo ?? null;

  const aplicar = (e: React.FormEvent) => {
    e.preventDefault();
    const c = texto.trim().toUpperCase();
    if (!c) return;
    cod.aplicar(c);
    setAberto(false);
    setTexto("");
  };

  return (
    <div className={cnPe("flex min-w-0 flex-col gap-3", className)}>
      <ResumoCompra plano={plano} periodo={periodo} orcamento={orcamento} aoMudarPlano={aoMudarPlano} />
      {erro && cod.codigo ? (
        <div className="flex flex-col items-start gap-1">
          <p className="m-0 text-pe-legenda font-semibold text-pe-errado" role="alert">
            Código {cod.codigo}: {erro}
          </p>
          <button type="button" onClick={cod.remover} className="min-h-11 bg-transparent p-0 text-[15px] font-semibold text-pe-azul-marca underline underline-offset-[3px]">
            Tirar o código
          </button>
        </div>
      ) : aberto ? (
        <form onSubmit={aplicar} className="flex flex-col gap-1.5">
          <label htmlFor="codigo" className="text-pe-rotulo">
            Código promocional
          </label>
          <div className="flex gap-2">
            <input
              id="codigo"
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              autoComplete="off"
              autoCapitalize="characters"
              autoFocus
              className="h-12 min-w-0 flex-1 rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo px-3 uppercase text-pe-tinta"
            />
            <Botao type="submit" tipo="secundario" tamanho="medio" disabled={!texto.trim()}>
              Aplicar
            </Botao>
          </div>
        </form>
      ) : valido ? (
        <div className="flex flex-col items-start gap-1">
          {orcamento?.codigo?.descricao ? (
            <p className="m-0 text-pe-legenda text-pe-certo">
              <span className="font-semibold">Código {valido}:</span> {orcamento.codigo.descricao.replace(/\.$/, "")}
              {orcamento.codigo.continua ? " (continua nesta renovação)" : ""}.
            </p>
          ) : null}
          <button type="button" onClick={cod.remover} className="min-h-11 bg-transparent p-0 text-[15px] font-semibold text-pe-azul-marca underline underline-offset-[3px]">
            Remover o código {valido}
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => setAberto(true)} className="min-h-11 self-start bg-transparent p-0 text-[15px] font-semibold text-pe-azul-marca underline underline-offset-[3px]">
          Tenho um código promocional
        </button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Passo 2: número de telemóvel                                         */
/* ------------------------------------------------------------------ */
function FormularioPagamento({
  plano,
  periodo,
  orcamento,
  codigo,
  aoMudarPeriodo,
  aoCriado,
}: {
  plano: Plano;
  periodo: Periodo;
  orcamento: Orcamento;
  codigo: string | null;
  aoMudarPeriodo: (p: Periodo) => void;
  aoCriado: (id: string) => void;
}) {
  const [criar, { isLoading }] = useCriarPagamentoMutation();
  const [ativar, { isLoading: aAtivar }] = useAtivarSemPagamentoMutation();
  const [telefone, setTelefone] = useState(() => {
    try {
      return telefoneLegivel(sessionStorage.getItem("pe-telefone-mcx") ?? "");
    } catch {
      return "";
    }
  });
  const [erro, setErro] = useState<{ campo?: boolean; texto: string } | null>(null);
  const digitos = telefone.replace(/\D/g, "").replace(/^244/, "");
  const valido = /^9\d{8}$/.test(digitos);

  const total = orcamento.final_kz;

  // Nada a pagar (o crédito ou o código cobrem o preço): activa logo, sem Multicaixa.
  if (!orcamento.requer_pagamento) {
    return (
      <div className="flex flex-col gap-5">
        {plano.yearly_price ? <SeletorPeriodo valor={periodo} aoMudar={aoMudarPeriodo} desconto={plano.yearly_discount_percentage} /> : null}
        <Aviso tipo="certo">
          {orcamento.credito_kz
            ? `Os dias que ainda tinha no ${orcamento.credito_plano?.nome ?? "plano actual"} cobrem o preço. Não paga nada hoje.`
            : "O código cobre o preço. Não paga nada hoje."}
        </Aviso>
        {erro ? <Aviso tipo="errado">{erro.texto}</Aviso> : null}
        <Botao
          className="w-full md:w-auto md:min-w-[240px] md:self-start"
          disabled={aAtivar}
          onClick={async () => {
            setErro(null);
            const r = await ativar({ planId: plano.id, periodo, codigo });
            if ("error" in r && r.error) return setErro({ texto: mensagemErro(r.error, "Não foi possível activar o plano. Tente outra vez.") });
            aoCriado(r.data!.id);
          }}
        >
          {aAtivar ? "A activar…" : `Activar o ${plano.name}`}
        </Botao>
      </div>
    );
  }

  const pagar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valido) {
      setErro({ campo: true, texto: "Escreva os 9 dígitos do número, a começar por 9. Por exemplo: 923 456 789." });
      return;
    }
    setErro(null);
    const r = await criar({ planId: plano.id, periodo, telefone: digitos, codigo });
    if ("error" in r && r.error) {
      setErro({ campo: codigoErro(r.error) === "telefone_invalido", texto: mensagemErro(r.error, "Não foi possível enviar o pedido. Tente outra vez.") });
      return;
    }
    try {
      sessionStorage.setItem("pe-telefone-mcx", digitos);
    } catch {
      /* sem armazenamento: o utilizador volta a escrever o número */
    }
    aoCriado(r.data!.id);
  };

  return (
    <form onSubmit={pagar} noValidate className="flex flex-col gap-6">
      {plano.yearly_price ? <SeletorPeriodo valor={periodo} aoMudar={aoMudarPeriodo} desconto={plano.yearly_discount_percentage} /> : null}

      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-3">
          <span aria-hidden className="pe-sobre-marca flex size-10 shrink-0 items-center justify-center rounded-[14px_14px_14px_0] bg-pe-azul-marca text-pe-sobre-marca">
            <Smartphone className="size-5" />
          </span>
          <span className="flex flex-col">
            <span className="font-pe-titulo text-[18px] font-semibold leading-6">Multicaixa Express</span>
            <span className="text-pe-legenda text-pe-tinta-suave">Pagamento em kwanzas, confirmado no telemóvel</span>
          </span>
        </div>
        <div className="flex max-w-[480px] flex-col gap-1">
          <label htmlFor="telefone-mcx" className="text-pe-rotulo">
            Número com Multicaixa Express
          </label>
          <div
            className={cnPe(
              "flex h-12 overflow-hidden rounded-pe-sm border-[1.5px] focus-within:outline focus-within:outline-[3px] focus-within:outline-offset-2 focus-within:outline-pe-azul-vivo",
              erro?.campo ? "border-pe-errado" : "border-pe-linha-forte"
            )}
          >
            <span className="flex items-center border-r border-pe-linha bg-pe-fundo-suave px-3 font-semibold">+244</span>
            <input
              id="telefone-mcx"
              type="tel"
              inputMode="numeric"
              autoComplete="tel-national"
              placeholder="923 456 789"
              value={telefone}
              onChange={(e) => setTelefone(telefoneLegivel(e.target.value))}
              aria-invalid={erro?.campo ? true : undefined}
              aria-describedby={erro?.campo ? "erro-mcx" : "ajuda-mcx"}
              className="min-w-0 flex-1 border-0 bg-pe-fundo px-3 text-[16px] text-pe-tinta outline-none"
            />
          </div>
          {erro?.campo ? (
            <p id="erro-mcx" className="m-0 text-pe-legenda font-semibold text-pe-errado">
              {erro.texto}
            </p>
          ) : (
            <p id="ajuda-mcx" className="m-0 text-pe-legenda text-pe-tinta-suave">
              Vai receber um pedido de pagamento na app Multicaixa Express. Tem 5 minutos para o confirmar.
            </p>
          )}
        </div>
        <p className="m-0 inline-flex items-start gap-2 text-pe-legenda text-pe-tinta-suave">
          <LockKeyhole aria-hidden className="mt-0.5 size-4 shrink-0" />
          Confirma o pagamento na app Multicaixa Express do seu telemóvel. Não há cobranças automáticas.
        </p>
      </div>

      {erro && !erro.campo ? <Aviso tipo="errado">{erro.texto}</Aviso> : null}

      <Botao type="submit" className="w-full md:w-auto md:min-w-[240px] md:self-start" disabled={isLoading}>
        {isLoading ? "A enviar o pedido…" : `Pagar ${kz(total)}`}
      </Botao>
    </form>
  );
}

/* ------------------------------------------------------------------ */
/* Aguardar, concluído ou falhou                                       */
/* ------------------------------------------------------------------ */
function AcompanharPagamento({
  id,
  plano,
  periodo,
  aoRecomecar,
  aoNovoPagamento,
}: {
  id: string;
  plano: Plano;
  periodo: Periodo;
  aoRecomecar: () => void;
  aoNovoPagamento: (id: string) => void;
}) {
  // Pergunta a cada 2 s enquanto o pagamento está por confirmar.
  const [aPerguntar, setAPerguntar] = useState(true);
  const { data: p, isError } = usePagamentoQuery(id, { pollingInterval: aPerguntar ? 2000 : 0, skipPollingIfUnfocused: false });
  if (p && p.estado !== "pendente" && aPerguntar) setAPerguntar(false);
  if (p && p.estado === "pendente" && !aPerguntar) setAPerguntar(true);

  if (isError) {
    return (
      <>
        <CabecalhoCheckout passo={2} />
        <main className="mx-auto flex max-w-[640px] flex-col items-start gap-4 px-5 py-12">
          <h1 className="m-0 text-pe-titulo-m">Não encontrámos este pagamento</h1>
          <p className="m-0 text-pe-tinta-suave">Se pagou, o plano aparece na sua subscrição em poucos minutos.</p>
          <div className="flex flex-wrap gap-3">
            <Botao onClick={aoRecomecar}>Começar de novo</Botao>
            <Botao asChild tipo="secundario">
              <Link href="/user/subscription">Ver a subscrição</Link>
            </Botao>
          </div>
        </main>
      </>
    );
  }
  if (!p) return <EsqueletoCheckout />;
  if (p.estado === "pago") return <Concluido p={p} plano={plano} />;

  return (
    <>
      <CabecalhoCheckout passo={2} />
      <main className="mx-auto flex max-w-[1080px] flex-col gap-8 px-5 pb-16 pt-6 md:flex-row md:items-start md:gap-10 md:px-6 md:pt-10">
        <section className="flex min-w-0 flex-col gap-6 md:flex-[3_1_460px]">
          <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-[34px] tracking-[-0.01em] md:text-[32px] md:leading-10">Pagamento</h1>
          {p.estado === "pendente" ? (
            <Aguardar p={p} plano={plano} periodo={periodo} aoOutroNumero={aoRecomecar} aoNovoPagamento={aoNovoPagamento} />
          ) : (
            <Falhou p={p} plano={plano} periodo={periodo} aoOutroNumero={aoRecomecar} aoNovoPagamento={aoNovoPagamento} />
          )}
        </section>
        <div className="flex min-w-0 flex-col md:sticky md:top-8 md:flex-[2_1_320px]">
          <ResumoCompra
            plano={plano}
            periodo={periodo}
            desconto={p.desconto_kz}
            codigo={p.codigo_promocional}
            credito={p.credito_kz ? { kz: p.credito_kz, plano: p.credito_plano?.nome, dias: p.credito_dias_restantes } : null}
          />
        </div>
      </main>
    </>
  );
}

function useReenviar(p: Pagamento, aoNovoPagamento: (id: string) => void) {
  const [criar, { isLoading }] = useCriarPagamentoMutation();
  const [erro, setErro] = useState<string | null>(null);
  const reenviar = async (planoId: string, periodo: Periodo) => {
    setErro(null);
    let telefone = "";
    try {
      telefone = sessionStorage.getItem("pe-telefone-mcx") ?? "";
    } catch {
      /* sem armazenamento */
    }
    if (!telefone) {
      setErro("Escreva o número outra vez para enviar um novo pedido.");
      return;
    }
    const r = await criar({ planId: planoId, periodo, telefone, codigo: p.codigo_promocional });
    if ("error" in r && r.error) {
      setErro(mensagemErro(r.error, "Não foi possível enviar o pedido. Tente outra vez."));
      return;
    }
    aoNovoPagamento(r.data!.id);
  };
  return { reenviar, aEnviar: isLoading, erro };
}

function useRelogio(expira: string | null) {
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const total = 5 * 60_000;
  const falta = expira ? Math.max(0, new Date(expira).getTime() - agora) : total;
  return { falta, pct: (100 * falta) / total, texto: `${Math.floor(falta / 60_000)}:${String(Math.floor((falta % 60_000) / 1000)).padStart(2, "0")}` };
}

function Aguardar({
  p,
  plano,
  periodo,
  aoOutroNumero,
  aoNovoPagamento,
}: {
  p: Pagamento;
  plano: Plano;
  periodo: Periodo;
  aoOutroNumero: () => void;
  aoNovoPagamento: (id: string) => void;
}) {
  const relogio = useRelogio(p.expira_em);
  const { reenviar, aEnviar, erro } = useReenviar(p, aoNovoPagamento);
  const [cancelar] = useCancelarPagamentoMutation();
  const numero = useMemo(() => {
    try {
      const d = sessionStorage.getItem("pe-telefone-mcx");
      return d ? telefoneLegivel(d) : p.telefone_mascarado;
    } catch {
      return p.telefone_mascarado;
    }
  }, [p.telefone_mascarado]);

  return (
    <>
      <div role="status" aria-live="polite" className="pe-sobre-marca flex items-center gap-3.5 rounded-pe-fala bg-pe-azul-marca px-5 py-4 text-pe-sobre-marca">
        <span aria-hidden className="flex size-11 shrink-0 items-center justify-center rounded-[16px_16px_16px_0] bg-pe-realce text-pe-tinta motion-safe:animate-pulse">
          <Smartphone className="size-6" />
        </span>
        <span className="flex flex-col">
          <span className="font-pe-titulo text-[20px] font-bold leading-[26px]">Confirme no seu telemóvel</span>
          <span className="text-[15px] leading-[22px]">Enviámos um pedido de {kz(p.total_kz)}.</span>
        </span>
      </div>
      <ol className="m-0 flex list-none flex-col gap-3 p-0">
        {[
          <>
            Abra a app Multicaixa Express no telemóvel <span className="whitespace-nowrap">{numero}</span>.
          </>,
          <>Aceite o pedido de {kz(p.total_kz)} para ProEnglish.</>,
          <>Esta página avança sozinha quando o pagamento for confirmado.</>,
        ].map((t, i) => (
          <li key={i} className="flex items-start gap-3">
            <span aria-hidden className="pe-sobre-marca flex size-7 shrink-0 items-center justify-center rounded-[10px_10px_10px_0] bg-pe-azul-marca font-pe-titulo text-[14px] font-bold text-pe-sobre-marca">
              {i + 1}
            </span>
            <span>{t}</span>
          </li>
        ))}
      </ol>
      <div role="timer" aria-live="off" className="flex max-w-[480px] flex-col gap-2">
        <div className="flex justify-between text-[15px]">
          <span>Tempo para confirmar</span>
          <span className="font-semibold tabular-nums">{relogio.texto}</span>
        </div>
        <BarraProgresso valor={relogio.pct} rotulo="Tempo restante" />
      </div>
      {p.simulado ? (
        <Aviso tipo="info">
          Pagamento de teste: ainda não há ligação real ao Multicaixa Express. O pedido confirma-se sozinho em poucos segundos. Números terminados em 0000 são recusados e em 1111 expiram.
        </Aviso>
      ) : null}
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Botao tipo="secundario" disabled={aEnviar} onClick={() => void reenviar(plano.id, periodo)}>
          {aEnviar ? "A enviar…" : "Enviar o pedido outra vez"}
        </Botao>
        <Botao
          tipo="ligacao"
          onClick={async () => {
            await cancelar(p.id);
            aoOutroNumero();
          }}
        >
          Usar outro número
        </Botao>
      </div>
    </>
  );
}

function Falhou({
  p,
  plano,
  periodo,
  aoOutroNumero,
  aoNovoPagamento,
}: {
  p: Pagamento;
  plano: Plano;
  periodo: Periodo;
  aoOutroNumero: () => void;
  aoNovoPagamento: (id: string) => void;
}) {
  const { reenviar, aEnviar, erro } = useReenviar(p, aoNovoPagamento);
  const titulo = { recusado: "O pagamento foi recusado", expirado: "O pedido expirou", cancelado: "O pedido foi cancelado", pendente: "", pago: "" }[p.estado];
  const texto =
    p.estado === "recusado"
      ? `O pedido foi recusado no telemóvel ${p.telefone_mascarado}. Não foi cobrado nada.`
      : p.estado === "expirado"
        ? "Passaram 5 minutos sem confirmação. Não foi cobrado nada."
        : "Não foi cobrado nada.";
  return (
    <>
      <div role="alert" className="flex items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
        <XCircle aria-hidden className="mt-0.5 size-7 shrink-0 text-pe-errado" />
        <div className="flex flex-col gap-1">
          <span className="font-pe-titulo text-[20px] font-bold leading-[26px]">{titulo}</span>
          <span>{texto}</span>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <h2 className="m-0 font-pe-titulo text-[18px] font-semibold leading-6">O que pode fazer</h2>
        <ul className="m-0 flex flex-col gap-1.5 pl-5">
          <li>Confirme que tem saldo e que o número está associado ao Multicaixa Express.</li>
          <li>Envie um novo pedido e aceite-o na app em 5 minutos.</li>
        </ul>
      </div>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Botao disabled={aEnviar} onClick={() => void reenviar(plano.id, periodo)}>
          {aEnviar ? "A enviar…" : "Enviar novo pedido"}
        </Botao>
        <Botao tipo="ligacao" onClick={aoOutroNumero}>
          Usar outro número
        </Botao>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Passo 3: concluído                                                   */
/* ------------------------------------------------------------------ */
function Concluido({ p, plano }: { p: Pagamento; plano: Plano }) {
  const a = p.ativacao?.plano;
  const preco = precoPlano(plano, p.periodo ?? "mensal");
  return (
    <>
      <CabecalhoCheckout passo={3} />
      <main className="mx-auto flex max-w-[640px] flex-col gap-7 px-5 pb-16 pt-10 md:pt-16">
        <div className="flex flex-col gap-2">
          <Etiqueta tipo="certo">
            <CheckCircle2 aria-hidden className="size-[18px]" /> {p.metodo_codigo === "sem_pagamento" ? "Plano activado" : "Pagamento confirmado"}
          </Etiqueta>
          <h1 className="m-0 font-pe-titulo text-[32px] font-bold leading-[38px] tracking-[-0.015em] md:text-pe-titulo-l">Já tem o {a?.nome ?? plano.name}</h1>
          <p className="m-0 text-pe-tinta-suave">O recibo fica em Pagamentos e recibos, na sua subscrição.</p>
        </div>
        <section className="pe-sobre-marca flex flex-col gap-3 rounded-pe-fala bg-pe-azul-marca p-6 text-pe-sobre-marca">
          <h2 className="m-0 font-pe-titulo text-[19px] font-semibold leading-[26px]">O que mudou</h2>
          <ul className="m-0 flex flex-col gap-1.5 pl-5 text-[15px] leading-[22px]">
            {vantagens(plano).map((v) => (
              <li key={v}>{v}</li>
            ))}
          </ul>
        </section>
        <dl className="m-0 flex flex-col">
          {(
            [
              ["Pago hoje", kz(p.total_kz)],
              ...(p.credito_kz ? ([["Crédito dos dias por usar", `menos ${kz(p.credito_kz)}`]] as [string, string][]) : []),
              ...(p.dias_extra ? ([["Dias a mais pelo crédito", String(p.dias_extra)]] as [string, string][]) : []),
              ["Válido até", dataPt(a?.expira_em)],
              [p.periodo === "anual" ? "Para renovar, por ano" : "Para renovar, por mês", kz(preco)],
            ] as [string, string][]
          ).map(([dt, dd]) => (
            <div key={dt} className="flex justify-between gap-4 border-b border-pe-linha py-2.5">
              <dt className="text-pe-tinta-suave">{dt}</dt>
              <dd className="m-0 font-semibold tabular-nums">{dd}</dd>
            </div>
          ))}
          {p.numero_recibo ? (
            <div className="flex justify-between gap-4 py-2.5">
              <dt className="text-pe-tinta-suave">Recibo</dt>
              <dd className="m-0">
                <Link href={`/user/billing?recibo=${p.numero_recibo}`} className="font-semibold underline-offset-[3px]">
                  Ver o recibo {p.numero_recibo}
                </Link>
              </dd>
            </div>
          ) : null}
        </dl>
        <Botao asChild className="md:self-start md:min-w-[240px]">
          <Link href="/user/dashboard">Continuar a aprender</Link>
        </Botao>
      </main>
    </>
  );
}

function EsqueletoCheckout() {
  return (
    <div aria-busy="true" aria-label="A carregar" className="flex flex-col">
      <div className="h-[69px] border-b border-pe-linha" />
      <div className="mx-auto flex w-full max-w-[1080px] flex-col gap-6 px-5 py-10 md:flex-row md:px-6">
        <div className="flex flex-1 flex-col gap-5">
          <Osso className="h-10 w-48" />
          <Osso className="h-12 max-w-[480px]" />
          <Osso className="h-[52px] w-60" />
        </div>
        <Osso className="h-[320px] rounded-pe-fala md:w-[380px]" />
      </div>
    </div>
  );
}
