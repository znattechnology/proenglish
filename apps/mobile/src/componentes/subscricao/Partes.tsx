/**
 * Peças da subscrição (web: components/pe/subscricao/Partes.tsx): lista de vantagens, linha de
 * pagamento, recibo, resumo da compra e os passos do pagamento.
 */
import { router } from "expo-router";
import { Check, ChevronRight, Receipt } from "lucide-react-native";
import { Pressable, View } from "react-native";
import { dataPt, kz, precoPlano, vantagens, type EntradaHistorico, type Orcamento, type Periodo, type Plano, type Recibo } from "@/dominios/subscricao/api";
import { cor, fonte, raio } from "@/tema";
import { Etiqueta, Logo, Texto } from "@/ui";

/** Lista de vantagens de um plano. `sobreMarca` dentro de um bloco azul. */
export function Vantagens({ plano, sobreMarca }: { plano: Plano; sobreMarca?: boolean }) {
  const c = sobreMarca ? cor.sobreMarca : cor.tinta;
  return (
    <View style={{ gap: 6 }}>
      {vantagens(plano).map((v) => (
        <View key={v} style={{ flexDirection: "row", gap: 8, alignItems: "flex-start" }}>
          <Check size={18} color={sobreMarca ? cor.realce : cor.certo} style={{ marginTop: 2 }} />
          <Texto v="legenda" cor={c} style={{ flex: 1, fontSize: 15, lineHeight: 22 }}>
            {v}
          </Texto>
        </View>
      ))}
    </View>
  );
}

const ESTADOS: Record<string, { texto: string; tom: "certo" | "errado" | "neutro" }> = {
  pago: { texto: "Pago", tom: "certo" },
  recusado: { texto: "Recusado", tom: "errado" },
  expirado: { texto: "Expirou", tom: "neutro" },
  cancelado: { texto: "Cancelado", tom: "neutro" },
  pendente: { texto: "Por confirmar", tom: "neutro" },
};

/** Um pagamento da lista: data, descrição, valor e estado. Com recibo, é tocável. */
export function LinhaPagamento({ p, activo, aoTocar }: { p: EntradaHistorico; activo?: boolean; aoTocar?: () => void }) {
  const estado = ESTADOS[p.status ?? "pago"] ?? ESTADOS.pago;
  const conteudo = (
    <>
      <Receipt size={20} color={cor.tintaSuave} />
      <View style={{ flex: 1 }}>
        <Texto forte style={{ lineHeight: 22 }}>
          {dataPt(p.date)}
        </Texto>
        <Texto v="legenda" suave numberOfLines={2}>
          {p.description}
        </Texto>
      </View>
      <View style={{ alignItems: "flex-end", gap: 4 }}>
        <Texto forte numeros>
          {kz(p.amount_kz)}
        </Texto>
        {estado.texto !== "Pago" ? <Etiqueta tom={estado.tom}>{estado.texto}</Etiqueta> : null}
      </View>
    </>
  );
  const estilo = { flexDirection: "row" as const, alignItems: "center" as const, gap: 12, minHeight: 56, padding: 12, borderRadius: raio.sm, borderBottomWidth: 1, borderColor: cor.linha };
  if (!aoTocar) return <View style={estilo}>{conteudo}</View>;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: !!activo }}
      accessibilityLabel={`${dataPt(p.date)}, ${p.description}, ${kz(p.amount_kz)}, ${estado.texto}`}
      accessibilityHint="Mostra o recibo"
      onPress={aoTocar}
      style={({ pressed }) => [estilo, activo || pressed ? { backgroundColor: cor.fundoSuave } : null]}
    >
      {conteudo}
    </Pressable>
  );
}

/** Linha simples de pagamentos (data e valor), como na subscrição do canvas. */
export function LinhaPagamentoCurta({ p }: { p: EntradaHistorico }) {
  const ir = () => router.push(p.receipt_number ? `/recibos?recibo=${encodeURIComponent(p.receipt_number)}` : "/recibos");
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`${dataPt(p.date, "diaMes")}, ${kz(p.amount_kz)}. Ver o recibo`}
      onPress={ir}
      style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 12, minHeight: 52, borderBottomWidth: 1, borderColor: cor.fundoForte, backgroundColor: pressed ? cor.fundoSuave : "transparent" })}
    >
      <Texto style={{ flex: 1 }}>{dataPt(p.date)}</Texto>
      <Texto forte numeros>
        {kz(p.amount_kz)}
      </Texto>
      <ChevronRight size={18} color={cor.tintaSuave} />
    </Pressable>
  );
}

/** Linhas do recibo (as mesmas da web). */
export function linhasRecibo(r: Recibo): [string, string][] {
  return [
    ["Cliente", r.cliente.nome],
    ["Email", r.cliente.email],
    ["Descrição", r.descricao],
    ...(r.validade ? ([["Período", `${dataPt(r.validade.inicio, "diaMes")} a ${dataPt(r.validade.fim)}`]] as [string, string][]) : []),
    ["Quantidade", String(r.quantidade)],
    ["Pago com", r.telefone_mascarado ? `${r.metodo}, ${r.telefone_mascarado}` : r.metodo],
    ...(r.desconto_kz || r.credito_kz ? ([["Subtotal", kz(r.subtotal_kz)]] as [string, string][]) : []),
    ...(r.desconto_kz ? ([[`Código ${r.codigo_promocional ?? ""}`.trim(), `menos ${kz(r.desconto_kz)}`]] as [string, string][]) : []),
    ...(r.credito_kz ? ([[r.credito_descricao ?? "Crédito do plano anterior", `menos ${kz(r.credito_kz)}`]] as [string, string][]) : []),
  ];
}

export function ReciboDoc({ r }: { r: Recibo }) {
  const linhas = linhasRecibo(r);
  return (
    <View accessibilityLabel={`Recibo ${r.numero_recibo}`} style={{ borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, padding: 20, gap: 16 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <Logo altura={36} />
        {r.estado === "pago" ? <Etiqueta tom="certo">Pago</Etiqueta> : <Etiqueta tom="neutro">{ESTADOS[r.estado]?.texto ?? r.estado}</Etiqueta>}
      </View>
      <View style={{ gap: 2 }}>
        <Texto accessibilityRole="header" v="tituloM" numeros>
          Recibo {r.numero_recibo}
        </Texto>
        <Texto v="legenda" suave style={{ fontSize: 15 }}>
          Emitido a {dataPt(r.data_emissao)}
        </Texto>
      </View>
      <View>
        {linhas.map(([dt, dd], i) => (
          <View key={dt} style={{ flexDirection: "row", justifyContent: "space-between", gap: 16, paddingVertical: 10, borderBottomWidth: i === linhas.length - 1 ? 0 : 1, borderColor: cor.linha }}>
            <Texto suave>{dt}</Texto>
            <Texto forte style={{ flex: 1, textAlign: "right" }}>
              {dd}
            </Texto>
          </View>
        ))}
      </View>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", paddingTop: 12, borderTopWidth: 2, borderColor: cor.tinta }}>
        <Texto forte>Total pago</Texto>
        <Texto v="tituloM" numeros>
          {kz(r.total_kz)}
        </Texto>
      </View>
      <Texto v="mini" suave style={{ fontSize: 13, lineHeight: 18 }}>
        ProEnglish, Luanda, Angola.{r.referencia ? ` Referência Multicaixa ${r.referencia}.` : ""}
      </Texto>
    </View>
  );
}

/**
 * Resumo da compra (fundo suave, como no canvas): preço, código, crédito e "A pagar hoje".
 * Com orçamento do servidor, é ele que manda.
 */
export function ResumoCompra({
  plano,
  periodo,
  orcamento,
  desconto,
  codigo,
  credito,
  aoMudarPlano,
}: {
  plano: Plano;
  periodo: Periodo;
  orcamento?: Orcamento;
  desconto?: number;
  codigo?: string | null;
  credito?: { kz: number; plano?: string | null; dias?: number } | null;
  aoMudarPlano?: () => void;
}) {
  const preco = precoPlano(plano, periodo);
  const linhas = orcamento
    ? orcamento.linhas
    : [
        { tipo: "plano", descricao: periodo === "anual" ? "Anuidade" : "Mensalidade", valor_kz: preco },
        ...(desconto ? [{ tipo: "codigo", descricao: `Código ${codigo ?? ""}`.trim(), valor_kz: -desconto }] : []),
        ...(credito?.kz ? [{ tipo: "credito", descricao: `Crédito do ${credito.plano ?? "plano actual"}${credito.dias ? ` (${credito.dias} dias por usar)` : ""}`, valor_kz: -credito.kz }] : []),
      ];
  const total = orcamento ? orcamento.final_kz : Math.max(0, preco - (desconto ?? 0) - (credito?.kz ?? 0));
  return (
    <View style={{ backgroundColor: cor.fundoSuave, borderRadius: raio.md, paddingVertical: 18, paddingHorizontal: 20, gap: 10 }}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <Texto accessibilityRole="header" style={{ fontFamily: fonte.tituloMedio, fontSize: 18, lineHeight: 24, flex: 1 }}>
          Plano {plano.name}
        </Texto>
        {aoMudarPlano ? (
          <Pressable accessibilityRole="button" onPress={aoMudarPlano} hitSlop={8} style={{ minHeight: 44, justifyContent: "center" }}>
            <Texto forte v="legenda" cor={cor.azulMarca} style={{ fontSize: 15, textDecorationLine: "underline" }}>
              Mudar
            </Texto>
          </Pressable>
        ) : null}
      </View>
      <View style={{ gap: 6 }}>
        {linhas.map((l) => (
          <View key={l.tipo + l.descricao} style={{ flexDirection: "row", justifyContent: "space-between", gap: 12 }}>
            <Texto suave style={{ flex: 1 }}>
              {l.descricao}
            </Texto>
            <Texto numeros forte={l.valor_kz < 0} cor={l.valor_kz < 0 ? cor.certo : cor.tinta}>
              {l.valor_kz < 0 ? `menos ${kz(-l.valor_kz)}` : kz(l.valor_kz)}
            </Texto>
          </View>
        ))}
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: 12, paddingTop: 8, borderTopWidth: 1, borderColor: cor.linha }}>
          <Texto forte>A pagar hoje</Texto>
          <Texto numeros style={{ fontFamily: fonte.titulo, fontSize: 20, lineHeight: 26 }}>
            {kz(total)}
          </Texto>
        </View>
      </View>
      {orcamento?.dias_extra ? (
        <Texto v="legenda" cor={cor.certo}>
          O crédito que sobra dá mais {orcamento.dias_extra} {orcamento.dias_extra === 1 ? "dia" : "dias"} de {plano.name}.
        </Texto>
      ) : null}
      <Texto v="legenda" suave>
        {orcamento?.credito_kz
          ? `Os dias que ainda tinha no ${orcamento.credito_plano?.nome ?? "plano actual"} passam a desconto. O ${plano.name} começa já e dura até ${dataPt(orcamento.termina_em)}.`
          : orcamento?.termina_em
            ? `Válido até ${dataPt(orcamento.termina_em, "diaMes")}. Não há cobranças automáticas: avisamos antes de terminar.`
            : `Dura ${periodo === "anual" ? "um ano" : "um mês"}. Não há cobranças automáticas: avisamos antes de terminar para renovar.`}
      </Texto>
      {orcamento?.aviso_codigo ? (
        <Texto v="legenda" suave>
          {orcamento.aviso_codigo}
        </Texto>
      ) : null}
    </View>
  );
}

/** "Passo 2 de 3" com as três barras do canvas. */
export function BarraPassos({ passo }: { passo: 1 | 2 | 3 }) {
  return (
    <View accessibilityRole="progressbar" accessibilityLabel={`Passo ${passo} de 3`} accessibilityValue={{ min: 1, max: 3, now: passo }} style={{ flexDirection: "row", gap: 6, paddingHorizontal: 20, paddingTop: 12 }}>
      {[1, 2, 3].map((n) => (
        <View key={n} style={{ flex: 1, height: 6, borderRadius: raio.pilula, backgroundColor: n <= passo ? cor.azulMarca : cor.fundoForte }} />
      ))}
    </View>
  );
}
