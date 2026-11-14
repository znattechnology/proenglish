/**
 * Pagamento por Multicaixa Express (simulado, em kwanzas). Canvas: CheckoutPagamento,
 * CheckoutAguardar, CheckoutConcluido, CheckoutRecusado. Web: components/pe/subscricao/Checkout.tsx.
 *
 * /checkout/PREMIUM?periodo=anual&codigo=BEMVINDO
 *  - pagamento: número de telefone, código promocional, teste grátis (se houver)
 *  - a aguardar: consulta o estado a cada 2 s até ficar pago, recusado, expirado ou cancelado
 *  - concluído / recusado
 */
import { skipToken } from "@reduxjs/toolkit/query/react";
import { router, useLocalSearchParams } from "expo-router";
import { CalendarClock, CheckCircle2, Gift, LockKeyhole, Smartphone, XCircle } from "lucide-react-native";
import { useEffect, useState } from "react";
import { TextInput, View } from "react-native";
import { codigoErro, mensagemErro } from "@/api/erros";
import { CampoTelefone, Segmentos } from "@/componentes/perfil/Campos";
import { BarraPassos, ResumoCompra, Vantagens } from "@/componentes/subscricao/Partes";
import {
  dataPt,
  kz,
  numeroMcx,
  periodoDoPlano,
  precoPlano,
  telefoneLegivel,
  useSubAtivarSemPagamentoMutation,
  useSubCancelarPagamentoMutation,
  useSubCriarPagamentoMutation,
  useSubIniciarTesteMutation,
  useSubMinhaQuery,
  useSubOrcamentoQuery,
  useSubPagamentoQuery,
  useSubPlanosQuery,
  type Orcamento,
  type Pagamento,
  type Periodo,
  type Plano,
  type TesteIniciado,
} from "@/dominios/subscricao/api";
import { useSessao } from "@/sessao/ContextoSessao";
import { balao, cor, fonte, raio } from "@/tema";
import { ACarregar, Aviso, BalaoFala, BarraProgresso, Botao, Cabecalho, Ecra, EstadoErro, EstadoVazio, Etiqueta, Texto, Titulo } from "@/ui";

const AJUDA_TELEFONE = "Escreva os 9 dígitos do número, a começar por 9. Por exemplo: 923 456 789.";

function CabecalhoPagamento({ passo = 2 }: { passo?: 1 | 2 | 3 }) {
  return (
    <>
      <Cabecalho titulo="Pagamento" subtitulo={`Passo ${passo} de 3`} />
      <BarraPassos passo={passo} />
    </>
  );
}

export default function EcraCheckout() {
  const q = useLocalSearchParams<{ plano?: string; periodo?: string; codigo?: string }>();
  const tipo = String(q.plano ?? "").toUpperCase();
  const [periodoPedido, setPeriodoPedido] = useState<Periodo>(q.periodo === "anual" ? "anual" : "mensal");
  const [codigo, setCodigo] = useState<string | null>(typeof q.codigo === "string" && q.codigo ? q.codigo.toUpperCase() : null);
  const [pagamentoId, setPagamentoId] = useState<string | null>(null);
  const [teste, setTeste] = useState<TesteIniciado | null>(null);

  const planos = useSubPlanosQuery();
  const plano = planos.data?.find((p) => p.plan_type === tipo && p.plan_type !== "FREE");
  // Um plano sem preço anual paga-se sempre ao mês.
  const periodo: Periodo = plano ? periodoDoPlano(plano, periodoPedido) : periodoPedido;

  if (planos.isError && !planos.data)
    return (
      <Ecra cabecalho={<CabecalhoPagamento />}>
        <EstadoErro erro={planos.error} titulo="Não conseguimos carregar os planos" aoTentar={() => planos.refetch()} />
      </Ecra>
    );
  if (!planos.data)
    return (
      <Ecra cabecalho={<CabecalhoPagamento />}>
        <ACarregar linhas={3} altura={120} />
      </Ecra>
    );
  if (!plano)
    return (
      <Ecra cabecalho={<CabecalhoPagamento passo={1} />}>
        <EstadoVazio
          titulo="Este plano não está disponível"
          texto="Escolha um dos planos que estão à venda."
          accao={
            <Botao href="/planos" substituir>
              Ver os planos
            </Botao>
          }
        />
      </Ecra>
    );

  if (teste) return <TesteComecou teste={teste} plano={plano} />;
  if (pagamentoId) return <AcompanharPagamento id={pagamentoId} plano={plano} periodo={periodo} aoRecomecar={() => setPagamentoId(null)} aoNovoPagamento={setPagamentoId} />;

  return (
    <FormularioPagamento
      plano={plano}
      periodo={periodo}
      codigo={codigo}
      aoMudarCodigo={setCodigo}
      aoMudarPeriodo={setPeriodoPedido}
      aoCriado={setPagamentoId}
      aoTeste={setTeste}
    />
  );
}

/* ------------------------------------------------------------------ */
/* Passo 2: número, código e teste grátis                              */
/* ------------------------------------------------------------------ */
function FormularioPagamento({
  plano,
  periodo,
  codigo,
  aoMudarCodigo,
  aoMudarPeriodo,
  aoCriado,
  aoTeste,
}: {
  plano: Plano;
  periodo: Periodo;
  codigo: string | null;
  aoMudarCodigo: (c: string | null) => void;
  aoMudarPeriodo: (p: Periodo) => void;
  aoCriado: (id: string) => void;
  aoTeste: (t: TesteIniciado) => void;
}) {
  const { utilizador } = useSessao();
  // O servidor calcula tudo: preço, código, crédito dos dias já pagos e o que fica a pagar.
  const orc = useSubOrcamentoQuery({ plano: plano.plan_type, periodo, codigo });
  const o = orc.data;
  const [criar, { isLoading: aCriar }] = useSubCriarPagamentoMutation();
  const [ativar, { isLoading: aAtivar }] = useSubAtivarSemPagamentoMutation();
  const [telefone, setTelefone] = useState(() => {
    const guardado = numeroMcx.get();
    const doPerfil = (utilizador?.phone ?? "").startsWith("+244") ? (utilizador?.phone ?? "").slice(4) : "";
    return telefoneLegivel(guardado || doPerfil);
  });
  const [erro, setErro] = useState<{ campo?: boolean; texto: string } | null>(null);
  const digitos = telefone.replace(/\D/g, "").replace(/^244/, "");
  const valido = /^9\d{8}$/.test(digitos);

  const pagar = async () => {
    if (!o) return;
    setErro(null);
    if (!o.requer_pagamento) {
      const r = await ativar({ planId: plano.id, periodo, codigo: o.codigo?.codigo ?? null });
      if ("error" in r && r.error) return setErro({ texto: mensagemErro(r.error, "Não foi possível activar o plano. Tente outra vez.") });
      return aoCriado(r.data.id);
    }
    if (!valido) return setErro({ campo: true, texto: AJUDA_TELEFONE });
    const r = await criar({ planId: plano.id, periodo, telefone: digitos, codigo: o.codigo?.codigo ?? null });
    if ("error" in r && r.error) return setErro({ campo: codigoErro(r.error) === "telefone_invalido", texto: mensagemErro(r.error, "Não foi possível enviar o pedido. Tente outra vez.") });
    numeroMcx.set(digitos);
    aoCriado(r.data.id);
  };

  const podePagar = !!o && o.pode_comprar;
  return (
    <Ecra
      cabecalho={<CabecalhoPagamento />}
      aoActualizar={() => orc.refetch()}
      aActualizar={orc.isFetching && !!o}
      rodape={
        podePagar ? (
          <Botao larguraTotal carregando={aCriar || aAtivar} onPress={() => void pagar()}>
            {!o.requer_pagamento ? (aAtivar ? "A activar…" : `Activar o ${plano.name}`) : aCriar ? "A enviar o pedido…" : `Pagar ${kz(o.final_kz)}`}
          </Botao>
        ) : undefined
      }
      style={{ gap: 20 }}
    >
      {orc.isError && !o ? (
        <EstadoErro erro={orc.error} titulo="Não conseguimos calcular o preço" aoTentar={() => orc.refetch()} />
      ) : !o ? (
        <ACarregar linhas={2} altura={150} rotulo="A calcular o preço" />
      ) : !o.pode_comprar ? (
        <>
          <Aviso tom="info">{o.motivo_bloqueio ?? "Este plano não está disponível agora."}</Aviso>
          <Botao tipo="secundario" larguraTotal href="/subscricao" substituir>
            Voltar à subscrição
          </Botao>
        </>
      ) : (
        <>
          {o.operacao === "conversao_teste" && o.teste_termina_em ? (
            <Aviso tom="info">
              {`Está a experimentar o ${plano.name} até ${dataPt(o.teste_termina_em, "diaMes")}. Se pagar agora, o período pago só começa no fim do teste: não perde nenhum dia.`}
            </Aviso>
          ) : null}

          <ResumoCompra plano={plano} periodo={periodo} orcamento={o} aoMudarPlano={() => (router.canGoBack() ? router.back() : router.replace("/planos"))} />
          <Codigo o={o} codigo={codigo} aoMudar={aoMudarCodigo} />

          {Number(plano.yearly_price) > 0 ? (
            <Segmentos
              rotulo="Período"
              opcoes={[
                { valor: "mensal", nome: "Mensal" },
                { valor: "anual", nome: plano.yearly_discount_percentage ? `Anual, poupa ${Math.round(plano.yearly_discount_percentage)}%` : "Anual" },
              ]}
              valor={periodo}
              aoMudar={aoMudarPeriodo}
            />
          ) : null}

          {!o.requer_pagamento ? (
            <Aviso tom="certo">
              {o.credito_kz ? `Os dias que ainda tinha no ${o.credito_plano?.nome ?? "plano actual"} cobrem o preço. Não paga nada hoje.` : "O código cobre o preço. Não paga nada hoje."}
            </Aviso>
          ) : (
            <View style={{ gap: 12 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
                <View style={[balao.pequeno, { width: 40, height: 40, borderTopLeftRadius: 14, borderTopRightRadius: 14, borderBottomRightRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: cor.azulMarca }]}>
                  <Smartphone size={20} color={cor.sobreMarca} />
                </View>
                <View style={{ flex: 1 }}>
                  <Texto style={{ fontFamily: fonte.tituloMedio, fontSize: 18, lineHeight: 24 }}>Multicaixa Express</Texto>
                  <Texto v="legenda" suave>
                    Pagamento em kwanzas, confirmado no telemóvel
                  </Texto>
                </View>
              </View>
              <CampoTelefone
                rotulo="Número com Multicaixa Express"
                valor={telefone}
                aoMudar={(v) => {
                  setErro(null);
                  setTelefone(v);
                }}
                erro={erro?.campo ? erro.texto : null}
                ajuda="Vai receber um pedido de pagamento na app Multicaixa Express. Tem 5 minutos para o confirmar."
              />
              <View style={{ flexDirection: "row", gap: 8, alignItems: "flex-start" }}>
                <LockKeyhole size={16} color={cor.tintaSuave} style={{ marginTop: 2 }} />
                <Texto v="legenda" suave style={{ flex: 1 }}>
                  Confirma o pagamento na app Multicaixa Express do seu telemóvel. Não há cobranças automáticas.
                </Texto>
              </View>
            </View>
          )}

          {erro && !erro.campo ? <Aviso tom="erro">{erro.texto}</Aviso> : null}

          {o.pode_experimentar && o.dias_teste > 0 ? <OfertaTeste plano={plano} dias={o.dias_teste} telefone={telefone} aoMudarTelefone={setTelefone} aoComecar={aoTeste} /> : null}
        </>
      )}
    </Ecra>
  );
}

/** Código promocional: o servidor diz no orçamento se é válido e quanto desconta. */
function Codigo({ o, codigo, aoMudar }: { o: Orcamento; codigo: string | null; aoMudar: (c: string | null) => void }) {
  const [aberto, setAberto] = useState(false);
  const [texto, setTexto] = useState("");
  const [foco, setFoco] = useState(false);
  const valido = o.codigo?.codigo ?? null;
  const aplicar = () => {
    const c = texto.trim().toUpperCase();
    if (!c) return;
    aoMudar(c);
    setAberto(false);
    setTexto("");
  };

  if (o.erro_codigo && codigo)
    return (
      <View style={{ gap: 2 }}>
        <Texto v="legenda" forte cor={cor.errado} accessibilityRole="alert">
          Código {codigo}: {o.erro_codigo.mensagem}
        </Texto>
        <Botao tipo="ligacao" tamanho="pequeno" onPress={() => aoMudar(null)}>
          Tirar o código
        </Botao>
      </View>
    );
  if (aberto)
    return (
      <View style={{ gap: 6 }}>
        <Texto v="rotulo">Código promocional</Texto>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <TextInput
            accessibilityLabel="Código promocional"
            value={texto}
            onChangeText={setTexto}
            autoCapitalize="characters"
            autoCorrect={false}
            autoFocus
            returnKeyType="done"
            onSubmitEditing={aplicar}
            onFocus={() => setFoco(true)}
            onBlur={() => setFoco(false)}
            style={{ flex: 1, minHeight: 48, paddingHorizontal: 12, fontFamily: fonte.texto, fontSize: 16, color: cor.tinta, borderWidth: foco ? 2 : 1.5, borderColor: foco ? cor.azulVivo : cor.linhaForte, borderRadius: raio.sm }}
          />
          <Botao tipo="secundario" tamanho="medio" disabled={!texto.trim()} onPress={aplicar}>
            Aplicar
          </Botao>
        </View>
      </View>
    );
  if (valido)
    return (
      <View style={{ gap: 2 }}>
        {o.codigo?.descricao ? (
          <Texto v="legenda" cor={cor.certo}>
            <Texto v="legenda" forte cor={cor.certo}>
              Código {valido}:
            </Texto>{" "}
            {o.codigo.descricao.replace(/\.$/, "")}
            {o.codigo.continua ? " (continua nesta renovação)" : ""}.
          </Texto>
        ) : null}
        <Botao tipo="ligacao" tamanho="pequeno" onPress={() => aoMudar(null)}>
          {`Remover o código ${valido}`}
        </Botao>
      </View>
    );
  return (
    <Botao tipo="ligacao" tamanho="pequeno" onPress={() => setAberto(true)}>
      Tenho um código promocional
    </Botao>
  );
}

/** Teste grátis: só para quem nunca experimentou nem pagou. Um teste por número. */
function OfertaTeste({ plano, dias, telefone, aoMudarTelefone, aoComecar }: { plano: Plano; dias: number; telefone: string; aoMudarTelefone: (v: string) => void; aoComecar: (t: TesteIniciado) => void }) {
  const [iniciar, { isLoading }] = useSubIniciarTesteMutation();
  const [erro, setErro] = useState<{ campo?: boolean; texto: string } | null>(null);
  const digitos = telefone.replace(/\D/g, "").replace(/^244/, "");

  const comecar = async () => {
    if (!/^9\d{8}$/.test(digitos)) return setErro({ campo: true, texto: AJUDA_TELEFONE });
    setErro(null);
    const r = await iniciar({ plano: plano.plan_type, telefone: digitos });
    if ("error" in r && r.error) {
      const c = codigoErro(r.error) ?? "";
      return setErro({ campo: c.startsWith("telefone"), texto: mensagemErro(r.error, "Não foi possível começar o teste. Tente outra vez.") });
    }
    numeroMcx.set(digitos);
    aoComecar(r.data);
  };

  return (
    <View style={{ gap: 14, padding: 18, borderRadius: raio.md, borderWidth: 2, borderColor: cor.certo, backgroundColor: cor.certoSuave }}>
      <View style={{ flexDirection: "row", gap: 12, alignItems: "flex-start" }}>
        <View style={{ width: 40, height: 40, borderTopLeftRadius: 14, borderTopRightRadius: 14, borderBottomRightRadius: 14, borderBottomLeftRadius: 0, alignItems: "center", justifyContent: "center", backgroundColor: cor.fundo }}>
          <Gift size={20} color={cor.certo} />
        </View>
        <View style={{ flex: 1, gap: 4 }}>
          <Texto accessibilityRole="header" style={{ fontFamily: fonte.tituloMedio, fontSize: 18, lineHeight: 24 }}>
            Ou experimente o {plano.name} {dias} dias grátis
          </Texto>
          <Texto v="legenda" style={{ fontSize: 15, lineHeight: 22 }}>
            Não paga nada agora. No fim do teste, pague com Multicaixa Express para continuar. Se não pagar, a conta volta ao Gratuito e o seu progresso fica guardado.
          </Texto>
        </View>
      </View>
      <Texto v="legenda" suave>
        Com o número acima. Cada número só dá direito a um teste grátis.
      </Texto>
      {erro?.campo ? (
        <CampoTelefone rotulo="Número com Multicaixa Express" valor={telefone} aoMudar={aoMudarTelefone} erro={erro.texto} />
      ) : erro ? (
        <Aviso tom="erro">{erro.texto}</Aviso>
      ) : null}
      <Botao tipo="secundario" larguraTotal carregando={isLoading} onPress={() => void comecar()}>
        {isLoading ? "A começar o teste…" : `Experimentar ${dias} dias grátis`}
      </Botao>
    </View>
  );
}

function TesteComecou({ teste, plano }: { teste: TesteIniciado; plano: Plano }) {
  return (
    <Ecra
      semScroll={false}
      rodape={
        <>
          <Botao tipo="realce" larguraTotal onPress={() => router.replace("/inicio")}>
            Começar a aprender
          </Botao>
          <Botao tipo="ligacao" larguraTotal onPress={() => router.replace("/subscricao")}>
            Ver a subscrição
          </Botao>
        </>
      }
      style={{ gap: 20, paddingTop: 40 }}
    >
      <View style={[balao.medio, { width: 56, height: 56, alignItems: "center", justifyContent: "center", backgroundColor: cor.certoSuave }]}>
        <CalendarClock size={28} color={cor.certo} />
      </View>
      <Titulo v="tituloL" accessibilityLiveRegion="polite">
        O seu teste do {plano.name} começou
      </Titulo>
      <Texto v="corpoL">
        Tem o {plano.name} grátis até {dataPt(teste.teste_termina_em, "diaMes")}. Dois dias antes do fim, avisamos para pagar com Multicaixa Express. Se não pagar, a conta volta ao Gratuito e o seu progresso
        fica guardado.
      </Texto>
    </Ecra>
  );
}

/* ------------------------------------------------------------------ */
/* Aguardar, concluído ou falhou                                       */
/* ------------------------------------------------------------------ */
function AcompanharPagamento({ id, plano, periodo, aoRecomecar, aoNovoPagamento }: { id: string; plano: Plano; periodo: Periodo; aoRecomecar: () => void; aoNovoPagamento: (id: string) => void }) {
  const [pendente, setPendente] = useState(true);
  // Pergunta a cada 2 s enquanto o pagamento está por confirmar (mesmo com a app em segundo plano).
  const { data: p, isError, refetch } = useSubPagamentoQuery(id ?? skipToken, { pollingInterval: pendente ? 2000 : 0, skipPollingIfUnfocused: false });
  if (p && (p.estado === "pendente") !== pendente) setPendente(p.estado === "pendente");

  if (isError && !p)
    return (
      <Ecra cabecalho={<CabecalhoPagamento />}>
        <EstadoErro
          titulo="Não encontrámos este pagamento"
          aoTentar={() => refetch()}
          outra={
            <>
              <Texto suave>Se pagou, o plano aparece na sua subscrição em poucos minutos.</Texto>
              <Botao tipo="secundario" larguraTotal onPress={aoRecomecar}>
                Começar de novo
              </Botao>
            </>
          }
        />
      </Ecra>
    );
  if (!p)
    return (
      <Ecra cabecalho={<CabecalhoPagamento />}>
        <ACarregar linhas={3} />
      </Ecra>
    );
  if (p.estado === "pago") return <Concluido p={p} plano={plano} />;
  if (p.estado === "pendente") return <Aguardar p={p} plano={plano} periodo={periodo} aoOutroNumero={aoRecomecar} aoNovoPagamento={aoNovoPagamento} />;
  return <Falhou p={p} plano={plano} periodo={periodo} aoOutroNumero={aoRecomecar} aoNovoPagamento={aoNovoPagamento} />;
}

function useReenviar(p: Pagamento, aoNovoPagamento: (id: string) => void) {
  const [criar, { isLoading }] = useSubCriarPagamentoMutation();
  const [erro, setErro] = useState<string | null>(null);
  const reenviar = async (planoId: string, periodo: Periodo) => {
    setErro(null);
    const telefone = numeroMcx.get();
    if (!telefone) return setErro("Escreva o número outra vez para enviar um novo pedido.");
    const r = await criar({ planId: planoId, periodo, telefone, codigo: p.codigo_promocional });
    if ("error" in r && r.error) return setErro(mensagemErro(r.error, "Não foi possível enviar o pedido. Tente outra vez."));
    aoNovoPagamento(r.data.id);
  };
  return { reenviar, aEnviar: isLoading, erro };
}

function useRelogio(expira: string | null) {
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const total = 5 * 60_000;
  const falta = expira ? Math.max(0, new Date(expira).getTime() - agora) : total;
  return { pct: (100 * falta) / total, texto: `${Math.floor(falta / 60_000)}:${String(Math.floor((falta % 60_000) / 1000)).padStart(2, "0")}` };
}

type PropsEstado = { p: Pagamento; plano: Plano; periodo: Periodo; aoOutroNumero: () => void; aoNovoPagamento: (id: string) => void };

function Aguardar({ p, plano, periodo, aoOutroNumero, aoNovoPagamento }: PropsEstado) {
  const relogio = useRelogio(p.expira_em);
  const { reenviar, aEnviar, erro } = useReenviar(p, aoNovoPagamento);
  const [cancelar, { isLoading: aCancelar }] = useSubCancelarPagamentoMutation();
  const numero = numeroMcx.get() ? telefoneLegivel(numeroMcx.get()) : p.telefone_mascarado;
  const passos = [`Abra a app Multicaixa Express no telemóvel ${numero ?? ""}.`, `Aceite o pedido de ${kz(p.total_kz)} para ProEnglish.`, "Este ecrã avança sozinho quando o pagamento for confirmado."];

  return (
    <Ecra
      cabecalho={<CabecalhoPagamento />}
      rodape={
        <>
          <Botao tipo="secundario" larguraTotal carregando={aEnviar} onPress={() => void reenviar(plano.id, periodo)}>
            {aEnviar ? "A enviar…" : "Enviar o pedido outra vez"}
          </Botao>
          <Botao
            tipo="ligacao"
            larguraTotal
            disabled={aCancelar}
            onPress={async () => {
              await cancelar(p.id);
              aoOutroNumero();
            }}
          >
            Usar outro número
          </Botao>
        </>
      }
      style={{ gap: 22, paddingTop: 32 }}
    >
      <BalaoFala style={{ flexDirection: "row", alignItems: "center", gap: 14, paddingVertical: 18, paddingHorizontal: 20 }}>
        <View style={{ width: 44, height: 44, borderTopLeftRadius: 16, borderTopRightRadius: 16, borderBottomRightRadius: 16, borderBottomLeftRadius: 0, alignItems: "center", justifyContent: "center", backgroundColor: cor.realce }}>
          <Smartphone size={24} color={cor.tinta} />
        </View>
        <View style={{ flex: 1 }} accessibilityLiveRegion="polite">
          <Texto cor={cor.sobreMarca} style={{ fontFamily: fonte.titulo, fontSize: 20, lineHeight: 26 }}>
            Confirme no seu telemóvel
          </Texto>
          <Texto v="legenda" cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
            Enviámos um pedido de {kz(p.total_kz)}.
          </Texto>
        </View>
      </BalaoFala>
      <View style={{ gap: 12 }}>
        {passos.map((t, i) => (
          <View key={t} style={{ flexDirection: "row", gap: 12, alignItems: "flex-start" }}>
            <View style={{ width: 28, height: 28, borderTopLeftRadius: 10, borderTopRightRadius: 10, borderBottomRightRadius: 10, borderBottomLeftRadius: 0, alignItems: "center", justifyContent: "center", backgroundColor: cor.azulMarca }}>
              <Texto cor={cor.sobreMarca} style={{ fontFamily: fonte.titulo, fontSize: 14, lineHeight: 18 }}>
                {i + 1}
              </Texto>
            </View>
            <Texto style={{ flex: 1 }}>{t}</Texto>
          </View>
        ))}
      </View>
      <View style={{ gap: 8 }}>
        <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
          <Texto v="legenda" style={{ fontSize: 15 }}>
            Tempo para confirmar
          </Texto>
          <Texto v="rotulo" numeros>
            {relogio.texto}
          </Texto>
        </View>
        <BarraProgresso valor={relogio.pct} rotulo="Tempo restante para confirmar" />
      </View>
      {p.simulado ? (
        <Aviso tom="info">Pagamento de teste: ainda não há ligação real ao Multicaixa Express. O pedido confirma-se sozinho em poucos segundos. Números terminados em 0000 são recusados e em 1111 expiram.</Aviso>
      ) : null}
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
      <ResumoCompra plano={plano} periodo={periodo} desconto={p.desconto_kz} codigo={p.codigo_promocional} credito={p.credito_kz ? { kz: p.credito_kz, plano: p.credito_plano?.nome, dias: p.credito_dias_restantes } : null} />
    </Ecra>
  );
}

function Falhou({ p, plano, periodo, aoOutroNumero, aoNovoPagamento }: PropsEstado) {
  const { reenviar, aEnviar, erro } = useReenviar(p, aoNovoPagamento);
  const titulo = p.estado === "recusado" ? "O pagamento foi recusado" : p.estado === "expirado" ? "O pedido expirou" : "O pedido foi cancelado";
  const texto =
    p.estado === "recusado"
      ? `O pedido foi recusado no telemóvel ${p.telefone_mascarado ?? ""}. Não foi cobrado nada.`
      : p.estado === "expirado"
        ? "Passaram 5 minutos sem confirmação. Não foi cobrado nada."
        : "Não foi cobrado nada.";
  return (
    <Ecra
      cabecalho={<CabecalhoPagamento />}
      rodape={
        <>
          <Botao larguraTotal carregando={aEnviar} onPress={() => void reenviar(plano.id, periodo)}>
            {aEnviar ? "A enviar…" : "Enviar novo pedido"}
          </Botao>
          <Botao tipo="ligacao" larguraTotal onPress={aoOutroNumero}>
            Usar outro número
          </Botao>
        </>
      }
      style={{ gap: 22, paddingTop: 32 }}
    >
      <View accessibilityRole="alert" style={{ gap: 6, paddingVertical: 18, paddingHorizontal: 20, backgroundColor: cor.erradoSuave, borderRadius: raio.md }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <XCircle size={22} color={cor.errado} />
          <Texto forte cor={cor.errado} style={{ fontSize: 17, flex: 1 }}>
            {titulo}
          </Texto>
        </View>
        <Texto>{texto}</Texto>
      </View>
      <View style={{ gap: 8 }}>
        <Texto forte>O que pode fazer</Texto>
        {["Confirme que tem saldo e que o número está associado ao Multicaixa Express.", "Envie um novo pedido e aceite-o na app em 5 minutos."].map((t) => (
          <View key={t} style={{ flexDirection: "row", gap: 10 }}>
            <Texto>•</Texto>
            <Texto style={{ flex: 1 }}>{t}</Texto>
          </View>
        ))}
      </View>
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
    </Ecra>
  );
}

/* ------------------------------------------------------------------ */
/* Passo 3: concluído                                                   */
/* ------------------------------------------------------------------ */
function Concluido({ p, plano }: { p: Pagamento; plano: Plano }) {
  const { data: sub } = useSubMinhaQuery();
  const a = p.ativacao?.plano;
  const preco = precoPlano(plano, p.periodo ?? "mensal");
  const linhas: [string, string][] = [
    ["Pago hoje", kz(p.total_kz)],
    ...(p.credito_kz ? ([["Crédito dos dias por usar", `menos ${kz(p.credito_kz)}`]] as [string, string][]) : []),
    ...(p.dias_extra ? ([["Dias a mais pelo crédito", String(p.dias_extra)]] as [string, string][]) : []),
    ["Válido até", dataPt(a?.expira_em ?? sub?.termina_em ?? sub?.expires_at)],
    [p.periodo === "anual" ? "Para renovar, por ano" : "Para renovar, por mês", kz(preco)],
  ];
  return (
    <Ecra
      rodape={
        <Botao tipo="realce" larguraTotal onPress={() => router.replace("/inicio")}>
          Continuar a aprender
        </Botao>
      }
      style={{ gap: 24, paddingTop: 40 }}
    >
      <View style={{ gap: 10 }}>
        <Etiqueta tom="certo" icone={<CheckCircle2 size={18} color={cor.certo} />}>
          {p.metodo_codigo === "sem_pagamento" ? "Plano activado" : "Pagamento confirmado"}
        </Etiqueta>
        <Titulo v="tituloXL" style={{ fontSize: 32, lineHeight: 38 }} accessibilityLiveRegion="polite">
          Já tem o {a?.nome ?? plano.name}
        </Titulo>
        <Texto suave>O recibo fica em Pagamentos e recibos, na sua subscrição.</Texto>
      </View>
      <BalaoFala style={{ gap: 12 }}>
        <Texto accessibilityRole="header" cor={cor.sobreMarca} style={{ fontFamily: fonte.tituloMedio, fontSize: 19, lineHeight: 26 }}>
          O que mudou
        </Texto>
        <Vantagens plano={plano} sobreMarca />
      </BalaoFala>
      <View>
        {linhas.map(([dt, dd]) => (
          <View key={dt} style={{ flexDirection: "row", justifyContent: "space-between", gap: 12, paddingVertical: 10, borderBottomWidth: 1, borderColor: cor.linha }}>
            <Texto suave>{dt}</Texto>
            <Texto forte numeros>
              {dd}
            </Texto>
          </View>
        ))}
        {p.numero_recibo ? (
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12, paddingTop: 2 }}>
            <Texto suave>Recibo</Texto>
            <Botao tipo="ligacao" tamanho="pequeno" onPress={() => router.replace(`/recibos?recibo=${encodeURIComponent(p.numero_recibo!)}`)}>
              {`Ver o recibo ${p.numero_recibo}`}
            </Botao>
          </View>
        ) : null}
      </View>
    </Ecra>
  );
}
