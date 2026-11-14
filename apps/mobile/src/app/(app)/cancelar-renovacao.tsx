/**
 * "Cancelar a renovação" (canvas: CancelarRenovacao). Com Multicaixa Express não há cobranças
 * automáticas, por isso aqui desligam-se os lembretes de renovação (web: diálogo
 * "Desligar os lembretes?" em user/subscription/page.tsx).
 */
import { router } from "expo-router";
import { BellOff } from "lucide-react-native";
import { useState } from "react";
import { View } from "react-native";
import { mensagemErro } from "@/api/erros";
import { Vantagens } from "@/componentes/subscricao/Partes";
import { dataPt, useSubLembretesMutation, useSubMinhaQuery, useSubPlanosQuery } from "@/dominios/subscricao/api";
import { balao, cor, raio } from "@/tema";
import { ACarregar, Aviso, Botao, Cabecalho, Ecra, EstadoErro, Texto, Titulo } from "@/ui";

export default function EcraCancelarRenovacao() {
  const sub = useSubMinhaQuery();
  const { data: planos } = useSubPlanosQuery();
  const [mudar, { isLoading }] = useSubLembretesMutation();
  const [erro, setErro] = useState<string | null>(null);
  const s = sub.data;
  const gratuito = planos?.find((p) => p.plan_type === "FREE");
  const voltar = () => (router.canGoBack() ? router.back() : router.replace("/subscricao"));

  if (sub.isError && !s)
    return (
      <Ecra cabecalho={<Cabecalho fechar />}>
        <EstadoErro erro={sub.error} aoTentar={() => sub.refetch()} />
      </Ecra>
    );
  if (!s)
    return (
      <Ecra cabecalho={<Cabecalho fechar />}>
        <ACarregar linhas={2} />
      </Ecra>
    );

  const fim = dataPt(s.termina_em ?? s.expires_at);
  const pago = s.plan.plan_type !== "FREE" && !s.em_teste;

  return (
    <Ecra
      cabecalho={<Cabecalho fechar linha={false} />}
      rodape={
        pago && s.lembretes_renovacao ? (
          <>
            <Botao larguraTotal onPress={voltar}>
              Manter os lembretes
            </Botao>
            <Botao
              tipo="perigo"
              larguraTotal
              carregando={isLoading}
              onPress={async () => {
                setErro(null);
                const r = await mudar(false);
                if ("error" in r && r.error) return setErro(mensagemErro(r.error, "Não foi possível guardar. Tente outra vez."));
                voltar();
              }}
            >
              {isLoading ? "A guardar…" : "Desligar lembretes"}
            </Botao>
          </>
        ) : (
          <Botao larguraTotal onPress={voltar}>
            Voltar à subscrição
          </Botao>
        )
      }
      style={{ gap: 18 }}
    >
      <View style={[balao.medio, { width: 56, height: 56, alignItems: "center", justifyContent: "center", backgroundColor: cor.fundoForte }]}>
        <BellOff size={28} color={cor.tinta} />
      </View>
      {!pago ? (
        <View style={{ gap: 8 }}>
          <Titulo v="tituloM">Não há renovação para cancelar</Titulo>
          <Texto suave>{s.em_teste ? "Está a experimentar um plano sem pagar. Se não pagar até ao fim do teste, a conta volta ao Gratuito e fica com o progresso." : "Está no plano Gratuito, que não tem prazo nem pagamentos."}</Texto>
        </View>
      ) : !s.lembretes_renovacao ? (
        <View style={{ gap: 8 }}>
          <Titulo v="tituloM">Os lembretes já estão desligados</Titulo>
          <Texto suave>O {s.plan.name} continua até {fim}. Não há cobranças automáticas: se não renovar, passa para o Gratuito.</Texto>
        </View>
      ) : (
        <>
          <View style={{ gap: 8 }}>
            <Titulo v="tituloL" style={{ fontSize: 24, lineHeight: 30 }}>
              Desligar os lembretes de renovação?
            </Titulo>
            <Texto>
              Não há cobranças automáticas: o {s.plan.name} continua até <Texto forte>{fim}</Texto>, mas não o avisamos antes de terminar. Se não renovar, passa para o Gratuito e fica com o
              progresso, os pontos e os certificados.
            </Texto>
          </View>
          {gratuito ? (
            <View style={{ backgroundColor: cor.fundoSuave, borderRadius: raio.md, paddingVertical: 14, paddingHorizontal: 16, gap: 8 }}>
              <Texto forte>No Gratuito passa a ter</Texto>
              <Vantagens plano={gratuito} />
            </View>
          ) : null}
        </>
      )}
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
    </Ecra>
  );
}
