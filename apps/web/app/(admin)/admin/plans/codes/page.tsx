"use client";

import Link from "next/link";
import { useState } from "react";
import { Plus } from "lucide-react";
import { Aviso, Botao, Etiqueta, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Numeros } from "@/components/pe/professor/Partes";
import { CabecaSeccao, LigacaoAbrir, SEPARADORES_PLANOS } from "@/components/pe/admin/Comum";
import { diaMesCurto, kz } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import { useCodigosQuery, type Codigo, type EstadoCodigo } from "@/src/domains/admin/administracao/negocio";

const FILTROS = { Todos: "todos", Activos: "activos", Rascunhos: "rascunhos", Esgotados: "esgotados", Expirados: "expirados", Desligados: "desligados" } as const;
const ESTADO: Record<EstadoCodigo, { nome: string; tipo: "certo" | "neutra" | "realce" | "errado" }> = {
  activo: { nome: "Activo", tipo: "certo" },
  rascunho: { nome: "Rascunho", tipo: "neutra" },
  esgotado: { nome: "Esgotado", tipo: "realce" },
  expirado: { nome: "Expirado", tipo: "neutra" },
  desligado: { nome: "Desligado", tipo: "neutra" },
};
const PLANO = { FREE: "Gratuito", PREMIUM: "Premium", PREMIUM_PLUS: "Premium Plus" } as const;

function paraQuem(c: Codigo) {
  const planos = c.aplica.planos.length ? c.aplica.planos.map((p) => PLANO[p]).join(" e ") : "Todos os planos";
  const per = c.aplica.periodo === "anual" ? ", anual" : c.aplica.periodo === "mensal" ? ", mensal" : "";
  return `${planos}${per}${c.so_primeira_compra ? ". Só primeira compra" : ""}`;
}

export default function Codigos() {
  const [filtro, setFiltro] = useState<keyof typeof FILTROS>("Todos");
  const { data, isError, refetch } = useCodigosQuery(FILTROS[filtro]);
  const n = data?.numeros;
  return (
    <Pagina className="gap-7">
      <CabecaSeccao titulo="Planos e códigos" activo="Códigos promocionais" itens={SEPARADORES_PLANOS}>
        <Botao asChild tamanho="medio">
          <Link href="/admin/plans/codes/new">
            <Plus aria-hidden className="size-5" />
            Novo código
          </Link>
        </Botao>
      </CabecaSeccao>
      {n ? (
        <Numeros
          itens={[
            { nome: "Activos", valor: num(n.activos), nota: n.rascunhos ? `${n.rascunhos} em rascunho` : "nenhum em rascunho" },
            { nome: "Usados este mês", valor: num(n.usados_mes), nota: `por ${num(n.pessoas_mes)} pessoas` },
            { nome: "Desconto dado", valor: kz(n.desconto_mes_kz), nota: "este mês" },
            { nome: "Pagam depois do desconto", valor: n.continuam_2_mes_pct == null ? "–" : `${Math.round(n.continuam_2_mes_pct)}%`, nota: "continuam no 2.º mês" },
          ]}
        />
      ) : isError ? null : (
        <Osso className="h-[104px] rounded-pe-md" />
      )}
      <Pilulas rotulo="Mostrar" opcoes={Object.keys(FILTROS) as (keyof typeof FILTROS)[]} valor={filtro} aoMudar={setFiltro} />
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os códigos.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-64 rounded-pe-md" />
      ) : !data.resultados.length ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">Nenhum código neste estado.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] border-collapse tabular-nums">
            <caption className="sr-only">Códigos promocionais</caption>
            <thead>
              <tr>
                {["Código", "Desconto", "Para quem", "Usos", "Termina", "Estado", ""].map((t, i) => (
                  <th key={i} scope="col" className="border-b border-pe-linha px-3 py-2.5 text-left text-pe-legenda font-semibold text-pe-tinta-suave">
                    {t || <span className="sr-only">Acções</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.resultados.map((c) => (
                <tr key={c.id}>
                  <td className="border-b border-pe-fundo-forte p-3 font-pe-titulo font-bold tracking-[0.04em]">{c.codigo}</td>
                  <td className="border-b border-pe-fundo-forte p-3">{c.descricao}</td>
                  <td className="border-b border-pe-fundo-forte p-3">{paraQuem(c)}</td>
                  <td className="border-b border-pe-fundo-forte p-3">
                    {num(c.usos)} de {c.max_usos == null ? "ilimitado" : num(c.max_usos)}
                  </td>
                  <td className="border-b border-pe-fundo-forte p-3">{c.termina ? diaMesCurto(new Date(`${c.termina}T12:00:00`), true) : "Sem fim"}</td>
                  <td className="border-b border-pe-fundo-forte p-3">
                    <Etiqueta tipo={ESTADO[c.estado].tipo}>{ESTADO[c.estado].nome}</Etiqueta>
                  </td>
                  <td className="border-b border-pe-fundo-forte px-3 text-right">
                    <LigacaoAbrir href={`/admin/plans/codes/${c.id}`} nome={c.codigo} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Pagina>
  );
}
