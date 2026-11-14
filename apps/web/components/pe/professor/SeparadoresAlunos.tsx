import { Separadores } from "@/components/pe";
import { Cabeca } from "./Partes";

export function CabecaAlunos({ activo, texto, children }: { activo: "Alunos" | "Resultados dos cursos"; texto: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4">
      <Cabeca titulo="Alunos e resultados" texto={texto}>
        {children}
      </Cabeca>
      <Separadores
        rotulo="Alunos e resultados"
        activo={activo}
        itens={[
          { nome: "Alunos", href: "/teacher/students" },
          { nome: "Resultados dos cursos", href: "/teacher/students/results" },
        ]}
      />
    </div>
  );
}
