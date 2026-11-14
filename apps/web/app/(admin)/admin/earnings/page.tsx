"use client";

import Link from "next/link";
import { useState } from "react";
import { Aviso, Botao, Campo, Etiqueta, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Cabeca, Numeros } from "@/components/pe/professor/Partes";
import { diaMesCurto, kz, mensagemErro } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import { useGanhosAdminQuery, useLazyIbanGanhoQuery, useMarcarPagoMutation, type LinhaGanho } from "@/src/domains/admin/administracao/negocio";

function mesAnterior() {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function GanhosProfessores() {
  const [mes, setMes] = useState(mesAnterior());
  const { data: g, isError, isFetching, refetch } = useGanhosAdminQuery(mes);
  const [pagar, setPagar] = useState<LinhaGanho | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  return (
    <Pagina className="gap-7">
      <Cabeca titulo="Ganhos dos professores" texto={g ? `${g.percentagem}% das subscrições do mês, divididos pelo tempo dos alunos pagantes nos cursos de cada professor.` : "Quanto pagar a cada professor, mês a mês."}>
        <Campo rotulo="Mês" type="month" value={mes} max={mesAnterior()} onChange={(e) => e.target.value && setMes(e.target.value)} className="w-48" />
      </Cabeca>
      {msg ? <Aviso tipo="certo">{msg}</Aviso> : null}
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os ganhos.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !g ? (
        <Osso className="h-80 rounded-pe-md" />
      ) : (
        <div aria-busy={isFetching} className="flex flex-col gap-7">
          <Numeros
            itens={[
              { nome: "Total do mês", valor: kz(g.total_kz), nota: g.nome },
              { nome: "Por pagar", valor: kz(g.por_pagar_kz), nota: `pagamento a ${diaMesCurto(new Date(`${g.pago_a}T12:00:00`))}` },
              { nome: "Professores", valor: num(g.linhas.length), nota: `${g.linhas.filter((l) => l.estado === "pago").length} já pagos` },
              { nome: "Sem conta indicada", valor: num(g.linhas.filter((l) => !l.conta).length), nota: "não podem ser pagos ainda" },
            ]}
          />
          {g.linhas.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] border-collapse tabular-nums">
                <caption className="sr-only">Ganhos de {g.nome}</caption>
                <thead>
                  <tr>
                    {["Professor", "Alunos", "Minutos", "Parte", "Valor", "Conta", "Estado", ""].map((t, i) => (
                      <th key={i} scope="col" className={`border-b border-pe-linha px-3 py-2.5 text-pe-legenda font-semibold text-pe-tinta-suave ${i >= 1 && i <= 4 ? "text-right" : "text-left"}`}>
                        {t || <span className="sr-only">Acções</span>}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {g.linhas.map((l) => (
                    <tr key={l.id}>
                      <td className="border-b border-pe-fundo-forte p-3">
                        <Link href={`/admin/users/${l.professor.id}`} className="font-semibold">
                          {l.professor.nome}
                        </Link>
                      </td>
                      <td className="border-b border-pe-fundo-forte p-3 text-right">{num(l.alunos)}</td>
                      <td className="border-b border-pe-fundo-forte p-3 text-right">{num(l.minutos)}</td>
                      <td className="border-b border-pe-fundo-forte p-3 text-right">{(l.quota * 100).toLocaleString("pt-PT", { maximumFractionDigits: 1 })}%</td>
                      <td className="border-b border-pe-fundo-forte p-3 text-right font-semibold">{kz(l.valor_kz)}</td>
                      <td className="border-b border-pe-fundo-forte p-3">{l.conta ? <ContaComIban l={l} /> : <span className="text-pe-errado">Sem conta</span>}</td>
                      <td className="border-b border-pe-fundo-forte p-3">
                        {l.estado === "pago" ? (
                          <span className="flex flex-col">
                            <Etiqueta tipo="certo">Pago</Etiqueta>
                            <span className="text-pe-legenda text-pe-tinta-suave">
                              {l.pago_em ? diaMesCurto(new Date(l.pago_em)) : ""}
                              {l.referencia ? `, ref. ${l.referencia}` : ""}
                            </span>
                          </span>
                        ) : (
                          <Etiqueta tipo="realce">A processar</Etiqueta>
                        )}
                      </td>
                      <td className="border-b border-pe-fundo-forte px-3 text-right">
                        {l.estado !== "pago" && l.conta ? (
                          <Botao tipo="secundario" tamanho="pequeno" onClick={() => setPagar(l)}>
                            Marcar como pago
                          </Botao>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">Sem ganhos neste mês. Os meses fecham automaticamente no dia 1 do mês seguinte.</p>
          )}
        </div>
      )}
      {pagar ? (
        <DialogoPago
          l={pagar}
          aoFechar={() => setPagar(null)}
          aoPago={() => {
            setMsg(`Pagamento a ${pagar.professor.nome} registado. O professor foi avisado.`);
            setPagar(null);
          }}
        />
      ) : null}
    </Pagina>
  );
}

function ContaComIban({ l }: { l: LinhaGanho }) {
  const [ver, { data, isFetching, isError }] = useLazyIbanGanhoQuery();
  return (
    <span className="flex flex-col text-[15px]">
      <span>
        {l.conta!.banco_nome}, ••{l.conta!.terminada_em}
      </span>
      <span className="text-pe-legenda text-pe-tinta-suave">{l.conta!.titular}</span>
      {data ? (
        <span className="select-all font-semibold tracking-[0.04em]">{data.iban.replace(/(.{4})/g, "$1 ").trim()}</span>
      ) : (
        <button type="button" disabled={isFetching} onClick={() => void ver(l.id)} className="self-start text-pe-legenda font-semibold text-pe-azul-vivo underline underline-offset-[3px]">
          {isError ? "Tentar outra vez" : "Ver IBAN completo"}
        </button>
      )}
    </span>
  );
}

function DialogoPago({ l, aoFechar, aoPago }: { l: LinhaGanho; aoFechar: () => void; aoPago: () => void }) {
  const [marcar, { isLoading }] = useMarcarPagoMutation();
  const [ref, setRef] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  return (
    <Dialogo aberto aoMudar={(v) => !v && aoFechar()} titulo={`Marcar ${kz(l.valor_kz)} como pago?`} descricao={`Transferência para ${l.professor.nome}, ${l.conta?.banco_nome} ••${l.conta?.terminada_em}. Faça a transferência no banco primeiro e escreva aqui a referência.`}>
      <Campo rotulo="Referência da transferência" value={ref} maxLength={80} onChange={(e) => setRef(e.target.value)} />
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="flex flex-wrap justify-end gap-3">
        <Botao tipo="secundario" tamanho="medio" onClick={aoFechar}>
          Cancelar
        </Botao>
        <Botao
          tamanho="medio"
          disabled={isLoading}
          onClick={async () => {
            setErro(null);
            if (ref.trim().length < 3) return setErro("Escreva a referência da transferência.");
            try {
              await marcar({ id: l.id, referencia: ref.trim() }).unwrap();
              aoPago();
            } catch (x) {
              setErro(mensagemErro(x, "Não foi possível registar o pagamento."));
            }
          }}
        >
          Marcar como pago
        </Botao>
      </div>
    </Dialogo>
  );
}
