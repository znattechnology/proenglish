/**
 * Separador Cursos (canvas MeusCursos e CursosMovel; web user/courses/page.tsx e
 * user/courses/explore/page.tsx): num só ecrã, os cursos em que a pessoa está inscrita e, logo
 * abaixo, todos os cursos (em vídeo e do laboratório), com o curso geral antes dos de sector.
 */
import { useState } from "react";
import { View } from "react-native";
import { ExplorarCursos, useCatalogo } from "@/componentes/cursos/Explorar";
import { CartaoCursoInscrito } from "@/componentes/cursos/Pecas";
import { useSessao } from "@/sessao/ContextoSessao";
import { Botao, Ecra, Osso, Seccao, Texto, Titulo } from "@/ui";

export default function SeparadorCursos() {
  const { utilizador } = useSessao();
  const userId = utilizador?.id ?? "";
  const { meus, actualizar } = useCatalogo();
  const [aActualizar, setAActualizar] = useState(false);
  const inscritos = meus.data ?? [];

  return (
    <Ecra
      cabecalho={
        <View style={{ paddingHorizontal: 20, paddingTop: 14, paddingBottom: 4 }}>
          <Titulo style={{ fontSize: 24, lineHeight: 30 }}>Cursos</Titulo>
        </View>
      }
      aoActualizar={async () => {
        setAActualizar(true);
        await actualizar();
        setAActualizar(false);
      }}
      aActualizar={aActualizar}
      style={{ paddingTop: 8 }}
    >
      {meus.isLoading ? (
        <Osso altura={150} />
      ) : inscritos.length ? (
        <Seccao
          titulo="Os seus cursos"
          gap={12}
          direita={
            <Botao tipo="ligacao" tamanho="pequeno" href="/notas">
              Ver as notas
            </Botao>
          }
        >
          {inscritos.map((c) => (
            <CartaoCursoInscrito key={c.courseId} curso={c} userId={userId} />
          ))}
        </Seccao>
      ) : meus.isError ? (
        <Texto v="legenda" suave>
          Não conseguimos carregar os cursos em que está inscrito. Puxe para baixo para tentar outra vez.
        </Texto>
      ) : null}

      <Seccao titulo={inscritos.length ? "Todos os cursos" : "Escolha o seu curso"} gap={12}>
        <ExplorarCursos />
      </Seccao>
    </Ecra>
  );
}
