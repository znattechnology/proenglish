import { Separadores } from "@/components/pe";
import { Cabeca } from "./Partes";

export function CabecaPerfil({ activo, texto }: { activo: "Perfil público" | "Definições"; texto: string }) {
  return (
    <div className="flex flex-col gap-4">
      <Cabeca titulo="Perfil e definições" texto={texto} />
      <Separadores
        rotulo="Perfil e definições"
        activo={activo}
        itens={[
          { nome: "Perfil público", href: "/teacher/profile" },
          { nome: "Definições", href: "/teacher/settings" },
        ]}
      />
    </div>
  );
}
