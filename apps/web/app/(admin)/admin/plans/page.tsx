"use client";

import Link from "next/link";
import { Aviso, Botao, Etiqueta, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaSeccao, SEPARADORES_PLANOS } from "@/components/pe/admin/Comum";
import { cnPe } from "@/lib/pe";
import { kz } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import { usePlanosQuery, type Plano } from "@/src/domains/admin/administracao/negocio";

function linhasPlano(p: Plano): [string, string][] {
  const l = p.limites;
  return [
    ["Lições por dia", l.licoes_dia == null ? "Ilimitadas" : String(l.licoes_dia)],
    ["Vidas", l.vidas == null ? "Ilimitadas" : `${l.vidas}, recuperam com o tempo`],
    ["Conversa por dia", l.conversa_min_dia == null ? "Sem limite" : `${l.conversa_min_dia} min`],
    ["Conversa por mês", l.conversa_min_mes == null ? "Sem limite" : `${l.conversa_min_mes} min`],
    ...(l.pronuncia_detalhada_dia ? ([["Pronúncia detalhada", `${l.pronuncia_detalhada_dia} por dia`]] as [string, string][]) : []),
    ...(l.sessoes_nativo_mes ? ([["Professor nativo", `${l.sessoes_nativo_mes} sessões por mês`]] as [string, string][]) : []),
    ["Certificados", p.certificados ? "Sim" : "Não"],
    ...(p.dias_teste ? ([["Teste grátis", `${p.dias_teste} dias`]] as [string, string][]) : []),
  ];
}

export default function Planos() {
  const { data, isError, refetch } = usePlanosQuery();
  return (
    <Pagina className="gap-7">
      <CabecaSeccao titulo="Planos e códigos" activo="Planos" itens={SEPARADORES_PLANOS} />
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os planos.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-96 rounded-pe-md" />
      ) : (
        <>
          <ul className="m-0 grid list-none gap-4 p-0 lg:grid-cols-3">
            {data.map((p) => (
              <li key={p.id} className={cnPe("flex flex-col gap-4 rounded-pe-md p-5", p.destaque ? "border-2 border-pe-azul-marca" : "border border-pe-linha", !p.activo && "opacity-70")}>
                <div className="flex items-start justify-between gap-2">
                  <span className="font-pe-titulo text-[20px] font-bold leading-7">{p.nome}</span>
                  {p.destaque ? <Etiqueta tipo="marca">Mais escolhido</Etiqueta> : !p.activo ? <Etiqueta>Desligado</Etiqueta> : null}
                </div>
                <div className="flex flex-col">
                  <span className="font-pe-titulo text-[28px] font-bold leading-9 tabular-nums">{kz(p.preco_mensal_kz)}</span>
                  <span className="text-pe-legenda text-pe-tinta-suave">{p.preco_mensal_kz ? (p.preco_anual_kz ? `por mês. Anual: ${kz(p.preco_anual_kz)}` : "por mês. Sem plano anual") : "Sem pagamento"}</span>
                </div>
                <dl className="m-0 flex flex-col">
                  {linhasPlano(p).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-3 border-b border-pe-fundo-forte py-2 text-[15px]">
                      <dt className="text-pe-tinta-suave">{k}</dt>
                      <dd className="m-0 text-right font-semibold">{v}</dd>
                    </div>
                  ))}
                </dl>
                <span className="text-[15px]">{p.tipo === "FREE" ? `${num(p.utilizadores)} utilizadores` : `${num(p.assinantes)} assinantes`}</span>
                <Botao asChild tipo="secundario" tamanho="pequeno" className="mt-auto self-start">
                  <Link href={`/admin/plans/${p.id}`}>Editar plano</Link>
                </Botao>
              </li>
            ))}
          </ul>
          <p className="m-0 text-pe-legenda text-pe-tinta-suave">Mudar o preço só vale para subscrições novas. Quem já paga mantém o preço enquanto renovar.</p>
        </>
      )}
    </Pagina>
  );
}
