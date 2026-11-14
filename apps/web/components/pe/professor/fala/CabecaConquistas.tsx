import { Separadores } from "@/components/pe";
import { Cabeca } from "../Partes";

export function CabecaConquistas({ activo, texto, children }: { activo: "Conquistas" | "Competições"; texto: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4">
      <Cabeca titulo="Conquistas e competições" texto={texto}>
        {children}
      </Cabeca>
      <Separadores
        rotulo="Conquistas e competições"
        activo={activo}
        itens={[
          { nome: "Conquistas", href: "/teacher/achievements" },
          { nome: "Competições", href: "/teacher/achievements/competitions" },
        ]}
      />
    </div>
  );
}
