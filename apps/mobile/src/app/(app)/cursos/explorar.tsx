/** Explorar cursos (canvas CursosMovel; web user/courses/explore/page.tsx), aberto por cima dos separadores. */
import { useState } from "react";
import { ExplorarCursos, useCatalogo } from "@/componentes/cursos/Explorar";
import { Cabecalho, Ecra } from "@/ui";

export default function EcraExplorar() {
  const { catalogo, meus } = useCatalogo();
  const [aActualizar, setAActualizar] = useState(false);
  return (
    <Ecra
      cabecalho={<Cabecalho titulo="Explorar cursos" />}
      aoActualizar={async () => {
        setAActualizar(true);
        await Promise.allSettled([catalogo.refetch(), meus.refetch()]);
        setAActualizar(false);
      }}
      aActualizar={aActualizar}
    >
      <ExplorarCursos />
    </Ecra>
  );
}
