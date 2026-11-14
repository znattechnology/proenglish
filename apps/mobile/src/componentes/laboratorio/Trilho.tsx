/**
 * Trilho do laboratório (apps/web/components/pe/laboratorio/Trilho.tsx) com o visual de
 * LaboratorioMovel.dc.html: contadores no topo, unidades com a faixa em balão e os discos em serpentina.
 */
import { router } from "expo-router";
import { Check, ChevronRight, Flame, Heart, RotateCcw, Star, Trophy, Zap } from "lucide-react-native";
import { useState } from "react";
import { Pressable, View } from "react-native";
import Svg, { Circle } from "react-native-svg";
import { fmt, ILIMITADAS, type EstadoVidas, type LicaoTrilho, type Sequencia, type Trilho } from "@/dominios/laboratorio/api";
import { nFrases, useResumoRevisaoQuery } from "@/dominios/revisao/api";
import { balao, cor, fonte, raio } from "@/tema";
import { Botao, Dialogo, MarcaIcone, Osso, Texto } from "@/ui";

/** Sombras sólidas dos discos (as mesmas do canvas e da web). */
const SOMBRA = { feita: "#00003d", actual: "#c79500", bloqueada: cor.linha } as const;
const DESVIOS = [0, 40, 68, 40, 0, -40, -68, -40];

/** Curso, dias seguidos, pontos e vidas (o topo do separador Praticar). */
export function Contadores({ curso, sequencia, vidas }: { curso?: string; sequencia?: Sequencia; vidas?: EstadoVidas }) {
  const ilimitadas = !!vidas?.unlimited || (vidas?.current ?? 0) >= ILIMITADAS;
  const dias = sequencia?.current_streak ?? 0;
  return (
    <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8, paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: 1, borderColor: cor.linha }}>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={curso ? `Curso: ${curso}. Mudar de curso` : "Escolher curso"}
        onPress={() => router.push("/lab/escolher-curso")}
        style={({ pressed }) => ({ flexShrink: 1, minHeight: 44, justifyContent: "center", paddingHorizontal: 12, borderRadius: raio.sm, backgroundColor: pressed ? cor.fundoForte : cor.fundoSuave })}
      >
        <Texto v="rotulo" numberOfLines={1}>
          {curso ?? "Escolher curso"}
        </Texto>
      </Pressable>
      <View accessible accessibilityLabel={`${dias} ${dias === 1 ? "dia seguido" : "dias seguidos"}`} style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
        <Flame size={22} color={sequencia?.practiced_today ? cor.tinta : cor.tintaSuave} fill={sequencia?.practiced_today ? cor.realce : "none"} strokeWidth={1.5} />
        <Texto forte numeros>
          {dias}
        </Texto>
      </View>
      <View accessible accessibilityLabel={`${fmt(vidas?.points ?? 0)} pontos`} style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
        <Zap size={22} color={cor.azulVivo} fill={cor.azulVivo} />
        <Texto forte numeros>
          {fmt(vidas?.points ?? 0)}
        </Texto>
      </View>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={ilimitadas ? "Vidas ilimitadas. Abrir a loja" : `${vidas?.current ?? 0} de ${vidas?.maximum ?? 3} vidas. Abrir a loja`}
        onPress={() => router.push("/lab/loja")}
        hitSlop={6}
        style={{ minHeight: 44, flexDirection: "row", alignItems: "center", gap: 4 }}
      >
        <Heart size={22} color={cor.vida} fill={cor.vida} />
        <Texto forte numeros>
          {ilimitadas ? "∞" : (vidas?.current ?? 0)}
        </Texto>
      </Pressable>
    </View>
  );
}

/** Entrada para a revisão de hoje. Não aparece quando não há nada para rever. */
export function CartaoRevisao() {
  const { data } = useResumoRevisaoQuery();
  if (!data?.para_rever) return null;
  const minutos = Math.max(1, data.minutos);
  const texto = `Tem ${nFrases(data.para_rever)} para rever, em cerca de ${minutos} ${minutos === 1 ? "minuto" : "minutos"}.`;
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`Revisão de hoje. ${texto}`}
      onPress={() => router.push("/revisao")}
      style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 14, borderWidth: 2, borderColor: cor.realce, backgroundColor: pressed ? cor.realce : cor.realceSuave, borderRadius: raio.md, paddingHorizontal: 14, paddingVertical: 12 })}
    >
      <MarcaIcone marca tamanho={44}>
        <RotateCcw size={22} color={cor.sobreMarca} />
      </MarcaIcone>
      <View style={{ flex: 1 }}>
        <Texto forte style={{ lineHeight: 22 }}>
          Revisão de hoje
        </Texto>
        <Texto v="legenda" suave>
          {texto}
        </Texto>
      </View>
      <ChevronRight size={20} color={cor.tintaSuave} />
    </Pressable>
  );
}

/** As unidades e os discos das lições. As feitas abrem "Praticar outra vez". */
export function TrilhoLicoes({ trilho }: { trilho: Trilho }) {
  const [praticar, setPraticar] = useState<LicaoTrilho | null>(null);
  let indice = 0;
  return (
    <View style={{ gap: 8 }}>
      {trilho.unidades.map((u) => {
        const aberta = u.licoes.some((l) => l.estado !== "bloqueada");
        return (
          <View key={u.id} style={{ gap: 8, paddingBottom: 24 }}>
            <View
              style={[
                aberta ? balao.grande : { borderRadius: raio.md },
                aberta ? { borderTopLeftRadius: 24, borderTopRightRadius: 24, borderBottomRightRadius: 24 } : null,
                { backgroundColor: aberta ? cor.azulMarca : cor.fundoSuave, paddingHorizontal: 18, paddingVertical: 14 },
              ]}
            >
              <Texto v="legenda" forte cor={aberta ? cor.sobreMarca : cor.tintaSuave}>
                Unidade {u.ordem}
              </Texto>
              <Texto accessibilityRole="header" cor={aberta ? cor.sobreMarca : cor.tintaSuave} style={{ fontFamily: fonte.titulo, fontSize: 19, lineHeight: 24 }}>
                {u.titulo}
              </Texto>
            </View>
            <View style={{ alignItems: "center", gap: 18, paddingTop: 14 }}>
              {u.licoes.map((l, i) => {
                const desvio = DESVIOS[indice++ % 8];
                return (
                  <View key={l.id} style={{ alignItems: "center", transform: [{ translateX: desvio }] }}>
                    <No licao={l} ultima={i === u.licoes.length - 1} aoPraticar={() => setPraticar(l)} />
                  </View>
                );
              })}
            </View>
          </View>
        );
      })}
      <PraticarDeNovo licao={praticar} aoFechar={() => setPraticar(null)} />
    </View>
  );
}

function Disco({ estado, children }: { estado: LicaoTrilho["estado"]; children: React.ReactNode }) {
  const fundo = estado === "feita" ? cor.azulMarca : estado === "actual" ? cor.realce : cor.fundoForte;
  return (
    <View style={{ width: 68, height: 74 }}>
      <View style={{ position: "absolute", top: 6, width: 68, height: 68, borderRadius: 34, backgroundColor: SOMBRA[estado] }} />
      <View style={{ width: 68, height: 68, borderRadius: 34, backgroundColor: fundo, alignItems: "center", justifyContent: "center" }}>{children}</View>
    </View>
  );
}

function No({ licao, ultima, aoPraticar }: { licao: LicaoTrilho; ultima: boolean; aoPraticar: () => void }) {
  const { estado } = licao;
  const nome = { feita: "concluída, praticar outra vez", actual: "lição actual", bloqueada: "por abrir" }[estado];
  const rotulo = `${licao.titulo}, ${nome}`;
  const corIcone = estado === "feita" ? cor.sobreMarca : estado === "actual" ? cor.tinta : cor.linhaForte;
  const Icone = estado === "feita" ? Check : ultima ? Trophy : Star;
  const icone = <Icone size={32} color={corIcone} strokeWidth={estado === "feita" ? 3 : 2} />;

  if (estado === "actual") {
    const pct = licao.exercicios ? licao.exercicios_feitos / licao.exercicios : 0;
    const r = 45;
    const per = 2 * Math.PI * r;
    // O balão "Continuar" e o disco são um só alvo de toque (tocar no balão também abre a lição).
    return (
      <Pressable accessibilityRole="link" accessibilityLabel={rotulo} onPress={() => router.push(`/licao/${licao.id}`)} style={({ pressed }) => ({ alignItems: "center", opacity: pressed ? 0.85 : 1 })}>
        <View style={[balao.pequeno, { borderTopLeftRadius: 18, borderTopRightRadius: 18, borderBottomRightRadius: 18, backgroundColor: cor.azulMarca, paddingHorizontal: 16, paddingVertical: 8, marginBottom: 4, maxWidth: 220 }]}>
          <Texto cor={cor.sobreMarca} style={{ fontFamily: fonte.titulo, fontSize: 15, lineHeight: 20 }}>
            {licao.exercicios_feitos ? "Continuar" : "Começar"}
          </Texto>
          <Texto cor={cor.sobreMarca} style={{ fontSize: 13, lineHeight: 18 }}>
            {licao.titulo}
          </Texto>
        </View>
        <View style={{ width: 98, height: 98, alignItems: "center", justifyContent: "center" }}>
          <Svg width={98} height={98} style={{ position: "absolute" }}>
            <Circle cx={49} cy={49} r={r} stroke={cor.fundoForte} strokeWidth={7} fill="none" />
            {pct > 0 ? <Circle cx={49} cy={49} r={r} stroke={cor.azulVivo} strokeWidth={7} fill="none" strokeDasharray={`${per * pct} ${per}`} strokeLinecap="round" rotation={-90} origin="49, 49" /> : null}
          </Svg>
          <View style={{ marginTop: 2 }}>
            <Disco estado="actual">{icone}</Disco>
          </View>
        </View>
      </Pressable>
    );
  }
  if (estado === "feita") {
    return (
      <Pressable accessibilityRole="button" accessibilityLabel={rotulo} onPress={aoPraticar} style={({ pressed }) => ({ opacity: pressed ? 0.85 : 1 })}>
        <Disco estado="feita">{icone}</Disco>
      </Pressable>
    );
  }
  return (
    <View accessible accessibilityRole="image" accessibilityLabel={rotulo}>
      <Disco estado="bloqueada">{icone}</Disco>
    </View>
  );
}

/** Tela PraticarDeNovo: repetir uma lição feita dá pontos e uma vida, sem perder nenhuma. */
function PraticarDeNovo({ licao, aoFechar }: { licao: LicaoTrilho | null; aoFechar: () => void }) {
  return (
    <Dialogo
      aberto={!!licao}
      aoFechar={aoFechar}
      titulo="Praticar outra vez"
      texto={licao ? `Já concluiu "${licao.titulo}". Ao repetir uma lição ganha pontos e recupera uma vida, e não perde nenhuma se errar.` : undefined}
    >
      <View style={{ flexDirection: "row", gap: 12 }}>
        {[
          ["Por lição repetida", "5 pontos"],
          ["Vidas", "Recupera 1"],
        ].map(([dt, dd]) => (
          <View key={dt} style={{ flex: 1, backgroundColor: cor.fundoSuave, borderRadius: raio.md, paddingHorizontal: 14, paddingVertical: 12 }}>
            <Texto v="legenda" suave>
              {dt}
            </Texto>
            <Texto forte>{dd}</Texto>
          </View>
        ))}
      </View>
      <Botao
        larguraTotal
        onPress={() => {
          const id = licao?.id;
          aoFechar();
          if (id) router.push(`/licao/${id}`);
        }}
      >
        Começar a prática
      </Botao>
      <Botao tipo="ligacao" larguraTotal onPress={aoFechar}>
        Agora não
      </Botao>
    </Dialogo>
  );
}

export function EsqueletoTrilho() {
  return (
    <View accessible accessibilityLabel="A carregar o trilho" accessibilityState={{ busy: true }} style={{ alignItems: "center", gap: 20 }}>
      <Osso altura={76} raio={24} />
      {[0, 40, 68, 40, 0].map((d, i) => (
        <Osso key={i} altura={68} largura={68} raio={34} style={{ transform: [{ translateX: d }] }} />
      ))}
    </View>
  );
}
