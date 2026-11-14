"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ChevronLeft } from "lucide-react";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { Aviso, Botao, Etiqueta, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Numeros } from "@/components/pe/professor/Partes";
import { DialogoSuspender } from "@/components/pe/admin/Suspender";
import { dataPt, diaMesCurto, kz, mensagemErro } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import {
  ESTADO_UTILIZADOR,
  MOTIVOS,
  PAPEL,
  quandoEntrou,
  useObrigarMudarSenhaMutation,
  useReactivarMutation,
  useTerminarSessoesMutation,
  useUtilizadorQuery,
  type DetalheUtilizador,
  type MotivoSuspensao,
} from "@/src/domains/admin/administracao/api";

const h2 = "m-0 font-pe-titulo text-[20px] font-semibold leading-7";
const ESTADO_PAGAMENTO = { pago: ["Pago", "certo"], pendente: ["Pendente", "realce"], falhou: ["Falhou", "errado"], expirado: ["Expirou", "neutra"], cancelado: ["Cancelado", "neutra"] } as const;

export default function DetalheUtilizadorPagina() {
  const { userId } = useParams<{ userId: string }>();
  const { data, isError, error } = useUtilizadorQuery(userId);
  return (
    <Pagina className="gap-7">
      <Link href="/admin/users" className="-mb-4 inline-flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-vivo no-underline">
        <ChevronLeft aria-hidden className="size-[18px]" />
        Utilizadores
      </Link>
      {isError ? (
        <Aviso tipo="errado">{(error as { status?: number })?.status === 404 ? "Este utilizador não existe." : "Não conseguimos carregar o utilizador."}</Aviso>
      ) : !data ? (
        <>
          <Osso className="h-[70px] w-3/4 max-w-[480px]" />
          <Osso className="h-[104px] rounded-pe-md" />
          <Osso className="h-80 rounded-pe-md" />
        </>
      ) : (
        <Conteudo d={data} />
      )}
    </Pagina>
  );
}

function Conteudo({ d }: { d: DetalheUtilizador }) {
  const u = d.utilizador;
  const { user: eu } = useDjangoAuth();
  const proprio = eu?.id === u.id;
  const [suspender, setSuspender] = useState(false);
  const [confirmar, setConfirmar] = useState<null | "sessoes" | "senha">(null);
  const [msg, setMsg] = useState<{ tipo: "certo" | "errado"; texto: string } | null>(null);
  const [reactivar, { isLoading: aReactivar }] = useReactivarMutation();
  const [terminar, { isLoading: aTerminar }] = useTerminarSessoesMutation();
  const [obrigar, { isLoading: aObrigar }] = useObrigarMudarSenhaMutation();
  const descricao = [PAPEL[u.papel] + (u.plano ? `, ${u.plano.nome}` : ""), [u.profissao, u.cidade].filter(Boolean).join(", ")].filter(Boolean).join(". ");

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
    <>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-center gap-4">
          <span aria-hidden className="flex size-14 shrink-0 items-center justify-center rounded-pe-fala bg-pe-azul-marca font-pe-titulo text-[20px] font-bold text-pe-sobre-marca">
            {u.nome
              .split(/\s+/)
              .slice(0, 2)
              .map((p) => p[0]?.toUpperCase())
              .join("")}
          </span>
          <div className="flex min-w-0 flex-col gap-1">
            <h1 className="m-0 flex flex-wrap items-center gap-3 font-pe-titulo text-[26px] font-bold leading-8 tracking-[-0.015em] md:text-[32px] md:leading-[38px]">
              {u.nome}
              <Etiqueta tipo={ESTADO_UTILIZADOR[u.estado].tipo}>{ESTADO_UTILIZADOR[u.estado].nome}</Etiqueta>
            </h1>
            <p className="m-0 text-pe-tinta-suave">{descricao}.</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <Botao asChild tipo="secundario" tamanho="medio">
            <Link href={`/admin/users/${u.id}/edit`}>Editar dados</Link>
          </Botao>
        </div>
      </div>

      {u.estado === "suspenso" && u.suspensao ? (
        <Aviso tipo="errado">
          <strong>Conta suspensa desde {dataPt(u.suspensao.desde)}</strong>
          {u.suspensao.por ? ` por ${u.suspensao.por}` : ""}. Motivo: {MOTIVOS[u.suspensao.motivo as MotivoSuspensao] ?? u.suspensao.motivo}.{u.suspensao.nota ? ` Nota: ${u.suspensao.nota}` : ""}
        </Aviso>
      ) : null}
      {msg ? <Aviso tipo={msg.tipo}>{msg.texto}</Aviso> : null}

      {u.papel === "student" ? (
        <Numeros
          itens={[
            {
              nome: "Plano",
              valor: u.plano?.nome ?? "Gratuito",
              nota: u.plano?.renova_a ? `renova a ${diaMesCurto(new Date(u.plano.renova_a))}` : u.plano?.termina_a ? `termina a ${diaMesCurto(new Date(u.plano.termina_a))}` : undefined,
            },
            { nome: "Cursos", valor: num(d.numeros.cursos), nota: `${d.numeros.concluidos} concluídos` },
            { nome: "Pontos", valor: num(d.numeros.pontos), nota: `${d.numeros.dias_seguidos} dias seguidos` },
            { nome: "Última entrada", valor: quandoEntrou(u.ultima_entrada), nota: `conta criada a ${diaMesCurto(new Date(u.criado_em), true)}` },
          ]}
        />
      ) : d.professor ? (
        <Numeros
          itens={[
            { nome: "Cursos publicados", valor: num(d.professor.cursos_publicados) },
            { nome: "Alunos", valor: num(d.professor.alunos) },
            { nome: "Publica sem revisão", valor: d.professor.publica_sem_revisao ? "Sim" : "Não", nota: d.professor.publica_sem_revisao ? "professor de confiança" : "os cursos passam pela revisão" },
            { nome: "Última entrada", valor: quandoEntrou(u.ultima_entrada) },
          ]}
        />
      ) : null}

      <div className="grid gap-9 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex flex-col gap-9">
          <section aria-labelledby="t-actividade" className="flex flex-col gap-3">
            <h2 id="t-actividade" className={h2}>
              Actividade recente
            </h2>
            {d.actividade.length ? (
              <ol className="m-0 flex list-none flex-col p-0">
                {d.actividade.map((a, i) => (
                  <li key={i} className="flex gap-4 border-b border-pe-fundo-forte py-2.5">
                    <time dateTime={a.quando} className="w-32 shrink-0 text-[15px] tabular-nums text-pe-tinta-suave">
                      {quandoEntrou(a.quando)}
                    </time>
                    <span>{a.texto}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Sem actividade registada.</p>
            )}
          </section>

          {d.pagamentos.length ? (
            <section aria-labelledby="t-pagamentos" className="flex flex-col gap-3">
              <h2 id="t-pagamentos" className={h2}>
                Pagamentos
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] border-collapse tabular-nums">
                  <caption className="sr-only">Pagamentos</caption>
                  <thead>
                    <tr>
                      {["Data", "Descrição", "Valor", "Estado"].map((t, i) => (
                        <th key={t} scope="col" className={`border-b border-pe-linha px-3 py-2.5 text-pe-legenda font-semibold text-pe-tinta-suave ${i === 2 ? "text-right" : "text-left"}`}>
                          {t}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {d.pagamentos.map((p) => (
                      <tr key={p.id}>
                        <td className="border-b border-pe-fundo-forte p-3">{diaMesCurto(new Date(p.data), true)}</td>
                        <td className="border-b border-pe-fundo-forte p-3">{p.descricao}</td>
                        <td className="border-b border-pe-fundo-forte p-3 text-right">{kz(p.valor_kz)}</td>
                        <td className="border-b border-pe-fundo-forte p-3">
                          <Etiqueta tipo={ESTADO_PAGAMENTO[p.estado][1]}>{ESTADO_PAGAMENTO[p.estado][0]}</Etiqueta>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </div>

        <section aria-labelledby="t-conta" className="flex flex-col gap-4">
          <h2 id="t-conta" className={h2}>
            Conta
          </h2>
          <dl className="m-0 flex flex-col">
            {(
              [
                ["Email", u.email],
                ["Telefone", u.telefone || "–"],
                ["Papel", PAPEL[u.papel]],
                ["Província", u.provincia_nome || u.provincia || "–"],
                ["Email verificado", u.email_verificado ? `Sim${u.verificado_em ? `, ${diaMesCurto(new Date(u.verificado_em))}` : ""}` : "Não"],
                ["Entra com", [u.entra_com_google ? "Google" : null, u.tem_senha ? "palavra-passe" : null].filter(Boolean).join(" e ") || "–"],
                ["Conta criada", dataPt(u.criado_em)],
              ] as [string, string][]
            ).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 border-b border-pe-fundo-forte py-2.5 text-[15px]">
                <dt className="text-pe-tinta-suave">{k}</dt>
                <dd className="m-0 min-w-0 break-words text-right font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
          {u.deve_mudar_senha ? <Aviso tipo="info">Tem de mudar a palavra-passe antes de continuar a usar a plataforma.</Aviso> : null}
          {u.email_pendente ? <Aviso tipo="info">Email novo à espera de confirmação: {u.email_pendente}. Até a pessoa o confirmar, continua a entrar com o actual.</Aviso> : null}
          {proprio ? (
            <p className="m-0 text-pe-legenda text-pe-tinta-suave">É a sua conta: as acções de segurança fazem-se nas suas definições.</p>
          ) : u.pode_gerir === false ? (
            <p className="m-0 text-pe-legenda text-pe-tinta-suave">Contas de administração só podem ser geridas por um superutilizador.</p>
          ) : (
            <div className="flex flex-col items-start gap-1">
              {u.tem_senha ? (
                <Botao tipo="ligacao" tamanho="pequeno" onClick={() => setConfirmar("senha")}>
                  Obrigar a mudar a palavra-passe
                </Botao>
              ) : null}
              <Botao tipo="ligacao" tamanho="pequeno" onClick={() => setConfirmar("sessoes")}>
                Terminar sessões abertas
              </Botao>
              {u.estado === "suspenso" ? (
                <Botao tipo="secundario" tamanho="pequeno" className="mt-2" disabled={aReactivar} onClick={() => accao(() => reactivar(u.id).unwrap(), "Conta reactivada: a pessoa já pode entrar.")}>
                  Reactivar conta
                </Botao>
              ) : u.papel !== "admin" || u.pode_gerir ? (
                <Botao tipo="perigo" tamanho="pequeno" className="mt-2" onClick={() => setSuspender(true)}>
                  Suspender conta
                </Botao>
              ) : null}
            </div>
          )}
        </section>
      </div>

      {suspender ? <DialogoSuspender id={u.id} nome={u.nome} temPlanoPago={!!u.plano && u.plano.tipo !== "FREE"} aoFechar={() => setSuspender(false)} /> : null}
      <Dialogo
        aberto={!!confirmar}
        aoMudar={(v) => !v && setConfirmar(null)}
        titulo={confirmar === "senha" ? "Obrigar a mudar a palavra-passe?" : "Terminar as sessões abertas?"}
        descricao={
          confirmar === "senha"
            ? "A partir da próxima acção, a pessoa tem de escolher uma palavra-passe nova antes de continuar."
            : "A pessoa sai de todos os dispositivos e tem de entrar outra vez."
        }
      >
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={() => setConfirmar(null)}>
            Cancelar
          </Botao>
          <Botao
            tamanho="medio"
            disabled={aTerminar || aObrigar}
            onClick={async () => {
              const c = confirmar;
              setConfirmar(null);
              if (c === "senha") await accao(() => obrigar(u.id).unwrap(), "Feito: a pessoa tem de mudar a palavra-passe antes de continuar.");
              else await accao(() => terminar(u.id).unwrap(), "Sessões terminadas.");
            }}
          >
            {confirmar === "senha" ? "Obrigar a mudar" : "Terminar sessões"}
          </Botao>
        </div>
      </Dialogo>
    </>
  );
}
