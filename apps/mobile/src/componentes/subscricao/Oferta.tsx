/**
 * Oferta de plano nos limites (sem vidas, lições do dia, análises de IA, minutos de conversa,
 * exame oral, certificados). Um só componente em todos os sítios:
 *  - <OfertaPlano>: o plano que a API sugere (nome, preço por mês, ganhos com o primeiro em
 *    destaque) e as acções "Assinar o …" e "Experimentar N dias grátis";
 *  - <FolhaOferta>: o mesmo numa folha de baixo, com a mensagem do limite e a saída gratuita
 *    (esperar, recarregar com pontos, saltar, voltar amanhã) como acção secundária.
 * O cliente nunca decide: sem oferta (null), mostra só a mensagem.
 */
import { router } from "expo-router";
import { Check } from "lucide-react-native";
import type { ReactNode } from "react";
import { ScrollView, useWindowDimensions, View } from "react-native";
import { kz, kzMes, type OfertaPlano as Oferta } from "@/dominios/subscricao/api";
import { balao, cor, fonte, raio } from "@/tema";
import { Botao, Dialogo, Texto } from "@/ui";

/** Para onde vão os botões: o pagamento do plano; com teste, o pagamento abre no teste grátis. */
export function irParaOferta(o: Oferta, teste = false) {
  router.push(`/checkout/${o.plano.tipo}${teste ? "?teste=1" : ""}`);
}

/**
 * O plano sugerido e as duas acções. `antesDeIr` corre antes de navegar (ex.: fechar a folha,
 * para o pagamento não abrir por baixo do modal).
 */
export function OfertaPlano({ oferta: o, antesDeIr }: { oferta: Oferta; antesDeIr?: () => void }) {
  const p = o.plano;
  const teste = p.pode_experimentar && p.dias_teste > 0;
  const [principal, ...resto] = o.ganhos;
  const ir = (comTeste: boolean) => {
    antesDeIr?.();
    irParaOferta(o, comTeste);
  };

  return (
    <View style={{ gap: 12 }}>
      <View
        accessible
        accessibilityLabel={`${p.nome}, ${kzMes(p.preco_mensal_kz)}. ${o.ganhos.join(". ")}.`}
        style={[balao.grande, { backgroundColor: cor.azulMarca, paddingHorizontal: 20, paddingTop: 20, paddingBottom: 22, gap: 14 }]}
      >
        <View style={{ gap: 2 }}>
          <Texto cor={cor.sobreMarca} style={{ fontFamily: fonte.tituloMedio, fontSize: 17, lineHeight: 22 }}>
            {p.nome}
          </Texto>
          <View style={{ flexDirection: "row", alignItems: "baseline", flexWrap: "wrap" }}>
            <Texto numeros cor={cor.realce} style={{ fontFamily: fonte.numero, fontSize: 32, lineHeight: 38, letterSpacing: -0.5 }}>
              {kz(p.preco_mensal_kz)}
            </Texto>
            <Texto cor={cor.sobreMarca} style={{ fontFamily: fonte.textoForte, fontSize: 16, lineHeight: 22 }}>
              /mês
            </Texto>
          </View>
          {p.preco_anual_kz ? (
            <Texto v="legenda" cor={cor.sobreMarca} style={{ opacity: 0.8 }}>
              ou {kz(p.preco_anual_kz)} por ano
            </Texto>
          ) : null}
        </View>

        {principal ? (
          <View style={{ gap: 10 }}>
            {/* O ganho que resolve este limite. */}
            <View style={{ flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: cor.realce, borderRadius: raio.sm, paddingHorizontal: 12, paddingVertical: 10 }}>
              <Check size={20} color={cor.azulMarca} strokeWidth={3} />
              <Texto forte style={{ flex: 1, fontSize: 16, lineHeight: 22 }}>
                {principal}
              </Texto>
            </View>
            {resto.map((g) => (
              <View key={g} style={{ flexDirection: "row", alignItems: "flex-start", gap: 10, paddingHorizontal: 12 }}>
                <Check size={18} color={cor.realce} strokeWidth={2.5} style={{ marginTop: 2 }} />
                <Texto cor={cor.sobreMarca} style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>
                  {g}
                </Texto>
              </View>
            ))}
          </View>
        ) : null}
      </View>

      <Botao larguraTotal onPress={() => ir(false)}>
        {`Assinar o ${p.nome}`}
      </Botao>
      {teste ? (
        <Botao tipo="secundario" larguraTotal onPress={() => ir(true)}>
          {`Experimentar ${p.dias_teste} dias grátis`}
        </Botao>
      ) : null}
    </View>
  );
}

/**
 * Folha de baixo de um limite. `children` são as saídas gratuitas (botões secundário/ligação),
 * que ficam sempre por baixo da oferta. Sem oferta, a folha mostra só a mensagem e as saídas.
 */
export function FolhaOferta({
  aberto,
  aoFechar,
  titulo,
  mensagem,
  oferta,
  children,
}: {
  aberto: boolean;
  aoFechar: () => void;
  titulo: string;
  mensagem?: string | null;
  oferta: Oferta | null | undefined;
  children?: ReactNode;
}) {
  const { height } = useWindowDimensions();
  return (
    <Dialogo aberto={aberto} aoFechar={aoFechar} titulo={titulo} texto={mensagem ?? undefined}>
      {oferta ? (
        <ScrollView style={{ maxHeight: height * 0.62 }} contentContainerStyle={{ gap: 12 }} bounces={false}>
          <OfertaPlano oferta={oferta} antesDeIr={aoFechar} />
          {children}
        </ScrollView>
      ) : (
        children
      )}
    </Dialogo>
  );
}
