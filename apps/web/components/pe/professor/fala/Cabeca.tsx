import Link from "next/link";
import { Plus } from "lucide-react";
import { Botao, Separadores } from "@/components/pe";
import { Cabeca } from "../Partes";

export function CabecaFala({ activo }: { activo: "Situações" | "Resultados" }) {
  return (
    <div className="flex flex-col gap-4">
      <Cabeca titulo="Conversa e escuta" texto="Situações para a conversa com o tutor de IA. Os exercícios de escuta e de pronúncia fazem-se nas lições de prática.">
        <Botao asChild tamanho="medio">
          <Link href="/teacher/speaking/new">
            <Plus aria-hidden className="size-5" />
            Nova situação de conversa
          </Link>
        </Botao>
      </Cabeca>
      <Separadores
        rotulo="Conversa e escuta"
        activo={activo}
        itens={[
          { nome: "Situações", href: "/teacher/speaking" },
          { nome: "Resultados", href: "/teacher/speaking/results" },
        ]}
      />
    </div>
  );
}
