import type { Metadata } from "next";
import { Sobre } from "@/components/pe/site/Sobre";
import { lerSite } from "@/src/domains/site/conteudo";

export const metadata: Metadata = {
  title: "Sobre o ProEnglish",
  alternates: { canonical: "/about" },
  description: "Feito em Angola, para quem trabalha em Angola: o inglês das situações do trabalho, 15 minutos por dia.",
};

export default async function PaginaSobre() {
  return <Sobre site={await lerSite()} />;
}
