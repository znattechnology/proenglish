import { Crown, Heart, Zap } from "lucide-react-native";
import { useState } from "react";
import { View } from "react-native";
import { voltarAoTrilho } from "@/componentes/licao/Jogador";
import { fmt, kz, tempoAte, useEstadoVidasQuery, useLabPlanosQuery, useRecarregarVidasMutation } from "@/dominios/laboratorio/api";
import { balao, cor, fonte, raio } from "@/tema";
import { Aviso, Botao, Cabecalho, Ecra, EstadoErro, Osso, Seccao, Texto } from "@/ui";

const GANHAR = [
  ["Lição concluída pela primeira vez", "10 pontos"],
  ["Lição repetida", "5 pontos e 1 vida"],
] as const;

/** Loja do laboratório: recarregar vidas com pontos e o Premium (tela Loja). */
export default function Loja() {
  const vidas = useEstadoVidasQuery();
  const planos = useLabPlanosQuery();
  const premium = planos.data?.find((p) => p.plan_type === "PREMIUM");
  const [recarregar, { isLoading: aRecarregar }] = useRecarregarVidasMutation();
  const [mensagem, setMensagem] = useState<{ tom: "certo" | "erro"; texto: string } | null>(null);
  const v = vidas.data;
  const cheias = v ? v.current >= v.maximum : false;
  const tempo = v && !cheias ? tempoAte(v.next_heart_at) : null;

  const aoRecarregar = async () => {
    setMensagem(null);
    const r = await recarregar();
    if ("error" in r && r.error) {
      const c = (r.error as { data?: { error?: string; message?: string } }).data;
      setMensagem({
        tom: "erro",
        texto:
          c?.error === "insufficient_points"
            ? `Precisa de ${v?.refill_cost_points ?? 50} pontos e tem ${fmt(v?.points ?? 0)}. Pratique uma lição já feita para ganhar mais.`
            : c?.error === "hearts_full"
              ? "Já tem as vidas todas."
              : (c?.message ?? "Não foi possível recarregar agora. Tente outra vez."),
      });
      return;
    }
    setMensagem({ tom: "certo", texto: `Vidas recarregadas. Gastou ${r.data!.points_spent} pontos.` });
  };

  return (
    <Ecra
      cabecalho={
        <Cabecalho
          titulo="Loja"
          direita={
            v ? (
              <View accessible accessibilityLabel={`${fmt(v.points)} pontos`} style={{ flexDirection: "row", alignItems: "center", gap: 6, paddingRight: 8 }}>
                <Zap size={22} color={cor.azulVivo} fill={cor.azulVivo} />
                <Texto forte numeros>
                  {fmt(v.points)}
                </Texto>
              </View>
            ) : null
          }
        />
      }
      aoActualizar={() => {
        void vidas.refetch();
        void planos.refetch();
      }}
    >
      <Seccao titulo="Vidas" gap={12}>
        {vidas.isError ? (
          <EstadoErro erro={vidas.error} aoTentar={() => void vidas.refetch()} />
        ) : !v ? (
          <Osso altura={180} />
        ) : v.unlimited ? (
          <View style={{ flexDirection: "row", alignItems: "center", gap: 16, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, padding: 20 }}>
            <Heart size={32} color={cor.vida} fill={cor.vida} />
            <Texto style={{ flex: 1 }}>Tem vidas ilimitadas com o seu plano. Não precisa de recarregar.</Texto>
          </View>
        ) : (
          <View style={{ borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, padding: 20, gap: 16 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 16 }}>
              <View accessible accessibilityLabel={`${v.current} de ${v.maximum} vidas`} style={{ flexDirection: "row", gap: 4 }}>
                {Array.from({ length: v.maximum }, (_, i) => (
                  <Heart key={i} size={28} color={i < v.current ? cor.vida : cor.linhaForte} fill={i < v.current ? cor.vida : "none"} />
                ))}
              </View>
              <View style={{ flex: 1 }}>
                <Texto forte style={{ lineHeight: 22 }}>
                  Tem {v.current} de {v.maximum} vidas
                </Texto>
                <Texto v="legenda" suave>
                  {cheias ? "Está tudo cheio." : tempo ? `A próxima volta daqui a ${tempo}.` : "As vidas voltam com o tempo."}
                </Texto>
              </View>
            </View>
            <Botao larguraTotal disabled={cheias} carregando={aRecarregar} onPress={() => void aoRecarregar()}>
              {aRecarregar ? "A recarregar…" : `Recarregar todas por ${v.refill_cost_points} pontos`}
            </Botao>
            {mensagem ? <Aviso tom={mensagem.tom}>{mensagem.texto}</Aviso> : null}
            {!cheias ? (
              <Botao tipo="ligacao" onPress={voltarAoTrilho}>
                Ou recupere uma vida a praticar uma lição já feita
              </Botao>
            ) : null}
          </View>
        )}
      </Seccao>

      <View style={[balao.grande, { backgroundColor: cor.azulMarca, padding: 24, gap: 14 }]}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
          <Crown size={24} color={cor.realce} />
          <Texto accessibilityRole="header" cor={cor.sobreMarca} style={{ fontFamily: fonte.titulo, fontSize: 20, lineHeight: 26 }}>
            Premium
          </Texto>
        </View>
        <View style={{ gap: 6 }}>
          {["Vidas e lições ilimitadas", premium?.daily_speaking_minutes ? `${premium.daily_speaking_minutes} minutos de conversa com o tutor por dia` : null, premium?.certificates ? "Certificados de conclusão" : null]
            .filter(Boolean)
            .map((t) => (
              <Texto key={t} cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
                {`•  ${t}`}
              </Texto>
            ))}
        </View>
        <Botao tipo="realce" tamanho="medio" larguraTotal href="/planos">
          {premium ? `Subscrever por ${kz(premium.monthly_price)} por mês` : "Ver os planos"}
        </Botao>
      </View>

      <Seccao titulo="Como ganhar pontos">
        <View>
          {GANHAR.map(([o, q], i) => (
            <View key={o} style={{ flexDirection: "row", justifyContent: "space-between", gap: 12, paddingVertical: 10, borderBottomWidth: i < GANHAR.length - 1 ? 1 : 0, borderColor: cor.linha }}>
              <Texto style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>{o}</Texto>
              <Texto forte numeros style={{ fontSize: 15, lineHeight: 22 }}>
                {q}
              </Texto>
            </View>
          ))}
        </View>
      </Seccao>
    </Ecra>
  );
}
