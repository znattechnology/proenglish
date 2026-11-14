"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Mail, UserPlus } from "lucide-react";
import { AreaTexto, Aviso, Botao, Campo, Etiqueta, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Numeros } from "@/components/pe/professor/Partes";
import { Avatar, CabecaSeccao, SEPARADORES_UTILIZADORES, Filtro, LigacaoAbrir, Paginacao, Procura } from "@/components/pe/admin/Comum";
import { DialogoConvidar } from "@/components/pe/admin/Convidar";
import { cnPe } from "@/lib/pe";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import {
  ESTADO_UTILIZADOR,
  PAPEL,
  quandoEntrou,
  useEnviarEmailMutation,
  useUtilizadoresQuery,
  type EstadoUtilizador,
  type Papel,
  type TipoPlano,
} from "@/src/domains/admin/administracao/api";

export default function Utilizadores() {
  return (
    <Pagina className="gap-7">
      <Suspense>
        <Lista />
      </Suspense>
    </Pagina>
  );
}

function Lista() {
  const sp = useSearchParams();
  const [q, setQ] = useState("");
  const [qAtrasado, setQAtrasado] = useState("");
  const [papel, setPapel] = useState(sp.get("papel") ?? "");
  const [plano, setPlano] = useState(sp.get("plano") ?? "");
  const [estado, setEstado] = useState(sp.get("estado") ?? "");
  const [pagina, setPagina] = useState(1);
  const [seleccao, setSeleccao] = useState<Set<string>>(new Set());
  const [convidar, setConvidar] = useState(false);
  const [email, setEmail] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => {
      setQAtrasado(q.trim());
      setPagina(1);
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const { data, isError, isFetching, refetch } = useUtilizadoresQuery({
    q: qAtrasado || undefined,
    papel: (papel || undefined) as Papel | undefined,
    plano: (plano || undefined) as TipoPlano | undefined,
    estado: (estado || undefined) as EstadoUtilizador | undefined,
    pagina,
  });
  const n = data?.numeros;
  const muda = (f: (v: string) => void) => (v: string) => {
    f(v);
    setPagina(1);
    setSeleccao(new Set());
  };
  const todosNaPagina = !!data?.resultados.length && data.resultados.every((u) => seleccao.has(u.id));

  return (
    <>
      <CabecaSeccao titulo="Utilizadores" activo="Utilizadores" itens={SEPARADORES_UTILIZADORES}>
        <Botao tamanho="medio" onClick={() => setConvidar(true)}>
          <UserPlus aria-hidden className="size-5" />
          Convidar professor
        </Botao>
      </CabecaSeccao>

      {n ? (
        <Numeros
          itens={[
            { nome: "Utilizadores", valor: num(n.total), nota: n.novos_mes ? `+${num(n.novos_mes)} este mês` : "nenhum novo este mês" },
            { nome: "Estudantes", valor: num(n.estudantes), nota: `${num(n.pagantes)} pagam` },
            { nome: "Professores", valor: num(n.professores), nota: n.professores_por_activar ? `${n.professores_por_activar} convites por aceitar` : "nenhum convite pendente" },
            { nome: "Por verificar o email", valor: num(n.email_por_verificar), nota: n.email_por_verificar_3d ? `há mais de 3 dias: ${num(n.email_por_verificar_3d)}` : "nenhum há mais de 3 dias" },
          ]}
        />
      ) : isError ? null : (
        <Osso className="h-[104px] rounded-pe-md" />
      )}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(0,2fr)_repeat(3,minmax(0,1fr))] xl:items-end">
        <Procura valor={q} aoMudar={setQ} rotulo="Procurar por nome, email ou telefone" className="md:col-span-2 xl:col-span-1" />
        <Filtro rotulo="Papel" valor={papel} aoMudar={muda(setPapel)} opcoes={[{ valor: "", nome: "Todos" }, ...(Object.keys(PAPEL) as Papel[]).map((p) => ({ valor: p, nome: PAPEL[p] }))]} />
        <Filtro
          rotulo="Plano"
          valor={plano}
          aoMudar={muda(setPlano)}
          opcoes={[
            { valor: "", nome: "Todos" },
            { valor: "FREE", nome: "Gratuito" },
            { valor: "PREMIUM", nome: "Premium" },
            { valor: "PREMIUM_PLUS", nome: "Premium Plus" },
          ]}
        />
        <Filtro rotulo="Estado" valor={estado} aoMudar={muda(setEstado)} opcoes={[{ valor: "", nome: "Todos" }, ...(Object.keys(ESTADO_UTILIZADOR) as EstadoUtilizador[]).map((e) => ({ valor: e, nome: ESTADO_UTILIZADOR[e].nome }))]} />
      </div>

      {seleccao.size ? (
        <div className="flex flex-wrap items-center gap-3 rounded-pe-md bg-pe-fundo-suave px-4 py-2.5" role="status">
          <span className="font-semibold">
            {seleccao.size} {seleccao.size === 1 ? "seleccionado" : "seleccionados"}
          </span>
          <Botao tipo="secundario" tamanho="pequeno" onClick={() => setEmail(true)}>
            <Mail aria-hidden className="size-[18px]" />
            Enviar email
          </Botao>
          <Botao tipo="ligacao" tamanho="pequeno" onClick={() => setSeleccao(new Set())}>
            Limpar selecção
          </Botao>
        </div>
      ) : null}

      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os utilizadores.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-80 rounded-pe-md" />
      ) : !data.resultados.length ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">{qAtrasado ? `Ninguém com "${qAtrasado}".` : "Nenhum utilizador com estes filtros."}</p>
      ) : (
        <div aria-busy={isFetching} className={cnPe("flex flex-col gap-4", isFetching && "opacity-70")}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] border-collapse">
              <caption className="sr-only">Utilizadores</caption>
              <thead>
                <tr>
                  <th scope="col" className="w-10 border-b border-pe-linha px-3 py-2.5">
                    <input
                      type="checkbox"
                      aria-label="Seleccionar todos nesta página"
                      checked={todosNaPagina}
                      onChange={(e) =>
                        setSeleccao((s) => {
                          const n2 = new Set(s);
                          data.resultados.forEach((u) => (e.target.checked ? n2.add(u.id) : n2.delete(u.id)));
                          return n2;
                        })
                      }
                      className="size-5 accent-pe-azul-marca"
                    />
                  </th>
                  {["Utilizador", "Papel", "Plano", "Estado", "Última entrada"].map((t) => (
                    <th key={t} scope="col" className="border-b border-pe-linha px-3 py-2.5 text-left text-pe-legenda font-semibold text-pe-tinta-suave">
                      {t}
                    </th>
                  ))}
                  <th scope="col" className="border-b border-pe-linha px-3 py-2.5">
                    <span className="sr-only">Acções</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.resultados.map((u) => (
                  <tr key={u.id} className={seleccao.has(u.id) ? "bg-pe-fundo-suave" : undefined}>
                    <td className="border-b border-pe-fundo-forte px-3 py-2">
                      <input
                        type="checkbox"
                        aria-label={`Seleccionar ${u.nome}`}
                        checked={seleccao.has(u.id)}
                        onChange={(e) =>
                          setSeleccao((s) => {
                            const n2 = new Set(s);
                            if (e.target.checked) n2.add(u.id);
                            else n2.delete(u.id);
                            return n2;
                          })
                        }
                        className="size-5 accent-pe-azul-marca"
                      />
                    </td>
                    <td className="border-b border-pe-fundo-forte p-3">
                      <span className="flex items-center gap-3">
                        <Avatar iniciais={u.iniciais} />
                        <span className="flex min-w-0 flex-col">
                          <span className="font-semibold">{u.nome}</span>
                          <span className="truncate text-pe-legenda text-pe-tinta-suave">{u.email}</span>
                        </span>
                      </span>
                    </td>
                    <td className="border-b border-pe-fundo-forte p-3">{PAPEL[u.papel]}</td>
                    <td className="border-b border-pe-fundo-forte p-3">{u.plano ?? "–"}</td>
                    <td className="border-b border-pe-fundo-forte p-3">
                      <Etiqueta tipo={ESTADO_UTILIZADOR[u.estado].tipo}>{ESTADO_UTILIZADOR[u.estado].nome}</Etiqueta>
                    </td>
                    <td className="border-b border-pe-fundo-forte p-3 tabular-nums">{quandoEntrou(u.ultima_entrada)}</td>
                    <td className="border-b border-pe-fundo-forte px-3 text-right">
                      <LigacaoAbrir href={`/admin/users/${u.id}`} nome={u.nome} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacao pagina={pagina} paginas={data.paginas} total={data.total} nome="utilizadores" aoMudar={setPagina} />
        </div>
      )}

      {convidar ? (
<DialogoConvidar aoFechar={() => setConvidar(false)} />
      ) : null}
      {email ? <DialogoEmail ids={[...seleccao]} aoFechar={() => setEmail(false)} aoEnviado={() => setSeleccao(new Set())} /> : null}
    </>
  );
}

function DialogoEmail({ ids, aoFechar, aoEnviado }: { ids: string[]; aoFechar: () => void; aoEnviado: () => void }) {
  const [enviar, { isLoading }] = useEnviarEmailMutation();
  const [assunto, setAssunto] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [feito, setFeito] = useState<string | null>(null);
  return (
    <Dialogo aberto aoMudar={(v) => !v && aoFechar()} titulo={`Enviar email a ${ids.length} ${ids.length === 1 ? "pessoa" : "pessoas"}`} descricao="Cada pessoa recebe o email em separado, com o nome dela. Não vê os outros destinatários." largura={600}>
      {feito ? (
        <>
          <Aviso tipo="certo">{feito}</Aviso>
          <Botao tamanho="medio" className="self-end" onClick={aoFechar}>
            Fechar
          </Botao>
        </>
      ) : (
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setErro(null);
            if (!assunto.trim() || !mensagem.trim()) return setErro("Escreva o assunto e a mensagem.");
            if (ids.length > 200) return setErro("No máximo 200 pessoas de cada vez.");
            try {
              const r = await enviar({ ids, assunto: assunto.trim(), mensagem: mensagem.trim() }).unwrap();
              const n = r.a_enviar ?? r.enviados;
              setFeito(
                r.em_segundo_plano
                  ? r.message ?? `A enviar a ${n} ${n === 1 ? "pessoa" : "pessoas"}. Pode fechar esta janela.`
                  : r.falhados
                    ? `Enviado a ${r.enviados}. Falharam ${r.falhados}.`
                    : `Enviado a ${n} ${n === 1 ? "pessoa" : "pessoas"}.`
              );
              aoEnviado();
            } catch (x) {
              setErro(mensagemErro(x, "Não foi possível enviar."));
            }
          }}
        >
          <Campo rotulo="Assunto" value={assunto} maxLength={120} onChange={(e) => setAssunto(e.target.value)} />
          <AreaTexto rotulo="Mensagem" rows={7} maxLength={4000} value={mensagem} onChange={(e) => setMensagem(e.target.value)} ajuda="Texto simples. Começa com “Olá, nome” e termina com a assinatura da ProEnglish." />
          {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
          <div className="flex flex-wrap justify-end gap-3">
            <Botao tipo="secundario" tamanho="medio" onClick={aoFechar}>
              Cancelar
            </Botao>
            <Botao type="submit" tamanho="medio" disabled={isLoading}>
              {isLoading ? "A enviar…" : "Enviar email"}
            </Botao>
          </div>
        </form>
      )}
    </Dialogo>
  );
}
