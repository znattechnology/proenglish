/** Explorar cursos (canvas CursosMovel; web user/courses/explore/page.tsx), aberto por cima dos separadores. */
import { useState } from "react";
import { ExplorarCursos, useCatalogo } from "@/componentes/cursos/Explorar";
import { Cabecalho, Ecra } from "@/ui";

export default function EcraExplorar() {
  const { actualizar } = useCatalogo();
  const [aActualizar, setAActualizar] = useState(false);
  return (
    <Ecra
      cabecalho={<Cabecalho titulo="Todos os cursos" />}
      aoActualizar={async () => {
        setAActualizar(true);
        await actualizar();
        setAActualizar(false);
      }}
      aActualizar={aActualizar}
    >
      <ExplorarCursos />
    </Ecra>
  );
}
