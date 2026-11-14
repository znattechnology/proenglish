"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { Aviso, Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Cabeca, Numeros } from "@/components/pe/professor/Partes";
import { COLUNA_ALUNOS, COLUNA_CONCLUSAO, TabelaCursos, hrefEditar } from "@/components/pe/professor/TabelaCursos";
import { num, pct, usePainelQuery, type Painel } from "@/src/domains/teacher/professor/api";

function resumo(n: Painel["numeros"]) {
  const partes = [
    n.publicados ? `${n.publicados} ${n.publicados === 1 ? "curso publicado" : "cursos publicados"}` : null,
    n.em_revisao ? `${n.em_revisao} em revisão` : null,
    n.rascunhos ? `${n.rascunhos} em rascunho` : null,
  ].filter(Boolean);
  if (!partes.length) return "Ainda não tem cursos.";
  return partes.join(", ").replace(/, ([^,]*)$/, " e $1") + ".";
}

export default function PainelProfessor() {
  const { data, isError, refetch } = usePainelQuery();

  return (
    <Pagina className="gap-8">
      <Cabeca titulo="Os seus cursos" texto={data ? resumo(data.numeros) : " "}>
        <Botao asChild tamanho="medio">
          <Link href="/teacher/courses/new">
            <Plus aria-hidden className="size-5" />
            Criar curso
          </Link>
        </Botao>
      </Cabeca>

      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar o painel.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-6">
          <Osso className="h-[104px] rounded-pe-md" />
          <Osso className="h-72 rounded-pe-md" />
        </div>
      ) : (
        <Conteudo p={data} />
      )}
    </Pagina>
  );
}

function Conteudo({ p }: { p: Painel }) {
  const n = p.numeros;
  const recusados = p.cursos.filter((c) => c.estado === "rascunho" && c.motivo_recusa);

  if (!p.cursos.length)
    return (
      <section className="flex max-w-[640px] flex-col items-start gap-3 rounded-pe-md bg-pe-fundo-suave p-6 md:p-8">
        <h2 className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">Crie o seu primeiro curso</h2>
        <p className="m-0 text-pe-tinta-suave">
          Pode ser um curso em vídeo, com aulas gravadas, ou um curso de prática, com lições curtas no laboratório. Fica em rascunho até o enviar para revisão; a
          equipa ProEnglish verifica-o antes de entrar no catálogo.
        </p>
        <Botao asChild tamanho="medio">
          <Link href="/teacher/courses/new">Criar curso</Link>
        </Botao>
      </section>
    );

  return (
    <>
      {recusados.map((c) => (
        <Aviso key={c.id} tipo="errado">
          <strong>&ldquo;{c.titulo}&rdquo; não foi aprovado e voltou para rascunho.</strong> {c.motivo_recusa}{" "}
          <Link href={hrefEditar(c)} className="font-semibold">
            Corrigir o curso
          </Link>
        </Aviso>
      ))}

      <Numeros
        itens={[
          { nome: "Alunos inscritos", valor: num(n.alunos), nota: `em ${n.publicados + (n.arquivados ?? 0)} ${n.publicados + (n.arquivados ?? 0) === 1 ? "curso" : "cursos"}` },
          { nome: "Activos esta semana", valor: num(n.alunos_activos_7d), nota: n.alunos ? `${Math.round((n.alunos_activos_7d / n.alunos) * 100)}% dos inscritos` : "sem alunos ainda" },
          { nome: "Conclusão média", valor: pct(n.conclusao_media), nota: "dos alunos inscritos" },
          { nome: "Em revisão", valor: num(n.em_revisao), nota: n.em_revisao ? "à espera da equipa ProEnglish" : "nenhum curso à espera" },
        ]}
      />

      <section aria-labelledby="t-cursos" className="flex flex-col gap-3">
        <h2 id="t-cursos" className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">
          Cursos
        </h2>
        <TabelaCursos cursos={p.cursos} legenda="Os seus cursos" colunas={[COLUNA_ALUNOS, { ...COLUNA_CONCLUSAO, nome: "Conclusão média" }]} />
      </section>

      <section aria-labelledby="t-tropecos" className="flex max-w-[760px] flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h2 id="t-tropecos" className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">
            Onde os alunos tropeçam
          </h2>
          <p className="m-0 text-pe-tinta-suave">Perguntas com mais respostas erradas nos últimos 7 dias.</p>
        </div>
        {p.tropecos.length ? (
          <ul className="m-0 flex list-none flex-col p-0">
            {p.tropecos.map((d) => (
              <li key={d.challenge_id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-pe-linha py-3">
                <span className="flex min-w-0 flex-[1_1_320px] flex-col">
                  <span className="font-semibold">{d.frase}</span>
                  <span className="text-pe-legenda text-pe-tinta-suave">
                    {d.curso}, {d.onde.charAt(0).toLowerCase() + d.onde.slice(1)}
                  </span>
                </span>
                <span className="tabular-nums">
                  {d.erros} {d.erros === 1 ? "erro" : "erros"}
                  {d.acerto != null ? <span className="text-pe-tinta-suave">, {Math.round(d.acerto)}% de acerto</span> : null}
                </span>
                <Link href={d.licao_id ? `/teacher/practice/${d.curso_id}/lessons/${d.licao_id}?exercicio=${d.challenge_id}` : `/teacher/practice/${d.curso_id}`} className="py-2 font-semibold text-pe-azul-vivo underline-offset-[3px]">
                  Rever pergunta
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-4">Sem erros repetidos esta semana. Aparecem aqui quando os alunos falharem a mesma pergunta várias vezes.</p>
        )}
      </section>
    </>
  );
}
