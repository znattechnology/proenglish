/**
 * Notas de todos os cursos (canvas NotasTodas; web user/grades/page.tsx): a média no balão azul e
 * uma linha por curso, com quanto falta para o mínimo do certificado.
 */
import { router } from "expo-router";
import { ChevronRight, ListChecks } from "lucide-react-native";
import { useState } from "react";
import { Pressable, View } from "react-native";
import { categoriaPt, useCursoCertificadosQuery, useNotasDeTodosQuery, type NotasDeTodos } from "@/dominios/cursos/api";
import { BalaoFala, Botao, Cabecalho, Ecra, EstadoErro, EstadoVazio, Osso, Texto } from "@/ui";
import { balao, cor, fonte, raio } from "@/tema";

type LinhaCurso = NotasDeTodos["courses"][number];

const minimo = (c: LinhaCurso) => c.nota_minima ?? c.missing_requirements?.find((r) => r.requirement === "final_grade")?.required ?? 70;
const semNota = (c: LinhaCurso) => c.grading_mode === "no_content" || c.active_components.length === 0;

export default function EcraNotas() {
  const { data, isError, error, refetch } = useNotasDeTodosQuery();
  const certs = useCursoCertificadosQuery();
  const [aActualizar, setAActualizar] = useState(false);
  const emitidos = new Set((certs.data?.certificados ?? []).filter((c) => c.estado === "valido").map((c) => c.curso.id));
  const comNota = (data?.courses ?? []).filter((c) => !semNota(c));

  return (
    <Ecra
      cabecalho={<Cabecalho titulo="As suas notas" subtitulo={data?.courses.length ? `${data.courses.length} ${data.courses.length === 1 ? "curso" : "cursos"}` : undefined} />}
      aoActualizar={async () => {
        setAActualizar(true);
        await Promise.allSettled([refetch(), certs.refetch()]);
        setAActualizar(false);
      }}
      aActualizar={aActualizar}
      style={{ gap: 20 }}
    >
      {isError ? (
        <EstadoErro titulo="Não conseguimos carregar as notas" erro={error} aoTentar={refetch} />
      ) : !data ? (
        <View accessible accessibilityLabel="A carregar" accessibilityState={{ busy: true }} style={{ gap: 12 }}>
          <Osso altura={130} style={balao.grande} />
          {[0, 1, 2].map((i) => (
            <Osso key={i} altura={96} />
          ))}
        </View>
      ) : !data.courses.length ? (
        <EstadoVazio
          icone={<ListChecks size={26} color={cor.azulMarca} />}
          titulo="Ainda não há notas"
          texto="A nota aparece depois do primeiro questionário de um curso. Para o certificado precisa de 70% ou mais na nota final."
          accao={
            <Botao larguraTotal href="/cursos">
              Ver os cursos
            </Botao>
          }
        />
      ) : (
        <>
          {comNota.length ? (
            <BalaoFala style={{ gap: 4, paddingVertical: 22 }}>
              <Texto v="legenda" forte cor={cor.sobreMarca}>
                {comNota.length === 1 ? "Nota do seu curso" : `Média dos ${comNota.length} cursos`}
              </Texto>
              <Texto numeros cor={cor.sobreMarca} style={{ fontFamily: fonte.numero, fontSize: 36, lineHeight: 42 }}>
                {Math.round(typeof data.summary.average_grade === "number" ? data.summary.average_grade : data.summary.average_grade.percentage)}%
              </Texto>
              <Texto v="legenda" cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
                Cada curso pede 70% para dar certificado.
                {data.summary.certificates_earned ? ` Já tem ${data.summary.certificates_earned} ${data.summary.certificates_earned === 1 ? "certificado" : "certificados"}.` : ""}
              </Texto>
            </BalaoFala>
          ) : null}

          {comNota.map((c) => (
            <Linha key={c.course.id} c={c} emitido={emitidos.has(c.course.id)} />
          ))}

          {data.courses.filter(semNota).length ? (
            <View style={{ gap: 6 }}>
              <Texto v="tituloS" accessibilityRole="header">
                Ainda sem nota
              </Texto>
              <Texto v="legenda" suave style={{ fontSize: 15 }}>
                A nota aparece depois do primeiro questionário ou lição de prática.
              </Texto>
              {data.courses.filter(semNota).map((c) => (
                <Pressable
                  key={c.course.id}
                  accessibilityRole="link"
                  accessibilityLabel={`${c.course.title}. Continuar`}
                  onPress={() => router.push(`/curso/${c.course.id}`)}
                  style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 12, minHeight: 56, paddingVertical: 8, borderBottomWidth: 1, borderColor: cor.fundoForte, backgroundColor: pressed ? cor.fundoSuave : undefined })}
                >
                  <View style={{ flex: 1 }}>
                    {categoriaPt(c.course.category) ? (
                      <Texto v="legenda" suave>
                        {categoriaPt(c.course.category)}
                      </Texto>
                    ) : null}
                    <Texto forte numberOfLines={2}>
                      {c.course.title}
                    </Texto>
                  </View>
                  <Texto v="legenda" forte cor={cor.azulMarca}>
                    Continuar
                  </Texto>
                  <ChevronRight size={20} color={cor.tintaSuave} />
                </Pressable>
              ))}
            </View>
          ) : null}
        </>
      )}
    </Ecra>
  );
}

function estado(c: LinhaCurso, emitido: boolean) {
  const pct = c.final_grade.percentage;
  const min = minimo(c);
  if (emitido) return { texto: "Aprovado, certificado emitido", ok: true };
  if (c.is_eligible_for_certificate) return { texto: "Aprovado. Já pode receber o certificado.", ok: true };
  if (pct >= min) {
    const outro = c.missing_requirements?.find((r) => r.requirement !== "final_grade");
    return { texto: outro ? `Já acima de ${min}%. Falta: ${outro.message.replace(/\.0%/g, "%")}` : `Em curso, já acima de ${min}%`, ok: false };
  }
  const faltam = Math.ceil(min - pct);
  return { texto: `Em curso, ${faltam === 1 ? "falta 1 ponto" : `faltam ${faltam} pontos`} para ${min}%`, ok: false };
}

function Linha({ c, emitido }: { c: LinhaCurso; emitido: boolean }) {
  const pct = Math.round(c.final_grade.percentage);
  const min = minimo(c);
  const e = estado(c, emitido);
  const tom = e.ok ? cor.certo : pct >= min ? cor.azulVivo : cor.errado;
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`${c.course.title}: ${pct}%. ${e.texto}`}
      onPress={() => router.push(`/curso/${c.course.id}/notas`)}
      style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 16, padding: 16, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, backgroundColor: pressed ? cor.fundoSuave : cor.fundo })}
    >
      <Texto numeros cor={tom} style={{ width: 64, fontFamily: fonte.numero, fontSize: 26, lineHeight: 32 }}>
        {pct}%
      </Texto>
      <View style={{ flex: 1, minWidth: 0, gap: 4 }}>
        {categoriaPt(c.course.category) ? (
          <Texto v="legenda" suave>
            {categoriaPt(c.course.category)}
          </Texto>
        ) : null}
        <Texto forte style={{ lineHeight: 22 }}>
          {c.course.title}
        </Texto>
        <Regua pct={pct} min={min} corBarra={tom} />
        <Texto v="legenda" forte={e.ok} cor={e.ok ? cor.certo : cor.tinta}>
          {e.texto}
        </Texto>
      </View>
      <ChevronRight size={20} color={cor.tintaSuave} />
    </Pressable>
  );
}

/** Barra da nota com um traço no mínimo do certificado: mostra quanto falta (ou sobra). */
function Regua({ pct, min, corBarra }: { pct: number; min: number; corBarra: string }) {
  return (
    <View importantForAccessibility="no-hide-descendants" style={{ height: 14, justifyContent: "center" }}>
      <View style={{ height: 6, borderRadius: raio.pilula, backgroundColor: cor.fundoForte, overflow: "hidden" }}>
        <View style={{ width: `${Math.min(100, Math.max(pct, 2))}%`, height: "100%", backgroundColor: corBarra, borderRadius: raio.pilula }} />
      </View>
      <View style={{ position: "absolute", left: `${min}%`, top: 0, bottom: 0, width: 2, borderRadius: 1, backgroundColor: cor.tinta }} />
    </View>
  );
}
