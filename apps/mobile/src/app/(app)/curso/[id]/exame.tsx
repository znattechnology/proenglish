/**
 * Exame oral do curso: o que é avaliado, o consentimento para gravar, a conversa com o tutor no papel
 * de examinador (sem gastar os minutos do plano) e o resultado.
 * Web: apps/web/app/(estudante)/user/courses/[courseId]/exame/page.tsx + components/pe/curso/Exame.tsx.
 * Pertence ao agente CONVERSA (a pasta curso/[id] é do agente CURSOS).
 */
import { useAudioPlayer, useAudioPlayerStatus } from "expo-audio";
import { router, useLocalSearchParams } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { Check, Mic, Pause, Play } from "lucide-react-native";
import { type ReactNode, useState } from "react";
import { ActivityIndicator, Pressable, View } from "react-native";
import { SITE_URL, urlAbsoluto } from "@/api/config";
import { Aviso, BarraProgresso, Botao, Cabecalho, Ecra, EstadoErro, Etiqueta, Osso, Seccao, Texto, Titulo } from "@/ui";
import { balao, cor, fonte, raio } from "@/tema";
import {
  COMPETENCIAS_EXAME,
  dataHoraLuanda,
  dataLonga,
  erroConversa,
  useExameOralApagarGravacaoMutation,
  useExameOralComecarMutation,
  useExameOralEstadoQuery,
  useLazyExameOralResultadoQuery,
  type EstadoExame,
  type ExameComecado,
  type ExameOral,
} from "@/dominios/conversa/api";
import { PermissaoMicrofone, useMicrofone } from "@/componentes/conversa/PermissaoMicrofone";
import { FolhaOferta, OfertaPlano } from "@/componentes/subscricao/Oferta";
import { ofertaDe, type OfertaPlano as Oferta } from "@/dominios/subscricao/api";
import { Viva } from "@/componentes/conversa/Viva";

type Fase = { tipo: "inicio" } | { tipo: "viva"; dados: ExameComecado } | { tipo: "a_avaliar" } | { tipo: "resultado"; exame: ExameOral };

const espera = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function EcraExameOral() {
  const { id: courseId } = useLocalSearchParams<{ id: string }>();
  const { data: estado, isLoading, isError, error, refetch, isFetching } = useExameOralEstadoQuery(courseId);
  const [lerExame] = useLazyExameOralResultadoQuery();
  const [fase, setFase] = useState<Fase>({ tipo: "inicio" });
  const [erro, setErro] = useState<string | null>(null);
  const tituloCurso = estado?.tentativas[0]?.curso.titulo;

  const mostrar = async (id: string) => {
    setFase({ tipo: "a_avaliar" });
    setErro(null);
    // A nota sai da chamada confirmada pelo serviço de voz e da avaliação: pode demorar até um minuto.
    for (let i = 0; i < 40; i++) {
      try {
        const e = await lerExame(id).unwrap();
        if (e.estado !== "em_curso" && e.estado !== "a_avaliar") {
          setFase({ tipo: "resultado", exame: e });
          void refetch();
          return;
        }
      } catch {
        break;
      }
      await espera(3000);
    }
    setErro("O resultado ainda não está pronto. Volte a abrir este ecrã daqui a um minuto.");
    setFase({ tipo: "inicio" });
    void refetch();
  };

  const voltarCurso = () => (router.canGoBack() ? router.back() : router.replace(`/curso/${courseId}`));
  const cabecalho = <Cabecalho titulo="Exame oral" subtitulo={tituloCurso} semVoltar={fase.tipo === "viva" || fase.tipo === "a_avaliar"} aoVoltar={fase.tipo === "resultado" ? () => setFase({ tipo: "inicio" }) : voltarCurso} />;

  if (fase.tipo === "viva")
    return (
      <Ecra cabecalho={cabecalho}>
        <View style={{ gap: 6 }}>
          <Titulo v="tituloM">Exame oral a decorrer</Titulo>
          <Texto suave>{`Fale o mais que conseguir: o exame é só falado. O examinador não corrige durante o exame.${fase.dados.gravacao ? " Esta conversa está a ser gravada." : ""}`}</Texto>
        </View>
        <Viva dados={fase.dados} frases={[]} semTexto aoTerminar={() => void mostrar(fase.dados.exame_id)} />
      </Ecra>
    );

  if (fase.tipo === "a_avaliar")
    return (
      <Ecra cabecalho={cabecalho}>
        <View accessibilityRole="alert" style={{ gap: 14, paddingVertical: 24 }}>
          <ActivityIndicator size="large" color={cor.azulMarca} style={{ alignSelf: "flex-start" }} />
          <Titulo v="tituloM">A avaliar o seu exame…</Titulo>
          <Texto suave>Demora até um minuto. Não feche este ecrã.</Texto>
        </View>
      </Ecra>
    );

  if (fase.tipo === "resultado")
    return (
      <Ecra cabecalho={cabecalho}>
        <ResultadoExame exame={fase.exame} courseId={courseId} aoRepetir={() => setFase({ tipo: "inicio" })} />
        <View style={{ gap: 10 }}>
          <Botao tipo="secundario" larguraTotal href={`/curso/${courseId}/notas`}>
            Ver as notas do curso
          </Botao>
          <Botao tipo="ligacao" style={{ alignSelf: "center" }} onPress={() => setFase({ tipo: "inicio" })}>
            Voltar ao exame
          </Botao>
        </View>
      </Ecra>
    );

  if (isError)
    return (
      <Ecra cabecalho={cabecalho}>
        <EstadoErro erro={error} titulo="Não conseguimos abrir o exame deste curso" aoTentar={refetch} outra={<Texto v="legenda" suave>Confirme que está inscrito no curso.</Texto>} />
      </Ecra>
    );
  if (isLoading || !estado)
    return (
      <Ecra cabecalho={cabecalho}>
        <View accessible accessibilityLabel="A carregar" style={{ gap: 14 }}>
          <Osso altura={34} largura="60%" />
          <Osso altura={80} />
          <Osso altura={200} />
        </View>
      </Ecra>
    );

  return (
    <Introducao estado={estado} courseId={courseId} erro={erro} cabecalho={cabecalho} aoActualizar={refetch} aActualizar={isFetching} aoComecar={(d) => setFase({ tipo: "viva", dados: d })} aoAbrir={(id) => void mostrar(id)} />
  );
}

function Introducao({
  estado: e,
  courseId,
  erro,
  cabecalho,
  aoActualizar,
  aActualizar,
  aoComecar,
  aoAbrir,
}: {
  estado: EstadoExame;
  courseId: string;
  erro: string | null;
  cabecalho: ReactNode;
  aoActualizar: () => void;
  aActualizar: boolean;
  aoComecar: (d: ExameComecado) => void;
  aoAbrir: (id: string) => void;
}) {
  const [consentimento, setConsentimento] = useState(false);
  const [comecar, { isLoading }] = useExameOralComecarMutation();
  const [erroInicio, setErroInicio] = useState<string | null>(null);
  // 403 {codigo: "plano", oferta}: o plano não inclui o exame.
  const [limite, setLimite] = useState<{ mensagem: string; oferta: Oferta } | null>(null);
  const mic = useMicrofone();
  const ofertaPlano = e.motivo === "plano" ? (e.oferta ?? null) : null;
  const tentativas = e.tentativas.filter((t) => t.estado !== "em_curso");

  const abrir = async () => {
    setErroInicio(null);
    if (!(await mic.garantir())) return;
    try {
      aoComecar(await comecar({ courseId, consentimento }).unwrap());
    } catch (x) {
      const oferta = ofertaDe(x);
      if (oferta) setLimite({ mensagem: erroConversa(x, "O seu plano não inclui o exame oral."), oferta });
      else setErroInicio(erroConversa(x, "Não foi possível começar o exame agora."));
    }
  };

  return (
    <Ecra
      cabecalho={cabecalho}
      aoActualizar={aoActualizar}
      aActualizar={aActualizar}
      rodape={
        e.disponivel && !ofertaPlano ? (
          <Botao larguraTotal onPress={() => void abrir()} carregando={isLoading} icone={<Mic size={20} color={cor.sobreMarca} />}>
            Começar o exame
          </Botao>
        ) : undefined
      }
    >
      <View style={{ gap: 8 }}>
        <Titulo>Exame oral</Titulo>
        <Texto suave>{`${Math.max(1, e.duracao_minutos - 2)} a ${e.duracao_minutos} minutos de conversa em inglês com o tutor, no papel de examinador. É obrigatório para o certificado e vale 40% da nota do curso. Não gasta os minutos de conversa do seu plano.`}</Texto>
      </View>

      {erro ? <Aviso>{erro}</Aviso> : null}
      {!e.disponivel && e.mensagem ? <Aviso tom={e.motivo === "aprovado" ? "certo" : "info"}>{e.mensagem}</Aviso> : null}
      {/* Sem exame no plano: a oferta toma o lugar do botão de começar. */}
      {ofertaPlano ? <OfertaPlano oferta={ofertaPlano} /> : null}

      <Seccao titulo="Como é o exame" gap={8}>
        {["Apresenta-se e fala um pouco do seu trabalho.", "Faz duas ou três tarefas de trabalho a partir das situações do curso: informar, pedir, explicar, resolver um problema.", "Dá a sua opinião sobre um tema do curso."].map((t, i) => (
          <View key={t} style={{ flexDirection: "row", gap: 10 }}>
            <Texto forte numeros style={{ width: 18 }}>{`${i + 1}.`}</Texto>
            <Texto style={{ flex: 1 }}>{t}</Texto>
          </View>
        ))}
        <Texto v="legenda" suave style={{ fontSize: 15, lineHeight: 22 }}>
          O examinador não corrige nem dá pistas. Use as frases que aprendeu no curso, sem as ler.
        </Texto>
      </Seccao>

      <View style={{ gap: 8, backgroundColor: cor.fundoSuave, borderRadius: raio.md, padding: 20 }}>
        <Texto forte style={{ fontSize: 17, lineHeight: 24 }}>
          O que é avaliado
        </Texto>
        {["Fluência: falar sem parar muito e manter a conversa.", `Gramática e vocabulário para o nível ${e.nivel_alvo ?? "do curso"}.`, "Tarefas: fazer o que cada tarefa pede."].map((t) => (
          <Texto key={t} v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>{`•  ${t}`}</Texto>
        ))}
        <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
          {`Passa com ${Math.round(e.nota_minima)}% ou mais. Se não passar, pode repetir 7 dias depois. O professor do curso pode rever a nota.`}
        </Texto>
      </View>

      {e.temas.length ? (
        <Seccao titulo="Situações do curso" gap={8}>
          {e.temas.map((t) => (
            <Texto key={t.titulo}>
              <Texto forte>{t.titulo}</Texto>
              {t.descricao ? <Texto suave>{`: ${t.descricao}`}</Texto> : null}
            </Texto>
          ))}
        </Seccao>
      ) : null}

      {e.frases.length ? (
        <Seccao titulo="Frases do curso para rever antes" gap={0}>
          {e.frases.map((f) => (
            <View key={f.en} style={{ paddingVertical: 8, borderBottomWidth: 1, borderColor: cor.fundoForte }}>
              <Texto forte>{f.en}</Texto>
              {f.pt ? (
                <Texto v="legenda" suave style={{ fontSize: 15 }}>
                  {f.pt}
                </Texto>
              ) : null}
            </View>
          ))}
          <Texto v="legenda" suave style={{ marginTop: 8 }}>
            Durante o exame não aparecem no ecrã.
          </Texto>
        </Seccao>
      ) : null}

      {tentativas.length ? (
        <Seccao titulo="As suas tentativas" gap={0}>
          {tentativas.map((t) => (
            <LinhaTentativa key={t.id} t={t} aoAbrir={() => aoAbrir(t.id)} />
          ))}
        </Seccao>
      ) : null}

      {e.disponivel ? (
        <View style={{ gap: 14, borderWidth: 1.5, borderColor: cor.azulMarca, borderRadius: raio.md, padding: 20 }}>
          <Texto accessibilityRole="header" style={{ fontFamily: fonte.tituloMedio, fontSize: 20, lineHeight: 26 }}>
            Antes de começar
          </Texto>
          <Texto style={{ fontSize: 15, lineHeight: 22 }}>
            Esteja num sítio calmo, com o microfone ligado. Pode gravar o exame para o professor o ouvir antes de confirmar a nota. Não é obrigatório: sem gravação o exame vale o mesmo.
          </Texto>
          <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: consentimento }} onPress={() => setConsentimento((v) => !v)} style={{ flexDirection: "row", gap: 12, minHeight: 44 }}>
            <View style={{ width: 24, height: 24, marginTop: 1, borderRadius: 4, borderWidth: 2, borderColor: cor.azulMarca, backgroundColor: consentimento ? cor.azulMarca : cor.fundo, alignItems: "center", justifyContent: "center" }}>
              {consentimento ? <Check size={16} color={cor.sobreMarca} strokeWidth={3} /> : null}
            </View>
            <View style={{ flex: 1, gap: 4 }}>
              <Texto>Autorizo a gravação desta prova para o professor a poder ouvir.</Texto>
              <Texto v="legenda" suave>
                Ouvem-na você e o professor do curso; a equipa ProEnglish só lhe acede se for preciso para resolver um problema ou uma reclamação sobre a nota. É apagada ao fim de 12 meses e pode apagá-la antes.
              </Texto>
            </View>
          </Pressable>
          <Botao tipo="ligacao" tamanho="pequeno" onPress={() => void WebBrowser.openBrowserAsync(`${SITE_URL}/privacidade#gravacoes`)}>
            Ver a política de privacidade
          </Botao>
          {erroInicio ? <Aviso tom="erro">{erroInicio}</Aviso> : null}
        </View>
      ) : null}
      <PermissaoMicrofone {...mic.folha} />
      {limite ? (
        <FolhaOferta aberto aoFechar={() => setLimite(null)} titulo="O exame oral não está no seu plano" mensagem={limite.mensagem} oferta={limite.oferta}>
          <Botao tipo="ligacao" larguraTotal onPress={() => setLimite(null)}>
            Agora não
          </Botao>
        </FolhaOferta>
      ) : null}
    </Ecra>
  );
}

function LinhaTentativa({ t, aoAbrir }: { t: ExameOral; aoAbrir: () => void }) {
  const nota = t.estado === "avaliado" ? `${Math.round(t.nota ?? 0)}%` : t.estado === "insuficiente" || t.estado === "anulado" ? "Sem nota" : "A avaliar";
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`Tentativa de ${dataLonga(t.criado_em)}: ${t.aprovado ? `passou, ${nota}` : nota}. Ver`} onPress={aoAbrir} style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12, minHeight: 60, paddingVertical: 10, borderBottomWidth: 1, borderColor: cor.fundoForte, backgroundColor: pressed ? cor.fundoSuave : undefined })}>
      <View style={{ flex: 1 }}>
        <Texto forte>{dataLonga(t.criado_em)}</Texto>
        {t.nivel_cefr ? (
          <Texto v="legenda" suave>
            {`Nível de fala ${t.nivel_cefr}`}
          </Texto>
        ) : null}
      </View>
      <Etiqueta tom={t.estado === "avaliado" && t.aprovado ? "certo" : "neutro"}>{t.estado === "avaliado" && t.aprovado ? `Passou, ${nota}` : nota}</Etiqueta>
      <Texto v="rotulo" cor={cor.azulMarca} style={{ textDecorationLine: "underline" }}>
        Ver
      </Texto>
    </Pressable>
  );
}

function ResultadoExame({ exame, courseId, aoRepetir }: { exame: ExameOral; courseId: string; aoRepetir: () => void }) {
  if (exame.estado === "insuficiente" || exame.estado === "anulado")
    return (
      <View style={{ gap: 12, backgroundColor: cor.fundoSuave, borderRadius: raio.md, padding: 20 }}>
        <Titulo v="tituloM">Este exame não teve nota</Titulo>
        <Texto>{`${exame.estado === "anulado" ? "A chamada não chegou a ligar." : "Não ouvimos respostas suficientes para avaliar (o exame precisa de pelo menos 2 minutos de conversa)."} Esta tentativa não conta: pode fazer o exame outra vez.`}</Texto>
        <Botao onPress={aoRepetir} style={{ alignSelf: "flex-start" }}>
          Voltar ao exame
        </Botao>
      </View>
    );

  const nota = Math.round(exame.nota ?? 0);
  const sobre = exame.aprovado ? cor.sobreMarca : cor.tinta;
  return (
    <>
      <View style={[balao.grande, { gap: 6, paddingVertical: 24, paddingHorizontal: 24, backgroundColor: exame.aprovado ? cor.azulMarca : cor.fundoSuave }]}>
        <Texto numeros cor={sobre} style={{ fontFamily: fonte.numero, fontSize: 56, lineHeight: 60, letterSpacing: -1 }}>{`${nota}%`}</Texto>
        <Texto accessibilityRole="header" cor={sobre} style={{ fontFamily: fonte.tituloMedio, fontSize: 22, lineHeight: 28 }}>
          {exame.aprovado ? "Passou no exame oral" : "Ainda não passou no exame oral"}
        </Texto>
        <Texto cor={sobre} style={{ fontSize: 15, lineHeight: 22 }}>
          {`${exame.nivel_cefr ? `Nível de fala atingido: ${exame.nivel_cefr}. ` : ""}${exame.aprovado ? "Conta para a nota e para o certificado do curso." : `Precisa de ${Math.round(exame.nota_minima)}%.${exame.pode_repetir_em ? ` Pode repetir a partir de ${dataHoraLuanda(exame.pode_repetir_em)}.` : ""}`}`}
        </Texto>
        {exame.revisao ? (
          <Texto cor={sobre} style={{ fontSize: 15, lineHeight: 22 }}>
            {`Nota revista pelo professor${exame.revisao.por ? ` ${exame.revisao.por}` : ""} (a da IA era ${Math.round(exame.nota_ia ?? 0)}%).${exame.revisao.comentario ? ` «${exame.revisao.comentario}»` : ""}`}
          </Texto>
        ) : null}
      </View>

      <Seccao titulo="Notas por competência" gap={0}>
        {COMPETENCIAS_EXAME.filter((c) => exame.notas[c.chave] != null).map((c) => {
          const v = Math.round(exame.notas[c.chave] as number);
          return (
            <View key={c.chave} style={{ gap: 6, paddingVertical: 10, borderBottomWidth: 1, borderColor: cor.fundoForte }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }}>
                <Texto forte>{c.nome}</Texto>
                <Texto numeros style={{ fontFamily: fonte.numero, fontSize: 18 }}>
                  {v}
                </Texto>
              </View>
              <BarraProgresso valor={v} rotulo={`${c.nome}: ${v}`} corBarra={v >= exame.nota_minima ? cor.certo : undefined} />
              <Texto v="legenda" suave>
                {c.ajuda}
              </Texto>
            </View>
          );
        })}
        <Texto v="legenda" suave style={{ marginTop: 8 }}>
          A pronúncia ainda não é avaliada no exame: a nota é a média das outras.
        </Texto>
      </Seccao>

      {exame.relatorio || exame.a_treinar.length ? (
        <Seccao titulo="O que treinar" gap={8}>
          {exame.relatorio ? <Texto>{exame.relatorio}</Texto> : null}
          {exame.a_treinar.map((t) => (
            <Texto key={t}>{`•  ${t}`}</Texto>
          ))}
        </Seccao>
      ) : null}

      {exame.frases_total ? (
        <Seccao titulo="Frases do curso" gap={6}>
          <Texto>{`Disse sozinho ${exame.frases_usadas.length} de ${exame.frases_total} frases do curso.`}</Texto>
          {exame.frases_usadas.map((f) => (
            <Texto key={f} forte>
              {f}
            </Texto>
          ))}
        </Seccao>
      ) : null}

      {exame.consentimento_gravacao ? <Gravacao exame={exame} courseId={courseId} /> : null}
    </>
  );
}

function Gravacao({ exame, courseId }: { exame: ExameOral; courseId: string }) {
  const [apagar, { isLoading: aApagar }] = useExameOralApagarGravacaoMutation();
  const [url, setUrl] = useState(urlAbsoluto(exame.gravacao_url));
  const [confirmar, setConfirmar] = useState(false);
  return (
    <View style={{ gap: 10, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, padding: 20 }}>
      <Texto forte style={{ fontSize: 17, lineHeight: 24 }}>
        Gravação do exame
      </Texto>
      {url ? (
        <>
          <Leitor url={url} />
          <Texto v="legenda" suave>
            Ouvem-na você e o professor do curso (a equipa ProEnglish só se for preciso para resolver uma reclamação). É apagada ao fim de 12 meses.
          </Texto>
          {confirmar ? (
            <View style={{ gap: 8 }}>
              <Botao
                tipo="perigo"
                tamanho="pequeno"
                carregando={aApagar}
                onPress={async () => {
                  try {
                    await apagar({ id: exame.id, courseId }).unwrap();
                    setUrl(null);
                  } finally {
                    setConfirmar(false);
                  }
                }}
              >
                Apagar a gravação
              </Botao>
              <Botao tipo="ligacao" tamanho="pequeno" onPress={() => setConfirmar(false)}>
                Manter
              </Botao>
            </View>
          ) : (
            <Botao tipo="ligacao" tamanho="pequeno" onPress={() => setConfirmar(true)}>
              Apagar a gravação
            </Botao>
          )}
        </>
      ) : (
        <Texto suave style={{ fontSize: 15 }}>
          {exame.gravacao_apagada || !exame.gravacao_url ? "A gravação foi apagada." : "A gravação ainda não está disponível. Volte a abrir daqui a pouco."}
        </Texto>
      )}
    </View>
  );
}

function Leitor({ url }: { url: string }) {
  const leitor = useAudioPlayer({ uri: url });
  const s = useAudioPlayerStatus(leitor);
  const total = s.duration || 0;
  const valor = total ? (s.currentTime / total) * 100 : 0;
  const mmss = (x: number) => `${Math.floor(x / 60)}:${String(Math.floor(x % 60)).padStart(2, "0")}`;
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={s.playing ? "Pausar a gravação" : "Ouvir a gravação"}
        onPress={() => {
          if (s.playing) leitor.pause();
          else {
            if (total && s.currentTime >= total - 0.2) void leitor.seekTo(0);
            leitor.play();
          }
        }}
        style={[balao.pequeno, { width: 48, height: 48, alignItems: "center", justifyContent: "center", backgroundColor: cor.azulMarca }]}
      >
        {s.playing ? <Pause size={22} color={cor.sobreMarca} /> : <Play size={22} color={cor.sobreMarca} />}
      </Pressable>
      <View style={{ flex: 1, gap: 4 }}>
        <BarraProgresso valor={valor} rotulo="Posição na gravação" />
        <Texto v="mini" suave numeros>
          {`${mmss(s.currentTime || 0)} / ${total ? mmss(total) : "–:––"}`}
        </Texto>
      </View>
    </View>
  );
}
