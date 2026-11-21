/**
 * Pagamentos e recibos (canvas: Recibo + EstadoSemPagamentos; web: user/billing/page.tsx).
 * O recibo pode guardar-se em PDF (expo-print) e partilhar-se (folha de partilha do telemóvel).
 */
import { useLocalSearchParams } from "expo-router";
import * as Print from "expo-print";
import * as Sharing from "expo-sharing";
import { FileDown, Receipt, Share2 } from "lucide-react-native";
import { useState } from "react";
import { Share, View } from "react-native";
import { LinhaPagamento, linhasRecibo, ReciboDoc } from "@/componentes/subscricao/Partes";
import { dataPt, kz, useSubHistoricoQuery, useSubMinhaQuery, useSubReciboQuery, type Recibo } from "@/dominios/subscricao/api";
import { balao, cor, fonte } from "@/tema";
import { ACarregar, Aviso, Botao, Cabecalho, Ecra, EstadoErro, Osso, Texto, Titulo } from "@/ui";

export default function EcraRecibos() {
  const q = useLocalSearchParams<{ recibo?: string }>();
  const historico = useSubHistoricoQuery();
  const { data: sub } = useSubMinhaQuery();
  const lista = historico.data?.payment_history ?? [];
  const comRecibo = lista.filter((p) => p.receipt_number);
  const [escolhido, setEscolhido] = useState<string | null>(typeof q.recibo === "string" && q.recibo ? q.recibo : null);
  const numero = escolhido ?? comRecibo[0]?.receipt_number ?? null;
  const recibo = useSubReciboQuery(numero ?? "", { skip: !numero });
  const [erro, setErro] = useState<string | null>(null);
  const [aGerar, setAGerar] = useState(false);

  const pdf = async (r: Recibo) => {
    setErro(null);
    setAGerar(true);
    try {
      const { uri } = await Print.printToFileAsync({ html: htmlRecibo(r) });
      if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(uri, { mimeType: "application/pdf", dialogTitle: `Recibo ${r.numero_recibo}`, UTI: "com.adobe.pdf" });
      else await Print.printAsync({ uri });
    } catch {
      setErro("Não foi possível criar o PDF. Tente outra vez.");
    } finally {
      setAGerar(false);
    }
  };

  const partilhar = (r: Recibo) =>
    Share.share({
      title: `Recibo ${r.numero_recibo}`,
      message: [`Recibo ${r.numero_recibo} (ProEnglish)`, `Emitido a ${dataPt(r.data_emissao)}`, ...linhasRecibo(r).map(([a, b]) => `${a}: ${b}`), `Total pago: ${kz(r.total_kz)}`].join("\n"),
    }).catch(() => {});

  const vazio = historico.data && !lista.length;
  return (
    <Ecra
      cabecalho={<Cabecalho titulo={vazio ? "Pagamentos" : "Pagamentos e recibos"} subtitulo={vazio && sub ? `Plano ${sub.plan.name}` : recibo.data ? recibo.data.descricao : undefined} />}
      aoActualizar={() => {
        historico.refetch();
        if (numero) recibo.refetch();
      }}
      aActualizar={historico.isFetching && !!historico.data}
      rodape={
        recibo.data ? (
          <View style={{ flexDirection: "row", gap: 10 }}>
            <Botao style={{ flex: 1 }} carregando={aGerar} icone={aGerar ? undefined : <FileDown size={20} color={cor.sobreMarca} />} onPress={() => void pdf(recibo.data!)}>
              PDF
            </Botao>
            <Botao style={{ flex: 1 }} tipo="secundario" icone={<Share2 size={20} color={cor.azulMarca} />} onPress={() => void partilhar(recibo.data!)}>
              Partilhar
            </Botao>
          </View>
        ) : undefined
      }
      style={{ gap: 20 }}
    >
      {historico.isError && !historico.data ? (
        <EstadoErro erro={historico.error} titulo="Não conseguimos carregar os pagamentos" aoTentar={() => historico.refetch()} />
      ) : !historico.data ? (
        <ACarregar linhas={2} altura={200} rotulo="A carregar os pagamentos" />
      ) : vazio ? (
        <View style={{ gap: 18 }}>
          <View style={[balao.grande, { width: 80, height: 80, borderTopLeftRadius: 26, borderTopRightRadius: 26, borderBottomRightRadius: 26, alignItems: "center", justifyContent: "center", backgroundColor: cor.fundoForte }]}>
            <Receipt size={36} color={cor.azulMarca} />
          </View>
          <View style={{ gap: 8 }}>
            <Titulo v="tituloM" style={{ fontSize: 24, lineHeight: 30 }}>
              Ainda não fez nenhum pagamento
            </Titulo>
            <Texto suave>Quando pagar um plano, o recibo aparece aqui.</Texto>
          </View>
          <Botao larguraTotal href="/planos">
            Ver os planos
          </Botao>
          <Botao tipo="secundario" larguraTotal href="/subscricao">
            Tenho um código promocional
          </Botao>
        </View>
      ) : (
        <>
          {!numero ? null : recibo.isError ? (
            <Aviso tom="erro">{`Não encontrámos o recibo ${numero}.`}</Aviso>
          ) : !recibo.data ? (
            <Osso altura={420} />
          ) : (
            <ReciboDoc r={recibo.data} />
          )}
          {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
          <View style={{ gap: 4 }}>
            <Texto accessibilityRole="header" style={{ fontFamily: fonte.tituloMedio, fontSize: 16, lineHeight: 22 }}>
              Todos os pagamentos
            </Texto>
            {lista.map((p) => (
              <LinhaPagamento key={p.id} p={p} activo={!!p.receipt_number && p.receipt_number === numero} aoTocar={p.receipt_number ? () => setEscolhido(p.receipt_number!) : undefined} />
            ))}
            <Texto v="legenda" suave style={{ paddingTop: 8 }}>
              Total pago: {kz(historico.data.summary.total_amount_paid)}.
            </Texto>
          </View>
        </>
      )}
    </Ecra>
  );
}

const esc = (t: string) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** O recibo em HTML para o PDF (as mesmas cores e linhas do ecrã). */
function htmlRecibo(r: Recibo) {
  const linhas = linhasRecibo(r)
    .map(([a, b]) => `<tr><td class="r">${esc(a)}</td><td class="v">${esc(b)}</td></tr>`)
    .join("");
  return `<!doctype html><html lang="pt"><head><meta charset="utf-8"><style>
  body{font-family:-apple-system,Roboto,Helvetica,Arial,sans-serif;color:${cor.tinta};margin:40px;font-size:14px;line-height:1.5}
  h1{font-size:22px;margin:0 0 4px;color:${cor.azulMarca}}
  .marca{font-weight:700;font-size:20px;color:${cor.azulMarca};margin-bottom:24px}
  .suave{color:${cor.tintaSuave}}
  table{width:100%;border-collapse:collapse;margin-top:20px}
  td{padding:10px 0;border-bottom:1px solid ${cor.linha};vertical-align:top}
  td.r{color:${cor.tintaSuave};padding-right:16px}td.v{text-align:right;font-weight:600}
  .total{display:flex;justify-content:space-between;border-top:2px solid ${cor.tinta};margin-top:12px;padding-top:12px;font-size:18px;font-weight:700}
  </style></head><body>
  <div class="marca">ProEnglish</div>
  <h1>Recibo ${esc(r.numero_recibo)}</h1>
  <div class="suave">Emitido a ${esc(dataPt(r.data_emissao))}${r.estado === "pago" ? ". Pago" : ""}</div>
  <table>${linhas}</table>
  <div class="total"><span>Total pago</span><span>${esc(kz(r.total_kz))}</span></div>
  <p class="suave" style="margin-top:24px;font-size:12px">ProEnglish, Luanda, Angola.${r.referencia ? ` Referência Multicaixa ${esc(r.referencia)}.` : ""}</p>
  </body></html>`;
}
