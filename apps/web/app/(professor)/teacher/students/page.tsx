"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Download, Search } from "lucide-react";
import { Aviso, BarraProgresso, Botao, Etiqueta, Escolha, Osso, Pilulas } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Numeros } from "@/components/pe/professor/Partes";
import { CabecaAlunos } from "@/components/pe/professor/SeparadoresAlunos";
import { cnPe } from "@/lib/pe";
import { num, pct, useCursosQuery } from "@/src/domains/teacher/professor/api";
import { descarregarCsv, haQuanto, useAlunosQuery, type EstadoAluno, type FiltroAlunos, type LinhaAluno } from "@/src/domains/teacher/professor/alunos";

const FILTROS = { Todos: "todos", "Em risco": "em_risco", Activos: "activos" } as const;
const ESTADO: Record<EstadoAluno, { nome: string; tipo: "certo" | "errado" | "neutra" }> = {
  activo: { nome: "Activo", tipo: "certo" },
  pouco_activo: { nome: "Pouco activo", tipo: "neutra" },
  em_risco: { nome: "Em risco", tipo: "errado" },
  novo: { nome: "Novo", tipo: "neutra" },
};

export default function Alunos() {
  const [filtro, setFiltro] = useState<keyof typeof FILTROS>("Todos");
  const [curso, setCurso] = useState("");
  const [q, setQ] = useState("");
  const [qAtrasado, setQAtrasado] = useState("");
  const [pagina, setPagina] = useState(1);
  const [aExportar, setAExportar] = useState(false);
  const [erroExportar, setErroExportar] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      setQAtrasado(q.trim());
      setPagina(1);
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const pedido: FiltroAlunos = { filtro: FILTROS[filtro], curso: curso || undefined, q: qAtrasado || undefined, pagina };
  const { data, isError, isFetching, refetch } = useAlunosQuery(pedido);
  const { data: video } = useCursosQuery({ tipo: "video" });
  const { data: pratica } = useCursosQuery({ tipo: "pratica" });
  const cursos = [...(video?.resultados ?? []), ...(pratica?.resultados ?? [])].filter((c) => c.estado !== "rascunho");
  const n = data?.numeros;

  return (
    <Pagina className="gap-7">
      <CabecaAlunos activo="Alunos" texto="Todos os alunos inscritos nos seus cursos." />

      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os alunos.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : null}

      {n ? (
        <Numeros
          itens={[
            { nome: "Alunos", valor: num(n.alunos), nota: `em ${n.cursos} ${n.cursos === 1 ? "curso" : "cursos"}` },
            { nome: "Activos esta semana", valor: num(n.activos_7d), nota: `${Math.round(n.pct_activos)}% dos alunos` },
            { nome: "Em risco", valor: num(n.em_risco), nota: "sem praticar há 10 dias ou mais" },
            { nome: "Acerto médio", valor: pct(n.acerto_medio), nota: "nos exercícios" },
          ]}
        />
      ) : !isError ? (
        <Osso className="h-[104px] rounded-pe-md" />
      ) : null}

      <div className="flex flex-col gap-3 xl:flex-row xl:items-end">
        <Pilulas
          rotulo="Mostrar"
          opcoes={Object.keys(FILTROS) as (keyof typeof FILTROS)[]}
          valor={filtro}
          aoMudar={(f) => {
            setFiltro(f);
            setPagina(1);
          }}
        />
        <label className="flex h-11 w-full items-center gap-2 rounded-pe-sm border-[1.5px] border-pe-linha-forte px-3 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-pe-azul-vivo xl:max-w-[300px]">
          <Search aria-hidden className="size-[18px] text-pe-tinta-suave" />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Procurar pelo nome"
            aria-label="Procurar pelo nome"
            className="min-w-0 flex-1 border-0 bg-transparent font-pe-texto text-[16px] text-pe-tinta outline-none"
          />
        </label>
        <Escolha rotulo="Curso" className="xl:w-[260px] [&_select]:h-11" value={curso} onChange={(e) => {
            setCurso(e.target.value);
            setPagina(1);
          }}>
          <option value="">Todos os cursos</option>
          {cursos.map((c) => (
            <option key={c.id} value={c.id}>
              {c.tipo === "pratica" ? `Prática: ${c.titulo}` : c.titulo}
            </option>
          ))}
        </Escolha>
        <Botao
          tipo="secundario"
          tamanho="pequeno"
          className="xl:ml-auto"
          disabled={aExportar || !data?.total}
          onClick={async () => {
            setErroExportar(null);
            setAExportar(true);
            try {
              const p = new URLSearchParams({ filtro: FILTROS[filtro], ...(curso ? { curso } : {}), ...(qAtrasado ? { q: qAtrasado } : {}) });
              await descarregarCsv(`/teacher/alunos/exportar/?${p}`, "alunos.csv");
            } catch {
              setErroExportar("Não foi possível exportar. Tente outra vez.");
            } finally {
              setAExportar(false);
            }
          }}
        >
          <Download aria-hidden className="size-[18px]" />
          {aExportar ? "A exportar…" : "Exportar"}
        </Botao>
      </div>
      {erroExportar ? <Aviso tipo="errado">{erroExportar}</Aviso> : null}

      {!data ? (
        isError ? null : <Osso className="h-80 rounded-pe-md" />
      ) : !data.resultados.length ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">
          {qAtrasado
            ? `Nenhum aluno com "${qAtrasado}".`
            : filtro === "Em risco"
              ? "Nenhum aluno em risco. Aparecem aqui os que ficam 10 dias ou mais sem praticar."
              : n?.alunos
                ? "Nenhum aluno com estes filtros."
                : "Ainda não tem alunos. Aparecem aqui quando alguém se inscrever num curso seu publicado."}
        </p>
      ) : (
        <div aria-busy={isFetching} className={cnPe("flex flex-col gap-4", isFetching && "opacity-70")}>
          <Tabela linhas={data.resultados} />
          {data.paginas > 1 ? (
            <nav aria-label="Páginas" className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-pe-tinta-suave">
                Página {pagina} de {data.paginas}, {num(data.total)} alunos
              </span>
              <span className="flex gap-2">
                <Botao tipo="secundario" tamanho="pequeno" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>
                  Anterior
                </Botao>
                <Botao tipo="secundario" tamanho="pequeno" disabled={pagina >= data.paginas} onClick={() => setPagina(pagina + 1)}>
                  Seguinte
                </Botao>
              </span>
            </nav>
          ) : null}
        </div>
      )}
    </Pagina>
  );
}

function Avatar({ iniciais }: { iniciais: string }) {
  return (
    <span aria-hidden className="flex size-9 shrink-0 items-center justify-center rounded-pe-fala-s bg-pe-fundo-forte text-[14px] font-semibold">
      {iniciais}
    </span>
  );
}

function NomeCurso({ a }: { a: LinhaAluno }) {
  return (
    <>
      {a.curso.tipo === "pratica" ? "Prática: " : ""}
      {a.curso.titulo}
      {a.outros_cursos ? <span className="text-pe-tinta-suave"> e mais {a.outros_cursos}</span> : null}
    </>
  );
}

function Tabela({ linhas }: { linhas: LinhaAluno[] }) {
  const th = "border-b border-pe-linha px-3 py-2.5 text-pe-legenda font-semibold text-pe-tinta-suave";
  const td = "border-b border-pe-fundo-forte p-3 align-middle";
  return (
    <>
      <table className="hidden w-full border-collapse tabular-nums lg:table">
        <caption className="sr-only">Alunos</caption>
        <thead>
          <tr>
            <th scope="col" className={`${th} text-left`}>Aluno</th>
            <th scope="col" className={`${th} text-left`}>Curso</th>
            <th scope="col" className={`${th} text-left`}>Progresso</th>
            <th scope="col" className={`${th} text-right`}>Acerto</th>
            <th scope="col" className={`${th} text-left`}>Última actividade</th>
            <th scope="col" className={`${th} text-left`}>Estado</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((a) => (
            <tr key={a.id} className="hover:bg-pe-fundo-suave">
              <td className={td}>
                <Link href={`/teacher/students/${a.id}`} className="flex items-center gap-3 font-semibold text-pe-tinta no-underline hover:underline">
                  <Avatar iniciais={a.iniciais} />
                  {a.nome}
                </Link>
              </td>
              <td className={`${td} max-w-[260px]`}>
                <NomeCurso a={a} />
              </td>
              <td className={td}>
                <span className="flex items-center gap-2">
                  <BarraProgresso valor={a.progresso} rotulo={`Progresso de ${a.nome}`} className="w-24" />
                  <span>{a.progresso}%</span>
                </span>
              </td>
              <td className={`${td} text-right`}>{pct(a.acerto)}</td>
              <td className={td}>{haQuanto(a.ultima_actividade)}</td>
              <td className={td}>
                <Etiqueta tipo={ESTADO[a.estado].tipo}>{ESTADO[a.estado].nome}</Etiqueta>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul aria-label="Alunos" className="m-0 flex list-none flex-col p-0 lg:hidden">
        {linhas.map((a) => (
          <li key={a.id} className="border-b border-pe-fundo-forte">
            <Link href={`/teacher/students/${a.id}`} className="flex items-start gap-3 py-3.5 text-pe-tinta no-underline">
              <Avatar iniciais={a.iniciais} />
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{a.nome}</span>
                  <Etiqueta tipo={ESTADO[a.estado].tipo}>{ESTADO[a.estado].nome}</Etiqueta>
                </span>
                <span className="text-[15px] leading-[22px] text-pe-tinta-suave">
                  <NomeCurso a={a} />
                </span>
                <span className="text-[15px] tabular-nums">
                  {a.progresso}% feito, {pct(a.acerto)} de acerto, {haQuanto(a.ultima_actividade).toLowerCase()}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
