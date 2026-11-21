import { BookOpen, ChevronRight, Trophy } from "lucide-react-native";
import { View } from "react-native";
import { CartaoRevisao, Contadores, EsqueletoTrilho, TrilhoLicoes } from "@/componentes/laboratorio/Trilho";
import { idCursoActivo, useEstadoVidasQuery, useLabTrilhoQuery, useProgressoPraticaQuery, useSequenciaQuery } from "@/dominios/laboratorio/api";
import { useResumoRevisaoQuery } from "@/dominios/revisao/api";
import { cor } from "@/tema";
import { Botao, Ecra, EstadoErro, EstadoVazio, LinhaLista, MarcaIcone } from "@/ui";

/** Separador Praticar: o trilho de lições do curso activo (tela LaboratorioMovel). */
export default function Praticar() {
  const progresso = useProgressoPraticaQuery();
  const cursoId = idCursoActivo(progresso.data?.active_course);
  const trilho = useLabTrilhoQuery(cursoId ?? "", { skip: !cursoId });
  const sequencia = useSequenciaQuery();
  const vidas = useEstadoVidasQuery();
  const revisao = useResumoRevisaoQuery();

  const actualizar = () => {
    void progresso.refetch();
    if (cursoId) void trilho.refetch();
    void sequencia.refetch();
    void vidas.refetch();
    void revisao.refetch();
  };
  const aActualizar = (progresso.isFetching || trilho.isFetching) && !progresso.isLoading && !trilho.isLoading;

  let corpo: React.ReactNode;
  if (progresso.isError) {
    corpo = <EstadoErro erro={progresso.error} aoTentar={() => void progresso.refetch()} titulo="Não conseguimos abrir o laboratório" />;
  } else if (progresso.data && !cursoId) {
    corpo = (
      <EstadoVazio
        titulo="Escolha um curso para praticar"
        texto="As lições do laboratório são curtas: escolher, escrever, ouvir e falar. Pode mudar de curso quando quiser."
        icone={<BookOpen size={26} color={cor.azulMarca} />}
        accao={
          <Botao larguraTotal href="/lab/escolher-curso">
            Escolher curso
          </Botao>
        }
      />
    );
  } else if (trilho.isError) {
    corpo = (
      <EstadoErro
        erro={trilho.error}
        titulo="Não conseguimos carregar o trilho deste curso"
        aoTentar={() => void trilho.refetch()}
        outra={
          <Botao tipo="ligacao" larguraTotal href="/lab/escolher-curso">
            Escolher outro curso
          </Botao>
        }
      />
    );
  } else if (trilho.data) {
    corpo = trilho.data.unidades.length ? (
      <TrilhoLicoes trilho={trilho.data} />
    ) : (
      <EstadoVazio
        titulo="Este curso ainda não tem lições"
        texto="O professor está a prepará-las. Entretanto pode praticar noutro curso."
        accao={
          <Botao tipo="secundario" larguraTotal href="/lab/escolher-curso">
            Escolher outro curso
          </Botao>
        }
      />
    );
  } else {
    corpo = <EsqueletoTrilho />;
  }

  const t = trilho.data;
  return (
    <Ecra
      cabecalho={<Contadores curso={t?.curso.titulo ?? (typeof progresso.data?.active_course === "object" ? progresso.data?.active_course?.title : undefined)} sequencia={sequencia.data} vidas={vidas.data} />}
      aoActualizar={actualizar}
      aActualizar={aActualizar}
      style={{ paddingHorizontal: 16, paddingTop: 12, gap: 12 }}
    >
      <CartaoRevisao />
      {t && t.licoes_total ? (
        <LinhaLista
          titulo="Liga e conquistas"
          descricao={`${t.licoes_feitas} de ${t.licoes_total} lições feitas neste curso`}
          href="/liga"
          icone={
            <MarcaIcone>
              <Trophy size={20} color={cor.azulMarca} />
            </MarcaIcone>
          }
          direita={<ChevronRight size={20} color={cor.tintaSuave} />}
        />
      ) : null}
      <View>{corpo}</View>
    </Ecra>
  );
}
