"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { Aviso, BarraProgresso, Etiqueta, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Numeros } from "@/components/pe/professor/Partes";
import { num, pct } from "@/src/domains/teacher/professor/api";
import { useAlunoQuery, type DetalheAluno } from "@/src/domains/teacher/professor/alunos";

const data = (iso: string) => new Date(iso).toLocaleDateString("pt-PT", { day: "numeric", month: "long" });

function horas(min: number) {
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

export default function DetalheAlunoPagina() {
  const { id } = useParams<{ id: string }>();
  const { data: d, isError, error } = useAlunoQuery(id);
  return (
    <Pagina className="gap-7">
      <Link href="/teacher/students" className="-mb-4 inline-flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-vivo no-underline">
        <ChevronLeft aria-hidden className="size-[18px]" />
        Alunos
      </Link>
      {isError ? (
        <Aviso tipo="errado">
          {(error as { status?: number })?.status === 404 ? "Este aluno não está inscrito em nenhum curso seu." : "Não conseguimos carregar os dados do aluno. Tente outra vez."}
        </Aviso>
      ) : !d ? (
        <>
          <Osso className="h-[70px] w-3/4 max-w-[480px]" />
          <Osso className="h-[104px] rounded-pe-md" />
          <Osso className="h-64 rounded-pe-md" />
        </>
      ) : (
        <Conteudo d={d} />
      )}
    </Pagina>
  );
}

function Conteudo({ d }: { d: DetalheAluno }) {
  const { aluno: a, numeros: n } = d;
  const quem = [a.profissao, a.cidade].filter(Boolean).join(", ");
  const variacao = n.acerto_variacao_30d;
  return (
    <>
      <div className="flex items-center gap-4">
        <span aria-hidden className="flex size-14 shrink-0 items-center justify-center rounded-pe-fala bg-pe-azul-marca font-pe-titulo text-[20px] font-bold text-pe-sobre-marca">
          {a.iniciais}
        </span>
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 tracking-[-0.015em] md:text-[32px] md:leading-[38px]">{a.nome}</h1>
          <p className="m-0 text-pe-tinta-suave">
            {quem ? `${quem}. ` : ""}
            {a.inscrito_em ? `Inscrição a ${data(a.inscrito_em)}. ` : ""}
            Plano {a.plano}.
          </p>
        </div>
      </div>

      <Numeros
        itens={[
          { nome: "Dias seguidos", valor: num(n.dias_seguidos), nota: n.pratica_de ? `pratica de ${n.pratica_de}` : undefined },
          { nome: "Pontos", valor: num(n.pontos), nota: n.liga ? `${n.liga.posicao}.º na Liga ${n.liga.nome}` : "ainda sem liga" },
          {
            nome: "Acerto",
            valor: pct(n.acerto),
            nota: variacao == null ? "nos seus cursos" : variacao === 0 ? "igual aos 30 dias anteriores" : `${variacao > 0 ? "+" : "−"}${Math.abs(variacao)} pontos em 30 dias`,
          },
          { nome: "Conversa com o tutor", valor: horas(n.conversa_min), nota: `${n.conversas} ${n.conversas === 1 ? "conversa" : "conversas"}` },
        ]}
      />

      <div className="grid gap-8 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section aria-labelledby="t-cursos" className="flex flex-col gap-3">
          <h2 id="t-cursos" className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">
            Cursos
          </h2>
          <table className="w-full border-collapse tabular-nums">
            <caption className="sr-only">Cursos de {a.nome}</caption>
            <thead>
              <tr>
                <th scope="col" className="border-b border-pe-linha px-3 py-2.5 text-left text-pe-legenda font-semibold text-pe-tinta-suave">
                  Curso
                </th>
                <th scope="col" className="border-b border-pe-linha px-3 py-2.5 text-left text-pe-legenda font-semibold text-pe-tinta-suave">
                  Progresso
                </th>
                <th scope="col" className="border-b border-pe-linha px-3 py-2.5 text-right text-pe-legenda font-semibold text-pe-tinta-suave">
                  Nota
                </th>
              </tr>
            </thead>
            <tbody>
              {d.cursos.map((c) => (
                <tr key={c.id}>
                  <td className="border-b border-pe-fundo-forte p-3">
                    {c.tipo === "pratica" ? "Prática: " : ""}
                    {c.titulo}
                    {c.tipo === "video" ? <span className="text-pe-tinta-suave"> (vídeo)</span> : null}
                  </td>
                  <td className="border-b border-pe-fundo-forte p-3">
                    <span className="flex items-center gap-2">
                      <BarraProgresso valor={c.progresso} rotulo={`Progresso em ${c.titulo}`} className="w-20 sm:w-28" />
                      {c.progresso}%
                    </span>
                  </td>
                  <td className="border-b border-pe-fundo-forte p-3 text-right">
                    <span className="flex flex-col items-end gap-1">
                      {pct(c.nota)}
                      {c.abaixo_minimo ? <Etiqueta tipo="errado">Abaixo do mínimo</Etiqueta> : null}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section aria-labelledby="t-erra" className="flex flex-col gap-3">
          <h2 id="t-erra" className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">
            Onde mais erra
          </h2>
          {d.onde_erra.length ? (
            <ul className="m-0 flex list-none flex-col p-0">
              {d.onde_erra.map((e) => (
                <li key={e.tema + e.onde} className="flex items-start justify-between gap-4 border-b border-pe-fundo-forte py-3">
                  <span className="flex min-w-0 flex-col">
                    <span className="font-semibold">{e.tema}</span>
                    <span className="text-pe-legenda text-pe-tinta-suave">{e.onde}</span>
                  </span>
                  <span className="shrink-0 tabular-nums">
                    {e.erros} {e.erros === 1 ? "erro" : "erros"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Sem erros repetidos nos últimos 60 dias.</p>
          )}
        </section>
      </div>
    </>
  );
}
