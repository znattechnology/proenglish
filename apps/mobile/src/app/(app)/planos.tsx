/**
 * Escolher o plano: passo 1 do pagamento (web: Checkout.tsx, EscolherPlano).
 * Aceita ?codigo=XXX (vindo da subscrição) e passa-o ao pagamento.
 */
import { router, useLocalSearchParams } from "expo-router";
import { Gift } from "lucide-react-native";
import { useState } from "react";
import { View } from "react-native";
import { Segmentos } from "@/componentes/perfil/Campos";
import { BarraPassos, Vantagens } from "@/componentes/subscricao/Partes";
import { escreverConsulta } from "@/lib/rotasWeb";
import { kz, periodoDoPlano, precoPlano, useSubMinhaQuery, useSubPlanosQuery, type Periodo } from "@/dominios/subscricao/api";
import { cor, fonte, raio } from "@/tema";
import { ACarregar, Aviso, Botao, Cabecalho, Ecra, EstadoErro, Etiqueta, Texto, Titulo } from "@/ui";

export default function EcraPlanos() {
  const q = useLocalSearchParams<{ codigo?: string; periodo?: string }>();
  const codigo = typeof q.codigo === "string" && q.codigo ? q.codigo.toUpperCase() : null;
  const planos = useSubPlanosQuery();
  const { data: sub } = useSubMinhaQuery();
  const [per, setPer] = useState<Periodo>(q.periodo === "anual" ? "anual" : "mensal");
  const pagos = (planos.data ?? []).filter((p) => p.plan_type !== "FREE");
  const desconto = Math.max(0, ...pagos.map((p) => p.yearly_discount_percentage || 0));

  return (
    <Ecra
      cabecalho={
        <>
          <Cabecalho titulo="Escolha o plano" subtitulo="Passo 1 de 3" />
          <BarraPassos passo={1} />
        </>
      }
      aoActualizar={() => planos.refetch()}
      aActualizar={planos.isFetching && !!planos.data}
      style={{ gap: 20 }}
    >
      <Texto suave>Paga em kwanzas com Multicaixa Express. Não há cobranças automáticas.</Texto>
      {codigo ? <Aviso tom="certo">{`O código ${codigo} é aplicado no pagamento, se for válido para o plano escolhido.`}</Aviso> : null}
      {planos.isError && !planos.data ? (
        <EstadoErro erro={planos.error} titulo="Não conseguimos carregar os planos" aoTentar={() => planos.refetch()} />
      ) : !planos.data ? (
        <ACarregar linhas={2} altura={260} rotulo="A carregar os planos" />
      ) : (
        <>
          <Segmentos
            rotulo="Período"
            opcoes={[
              { valor: "mensal", nome: "Mensal" },
              { valor: "anual", nome: desconto ? `Anual, poupa ${Math.round(desconto)}%` : "Anual" },
            ]}
            valor={per}
            aoMudar={setPer}
          />
          {pagos.map((p) => {
            const eActual = p.id === sub?.plan.id;
            const perPlano = periodoDoPlano(p, per);
            const rotulo = eActual && sub?.em_teste ? `Pagar o ${p.name}` : eActual || p.so_renovacao ? `Renovar o ${p.name}` : `Escolher ${p.name}`;
            return (
              <View key={p.id} style={{ gap: 14, padding: 20, borderRadius: raio.md, borderWidth: p.is_most_popular ? 2 : 1, borderColor: p.is_most_popular ? cor.azulMarca : cor.linha }}>
                <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
                  <Titulo v="tituloM">{p.name}</Titulo>
                  {eActual ? <Etiqueta tom="marca">O seu plano</Etiqueta> : p.is_most_popular ? <Etiqueta tom="realce">O mais escolhido</Etiqueta> : null}
                </View>
                <View style={{ flexDirection: "row", alignItems: "baseline", gap: 6 }}>
                  <Texto numeros style={{ fontFamily: fonte.titulo, fontSize: 28, lineHeight: 34 }}>
                    {kz(precoPlano(p, perPlano))}
                  </Texto>
                  <Texto suave>{perPlano === "anual" ? "por ano" : "por mês"}</Texto>
                </View>
                {per === "anual" && perPlano === "mensal" ? (
                  <Texto v="legenda" suave>
                    Este plano só tem pagamento mensal.
                  </Texto>
                ) : null}
                {p.so_renovacao ? (
                  <Texto v="legenda" suave>
                    Já não está à venda, mas pode continuar com ele.
                  </Texto>
                ) : null}
                <Vantagens plano={p} />
                {p.pode_experimentar && p.dias_teste ? (
                  <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                    <Gift size={18} color={cor.certo} />
                    <Texto v="legenda" forte cor={cor.certo} style={{ flex: 1, fontSize: 15 }}>
                      Pode experimentar {p.dias_teste} dias grátis antes de pagar
                    </Texto>
                  </View>
                ) : null}
                <Botao tipo={p.is_most_popular ? "principal" : "secundario"} larguraTotal onPress={() => router.push(`/checkout/${p.plan_type}${escreverConsulta({ periodo: perPlano, codigo })}`)}>
                  {rotulo}
                </Botao>
              </View>
            );
          })}
        </>
      )}
    </Ecra>
  );
}
