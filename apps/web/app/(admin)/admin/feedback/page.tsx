"use client";

import { useState } from "react";
import { Aviso, AreaTexto, Botao, Etiqueta, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Numeros } from "@/components/pe/professor/Partes";
import { Avatar, CabecaSeccao, Paginacao, SEPARADORES_OPINIOES } from "@/components/pe/admin/Comum";
import { cnPe } from "@/lib/pe";
import { diaMesCurto, mensagemErro } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import { useMudarOpiniaoMutation, useOpinioesQuery, type Opiniao } from "@/src/domains/admin/administracao/negocio";

const FILTROS = { "Por rever": "por_rever", Aprovadas: "aprovada", Recusadas: "recusada", Todas: "todas" } as const;
const ESTADO: Record<Opiniao["estado"], { nome: string; tipo: "realce" | "certo" | "neutra" }> = {
  por_rever: { nome: "Por rever", tipo: "realce" },
  aprovada: { nome: "Aprovada", tipo: "certo" },
  recusada: { nome: "Recusada", tipo: "neutra" },
};
const iniciais = (n: string) =>
  n
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");

export default function Opinioes() {
  const [filtro, setFiltro] = useState<keyof typeof FILTROS>("Por rever");
  const [pagina, setPagina] = useState(1);
  const [aberta, setAberta] = useState<string | null>(null);
  const { data, isError, refetch } = useOpinioesQuery({ estado: FILTROS[filtro], pagina });
  const n = data?.numeros;
  const sel = data?.resultados.find((o) => o.id === aberta) ?? data?.resultados[0] ?? null;

  return (
    <Pagina className="gap-7">
      <CabecaSeccao titulo="Opiniões e testemunhos" activo="Opiniões" itens={SEPARADORES_OPINIOES} />
      {n ? (
        <Numeros
          itens={[
            { nome: "Opiniões", valor: num(n.total), nota: n.novas_mes ? `+${n.novas_mes} este mês` : "nenhuma este mês" },
            { nome: "Média", valor: n.media == null ? "–" : n.media.toLocaleString("pt-PT", { maximumFractionDigits: 1 }), nota: "em 5" },
            { nome: "Por rever", valor: num(n.por_rever), nota: n.por_rever_publicas ? `${n.por_rever_publicas} aceitam ir para o site` : undefined },
            { nome: "No site", valor: num(n.no_site), nota: "testemunhos aprovados" },
          ]}
        />
      ) : isError ? null : (
        <Osso className="h-[104px] rounded-pe-md" />
      )}
      <Pilulas
        rotulo="Mostrar"
        opcoes={Object.keys(FILTROS) as (keyof typeof FILTROS)[]}
        valor={filtro}
        aoMudar={(v) => {
          setFiltro(v);
          setPagina(1);
          setAberta(null);
        }}
      />
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar as opiniões.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-80 rounded-pe-md" />
      ) : !data.resultados.length ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">{filtro === "Por rever" ? "Nenhuma opinião por rever." : "Nenhuma opinião neste filtro."}</p>
      ) : (
        <div className="grid gap-8 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] xl:items-start">
          <div className="flex flex-col gap-4">
            <ul className="m-0 flex list-none flex-col p-0">
              {data.resultados.map((o) => (
                <li key={o.id}>
                  <button
                    type="button"
                    aria-current={sel?.id === o.id ? "true" : undefined}
                    onClick={() => setAberta(o.id)}
                    className={cnPe("flex w-full items-start gap-3 border-b border-pe-fundo-forte px-2 py-3 text-left", sel?.id === o.id ? "bg-pe-fundo-suave" : "hover:bg-pe-fundo-suave")}
                  >
                    <Avatar iniciais={iniciais(o.nome)} />
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="flex items-center justify-between gap-2">
                        <span className="font-semibold">{o.nome}</span>
                        <Etiqueta tipo={ESTADO[o.estado].tipo}>{ESTADO[o.estado].nome}</Etiqueta>
                      </span>
                      <span className="line-clamp-2 text-[15px]">{o.comentario || <span className="text-pe-tinta-suave">Só a nota, sem comentário.</span>}</span>
                      <span className="text-pe-legenda text-pe-tinta-suave">
                        {o.nota} de 5. Pedida em: {o.momento}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <Paginacao pagina={pagina} paginas={data.paginas} total={data.total} nome="opiniões" aoMudar={setPagina} />
          </div>
          {sel ? <Detalhe key={sel.id} o={sel} /> : null}
        </div>
      )}
    </Pagina>
  );
}

function Detalhe({ o }: { o: Opiniao }) {
  const [mudar, { isLoading }] = useMudarOpiniaoMutation();
  const [nota, setNota] = useState(o.nota_interna);
  const [erro, setErro] = useState<string | null>(null);
  const accao = async (corpo: Partial<Opiniao>) => {
    setErro(null);
    try {
      await mudar({ id: o.id, ...corpo }).unwrap();
    } catch (x) {
      setErro(mensagemErro(x, "Não foi possível guardar."));
    }
  };
  return (
    <aside aria-label="Opinião seleccionada" className="flex flex-col gap-4 rounded-pe-md border border-pe-linha p-5 xl:sticky xl:top-6">
      <div className="flex flex-col">
        <span className="font-pe-titulo text-[18px] font-semibold">{o.nome}</span>
        <span className="text-pe-legenda text-pe-tinta-suave">{[o.area, o.plano].filter(Boolean).join(", ")}</span>
      </div>
      <blockquote className="m-0 text-[17px] leading-[26px]">{o.comentario ? `“${o.comentario}”` : "Sem comentário."}</blockquote>
      <dl className="m-0 grid grid-cols-2 gap-2 text-[15px]">
        <dt className="text-pe-tinta-suave">Nota</dt>
        <dd className="m-0 font-semibold">{o.nota} de 5</dd>
        <dt className="text-pe-tinta-suave">Pedida em</dt>
        <dd className="m-0">{o.momento}</dd>
        <dt className="text-pe-tinta-suave">Data</dt>
        <dd className="m-0">{diaMesCurto(new Date(o.criada_em), true)}</dd>
        <dt className="text-pe-tinta-suave">Pode ir para o site</dt>
        <dd className="m-0">{o.permite_publico ? "Sim, com o primeiro nome e a área" : "Não"}</dd>
        <dt className="text-pe-tinta-suave">Aceita contacto</dt>
        <dd className="m-0 break-words">{o.permite_contacto ? (o.contacto ? <a href={`mailto:${o.contacto}`}>{o.contacto}</a> : "Sim, por email") : "Não"}</dd>
      </dl>
      <AreaTexto rotulo="Nota interna" rows={2} maxLength={2000} value={nota} onChange={(e) => setNota(e.target.value)} onBlur={() => nota !== o.nota_interna && void accao({ nota_interna: nota })} ajuda="Só a administração vê. Guarda ao sair do campo." />
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="flex flex-wrap gap-2">
        {o.estado !== "aprovada" ? (
          <Botao tamanho="pequeno" disabled={isLoading} onClick={() => accao({ estado: "aprovada" })}>
            {o.permite_publico && o.comentario ? "Aprovar para o site" : "Aprovar"}
          </Botao>
        ) : null}
        {o.estado !== "recusada" ? (
          <Botao tipo="secundario" tamanho="pequeno" disabled={isLoading} onClick={() => accao({ estado: "recusada" })}>
            Recusar
          </Botao>
        ) : null}
        {o.estado !== "por_rever" ? (
          <Botao tipo="ligacao" tamanho="pequeno" disabled={isLoading} onClick={() => accao({ estado: "por_rever" })}>
            Voltar a rever
          </Botao>
        ) : null}
      </div>
      {o.estado === "aprovada" && o.permite_publico && o.comentario ? <p className="m-0 text-pe-legenda text-pe-tinta-suave">Aparece em Testemunhos no site, onde escolhe se fica visível e a ordem.</p> : null}
    </aside>
  );
}
