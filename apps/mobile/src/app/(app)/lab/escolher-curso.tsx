import { router } from "expo-router";
import { BookOpen, Lock } from "lucide-react-native";
import { Fragment, useState } from "react";
import { ActivityIndicator, Pressable, View } from "react-native";
import { categoriaPt, idCursoActivo, nivelEmFrase, useCursosPraticaQuery, useEscolherCursoPraticaMutation, useProgressoPraticaQuery } from "@/dominios/laboratorio/api";
import { balao, cor, raio } from "@/tema";
import { AvisoNivelBasico } from "@/componentes/cursos/NivelBasico";
import { ACarregar, Aviso, Cabecalho, Ecra, EstadoErro, EstadoVazio, Texto } from "@/ui";

const voltar = () => (router.canGoBack() ? router.back() : router.replace("/praticar"));

/** Escolher o curso do laboratório (tela EscolherCurso). */
export default function EscolherCurso() {
  const cursos = useCursosPraticaQuery();
  const progresso = useProgressoPraticaQuery();
  const [escolher] = useEscolherCursoPraticaMutation();
  const [aEscolher, setAEscolher] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const actual = idCursoActivo(progresso.data?.active_course);

  // Primeiro os cursos que a pessoa pode começar já; os que pedem o nível básico ficam no fim.
  const ordenados = (cursos.data ?? []).slice().sort((a, b) => Number(!!a.requisito_basico) - Number(!!b.requisito_basico));
  const primeiroFechado = ordenados.findIndex((c) => c.requisito_basico);

  const aoEscolher = async (id: string) => {
    if (id === actual) return voltar();
    setErro(null);
    setAEscolher(id);
    const r = await escolher(id);
    setAEscolher(null);
    if ("error" in r && r.error) {
      setErro("Não foi possível mudar de curso. Tente outra vez.");
      return;
    }
    voltar();
  };

  return (
    <Ecra
      cabecalho={<Cabecalho titulo="Escolher curso" />}
      aoActualizar={() => {
        void cursos.refetch();
        void progresso.refetch();
      }}
      style={{ gap: 12 }}
    >
      <Texto suave>{actual ? "Pode mudar de curso quando quiser. O progresso de cada um fica guardado." : "Escolha o curso em que quer praticar. Pode mudar quando quiser."}</Texto>
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
      {cursos.isLoading ? (
        <ACarregar linhas={4} altura={84} />
      ) : cursos.isError ? (
        <EstadoErro erro={cursos.error} titulo="Não conseguimos carregar os cursos" aoTentar={() => void cursos.refetch()} />
      ) : !cursos.data?.length ? (
        <EstadoVazio titulo="Ainda não há cursos de prática" texto="Quando os professores publicarem cursos, aparecem aqui. Puxe para baixo para actualizar." />
      ) : (
        ordenados.map((c, i) => {
          const eActual = c.id === actual;
          const fechado = !!c.requisito_basico;
          const contexto = [categoriaPt(c.category), nivelEmFrase(c.level)].filter(Boolean).join(", ");
          return (
            <Fragment key={c.id}>
              {i === primeiroFechado ? <AvisoNivelBasico semCursoGeral={primeiroFechado === 0} /> : null}
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`${c.title}${contexto ? `, ${contexto}` : ""}${eActual ? ", curso actual" : ""}${fechado ? ", pede o nível básico" : ""}`}
                accessibilityState={{ selected: eActual, busy: aEscolher === c.id, disabled: !!aEscolher }}
                disabled={!!aEscolher}
                onPress={() => (fechado ? router.push("/teste-basico") : void aoEscolher(c.id))}
                style={({ pressed }) => ({
                  flexDirection: "row",
                  alignItems: "center",
                  gap: 14,
                  minHeight: 84,
                  paddingHorizontal: 14,
                  paddingVertical: 12,
                  borderRadius: raio.md,
                  borderWidth: eActual ? 2 : 1,
                  borderColor: eActual ? cor.azulMarca : cor.linha,
                  backgroundColor: eActual || pressed ? cor.fundoSuave : cor.fundo,
                })}
              >
                <View style={[balao.pequeno, { borderTopLeftRadius: 16, borderTopRightRadius: 16, borderBottomRightRadius: 16, width: 48, height: 48, alignItems: "center", justifyContent: "center", backgroundColor: eActual ? cor.azulMarca : cor.fundoForte }]}>
                  <BookOpen size={24} color={eActual ? cor.sobreMarca : cor.tinta} />
                </View>
                <View style={{ flex: 1 }}>
                  <Texto forte style={{ lineHeight: 22 }}>
                    {c.title}
                  </Texto>
                  {contexto ? (
                    <Texto v="legenda" suave>
                      {contexto}
                    </Texto>
                  ) : null}
                </View>
                {aEscolher === c.id ? (
                  <ActivityIndicator color={cor.azulMarca} />
                ) : fechado ? (
                  <Lock size={20} color={cor.tintaSuave} />
                ) : (
                  <View style={eActual ? { backgroundColor: cor.realce, paddingHorizontal: 10, paddingVertical: 2, borderRadius: raio.sm } : null}>
                    <Texto v="legenda" forte cor={eActual ? cor.tinta : cor.azulVivo}>
                      {eActual ? "Actual" : "Escolher"}
                    </Texto>
                  </View>
                )}
              </Pressable>
            </Fragment>
          );
        })
      )}
    </Ecra>
  );
}
