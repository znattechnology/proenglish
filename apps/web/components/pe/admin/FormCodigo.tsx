"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft } from "lucide-react";
import { Aviso, Botao, Campo, Escolha } from "@/components/pe";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { cnPe } from "@/lib/pe";
import { kz, mensagemErro } from "@/src/domains/student/subscricao/api";
import {
  useActivarCodigoMutation,
  useCriarCodigoMutation,
  useDesligarCodigoMutation,
  useMudarCodigoMutation,
  usePlanosQuery,
  type Codigo,
  type NovoCodigo,
  type Utilizacao,
} from "@/src/domains/admin/administracao/negocio";
import type { TipoPlano } from "@/src/domains/admin/administracao/api";

const radio = "flex min-h-11 cursor-pointer items-center rounded-pe-sm px-4 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pe-azul-vivo";

function Escolhas<T extends string>({ legenda, nome, valor, aoMudar, opcoes, disabled }: { legenda: string; nome: string; valor: T; aoMudar: (v: T) => void; opcoes: { v: T; nome: string }[]; disabled?: boolean }) {
  return (
    <fieldset className="m-0 border-0 p-0" disabled={disabled}>
      <legend className="mb-1.5 p-0 text-pe-rotulo">{legenda}</legend>
      <div className="flex flex-wrap gap-2">
        {opcoes.map((o) => (
          <label key={o.v} className={cnPe(radio, valor === o.v ? "bg-pe-azul-marca text-pe-sobre-marca" : "border-[1.5px] border-pe-linha-forte", disabled && "cursor-not-allowed opacity-60")}>
            <input type="radio" name={nome} checked={valor === o.v} onChange={() => aoMudar(o.v)} className="sr-only" />
            {o.nome}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** Criar ou editar um código promocional. Depois de usado, só mudam o máximo, a data e o estado. */
export function FormCodigo({ inicial }: { inicial?: Codigo & { utilizacoes?: Utilizacao[] } }) {
  const router = useRouter();
  const { data: planos } = usePlanosQuery();
  const [criar, { isLoading: aCriar }] = useCriarCodigoMutation();
  const [mudar, { isLoading: aMudar }] = useMudarCodigoMutation();
  const [activar] = useActivarCodigoMutation();
  const [desligar] = useDesligarCodigoMutation();
  const usado = inicial?.bloqueado ?? !!inicial?.usos;
  const [v, setV] = useState({
    codigo: inicial?.codigo ?? "",
    tipo: inicial?.desconto.tipo ?? ("percentagem" as "percentagem" | "valor"),
    valor: inicial ? String(inicial.desconto.valor) : "",
    planos: (inicial?.aplica.planos ?? []) as TipoPlano[],
    periodo: inicial?.aplica.periodo ?? ("todos" as "todos" | "mensal" | "anual"),
    duracao: inicial?.duracao.tipo ?? ("primeiro" as "primeiro" | "meses" | "sempre"),
    meses: String(inicial?.duracao.meses ?? 3),
    max: inicial?.max_usos == null ? "" : String(inicial.max_usos),
    termina: inicial?.termina ?? "",
    primeira: inicial?.so_primeira_compra ?? false,
  });
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const muda = <K extends keyof typeof v>(k: K, x: (typeof v)[K]) => setV((a) => ({ ...a, [k]: x }));

  // Exemplo calculado no momento, com o preço anual do Premium (ou do plano escolhido).
  const periodo = v.duracao === "meses" ? "mensal" : v.periodo; // "vários meses" só se aplica a pagamentos mensais
  const plano = planos?.find((p) => p.tipo === (v.planos[0] ?? "PREMIUM"));
  const base = plano ? (periodo === "mensal" || !plano.preco_anual_kz ? plano.preco_mensal_kz : plano.preco_anual_kz) : 0;
  const valor = Number(v.valor.replace(",", ".")) || 0;
  const final = Math.max(0, v.tipo === "percentagem" ? Math.round(base * (1 - valor / 100)) : base - valor);
  const exemplo = plano && valor ? `Exemplo: o ${plano.nome} ${periodo === "mensal" || !plano.preco_anual_kz ? "mensal" : "anual"} passa de ${kz(base)} para ${kz(final)} ${v.duracao === "primeiro" ? "no 1.º pagamento" : v.duracao === "meses" ? `nos primeiros ${v.meses} pagamentos` : "em todos os pagamentos"}.` : null;

  async function guardar(activo: boolean) {
    setGeral(null);
    const er: Record<string, string> = {};
    if (!/^[A-Z0-9]{3,20}$/.test(v.codigo)) er.codigo = "Use 3 a 20 letras maiúsculas e números, sem espaços.";
    if (!valor || valor <= 0) er.valor = "Escreva o desconto.";
    const meses = Number(v.meses);
    if (v.duracao === "meses" && !(meses >= 2 && meses <= 24)) er.meses = "Entre 2 e 24 meses.";
    else if (v.tipo === "percentagem" && valor > 100) er.valor = "Uma percentagem vai até 100.";
    setErros(er);
    if (Object.keys(er).length) return;
    const corpo: NovoCodigo = {
      codigo: v.codigo,
      desconto: { tipo: v.tipo, valor },
      aplica: { planos: v.planos, periodo },
      duracao: { tipo: v.duracao, meses: v.duracao === "meses" ? meses : null },
      so_primeira_compra: v.primeira,
      max_usos: v.max.trim() ? Number(v.max) : null,
      termina: v.termina || null,
    };
    try {
      if (inicial) {
        await mudar({ id: inicial.id, ...(usado ? { max_usos: corpo.max_usos, termina: corpo.termina } : corpo) }).unwrap();
        if (activo && inicial.estado === "rascunho") await activar(inicial.id).unwrap();
      } else {
        await criar({ ...corpo, estado: activo ? "activo" : "rascunho" }).unwrap();
      }
      router.push("/admin/plans/codes");
    } catch (x) {
      // A API devolve "desconto.valor", "duracao.meses", "aplica.periodo"…: junto do campo certo.
      const mapa: Record<string, string> = { "desconto.valor": "valor", "desconto.tipo": "valor", "duracao.meses": "meses", "duracao.tipo": "meses", "aplica.planos": "planos", "aplica.periodo": "periodo" };
      setErros(Object.fromEntries(Object.entries(errosPorCampo(x)).map(([k, m]) => [mapa[k] ?? k, m])));
      setGeral(mensagemErro(x, "Não foi possível guardar o código."));
    }
  }

  return (
    <>
      <Link href="/admin/plans/codes" className="-mb-2 inline-flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-vivo no-underline">
        <ChevronLeft aria-hidden className="size-[18px]" />
        Códigos promocionais
      </Link>
      <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-[32px] md:leading-[38px]">{inicial ? inicial.codigo : "Novo código promocional"}</h1>
      {usado ? <Aviso tipo="info">Este código já foi usado ou está reservado num pagamento em curso{inicial!.usos ? ` (${inicial!.usos} usos)` : ""}: o desconto e a quem se aplica já não podem mudar. Pode mudar o máximo de usos, a data de fim, ou desligá-lo.</Aviso> : null}

      <form noValidate className="flex max-w-[720px] flex-col gap-5" onSubmit={(e) => (e.preventDefault(), void guardar(true))}>
        <Campo
          rotulo="Código"
          value={v.codigo}
          disabled={usado}
          onChange={(e) => muda("codigo", e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))}
          erro={erros.codigo}
          ajuda="Letras e números, sem espaços. É o que a pessoa escreve no checkout."
          maxLength={20}
          className="max-w-[320px]"
        />
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_200px]">
          <Escolhas legenda="Desconto em" nome="tipo" valor={v.tipo} aoMudar={(x) => muda("tipo", x)} disabled={usado} opcoes={[{ v: "percentagem", nome: "Percentagem (%)" }, { v: "valor", nome: "Valor fixo (Kz)" }]} />
          <Campo rotulo={v.tipo === "percentagem" ? "Percentagem" : "Valor (Kz)"} inputMode="decimal" value={v.valor} disabled={usado} onChange={(e) => muda("valor", e.target.value)} erro={erros.valor} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <fieldset className="m-0 border-0 p-0" disabled={usado}>
            <legend className="mb-1.5 p-0 text-pe-rotulo">Aplica-se a</legend>
            <div className="flex flex-col gap-1">
              {(["PREMIUM", "PREMIUM_PLUS"] as TipoPlano[]).map((t) => (
                <label key={t} className="flex min-h-10 items-center gap-2 text-[15px]">
                  <input
                    type="checkbox"
                    checked={v.planos.includes(t)}
                    onChange={(e) => muda("planos", e.target.checked ? [...v.planos, t] : v.planos.filter((x) => x !== t))}
                    className="size-5 accent-pe-azul-marca"
                  />
                  {t === "PREMIUM" ? "Premium" : "Premium Plus"}
                </label>
              ))}
              <span className="text-pe-legenda text-pe-tinta-suave">{v.planos.length ? "" : "Nenhum marcado: vale para todos os planos pagos."}</span>
              {erros.planos ? <span className="text-pe-legenda font-semibold text-pe-errado">{erros.planos}</span> : null}
            </div>
          </fieldset>
          <Escolha
            rotulo="Período"
            value={periodo}
            disabled={usado || v.duracao === "meses"}
            onChange={(e) => muda("periodo", e.target.value as typeof v.periodo)}
            erro={erros.periodo}
            ajuda={v.duracao === "meses" ? "Um desconto de vários meses só se aplica a pagamentos mensais." : undefined}
          >
            <option value="todos">Mensal e anual</option>
            <option value="mensal">Só mensal</option>
            <option value="anual">Só anual</option>
          </Escolha>
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <Escolhas legenda="Durante" nome="duracao" valor={v.duracao} aoMudar={(x) => muda("duracao", x)} disabled={usado} opcoes={[{ v: "primeiro", nome: "1.º pagamento" }, { v: "meses", nome: "Vários meses" }, { v: "sempre", nome: "Sempre" }]} />
          {v.duracao === "meses" ? <Campo rotulo="Quantos meses" inputMode="numeric" value={v.meses} disabled={usado} onChange={(e) => muda("meses", e.target.value.replace(/\D/g, ""))} erro={erros.meses} ajuda="Entre 2 e 24." className="w-40" /> : null}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo rotulo="Máximo de usos" inputMode="numeric" value={v.max} onChange={(e) => muda("max", e.target.value.replace(/\D/g, ""))} erro={erros.max_usos} ajuda="Vazio para ilimitado." />
          <Campo rotulo="Termina a" type="date" value={v.termina} onChange={(e) => muda("termina", e.target.value)} erro={erros.termina} ajuda="Vazio para não ter fim." />
        </div>
        <label className="flex items-start gap-3 text-[15px] leading-[22px]">
          <input type="checkbox" checked={v.primeira} disabled={usado} onChange={(e) => muda("primeira", e.target.checked)} className="mt-0.5 size-5 shrink-0 accent-pe-azul-marca" />
          <span>Só para quem nunca pagou</span>
        </label>
        {exemplo ? <p className="m-0 rounded-pe-md bg-pe-fundo-suave px-4 py-3">{exemplo}</p> : null}
        {geral ? <Aviso tipo="errado">{geral}</Aviso> : null}
        <div className="flex flex-wrap items-center gap-3 border-t border-pe-linha pt-5">
          {!inicial || inicial.estado === "rascunho" ? (
            <Botao tipo="secundario" tamanho="medio" disabled={aCriar || aMudar} onClick={() => void guardar(false)}>
              Guardar rascunho
            </Botao>
          ) : null}
          <Botao type="submit" tamanho="medio" disabled={aCriar || aMudar}>
            {!inicial || inicial.estado === "rascunho" ? "Activar código" : "Guardar alterações"}
          </Botao>
          {inicial && inicial.estado === "activo" ? (
            <Botao
              tipo="ligacao"
              tamanho="medio"
              className="ml-auto text-pe-errado hover:text-pe-errado"
              onClick={async () => {
                setGeral(null);
                try {
                  await desligar(inicial.id).unwrap();
                  router.push("/admin/plans/codes");
                } catch (x) {
                  setGeral(mensagemErro(x, "Não foi possível desligar."));
                }
              }}
            >
              Desligar código
            </Botao>
          ) : inicial && inicial.estado === "desligado" ? (
            <Botao tipo="ligacao" tamanho="medio" className="ml-auto" onClick={() => activar(inicial.id).unwrap().then(() => router.push("/admin/plans/codes"), (x) => setGeral(mensagemErro(x, "Não foi possível activar.")))}>
              Voltar a activar
            </Botao>
          ) : null}
        </div>
      </form>

      {inicial?.utilizacoes?.length ? (
        <section aria-labelledby="t-usos" className="flex max-w-[720px] flex-col gap-3">
          <h2 id="t-usos" className="m-0 font-pe-titulo text-[20px] font-semibold leading-7">
            Últimas utilizações
          </h2>
          <ul className="m-0 flex list-none flex-col p-0">
            {inicial.utilizacoes.map((u, i) => (
              <li key={i} className="flex justify-between gap-4 border-b border-pe-fundo-forte py-2.5 text-[15px]">
                <Link href={`/admin/users/${u.utilizador.id}`}>{u.utilizador.nome}</Link>
                <span className="text-right tabular-nums text-pe-tinta-suave">
                  {new Date(u.data).toLocaleDateString("pt-PT")}, {u.plano} {u.periodo}
                  {u.renovacao ? " (renovação)" : ""}, −{kz(u.valor_desconto_kz)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
