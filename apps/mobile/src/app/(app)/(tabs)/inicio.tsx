/**
 * Início do estudante (canvas Main + EstadoCarregar; web user/dashboard/page.tsx):
 * saudação e meta de hoje, sequência e vidas, o cartão "Continuar" no balão azul,
 * "Praticar hoje" (revisão, conversa, laboratório), os outros cursos e a liga.
 */
import { router, useFocusEffect } from "expo-router";
import { BookOpen, ChevronRight, Flame, Mic, RotateCcw, Star, Trophy } from "lucide-react-native";
import { useCallback, useState } from "react";
import { Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { SinoNotificacoes } from "@/componentes/SinoNotificacoes";
import { useIrParaPrimeiraEntrada } from "@/dominios/conta/primeiraEntrada";
import { contextoCurso, useMeusCursosQuery, useProgressoCursoQuery, type CursoVideo } from "@/dominios/cursos/api";
import { minutosDe, minSeg, useFalaResumoQuery } from "@/dominios/fala/api";
import { saudacao, useInicioLigaQuery, useInicioRevisaoQuery, useInicioSequenciaQuery, useInicioVidasQuery, VIDAS_ILIMITADAS } from "@/dominios/inicio/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { BalaoFala, BarraProgresso, Botao, Ecra, LinhaLista, Logo, MarcaIcone, Osso, Seccao, Texto, Titulo, Vidas } from "@/ui";
import { balao, cor, raio } from "@/tema";

export default function Inicio() {
  const { utilizador } = useSessao();
  const userId = utilizador?.id ?? "";
  const seq = useInicioSequenciaQuery(undefined, { skip: !utilizador });
  const vidasQ = useInicioVidasQuery(undefined, { skip: !utilizador });
  const liga = useInicioLigaQuery(undefined, { skip: !utilizador });
  const revisao = useInicioRevisaoQuery(undefined, { skip: !utilizador });
  const cursos = useMeusCursosQuery(userId, { skip: !userId });
  const [aActualizar, setAActualizar] = useState(false);

  // Quem ainda não fez o acolhimento vai primeiro para a primeira entrada (agente CONTA).
  useIrParaPrimeiraEntrada();

  // Ao voltar de uma lição, aula ou conversa, os números mudam: volta a ler sem esperar.
  const { refetch: rSeq } = seq;
  const { refetch: rVidas } = vidasQ;
  const { refetch: rRev } = revisao;
  useFocusEffect(
    useCallback(() => {
      if (!utilizador) return;
      rSeq();
      rVidas();
      rRev();
    }, [utilizador, rSeq, rVidas, rRev])
  );

  const actualizar = async () => {
    setAActualizar(true);
    await Promise.allSettled([seq.refetch(), vidasQ.refetch(), liga.refetch(), revisao.refetch(), userId ? cursos.refetch() : null]);
    setAActualizar(false);
  };

  const vidas = vidasQ.data ? (vidasQ.data.unlimited ? VIDAS_ILIMITADAS : vidasQ.data.current) : undefined;
  const ilimitadas = vidas !== undefined && vidas >= VIDAS_ILIMITADAS;
  const [primeiro, ...outros] = cursos.data ?? [];
  const aCarregar = cursos.isLoading || (!userId && !cursos.data);

  return (
    <Ecra cabecalho={<Topo sequencia={seq.data?.current_streak} vidas={vidas} ilimitadas={ilimitadas} />} aoActualizar={actualizar} aActualizar={aActualizar} semTopo>
      <View style={{ gap: 4 }}>
        <Titulo>{saudacao(utilizador?.name)}</Titulo>
        {seq.data ? <Texto suave>{textoMeta(seq.data.daily_goal_minutes, seq.data.minutes_today, seq.data.goal_completed)}</Texto> : null}
      </View>

      {aCarregar ? (
        <View accessible accessibilityLabel="A carregar o início" accessibilityState={{ busy: true }} style={{ gap: 20 }}>
          <Osso altura={170} raio={28} style={balao.grande} />
          <Osso altura={22} largura="40%" raio={6} />
          <Osso altura={64} />
          <Osso altura={64} />
        </View>
      ) : cursos.isError ? (
        <View accessibilityRole="alert" style={{ gap: 12, backgroundColor: cor.erradoSuave, borderRadius: raio.md, padding: 16 }}>
          <Texto>
            <Texto forte>Não conseguimos carregar os seus cursos.</Texto> O problema é do nosso lado; o seu progresso está guardado.
          </Texto>
          <Botao tipo="secundario" tamanho="pequeno" onPress={() => cursos.refetch()}>
            Tentar outra vez
          </Botao>
        </View>
      ) : primeiro ? (
        <Continuar curso={primeiro} userId={userId} />
      ) : (
        <PrimeiroCurso />
      )}

      {!aCarregar ? <SuaFala /> : null}

      {!aCarregar ? (
        <Seccao titulo="Praticar hoje">
          {revisao.data?.para_rever ? (
            <LinhaLista
              href="/revisao"
              icone={
                <MarcaIcone marca>
                  <RotateCcw size={20} color={cor.sobreMarca} />
                </MarcaIcone>
              }
              titulo="Revisão de hoje"
              descricao={`Tem ${revisao.data.para_rever} ${revisao.data.para_rever === 1 ? "frase" : "frases"} para rever, em cerca de ${Math.max(1, revisao.data.minutos)} ${Math.max(1, revisao.data.minutos) === 1 ? "minuto" : "minutos"}.`}
            />
          ) : null}
          <LinhaLista
            href="/conversa"
            icone={
              <MarcaIcone marca>
                <Mic size={20} color={cor.sobreMarca} />
              </MarcaIcone>
            }
            titulo="Conversa com o tutor"
            descricao="Fale 5 minutos sobre uma situação do seu trabalho."
          />
          <LinhaLista
            href="/praticar"
            icone={
              <MarcaIcone>
                <Star size={20} color={cor.tinta} />
              </MarcaIcone>
            }
            titulo="Laboratório de prática"
            descricao={
              vidas === undefined
                ? "Lições de 5 minutos, com vidas e pontos."
                : ilimitadas
                  ? "Lições de 5 minutos. Vidas ilimitadas no seu plano."
                  : `Lições de 5 minutos. Tem ${vidas} ${vidas === 1 ? "vida" : "vidas"}.`
            }
          />
        </Seccao>
      ) : null}

      {outros.length > 0 ? (
        <Seccao titulo="Os seus cursos" direita={<Botao tipo="ligacao" tamanho="pequeno" href="/cursos">Ver todos</Botao>}>
          {outros.slice(0, 3).map((c) => (
            <OutroCurso key={c.courseId} curso={c} userId={userId} />
          ))}
        </Seccao>
      ) : null}

      {liga.data ? (
        <LinhaLista
          href="/liga"
          icone={<Trophy size={24} color={cor.azulMarca} />}
          titulo={liga.data.liga.nome}
          descricao={`${liga.data.eu.posicao}.º lugar esta semana, ${liga.data.eu.pontos_semana.toLocaleString("pt-PT")} pontos`}
        />
      ) : null}
    </Ecra>
  );
}

function textoMeta(meta: number, feitos: number, cumprida: boolean) {
  if (cumprida) return "Meta de hoje cumprida. Bom trabalho.";
  const faltam = Math.max(1, Math.ceil(meta - feitos));
  return `${faltam === 1 ? "Falta 1 minuto" : `Faltam ${faltam} minutos`} para a sua meta de hoje.`;
}

/** Cabeçalho: logótipo à esquerda; sequência, vidas e sino à direita. */
function Topo({ sequencia, vidas, ilimitadas }: { sequencia?: number; vidas?: number; ilimitadas: boolean }) {
  const ins = useSafeAreaInsets();
  return (
    <View style={{ paddingTop: ins.top + 12, paddingHorizontal: 20, paddingBottom: 4, flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
      <Logo altura={36} />
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
        {sequencia ? (
          <View
            accessible
            accessibilityRole="image"
            accessibilityLabel={`${sequencia} ${sequencia === 1 ? "dia seguido" : "dias seguidos"}`}
            style={{ flexDirection: "row", alignItems: "center", gap: 4, backgroundColor: cor.fundoSuave, paddingHorizontal: 10, paddingVertical: 6, borderRadius: raio.sm }}
          >
            <Flame size={18} color={cor.tinta} fill={cor.realce} />
            <Texto v="rotulo" numeros>
              {sequencia} {sequencia === 1 ? "dia" : "dias"}
            </Texto>
          </View>
        ) : null}
        {vidas !== undefined ? <Vidas quantas={vidas} ilimitadas={ilimitadas} /> : null}
        <View style={{ marginRight: -10 }}>
          <SinoNotificacoes />
        </View>
      </View>
    </View>
  );
}

/**
 * "A sua fala" (web components/pe/fala/Fala.tsx, ResumoFala): quanto falou, feito só com dados
 * reais, e a meta de fala de hoje. Sem dados (ou com erro) não aparece.
 */
function SuaFala() {
  const { data, refetch } = useFalaResumoQuery();
  useFocusEffect(
    useCallback(() => {
      void refetch();
    }, [refetch])
  );
  if (!data) return null;
  const { hoje, semana } = data;
  const vazio = semana.segundos === 0;
  const faltam = Math.max(0, hoje.meta_min * 60 - hoje.segundos);
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`A sua fala. ${data.frase} Hoje: ${minutosDe(hoje.segundos)} de ${hoje.meta_min} minutos a falar.`}
      onPress={() => router.push(vazio ? "/conversa" : "/conversa/progresso")}
      style={({ pressed }) => ({ gap: 12, padding: 16, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, backgroundColor: pressed ? cor.fundoSuave : cor.fundo })}
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <Mic size={18} color={cor.azulMarca} />
        <Texto v="rotulo" suave style={{ flex: 1 }}>
          A sua fala
        </Texto>
        <Texto v="legenda" suave numeros>
          <Texto v="rotulo" numeros>
            {minutosDe(hoje.segundos)}
          </Texto>
          {` de ${hoje.meta_min} min hoje`}
        </Texto>
      </View>
      <Texto v="tituloXS" style={{ fontSize: 17, lineHeight: 24 }}>
        {data.frase}
      </Texto>
      <BarraProgresso valor={hoje.percentagem} rotulo={`Meta de fala de hoje: ${hoje.percentagem}%`} corBarra={hoje.cumprida ? cor.certo : undefined} />
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <Texto v="legenda" suave style={{ flex: 1 }}>
          {hoje.cumprida ? "Meta de fala cumprida." : hoje.segundos ? `Faltam ${minSeg(faltam)}.` : "Conta o tempo em que fala: conversas, lições, revisão e aulas."}
        </Texto>
        <Texto v="legenda" forte cor={cor.azulVivo}>
          {vazio ? "Falar com o tutor" : "Ver o progresso"}
        </Texto>
      </View>
    </Pressable>
  );
}

/** O único destaque do ecrã: voltar ao curso onde ficou. */
function Continuar({ curso, userId }: { curso: CursoVideo; userId: string }) {
  const { data: progresso, isLoading } = useProgressoCursoQuery({ userId, courseId: curso.courseId });
  const pct = Math.round(progresso?.overallProgress ?? 0);
  const comecou = pct > 0;
  const contexto = contextoCurso(curso);
  return (
    <BalaoFala style={{ gap: 16 }}>
      <View style={{ gap: 4 }}>
        {contexto ? (
          <Texto v="legenda" forte cor={cor.sobreMarca}>
            {contexto}
          </Texto>
        ) : null}
        <Texto v="tituloM" accessibilityRole="header" cor={cor.sobreMarca}>
          {curso.title}
        </Texto>
      </View>
      {isLoading ? (
        <Osso altura={8} style={{ opacity: 0.3 }} />
      ) : !comecou ? (
        <Texto v="legenda" cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
          Ainda não começou. A primeira aula leva cerca de 8 minutos.
        </Texto>
      ) : (
        <View style={{ gap: 8 }}>
          <BarraProgresso valor={pct} rotulo={`Progresso em ${curso.title}`} sobreMarca />
          <Texto v="legenda" cor={cor.sobreMarca} numeros>
            {pct === 100 ? "Todas as aulas vistas" : `${pct}% do curso feito`}
          </Texto>
        </View>
      )}
      <Botao tipo="realce" tamanho="medio" larguraTotal href={`/curso/${curso.courseId}`}>
        {comecou ? "Continuar curso" : "Começar o curso"}
      </Botao>
    </BalaoFala>
  );
}

/** Sem cursos: o destaque passa a ser escolher o primeiro. */
function PrimeiroCurso() {
  return (
    <BalaoFala style={{ gap: 16 }}>
      <View style={[balao.medio, { width: 56, height: 56, alignItems: "center", justifyContent: "center", backgroundColor: cor.realce }]}>
        <BookOpen size={26} color={cor.tinta} />
      </View>
      <View style={{ gap: 6 }}>
        <Texto v="tituloM" accessibilityRole="header" cor={cor.sobreMarca}>
          Escolha o seu primeiro curso
        </Texto>
        <Texto v="legenda" cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
          Há o curso geral, do básico ao avançado, e cursos por sector. A primeira aula leva cerca de 8 minutos.
        </Texto>
      </View>
      <Botao tipo="realce" tamanho="medio" larguraTotal href="/cursos">
        Ver os cursos
      </Botao>
    </BalaoFala>
  );
}

/** Outro curso inscrito: título, barra e percentagem. */
function OutroCurso({ curso, userId }: { curso: CursoVideo; userId: string }) {
  const { data: progresso, isLoading } = useProgressoCursoQuery({ userId, courseId: curso.courseId });
  const pct = Math.round(progresso?.overallProgress ?? 0);
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`${curso.title}, ${pct}% feito`}
      onPress={() => router.push(`/curso/${curso.courseId}`)}
      style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 12, padding: 16, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, backgroundColor: pressed ? cor.fundoSuave : cor.fundo })}
    >
      <View style={{ flex: 1, gap: 8 }}>
        <Texto forte style={{ lineHeight: 22 }}>
          {curso.title}
        </Texto>
        {isLoading ? <Osso altura={8} /> : <BarraProgresso valor={pct} rotulo={`Progresso em ${curso.title}`} corBarra={pct === 100 ? cor.certo : undefined} />}
        <Texto v="legenda" suave numeros>
          {pct === 100 ? "Concluído" : `${pct}% feito`}
        </Texto>
      </View>
      <ChevronRight size={20} color={cor.tintaSuave} />
    </Pressable>
  );
}
