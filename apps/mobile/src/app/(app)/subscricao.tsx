/**
 * Subscrição (canvas: SubscricaoMovel; web: user/subscription/page.tsx).
 * Não há cobranças automáticas (Multicaixa Express): "cancelar a renovação" é desligar os
 * lembretes de renovação (ecrã /cancelar-renovacao).
 */
import { router } from "expo-router";
import { Gift } from "lucide-react-native";
import { useState } from "react";
import { TextInput, View } from "react-native";
import { Segmentos } from "@/componentes/perfil/Campos";
import { LinhaPagamentoCurta } from "@/componentes/subscricao/Partes";
import { mensagemErro } from "@/api/erros";
import { escreverConsulta } from "@/lib/rotasWeb";
import {
  dataPt,
  horaPt,
  kz,
  periodoDoPlano,
  precoPlano,
  useSubHistoricoQuery,
  useSubLembretesMutation,
  useSubMinhaQuery,
  useSubPlanosQuery,
  type MinhaSubscricao,
  type Periodo,
  type Plano,
} from "@/dominios/subscricao/api";
import { cor, fonte, raio } from "@/tema";
import { ACarregar, Aviso, BalaoFala, Botao, Cabecalho, Ecra, EstadoErro, Etiqueta, Interruptor, Osso, Texto } from "@/ui";

export default function EcraSubscricao() {
  const sub = useSubMinhaQuery();
  const planos = useSubPlanosQuery();
  const historico = useSubHistoricoQuery();
  const pagos = (historico.data?.payment_history ?? []).filter((p) => (p.status ?? "pago") === "pago");

  const actualizar = () => {
    sub.refetch();
    planos.refetch();
    historico.refetch();
  };

  return (
    <Ecra cabecalho={<Cabecalho titulo="Subscrição" />} aoActualizar={actualizar} aActualizar={sub.isFetching && !!sub.data} style={{ gap: 22 }}>
      {sub.isError && !sub.data ? (
        <EstadoErro erro={sub.error} titulo="Não conseguimos carregar a sua subscrição" aoTentar={actualizar} />
      ) : !sub.data ? (
        <ACarregar linhas={2} altura={160} rotulo="A carregar a subscrição" />
      ) : (
        <>
          <OSeuPlano sub={sub.data} />
          <Lembretes sub={sub.data} />
          <MudarDePlano planos={planos.data} sub={sub.data} erro={planos.isError} aoTentar={() => planos.refetch()} />
          <CodigoPromocional />
          <View style={{ gap: 4 }}>
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <Texto accessibilityRole="header" style={{ fontFamily: fonte.tituloMedio, fontSize: 18, lineHeight: 24 }}>
                Pagamentos
              </Texto>
              {pagos.length ? (
                <Botao tipo="ligacao" tamanho="pequeno" href="/recibos">
                  Ver todos e os recibos
                </Botao>
              ) : null}
            </View>
            {!historico.data ? (
              historico.isError ? (
                <Botao tipo="secundario" tamanho="pequeno" onPress={() => historico.refetch()} style={{ alignSelf: "flex-start" }}>
                  Tentar outra vez
                </Botao>
              ) : (
                <Osso altura={104} />
              )
            ) : pagos.length ? (
              pagos.slice(0, 3).map((p) => <LinhaPagamentoCurta key={p.id} p={p} />)
            ) : (
              <Texto suave>Ainda não fez pagamentos. Quando fizer, os recibos ficam aqui.</Texto>
            )}
          </View>
        </>
      )}
    </Ecra>
  );
}

function OSeuPlano({ sub }: { sub: MinhaSubscricao }) {
  const gratuito = sub.plan.plan_type === "FREE";
  const emTeste = !!sub.em_teste;
  const [agora] = useState(() => Date.now());
  const terminaEm = sub.termina_em ?? sub.expires_at;
  const activo = !gratuito && !!terminaEm && new Date(terminaEm).getTime() > agora;
  const dias = Math.max(0, Math.ceil((terminaEm ? new Date(terminaEm).getTime() - agora : 0) / 86_400_000));
  const podeRenovar = !gratuito && (sub.pode_renovar ?? !activo);
  const fim = dataPt(terminaEm);
  const anual = sub.periodo === "anual";
  const preco = sub.valor_periodo_kz ?? Number(anual ? sub.plan.yearly_price : sub.plan.monthly_price);

  const texto = emTeste
    ? `Em teste até ${dataPt(sub.teste_termina_em ?? terminaEm, "diaMes")}. Não pagou nada. Para continuar depois disso, pague com Multicaixa Express; se não pagar, volta ao Gratuito e fica com o progresso.`
    : gratuito
      ? "Grátis, sem prazo. Pode passar para um plano pago quando quiser."
      : !activo
        ? `Terminou a ${fim}. Renove para voltar a ter o ${sub.plan.name}.`
        : sub.termina_hoje
          ? `${kz(preco)} por ${anual ? "ano" : "mês"}. Termina hoje, às ${horaPt(terminaEm)}.`
          : `${kz(preco)} por ${anual ? "ano" : "mês"}. Válido até ${fim}${podeRenovar ? ` (faltam ${dias} ${dias === 1 ? "dia" : "dias"})` : ""}.`;

  const u = sub.daily_usage;
  const hoje = [
    u?.speaking_limit == null ? "conversa sem limite" : u.speaking_limit > 0 ? `${Math.max(0, u.speaking_limit - u.speaking_minutes_used)} dos ${u.speaking_limit} minutos de conversa` : null,
    u?.lessons_limit ? `${Math.max(0, u.lessons_limit - u.lessons_used)} das ${u.lessons_limit} lições` : "lições ilimitadas",
  ]
    .filter(Boolean)
    .join(" e ");

  const teste = sub.pode_experimentar && sub.dias_teste && sub.plano_teste;
  return (
    <BalaoFala style={{ padding: 20, gap: 6 }}>
      <Texto v="legenda" forte cor={cor.sobreMarca}>
        O seu plano
      </Texto>
      <Texto accessibilityRole="header" cor={cor.sobreMarca} style={{ fontFamily: fonte.titulo, fontSize: 26, lineHeight: 32 }}>
        {sub.plan.name}
      </Texto>
      <Texto v="legenda" cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
        {texto}
      </Texto>
      <Texto v="legenda" cor={cor.sobreMarca} style={{ fontSize: 15, lineHeight: 22 }}>
        Hoje ainda tem {hoje}.
      </Texto>
      <View style={{ gap: 10, paddingTop: 10 }}>
        {emTeste ? (
          <Botao tipo="realce" larguraTotal href={`/checkout/${sub.plan.plan_type}`}>
            Pagar agora
          </Botao>
        ) : gratuito ? (
          <>
            <Botao tipo="realce" larguraTotal href={`/checkout/${teste ? sub.plano_teste : "PREMIUM"}`}>
              {teste ? `Experimentar ${sub.dias_teste} dias grátis` : "Passar para Premium"}
            </Botao>
            <Botao tipo="sobreMarca" href="/checkout/PREMIUM_PLUS">
              Ver o Premium Plus
            </Botao>
          </>
        ) : (
          <>
            {podeRenovar ? (
              <Botao tipo="realce" larguraTotal href={`/checkout/${sub.plan.plan_type}${escreverConsulta({ periodo: sub.periodo })}`}>
                {`Renovar o ${sub.plan.name}`}
              </Botao>
            ) : null}
            {sub.plan.plan_type === "PREMIUM" ? (
              <Botao tipo="sobreMarca" href="/checkout/PREMIUM_PLUS">
                Passar para Premium Plus
              </Botao>
            ) : null}
          </>
        )}
      </View>
      {emTeste ? (
        <Texto v="legenda" cor={cor.sobreMarca}>
          Se pagar agora, o período pago começa no fim do teste: não perde nenhum dia.
        </Texto>
      ) : null}
      {!gratuito && !emTeste && !podeRenovar && sub.renovavel_a_partir_de ? (
        <Texto v="legenda" cor={cor.sobreMarca}>
          Pode renovar a partir de {dataPt(sub.renovavel_a_partir_de, "diaMes")}.
        </Texto>
      ) : null}
      {!gratuito && !emTeste && activo && sub.plan.plan_type === "PREMIUM" ? (
        <Texto v="legenda" cor={cor.sobreMarca}>
          Se passar para o Premium Plus, os dias que ainda tem passam a desconto.
        </Texto>
      ) : null}
    </BalaoFala>
  );
}

function Lembretes({ sub }: { sub: MinhaSubscricao }) {
  const [mudar, { isLoading }] = useSubLembretesMutation();
  const [erro, setErro] = useState<string | null>(null);
  if (sub.plan.plan_type === "FREE" || sub.em_teste) return null;
  return (
    <View style={{ gap: 4, borderWidth: 1, borderColor: cor.linha, borderRadius: raio.md, paddingHorizontal: 16, paddingVertical: 8 }}>
      <Interruptor
        rotulo="Lembretes de renovação"
        descricao={sub.lembretes_renovacao ? "Avisamos cerca de 3 dias antes e nas últimas 24 horas." : "Não vai receber avisos antes de terminar."}
        valor={sub.lembretes_renovacao}
        inactivo={isLoading}
        aoMudar={async (v) => {
          setErro(null);
          if (!v) return router.push("/cancelar-renovacao");
          const r = await mudar(true);
          if ("error" in r && r.error) setErro(mensagemErro(r.error, "Não foi possível guardar. Tente outra vez."));
        }}
      />
      <Texto v="legenda" suave style={{ paddingBottom: 8 }}>
        Não há cobranças automáticas. Se não renovar, passa para o Gratuito e fica com o progresso.
      </Texto>
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
    </View>
  );
}

function MudarDePlano({ planos, sub, erro, aoTentar }: { planos?: Plano[]; sub: MinhaSubscricao; erro: boolean; aoTentar: () => void }) {
  const [periodo, setPeriodo] = useState<Periodo>(sub.periodo === "anual" ? "anual" : "mensal");
  const desconto = Math.max(0, ...(planos ?? []).map((p) => p.yearly_discount_percentage || 0));
  const temAnual = (planos ?? []).some((p) => Number(p.yearly_price) > 0);
  return (
    <View style={{ gap: 10 }}>
      <Texto accessibilityRole="header" style={{ fontFamily: fonte.tituloMedio, fontSize: 18, lineHeight: 24 }}>
        Mudar de plano
      </Texto>
      {temAnual ? (
        <Segmentos
          rotulo="Forma de pagamento"
          opcoes={[
            { valor: "mensal", nome: "Mensal" },
            { valor: "anual", nome: desconto ? `Anual, poupa ${Math.round(desconto)}%` : "Anual" },
          ]}
          valor={periodo}
          aoMudar={setPeriodo}
        />
      ) : null}
      {erro && !planos ? (
        <Botao tipo="secundario" tamanho="pequeno" onPress={aoTentar} style={{ alignSelf: "flex-start" }}>
          Tentar outra vez
        </Botao>
      ) : !planos ? (
        <Osso altura={240} />
      ) : (
        planos.map((p) => {
          const actual = p.id === sub.plan.id;
          const per = periodoDoPlano(p, periodo);
          const gratis = p.plan_type === "FREE";
          const texto = [p.daily_lessons_limit ? `${p.daily_lessons_limit} lições` : "Lições ilimitadas", p.daily_speaking_minutes == null ? "conversa sem limite" : p.daily_speaking_minutes > 0 ? `${p.daily_speaking_minutes} min de conversa por dia` : null, p.certificates ? "certificados" : null]
            .filter(Boolean)
            .join(", ");
          return (
            <View
              key={p.id}
              style={{ gap: 6, padding: 16, borderRadius: raio.md, borderWidth: actual ? 2 : 1, borderColor: actual ? cor.azulMarca : cor.linha, backgroundColor: actual ? cor.fundoSuave : cor.fundo }}
            >
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
                <Texto style={{ fontFamily: fonte.titulo, fontSize: 18, lineHeight: 24 }}>{p.name}</Texto>
                <Texto numeros style={{ fontFamily: fonte.titulo, fontSize: 18, lineHeight: 24 }}>
                  {gratis ? "Grátis" : `${kz(precoPlano(p, per))}/${per === "anual" ? "ano" : "mês"}`}
                </Texto>
              </View>
              <Texto v="legenda" suave>
                {texto}.
              </Texto>
              {p.pode_experimentar && p.dias_teste && !actual ? (
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                  <Gift size={16} color={cor.certo} />
                  <Texto v="legenda" forte cor={cor.certo}>
                    Pode experimentar {p.dias_teste} dias grátis
                  </Texto>
                </View>
              ) : null}
              {actual ? (
                <Etiqueta tom="marca">O seu plano</Etiqueta>
              ) : gratis ? null : (
                <Botao tipo="ligacao" tamanho="pequeno" href={`/checkout/${p.plan_type}${escreverConsulta({ periodo: per })}`}>
                  {p.so_renovacao ? `Renovar o ${p.name}` : `Escolher ${p.name}`}
                </Botao>
              )}
            </View>
          );
        })
      )}
    </View>
  );
}

/** O código fica no endereço até ao pagamento: o servidor diz no orçamento se é válido. */
function CodigoPromocional() {
  const [texto, setTexto] = useState("");
  const [foco, setFoco] = useState(false);
  const aplicar = () => {
    const c = texto.trim().toUpperCase();
    if (!c) return;
    setTexto("");
    router.push(`/planos${escreverConsulta({ codigo: c })}`);
  };
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
          placeholder="Escreva o código"
          placeholderTextColor={cor.tintaSuave}
          onSubmitEditing={aplicar}
          returnKeyType="done"
          onFocus={() => setFoco(true)}
          onBlur={() => setFoco(false)}
          style={[
            { flex: 1, minHeight: 48, paddingHorizontal: 12, fontFamily: fonte.texto, fontSize: 16, color: cor.tinta, borderWidth: foco ? 2 : 1.5, borderColor: foco ? cor.azulVivo : cor.linhaForte, borderRadius: raio.sm },
          ]}
        />
        <Botao tipo="secundario" tamanho="medio" disabled={!texto.trim()} onPress={aplicar}>
          Aplicar
        </Botao>
      </View>
      <Texto v="legenda" suave>
        Escolha o plano a seguir e veja o desconto antes de pagar.
      </Texto>
    </View>
  );
}
