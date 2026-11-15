import type { Metadata } from "next";
import { TesteBasico } from "@/components/pe/acolhimento/TesteBasico";

export const metadata: Metadata = { title: "Teste do nível básico" };

export default function PaginaTesteBasico() {
  return <TesteBasico />;
}
