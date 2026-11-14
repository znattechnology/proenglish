"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { CheckCircle2, ChevronLeft, FileText, XCircle } from "lucide-react";
import { AreaTexto, Aviso, Botao, Etiqueta, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { EtiquetaEstado } from "@/components/pe/professor/Partes";
import { cnPe } from "@/lib/pe";
import { dataPt, mensagemErro } from "@/src/domains/student/subscricao/api";
import { duracaoPorExtenso } from "@/src/domains/teacher/professor/envio";
import { nomeTipo } from "@/src/domains/teacher/professor/pratica";
import { useAprovarMutation, useArquivarAdminMutation, useCursoRevisaoQuery, useRecusarMutation, type DetalheRevisao, type ExercicioRevisao } from "@/src/domains/admin/administracao/api";

const h2 = "m-0 font-pe-titulo text-[20px] font-semibold leading-7";

export default function RevisaoCurso() {
  const { id } = useParams<{ id: string }>();
  const { data, isError, refetch } = useCursoRevisaoQuery(id);
  const emRevisao = data?.curso.estado === "em_revisao";
  return (
    <Pagina className="gap-7">
      <Link href={emRevisao ? "/admin/courses/review" : "/admin/courses"} className="-mb-4 inline-flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-vivo no-underline">
        <ChevronLeft aria-hidden className="size-[18px]" />
        {emRevisao ? "Cursos em revisão" : "Todos os cursos"}
      </Link>
      {isError ? <Aviso tipo="errado">Não conseguimos abrir o curso.</Aviso> : !data ? <Osso className="h-96 rounded-pe-md" /> : <Conteudo d={data} recarregar={() => void refetch()} />}
    </Pagina>
  );
}

function Conteudo({ d, recarregar }: { d: DetalheRevisao; recarregar: () => void }) {
  const c = d.curso;
  const [recusar, setRecusar] = useState(false);
  const [arquivar, setArquivar] = useState(false);
  const [aprovar, { isLoading: aAprovar }] = useAprovarMutation();
  const [msg, setMsg] = useState<{ tipo: "certo" | "errado"; texto: string } | null>(null);
  const falhas = d.verificacao.itens.filter((i) => !i.ok);

  return (
    <>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="m-0 flex flex-wrap items-center gap-3 font-pe-titulo text-[26px] font-bold leading-8 tracking-[-0.015em] md:text-[32px] md:leading-[38px]">
            {c.titulo}
            <EtiquetaEstado estado={c.estado} />
          </h1>
          <p className="m-0 text-pe-tinta-suave">
            {c.tipo === "video" ? "Curso em vídeo" : "Curso de prática"}, {[c.area, c.nivel].filter(Boolean).join(", ")}. Por{" "}
            <Link href={`/admin/users/${d.professor.id}`}>{d.professor.nome}</Link> ({d.professor.cursos_publicados} {d.professor.cursos_publicados === 1 ? "curso publicado" : "cursos publicados"}).
            {c.submetido_em ? ` Enviado a ${dataPt(c.submetido_em)}.` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          {c.estado === "em_revisao" ? (
            <>
              <Botao tipo="secundario" tamanho="medio" onClick={() => setRecusar(true)}>
                Recusar
              </Botao>
              <Botao
                tamanho="medio"
                disabled={aAprovar || !d.verificacao.pode_submeter}
                onClick={async () => {
                  setMsg(null);
                  try {
                    await aprovar(c.id).unwrap();
                    setMsg({ tipo: "certo", texto: "Curso aprovado: já está no catálogo e o professor foi avisado." });
                  } catch (x) {
                    setMsg({ tipo: "errado", texto: mensagemErro(x, "Não foi possível aprovar.") });
                    recarregar(); // o curso pode ter mudado: mostra a lista de verificação actual
                  }
                }}
              >
                {aAprovar ? "A aprovar…" : "Aprovar e publicar"}
              </Botao>
            </>
          ) : c.estado === "publicado" ? (
            <Botao tipo="perigo" tamanho="medio" onClick={() => setArquivar(true)}>
              Arquivar curso
            </Botao>
          ) : null}
        </div>
      </div>

      {msg ? <Aviso tipo={msg.tipo}>{msg.texto}</Aviso> : null}
      {c.estado === "em_revisao" && c.estado_antes_revisao === "arquivado" ? (
        <Aviso tipo="info">Este curso estava arquivado. Se for recusado, volta a arquivado; os alunos inscritos mantêm o acesso que tinham.</Aviso>
      ) : null}
      {c.estado === "em_revisao" && falhas.length ? (
        <Aviso tipo="errado">Não pode aprovar enquanto a lista de verificação tiver pontos a vermelho. Recuse e diga ao professor o que falta.</Aviso>
      ) : null}

      <div className="flex flex-col gap-8 lg:flex-row lg:items-start">
        <div className="flex min-w-0 flex-1 flex-col gap-8">
          <section aria-labelledby="t-lista" className="flex flex-col gap-2">
            <h2 id="t-lista" className={h2}>
              Lista de verificação
            </h2>
            <ul className="m-0 flex list-none flex-col p-0">
              {d.verificacao.itens.map((i) => (
                <li key={i.chave} className="flex gap-3 border-b border-pe-fundo-forte py-2.5">
                  {i.ok ? <CheckCircle2 aria-hidden className="mt-0.5 size-5 shrink-0 text-pe-certo" /> : <XCircle aria-hidden className="mt-0.5 size-5 shrink-0 text-pe-errado" />}
                  <span className="flex flex-col">
                    <span className="font-semibold">
                      <span className="sr-only">{i.ok ? "Feito: " : "Por corrigir: "}</span>
                      {i.titulo}
                    </span>
                    {i.detalhe ? <span className="text-pe-legenda text-pe-tinta-suave">{i.detalhe}</span> : null}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="t-conteudo" className="flex flex-col gap-3">
            <h2 id="t-conteudo" className={h2}>
              Conteúdo
            </h2>
            {d.estrutura.seccoes ? <ConteudoVideo seccoes={d.estrutura.seccoes} /> : null}
            {d.estrutura.unidades ? <ConteudoPratica unidades={d.estrutura.unidades} /> : null}
          </section>
        </div>

        <aside aria-label="Como aparece no catálogo" className="flex w-full shrink-0 flex-col overflow-hidden rounded-pe-md border border-pe-linha lg:sticky lg:top-6 lg:w-[340px]">
          {c.tipo === "video" ? (
            <div className="relative flex aspect-video items-center justify-center bg-pe-fundo-forte">
              {c.imagem ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={c.imagem} alt="" className="absolute inset-0 size-full object-cover" />
              ) : (
                <span className="text-pe-legenda text-pe-tinta-suave">Sem imagem de capa</span>
              )}
            </div>
          ) : null}
          <div className="flex flex-col gap-2 p-5">
            <span className="font-pe-titulo text-[18px] font-bold leading-6">{c.titulo}</span>
            <span className="text-[15px] leading-[22px] text-pe-tinta-suave">{c.descricao}</span>
            {c.acesso ? <Etiqueta className="mt-1">{c.acesso === "todos" ? "Todos os planos" : "Premium e Premium Plus"}</Etiqueta> : null}
          </div>
        </aside>
      </div>

      {recusar ? <DialogoRecusar id={c.id} titulo={c.titulo} falhas={falhas.map((f) => [f.titulo, f.detalhe].filter(Boolean).join(": "))} aoFechar={() => setRecusar(false)} aoFeito={(t) => setMsg({ tipo: "certo", texto: t })} /> : null}
      {arquivar ? <DialogoArquivarAdmin id={c.id} titulo={c.titulo} aoFechar={() => setArquivar(false)} aoFeito={(t) => setMsg({ tipo: "certo", texto: t })} /> : null}
    </>
  );
}

function ConteudoVideo({ seccoes }: { seccoes: NonNullable<DetalheRevisao["estrutura"]["seccoes"]> }) {
  const [aberta, setAberta] = useState<string | null>(null);
  return (
    <ol className="m-0 flex list-none flex-col gap-4 p-0">
      {seccoes.map((s, i) => (
        <li key={s.id} className="flex flex-col gap-1">
          <span className="font-semibold">
            Secção {i + 1}: {s.titulo}
          </span>
          <ul className="m-0 flex list-none flex-col p-0">
            {s.aulas.map((a) => (
              <li key={a.id} className="border-b border-pe-fundo-forte">
                <button type="button" aria-expanded={aberta === a.id} onClick={() => setAberta(aberta === a.id ? null : a.id)} className="flex min-h-11 w-full items-center justify-between gap-3 py-2 text-left hover:bg-pe-fundo-suave">
                  <span>{a.titulo}</span>
                  <span className="shrink-0 text-[14px] text-pe-tinta-suave">
                    {a.video ? duracaoPorExtenso(a.duracao_s) ?? "vídeo" : a.tipo && a.tipo !== "Video" ? (a.tipo === "Quiz" ? "questionário" : "texto") : "sem vídeo"}
                    {a.questionario.activo && a.questionario.perguntas ? `, ${a.questionario.perguntas} perguntas` : ""}
                  </span>
                </button>
                {aberta === a.id ? (
                  <div className="flex flex-col gap-3 pb-4">
                    {a.video ? (
                       
                      <video src={a.video.url} controls preload="metadata" className="aspect-video w-full max-w-[560px] rounded-pe-md bg-pe-azul-marca" />
                    ) : null}
                    {a.resumo ? <p className="m-0 text-[15px]">{a.resumo}</p> : null}
                    {a.materiais.length ? (
                      <ul className="m-0 flex list-none flex-col gap-1 p-0">
                        {a.materiais.map((m) => (
                          <li key={m.id} className="flex items-center gap-2 text-[15px]">
                            <FileText aria-hidden className="size-4 text-pe-tinta-suave" />
                            <a href={m.url} target="_blank" rel="noreferrer">
                              {m.nome}
                            </a>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}

function Exercicio({ e, n }: { e: ExercicioRevisao; n: number }) {
  return (
    <li className="flex flex-col gap-1.5 border-b border-pe-fundo-forte py-3">
      <span className="flex items-center gap-2 text-[14px] font-semibold text-pe-tinta-suave">
        {n}. <Etiqueta>{nomeTipo(e.tipo)}</Etiqueta>
        {e.tipo === "escuta" && !e.audio_url ? <span className="text-pe-errado">sem áudio</span> : null}
      </span>
      {e.enunciado ? <span>{e.enunciado}</span> : null}
      {e.frase ? <span lang="en" className="font-semibold">{e.frase}</span> : null}
      {e.resposta ? (
        <span className="text-[15px]">
          Resposta: <strong lang="en">{e.resposta}</strong>
        </span>
      ) : null}
      {e.opcoes.length ? (
        <span className="flex flex-wrap gap-1.5">
          {e.opcoes.map((o, i) => (
            <span key={i} className={cnPe("rounded-pe-sm px-2 py-0.5 text-[15px]", o.certa ? "bg-pe-certo-suave font-semibold text-pe-certo" : "bg-pe-fundo-suave")}>
              {o.texto}
              {o.certa ? <span className="sr-only"> (certa)</span> : null}
            </span>
          ))}
        </span>
      ) : null}
      {e.pares.length ? <span className="text-[15px]">{e.pares.map((p) => `${p.a} = ${p.b}`).join("; ")}</span> : null}
      {e.audio_url ? (
         
        <audio controls src={e.audio_url} className="h-9 max-w-full" />
      ) : null}
      {e.explicacao ? <span className="text-[14px] text-pe-tinta-suave">{e.explicacao}</span> : null}
    </li>
  );
}

function ConteudoPratica({ unidades }: { unidades: NonNullable<DetalheRevisao["estrutura"]["unidades"]> }) {
  const [aberta, setAberta] = useState<string | null>(null);
  return (
    <ol className="m-0 flex list-none flex-col gap-4 p-0">
      {unidades.map((u, i) => (
        <li key={u.id} className="flex flex-col gap-1">
          <span className="font-semibold">
            Unidade {i + 1}: {u.titulo}
          </span>
          <ul className="m-0 flex list-none flex-col p-0">
            {u.licoes.map((l) => (
              <li key={l.id} className="border-b border-pe-fundo-forte">
                <button type="button" aria-expanded={aberta === l.id} onClick={() => setAberta(aberta === l.id ? null : l.id)} className="flex min-h-11 w-full items-center justify-between gap-3 py-2 text-left hover:bg-pe-fundo-suave">
                  <span>{l.titulo}</span>
                  <span className="shrink-0 text-[14px] text-pe-tinta-suave">{l.exercicios.length} exercícios</span>
                </button>
                {aberta === l.id ? (
                  <ol className="m-0 mb-3 flex list-none flex-col rounded-pe-md bg-pe-fundo px-3 p-0">
                    {l.exercicios.map((e, k) => (
                      <Exercicio key={e.id} e={e} n={k + 1} />
                    ))}
                  </ol>
                ) : null}
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}

function DialogoRecusar({ id, titulo, falhas, aoFechar, aoFeito }: { id: string; titulo: string; falhas: string[]; aoFechar: () => void; aoFeito: (t: string) => void }) {
  const [recusar, { isLoading }] = useRecusarMutation();
  const [motivo, setMotivo] = useState(falhas.length ? `Falta corrigir: ${falhas.join("; ")}.` : "");
  const [erro, setErro] = useState<string | null>(null);
  return (
    <Dialogo aberto aoMudar={(v) => !v && aoFechar()} titulo={`Recusar "${titulo}"?`} descricao="O curso volta para o professor com o motivo. Ele recebe uma notificação e pode corrigir e enviar outra vez." largura={560}>
      <AreaTexto rotulo="Motivo para o professor" rows={5} maxLength={1000} value={motivo} onChange={(e) => setMotivo(e.target.value)} ajuda="Seja concreto: o que tem de mudar e onde." />
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="flex flex-wrap justify-end gap-3">
        <Botao tipo="secundario" tamanho="medio" onClick={aoFechar}>
          Cancelar
        </Botao>
        <Botao
          tipo="perigo"
          tamanho="medio"
          disabled={isLoading}
          onClick={async () => {
            setErro(null);
            if (motivo.trim().length < 5) return setErro("Escreva o motivo (pelo menos uma frase).");
            try {
              await recusar({ id, motivo: motivo.trim() }).unwrap();
              aoFechar();
              aoFeito("Curso recusado: o professor foi avisado com o motivo.");
            } catch (x) {
              setErro(mensagemErro(x, "Não foi possível recusar."));
            }
          }}
        >
          Recusar curso
        </Botao>
      </div>
    </Dialogo>
  );
}

function DialogoArquivarAdmin({ id, titulo, aoFechar, aoFeito }: { id: string; titulo: string; aoFechar: () => void; aoFeito: (t: string) => void }) {
  const [arquivar, { isLoading }] = useArquivarAdminMutation();
  const [modo, setModo] = useState<"manter" | "fechar">("manter");
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  return (
    <Dialogo aberto aoMudar={(v) => !v && aoFechar()} titulo={`Arquivar "${titulo}"?`} descricao="O curso sai do catálogo e deixa de aceitar inscrições. O professor é avisado com o motivo." largura={560}>
      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-2 p-0 font-semibold">E os alunos inscritos?</legend>
        {(
          [
            { v: "manter", nome: "Podem terminar o curso", texto: "Mantêm o progresso e o certificado." },
            { v: "fechar", nome: "Fechar para todos", texto: "Deixam de ver as aulas. Os certificados emitidos continuam válidos." },
          ] as const
        ).map((o) => (
          <label key={o.v} className={cnPe("flex cursor-pointer items-start gap-3 rounded-pe-md p-3", modo === o.v ? "border-2 border-pe-azul-marca bg-pe-fundo-suave" : "border-[1.5px] border-pe-linha")}>
            <input type="radio" name="modo-admin" checked={modo === o.v} onChange={() => setModo(o.v)} className="mt-1 size-5 shrink-0 accent-pe-azul-marca" />
            <span className="flex flex-col">
              <span className="font-semibold">{o.nome}</span>
              <span className="text-[15px] text-pe-tinta-suave">{o.texto}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <AreaTexto rotulo="Motivo para o professor" rows={3} maxLength={1000} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="flex flex-wrap justify-end gap-3">
        <Botao tipo="secundario" tamanho="medio" onClick={aoFechar}>
          Cancelar
        </Botao>
        <Botao
          tipo="perigo"
          tamanho="medio"
          disabled={isLoading}
          onClick={async () => {
            setErro(null);
            if (motivo.trim().length < 5) return setErro("Escreva o motivo.");
            try {
              await arquivar({ id, modo, motivo: motivo.trim() }).unwrap();
              aoFechar();
              aoFeito("Curso arquivado: o professor foi avisado.");
            } catch (x) {
              setErro(mensagemErro(x, "Não foi possível arquivar."));
            }
          }}
        >
          Arquivar curso
        </Botao>
      </div>
    </Dialogo>
  );
}
