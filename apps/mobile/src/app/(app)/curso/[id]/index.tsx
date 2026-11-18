/**
 * Página do curso (web user/courses/[courseId]/page.tsx).
 * Inscrito: canvas CursoDetalhe (balão azul com progresso e "Continuar", aulas por secção, nota, exame).
 * Por começar: canvas CursoInscrever (programa, professor, plano e "Começar o curso").
 */
import { Image } from "expo-image";
import { router, useFocusEffect, useLocalSearchParams } from "expo-router";
import { Check, Lock } from "lucide-react-native";
import { useCallback, useState } from "react";
import { Pressable, View } from "react-native";
import { urlAbsoluto } from "@/api/config";
import { mensagemErro } from "@/api/erros";
import {
  capitulosPorOrdem,
  categoriaPt,
  concluidos,
  duracaoAula,
  nivelEmFrase,
  nomeCompletoNivel,
  PLANO_DO_CURSO,
  accaoDoPasso,
  rotaDoPasso,
  TIPO_PT,
  useCursoDetalheQuery,
  useCursoExameEstadoQuery,
  useCursosPlanoActualQuery,
  useInscreverCursoMutation,
  useInscricaoCursoQuery,
  useNotasCursoQuery,
  usePercursoCursoQuery,
  useProfessorPublicoQuery,
  useProgressoCursoQuery,
  type Curso,
  type Notas,
} from "@/dominios/cursos/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { Aviso, BarraProgresso, Botao, Cabecalho, Ecra, EstadoErro, Osso, Texto, Titulo } from "@/ui";
import { balao, cor, fonte, raio } from "@/tema";
import { AvisoNivelBasico } from "@/componentes/cursos/NivelBasico";
import { SeparadoresCursos } from "@/componentes/cursos/Pecas";
import { duracaoDoPasso, PassosDaAula } from "@/componentes/cursos/Percurso";
import { CODIGO_REQUISITO_BASICO, faltaNivelBasico } from "@/dominios/cursos/testeBasico";

export default function PaginaCurso() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const curso = useCursoDetalheQuery(id);
  const inscricao = useInscricaoCursoQuery(id);

  if (curso.isError || inscricao.isError) {
    return (
      <Ecra cabecalho={<Cabecalho titulo="Curso" />}>
        <EstadoErro
          titulo="Não encontrámos este curso"
          erro={curso.error ?? inscricao.error}
          aoTentar={() => {
            curso.refetch();
            inscricao.refetch();
          }}
          outra={
            <Botao tipo="secundario" larguraTotal href="/cursos/explorar">
              Explorar cursos
            </Botao>
          }
        />
      </Ecra>
    );
  }
  if (!curso.data || !inscricao.data) {
    return (
      <Ecra cabecalho={<Cabecalho titulo="Curso" />} semMargem style={{ paddingTop: 0 }}>
        <View accessible accessibilityLabel="A carregar o curso" accessibilityState={{ busy: true }} style={{ gap: 12 }}>
          <Osso altura={220} raio={0} style={{ borderBottomRightRadius: 28 }} />
          <View style={{ paddingHorizontal: 20, gap: 12 }}>
            <Osso altura={26} largura="60%" />
            {[0, 1, 2, 3].map((i) => (
              <Osso key={i} altura={52} />
            ))}
          </View>
        </View>
      </Ecra>
    );
  }
  const actualizar = () => {
    curso.refetch();
    inscricao.refetch();
  };
  return inscricao.data.is_enrolled && curso.data.temAcesso ? (
    <CursoInscrito curso={curso.data.curso} aoActualizar={actualizar} />
  ) : (
    <CursoPorComecar curso={curso.data.curso} temAcesso={curso.data.temAcesso} pedeNivelBasico={inscricao.data?.codigo_sem_inscricao === CODIGO_REQUISITO_BASICO} aoActualizar={actualizar} />
  );
}

/* ------------------------------------------------------------------ */
/* Inscrito                                                            */
/* ------------------------------------------------------------------ */
function CursoInscrito({ curso, aoActualizar }: { curso: Curso; aoActualizar: () => void }) {
  const { utilizador } = useSessao();
  const progresso = useProgressoCursoQuery({ userId: utilizador?.id ?? "", courseId: curso.courseId }, { skip: !utilizador });
  const notas = useNotasCursoQuery(curso.courseId);
  // O percurso (aula, questionário, laboratório e conversas) e o passo seguinte: o servidor decide.
  const percurso = usePercursoCursoQuery(curso.courseId);
  const { refetch: lerPercurso } = percurso;
  // Ao voltar de uma lição ou de uma conversa, os passos mudam.
  useFocusEffect(
    useCallback(() => {
      lerPercurso();
    }, [lerPercurso])
  );
  const passosPorAula = new Map((percurso.data?.unidades ?? []).flatMap((u) => u.aulas).map((a) => [a.id, a.passos]));
  const proximo = percurso.data?.proximo ?? null;
  const [aActualizar, setAActualizar] = useState(false);
  const lista = capitulosPorOrdem(curso);
  const feitos = concluidos(progresso.data);
  const seguinte = lista.find((c) => !feitos.has(c.chapterId));
  const nFeitos = lista.filter((c) => feitos.has(c.chapterId)).length;
  const pct = lista.length ? Math.round((100 * nFeitos) / lista.length) : 0;
  const area = categoriaPt(curso.category);
  const linha = [curso.teacherName ? `Prof. ${curso.teacherName}` : null, nivelEmFrase(curso.level)].filter(Boolean).join(", ");

  return (
    <Ecra
      cabecalho={<Cabecalho titulo="Curso" />}
      semMargem
      style={{ paddingTop: 0 }}
      aoActualizar={async () => {
        setAActualizar(true);
        aoActualizar();
        await Promise.allSettled([progresso.refetch(), notas.refetch(), percurso.refetch()]);
        setAActualizar(false);
      }}
      aActualizar={aActualizar}
    >
      <View style={{ backgroundColor: cor.azulMarca, paddingHorizontal: 20, paddingTop: 20, paddingBottom: 24, borderBottomRightRadius: 28, gap: 12 }}>
        {area ? (
          <View style={{ alignSelf: "flex-start", backgroundColor: cor.fundo, paddingHorizontal: 10, paddingVertical: 2, borderRadius: raio.sm }}>
            <Texto v="legenda" forte>
              {area}
            </Texto>
          </View>
        ) : null}
        <Titulo cor={cor.sobreMarca} style={{ fontSize: 26, lineHeight: 32 }}>
          {curso.title}
        </Titulo>
        {linha ? (
          <Texto v="legenda" cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
            {linha}
          </Texto>
        ) : null}
        <View style={{ gap: 6 }}>
          <BarraProgresso valor={pct} rotulo="Progresso do curso" sobreMarca />
          <Texto v="legenda" cor={cor.sobreMarca} numeros>
            {nFeitos} de {lista.length} aulas, {pct}%
          </Texto>
        </View>
        {proximo ? (
          <View style={{ gap: 8 }}>
            <Texto v="legenda" cor={cor.sobreMarca} numeros style={{ fontSize: 15, lineHeight: 22 }}>
              A seguir: {proximo.tipo === "questionario" ? "questionário" : proximo.titulo}
              {duracaoDoPasso(proximo) ? `, ${duracaoDoPasso(proximo)}` : ""}
            </Texto>
            <Botao tipo="realce" tamanho="medio" larguraTotal href={rotaDoPasso(curso.courseId, proximo)}>
              {accaoDoPasso(proximo)}
            </Botao>
          </View>
        ) : seguinte ? (
          <Botao tipo="realce" tamanho="medio" larguraTotal href={`/curso/${curso.courseId}/aula/${seguinte.chapterId}`}>
            {nFeitos ? `Continuar: aula ${seguinte.numero}` : "Começar a primeira aula"}
          </Botao>
        ) : (
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Check size={20} color={cor.sobreMarca} />
            <Texto forte cor={cor.sobreMarca}>
              Todas as aulas vistas
            </Texto>
          </View>
        )}
      </View>

      <View style={{ paddingHorizontal: 20, paddingTop: 8 }}>
        <SeparadoresCursos
          itens={[
            { valor: "aulas", nome: "Aulas" },
            { valor: "notas", nome: "Notas" },
          ]}
          activo="aulas"
          aoMudar={(v) => v === "notas" && router.push(`/curso/${curso.courseId}/notas`)}
        />
      </View>

      <View style={{ paddingHorizontal: 20, gap: 20 }}>
        {curso.sections.map((s) => {
          const caps = lista.filter((c) => c.sectionId === s.sectionId);
          const feitosS = caps.filter((c) => feitos.has(c.chapterId)).length;
          return (
            <View key={s.sectionId} style={{ gap: 6 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
                <Texto v="tituloXS" accessibilityRole="header" style={{ flex: 1, fontSize: 17, lineHeight: 24 }}>
                  {s.sectionTitle}
                </Texto>
                <Texto v="legenda" suave numeros>
                  {feitosS} de {caps.length}
                </Texto>
              </View>
              {caps.map((c) => {
                const feita = feitos.has(c.chapterId);
                const actual = proximo ? proximo.aula_id === c.chapterId && proximo.tipo === "aula" : seguinte?.chapterId === c.chapterId;
                return (
                  <View key={c.chapterId}>
                  <Pressable
                    accessibilityRole="link"
                    accessibilityLabel={`Aula ${c.numero}: ${c.title}${feita ? ", vista" : actual ? ", a seguir" : ""}`}
                    onPress={() => router.push(`/curso/${curso.courseId}/aula/${c.chapterId}`)}
                    style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 12, minHeight: 52, paddingVertical: 4, borderBottomWidth: 1, borderColor: cor.fundoForte, backgroundColor: pressed ? cor.fundoSuave : undefined })}
                  >
                    <View
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: 14,
                        alignItems: "center",
                        justifyContent: "center",
                        backgroundColor: feita ? cor.certoSuave : actual ? cor.realce : cor.fundoForte,
                      }}
                    >
                      {feita ? (
                        <Check size={15} strokeWidth={3} color={cor.certo} />
                      ) : (
                        <Texto v="mini" forte numeros cor={actual ? cor.tinta : cor.tintaSuave} style={{ fontSize: 13 }}>
                          {c.type === "Quiz" ? "Q" : c.numero}
                        </Texto>
                      )}
                    </View>
                    <Texto forte={actual} cor={actual ? cor.azulMarca : cor.tinta} style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>
                      {c.title}
                    </Texto>
                    <Texto v="legenda" suave>
                      {duracaoAula(c.duracao_s) ?? TIPO_PT[c.type] ?? c.type}
                    </Texto>
                  </Pressable>
                  <PassosDaAula courseId={curso.courseId} passos={passosPorAula.get(c.chapterId) ?? []} />
                  </View>
                );
              })}
            </View>
          );
        })}

        <Pressable
          accessibilityRole="link"
          onPress={() => router.push(`/curso/${curso.courseId}/notas`)}
          style={({ pressed }) => ({ gap: 6, padding: 20, borderRadius: raio.md, backgroundColor: pressed ? cor.fundoForte : cor.fundoSuave })}
        >
          <Texto v="legenda" suave style={{ fontSize: 15 }}>
            Nota até agora
          </Texto>
          {notas.data ? (
            <Texto numeros style={{ fontFamily: fonte.numero, fontSize: 34, lineHeight: 40 }}>
              {Math.round(notas.data.final_grade.percentage)}%
            </Texto>
          ) : (
            <Osso altura={40} largura={96} />
          )}
          {notas.data ? (
            <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
              {textoNota(notas.data)}
            </Texto>
          ) : null}
          <Texto forte cor={cor.azulVivo} style={{ textDecorationLine: "underline" }}>
            Ver as notas
          </Texto>
        </Pressable>

        <CartaoExame courseId={curso.courseId} />

        {curso.description ? (
          <View style={{ gap: 8, padding: 20, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md }}>
            <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
              Sobre o curso
            </Texto>
            <Texto style={{ fontSize: 15, lineHeight: 22 }}>{curso.description}</Texto>
          </View>
        ) : null}
      </View>
    </Ecra>
  );
}

function textoNota(n: Notas) {
  if (n.plano_inclui_certificados === false) return "O seu plano não inclui certificados.";
  if (n.certificate_eligibility.is_eligible) return "Já cumpre tudo o que o certificado pede.";
  const falta = Object.values(n.certificate_eligibility.details).filter((d) => !d.met && !d.info_only).length;
  return `Certificado a partir de ${n.nota_minima ?? n.certificate_eligibility.nota_minima ?? 70}%. ${falta} ${falta === 1 ? "requisito por cumprir" : "requisitos por cumprir"}.`;
}

/** O estado do exame oral e a ligação para ele (o ecrã do exame é do agente da conversa). */
function CartaoExame({ courseId }: { courseId: string }) {
  const { data: e, isLoading } = useCursoExameEstadoQuery(courseId);
  if (isLoading) return <Osso altura={130} />;
  if (!e || e.motivo === "curso_pratica" || e.motivo === "desligado") return null;
  const ultimo = e.tentativas?.find((t) => t.estado === "avaliado");
  const texto = e.aprovado
    ? `Passou${ultimo?.nivel_cefr ? ` com nível de fala ${ultimo.nivel_cefr}` : ""}.`
    : e.disponivel
      ? `${e.duracao_minutos} minutos a falar com o tutor. Precisa de ${Math.round(e.nota_minima)}% para o certificado.`
      : (e.mensagem ?? "");
  const marca = e.disponivel;
  const c = marca ? cor.sobreMarca : cor.tinta;
  return (
    <Pressable
      accessibilityRole="link"
      onPress={() => router.push(`/curso/${courseId}/exame`)}
      style={({ pressed }) => [
        marca ? balao.medio : { borderRadius: raio.md, borderWidth: 1, borderColor: cor.linha },
        { gap: 6, padding: 20, backgroundColor: marca ? (pressed ? cor.azulVivo : cor.azulMarca) : pressed ? cor.fundoSuave : cor.fundo },
      ]}
    >
      <Texto v="tituloS" cor={c}>
        Exame oral
      </Texto>
      {texto ? (
        <Texto v="legenda" cor={c} style={{ fontSize: 15, lineHeight: 22 }}>
          {texto}
        </Texto>
      ) : null}
      <Texto forte cor={c} style={{ textDecorationLine: "underline" }}>
        {e.disponivel ? "Preparar o exame" : e.aprovado ? "Ver o resultado" : "Ver o exame"}
      </Texto>
    </Pressable>
  );
}

/* ------------------------------------------------------------------ */
/* Ainda não inscrito                                                  */
/* ------------------------------------------------------------------ */
function CursoPorComecar({ curso, temAcesso, pedeNivelBasico, aoActualizar }: { curso: Curso; temAcesso: boolean; pedeNivelBasico: boolean; aoActualizar: () => void }) {
  const { data: sub } = useCursosPlanoActualQuery();
  const [inscrever, { isLoading }] = useInscreverCursoMutation();
  const [erro, setErro] = useState<string | null>(null);
  // A API recusou a inscrição por faltar o nível básico (o estado da inscrição podia estar antigo).
  const [recusadoBasico, setRecusadoBasico] = useState(false);
  const faltaBasico = pedeNivelBasico || recusadoBasico;
  const plano = PLANO_DO_CURSO[curso.access_level] ?? PLANO_DO_CURSO.free;
  const lista = capitulosPorOrdem(curso);
  const total = curso.total_chapters || lista.length;
  const imagem = urlAbsoluto(curso.image || null);
  const etiqueta = [categoriaPt(curso.category), nivelEmFrase(curso.level)].filter(Boolean).join(", ");

  const comecar = async () => {
    setErro(null);
    const r = await inscrever(curso.courseId);
    if ("error" in r && r.error) {
      if (faltaNivelBasico(r.error)) return setRecusadoBasico(true);
      setErro(mensagemErro(r.error, "Não foi possível começar o curso. Tente outra vez."));
    }
    // A inscrição invalida o curso e o estado: o ecrã passa sozinho para a vista de inscrito.
  };

  const rodape = temAcesso && faltaBasico ? (
    <>
      <AvisoNivelBasico texto="Este é um curso de sector: pede, no mínimo, o nível básico de inglês. Faça o teste ou comece pelo curso geral." />
      <Botao tipo="ligacao" tamanho="pequeno" style={{ alignSelf: "center" }} onPress={() => router.dismissTo("/cursos")}>
        Ver o curso geral
      </Botao>
    </>
  ) : temAcesso ? (
    <>
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
      <Botao larguraTotal carregando={isLoading} onPress={() => void comecar()}>
        {isLoading ? "A preparar o curso…" : "Começar o curso"}
      </Botao>
    </>
  ) : (
    <>
      <Botao tipo="realce" larguraTotal href={`/checkout/${plano.tipo}`}>
        {`Passar para ${plano.nome}`}
      </Botao>
      <Botao tipo="ligacao" tamanho="pequeno" href="/planos" style={{ alignSelf: "center" }}>
        Comparar planos
      </Botao>
    </>
  );

  return (
    <Ecra cabecalho={<Cabecalho titulo="Explorar cursos" />} semMargem style={{ paddingTop: 0, gap: 20 }} rodape={rodape} aoActualizar={aoActualizar}>
      {imagem ? <Image source={{ uri: imagem }} accessible={false} contentFit="cover" style={{ height: 170, backgroundColor: cor.fundoForte }} /> : null}
      <View style={{ paddingHorizontal: 20, gap: 20, paddingTop: imagem ? 0 : 4 }}>
        <View style={{ gap: 8 }}>
          {etiqueta ? (
            <View style={{ alignSelf: "flex-start", backgroundColor: cor.fundoSuave, paddingHorizontal: 10, paddingVertical: 2, borderRadius: raio.sm }}>
              <Texto v="legenda" forte>
                {etiqueta}
              </Texto>
            </View>
          ) : null}
          <Titulo style={{ fontSize: 26, lineHeight: 32 }}>{curso.title}</Titulo>
          {curso.description ? <Texto suave>{curso.description}</Texto> : null}
        </View>

        <Professor id={curso.teacherId} nome={curso.teacherName} />

        <View style={{ flexDirection: "row", gap: 10, padding: 14, backgroundColor: cor.realceSuave, borderRadius: raio.md }}>
          <Lock size={20} color={cor.tinta} style={{ marginTop: 1 }} />
          <Texto style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>
            {temAcesso
              ? curso.access_level === "free"
                ? "Este curso é gratuito para todos."
                : `Incluído no seu plano ${sub?.plan.name ?? plano.nome}.`
              : `Este curso faz parte do ${plano.nome}. O seu plano é o ${sub?.plan.name ?? "Gratuito"}.`}
          </Texto>
        </View>

        <View style={{ gap: 4 }}>
          <Texto v="tituloXS" accessibilityRole="header" style={{ fontSize: 18, lineHeight: 24 }}>
            Programa
          </Texto>
          {curso.sections.map((s, i) => {
            const caps = s.chapters;
            const quest = caps.filter((c) => c.type === "Quiz").length;
            const aulas = caps.length - quest;
            return (
              <View key={s.sectionId} style={{ flexDirection: "row", alignItems: "center", gap: 14, paddingVertical: 12, borderBottomWidth: i < curso.sections.length - 1 ? 1 : 0, borderColor: cor.linha }}>
                <View style={[balao.pequeno, { width: 36, height: 36, alignItems: "center", justifyContent: "center", backgroundColor: cor.fundoForte }]}>
                  <Texto numeros style={{ fontFamily: fonte.titulo }}>
                    {i + 1}
                  </Texto>
                </View>
                <View style={{ flex: 1 }}>
                  <Texto forte style={{ lineHeight: 22 }}>
                    {s.sectionTitle}
                  </Texto>
                  <Texto v="legenda" suave>
                    {caps.length
                      ? `${aulas} ${aulas === 1 ? "aula" : "aulas"}${quest ? `, ${quest} ${quest === 1 ? "questionário" : "questionários"}` : ""}`
                      : s.sectionDescription || "Conteúdo disponível com o plano certo"}
                  </Texto>
                </View>
              </View>
            );
          })}
        </View>

        <View>
          {(
            [
              ["Professor", curso.teacherName || "—"],
              ["Nível", nomeCompletoNivel(curso.level) ?? "—"],
              ["Aulas", total ? `${total}` : "—"],
              ["Incluído no plano", plano.nome],
            ] as [string, string][]
          ).map(([dt, dd], i, a) => (
            <View key={dt} style={{ flexDirection: "row", justifyContent: "space-between", gap: 16, paddingVertical: 10, borderBottomWidth: i < a.length - 1 ? 1 : 0, borderColor: cor.linha }}>
              <Texto suave>{dt}</Texto>
              <Texto forte style={{ flex: 1, textAlign: "right" }}>
                {dd}
              </Texto>
            </View>
          ))}
        </View>
      </View>
    </Ecra>
  );
}

/** O professor do curso, como ele próprio se apresenta. Sem perfil preenchido, mostra só o nome. */
function Professor({ id, nome }: { id?: string; nome?: string }) {
  const { data: p } = useProfessorPublicoQuery(id ?? "", { skip: !id });
  if (!p && !nome) return null;
  const linha = p ? [p.especialidade, p.cidade].filter(Boolean).join(", ") : "";
  const foto = urlAbsoluto(p?.fotografia ?? null);
  const iniciais = p?.iniciais ?? (nome ?? "").split(/\s+/).map((x) => x[0]).slice(0, 2).join("").toUpperCase();
  return (
    <View style={{ gap: 8 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
        {foto ? (
          <Image source={{ uri: foto }} accessible={false} style={[balao.pequeno, { width: 44, height: 44 }]} contentFit="cover" />
        ) : (
          <View style={[balao.pequeno, { width: 44, height: 44, alignItems: "center", justifyContent: "center", backgroundColor: cor.fundoForte }]}>
            <Texto forte>{iniciais}</Texto>
          </View>
        )}
        <View style={{ flex: 1 }}>
          <Texto forte style={{ lineHeight: 22 }}>
            Prof. {p?.nome ?? nome}
          </Texto>
          {linha ? (
            <Texto v="legenda" suave>
              {linha}
            </Texto>
          ) : null}
        </View>
      </View>
      {p?.experiencia ? <Texto style={{ fontSize: 15, lineHeight: 22 }}>{p.experiencia}</Texto> : null}
      {p?.sobre ? (
        <Texto suave style={{ fontSize: 15, lineHeight: 22 }}>
          {p.sobre}
        </Texto>
      ) : null}
      {p ? (
        <Texto v="legenda" suave>
          {p.cursos_publicados} {p.cursos_publicados === 1 ? "curso" : "cursos"} na ProEnglish{p.desde ? `, desde ${p.desde}` : ""}.
        </Texto>
      ) : null}
    </View>
  );
}
