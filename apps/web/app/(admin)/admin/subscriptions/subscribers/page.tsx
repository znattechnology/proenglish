"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Aviso, Etiqueta, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Avatar, CabecaSeccao, LigacaoAbrir, Paginacao, Procura, SEPARADORES_SUBSCRICOES } from "@/components/pe/admin/Comum";
import { cnPe } from "@/lib/pe";
import { diaMesCurto } from "@/src/domains/student/subscricao/api";
import { num } from "@/src/domains/teacher/professor/api";
import { ESTADO_SUBSCRICAO, useSubscricoesQuery } from "@/src/domains/admin/administracao/negocio";

const FILTROS = { Todas: "todas", Activas: "activas", "Em teste": "em_teste", "A expirar": "a_expirar", Falhou: "falhou", Canceladas: "canceladas" } as const;
type Filtro = keyof typeof FILTROS;

export default function Assinantes() {
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
  const inicial = (Object.keys(FILTROS) as Filtro[]).find((k) => FILTROS[k] === sp.get("estado")) ?? "Todas";
  const [filtro, setFiltro] = useState<Filtro>(inicial);
  const [q, setQ] = useState("");
  const [qAtrasado, setQAtrasado] = useState("");
  const [pagina, setPagina] = useState(1);
  // "Terminam em 3 dias" chega aqui com ?dias=3; mudar de filtro tira-o.
  const [dias, setDias] = useState(Number(sp.get("dias")) || undefined);
  useEffect(() => {
    const t = setTimeout(() => {
      setQAtrasado(q.trim());
      setPagina(1);
    }, 300);
    return () => clearTimeout(t);
  }, [q]);
  const { data, isError, isFetching, refetch } = useSubscricoesQuery({ estado: FILTROS[filtro], q: qAtrasado || undefined, pagina, dias });

  return (
    <>
      <CabecaSeccao titulo="Subscrições e pagamentos" activo="Assinantes" itens={SEPARADORES_SUBSCRICOES} />
      {dias && filtro === "A expirar" ? <p className="m-0 text-pe-tinta-suave">Planos pagos que terminam nos próximos {dias} dias sem renovação.</p> : null}
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
        <Procura valor={q} aoMudar={setQ} rotulo="Procurar por nome ou email" className="xl:max-w-[360px]" />
        <Pilulas
          rotulo="Estado"
          opcoes={Object.keys(FILTROS) as Filtro[]}
          valor={filtro}
          aoMudar={(v) => {
            setFiltro(v);
            setPagina(1);
            setDias(undefined);
          }}
        />
      </div>
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar as subscrições.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-80 rounded-pe-md" />
      ) : !data.resultados.length ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">Nenhuma subscrição neste estado.</p>
      ) : (
        <div aria-busy={isFetching} className={cnPe("flex flex-col gap-4", isFetching && "opacity-70")}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] border-collapse tabular-nums">
              <caption className="sr-only">Assinantes</caption>
              <thead>
                <tr>
                  {["Assinante", "Plano", "Estado", "Próxima data", "Pagamento", ""].map((t, i) => (
                    <th key={i} scope="col" className="border-b border-pe-linha px-3 py-2.5 text-left text-pe-legenda font-semibold text-pe-tinta-suave">
                      {t || <span className="sr-only">Acções</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.resultados.map((s) => (
                  <tr key={s.id}>
                    <td className="border-b border-pe-fundo-forte p-3">
                      <span className="flex items-center gap-3">
                        <Avatar iniciais={s.utilizador.iniciais} />
                        <span className="flex min-w-0 flex-col">
                          <span className="font-semibold">{s.utilizador.nome}</span>
                          <span className="truncate text-pe-legenda text-pe-tinta-suave">{s.utilizador.email}</span>
                        </span>
                      </span>
                    </td>
                    <td className="border-b border-pe-fundo-forte p-3">
                      {s.plano}, {s.periodo === "teste" ? "em teste" : s.periodo}
                    </td>
                    <td className="border-b border-pe-fundo-forte p-3">
                      <Etiqueta tipo={ESTADO_SUBSCRICAO[s.estado].tipo}>{ESTADO_SUBSCRICAO[s.estado].nome}</Etiqueta>
                    </td>
                    <td className="border-b border-pe-fundo-forte p-3">{s.proxima_data ? diaMesCurto(new Date(s.proxima_data), new Date(s.proxima_data).getFullYear() !== new Date().getFullYear()) : "–"}</td>
                    <td className="border-b border-pe-fundo-forte p-3">
                      {s.pagamento ?? <span className="text-pe-tinta-suave">{s.nota ?? "–"}</span>}
                      {s.pagamento && s.nota ? <span className="block text-pe-legenda text-pe-tinta-suave">{s.nota}</span> : null}
                    </td>
                    <td className="border-b border-pe-fundo-forte px-3 text-right">
                      <LigacaoAbrir href={`/admin/users/${s.utilizador.id}`} nome={s.utilizador.nome} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacao pagina={pagina} paginas={data.paginas} total={data.total} nome={`subscrições (${num(data.pagas)} pagas, ${num(data.em_teste)} em teste)`} aoMudar={setPagina} />
        </div>
      )}
    </>
  );
}
