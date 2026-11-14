import type { Metadata } from "next";
import { Landing } from "@/components/pe/site/Landing";
import { lerSite } from "@/src/domains/site/conteudo";

export async function generateMetadata(): Promise<Metadata> {
  const { definicoes: d } = await lerSite();
  return {
    title: d.titulo,
    description: d.descricao,
    keywords: d.palavras_chave || undefined,
    alternates: { canonical: "/" },
    openGraph: { title: d.titulo, description: d.descricao, locale: "pt_AO", type: "website", url: "/", siteName: "ProEnglish" },
  };
}

export default async function PaginaInicial() {
  return <Landing site={await lerSite()} />;
}
