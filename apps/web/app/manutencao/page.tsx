import type { Metadata } from "next";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { Manutencao } from "@/components/pe/site/Sobre";
import { lerManutencao } from "@/src/domains/site/conteudo";

export const metadata: Metadata = { title: "Em manutenção", robots: { index: false } };
export const dynamic = "force-dynamic";

export default async function PaginaManutencao() {
  const m = await lerManutencao();
  // Sem resposta da API (o proxy mostra esta página com o último estado conhecido): mensagem por defeito.
  // Aberta à mão (não pelo proxy) fora da manutenção: volta à página inicial.
  if (m && !m.activa && !(await headers()).get("x-pe-manutencao")) redirect("/");
  return <Manutencao mensagem={m?.mensagem ?? ""} voltaEm={m?.volta_em ?? null} />;
}
