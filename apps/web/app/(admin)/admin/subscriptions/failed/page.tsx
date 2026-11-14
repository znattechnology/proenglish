"use client";

import { useState } from "react";
import { Aviso, Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Avatar, CabecaSeccao, SEPARADORES_SUBSCRICOES } from "@/components/pe/admin/Comum";
import { diaMesCurto, kz, mensagemErro } from "@/src/domains/student/subscricao/api";
import { useFalhadosQuery, useLembreteMutation, useNovoPedidoMutation } from "@/src/domains/admin/administracao/negocio";

export default function PagamentosFalhados() {
  const { data, isError, refetch } = useFalhadosQuery();
  const [pedido, { isLoading: aPedir }] = useNovoPedidoMutation();
  const [lembrete, { isLoading: aLembrar }] = useLembreteMutation();
  const [msg, setMsg] = useState<{ tipo: "certo" | "errado"; texto: string } | null>(null);
  const accao = async (f: () => Promise<unknown>, ok: string) => {
    setMsg(null);
    try {
      await f();
      setMsg({ tipo: "certo", texto: ok });
    } catch (x) {
      setMsg({ tipo: "errado", texto: mensagemErro(x, "Não foi possível concluir.") });
    }
  };

  return (
    <Pagina className="gap-7">
      <CabecaSeccao
        titulo="Subscrições e pagamentos"
        texto="Pedidos de pagamento por Multicaixa Express que não foram aceites. O Multicaixa Express não cobra sozinho: pode enviar um novo pedido para o telemóvel da pessoa."
        activo="Pagamentos falhados"
        itens={SEPARADORES_SUBSCRICOES}
      />
      {msg ? <Aviso tipo={msg.tipo}>{msg.texto}</Aviso> : null}
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os pagamentos.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-64 rounded-pe-md" />
      ) : !data.resultados.length ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">Nenhum pagamento por resolver neste período.</p>
      ) : (
        <>
          <ul className="m-0 flex list-none flex-col p-0">
            {data.resultados.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-pe-fundo-forte py-3.5">
                <Avatar iniciais={p.utilizador.iniciais} />
                <span className="flex min-w-0 flex-[1_1_220px] flex-col">
                  <span className="font-semibold">{p.utilizador.nome}</span>
                  <span className="truncate text-pe-legenda text-pe-tinta-suave">
                    {p.utilizador.email}, {p.plano}
                  </span>
                </span>
                <span className="w-28 font-semibold tabular-nums">{kz(p.valor_kz)}</span>
                <span className="flex w-56 flex-col text-[15px]">
                  <span>{p.motivo}</span>
                  <span className="text-pe-legenda text-pe-tinta-suave">
                    a {diaMesCurto(new Date(p.falhou_a))}, {p.pedidos} {p.pedidos === 1 ? "pedido" : "pedidos"}
                  </span>
                </span>
                <span className="ml-auto flex flex-wrap gap-2">
                  <Botao
                    tipo="secundario"
                    tamanho="pequeno"
                    disabled={aPedir}
                    onClick={async () => {
                      setMsg(null);
                      try {
                        const r = await pedido(p.id).unwrap();
                        setMsg({ tipo: "certo", texto: `Novo pedido enviado para o telemóvel de ${p.utilizador.nome}.${r?.aviso ? ` ${r.aviso}` : ""}` });
                      } catch (x) {
                        setMsg({ tipo: "errado", texto: mensagemErro(x, "Não foi possível enviar o pedido.") });
                      }
                    }}
                  >
                    Enviar novo pedido
                  </Botao>
                  <Botao tipo="ligacao" tamanho="pequeno" disabled={aLembrar} onClick={() => accao(() => lembrete(p.id).unwrap(), `Lembrete enviado por email a ${p.utilizador.nome}.`)}>
                    Enviar lembrete
                  </Botao>
                </span>
              </li>
            ))}
          </ul>
          <p className="m-0 font-semibold">Total em risco nos últimos 30 dias: {kz(data.total_em_risco_kz)}.</p>
          <p className="m-0 max-w-[68ch] text-pe-legenda text-pe-tinta-suave">Quem já tinha um plano pago passa para o Gratuito no fim do período, sem perder o progresso. Quem nunca pagou já está no Gratuito.</p>
        </>
      )}
    </Pagina>
  );
}
