import type { Metadata } from "next";
import { Revisao } from "@/components/pe/revisao/Revisao";

export const metadata: Metadata = { title: "Revisão de hoje" };

export default function PaginaRevisao() {
  return <Revisao />;
}
