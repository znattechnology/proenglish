"use client";

import { useRef, useState } from "react";
import { ArrowDown, ArrowUp, FileText, Paperclip, Trash2, Upload, X } from "lucide-react";
import { AreaTexto, Aviso, Botao, Campo, Escolha } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { duracaoDoVideo, duracaoPorExtenso, enviarFicheiro, tamanho } from "@/src/domains/teacher/professor/envio";
import {
  professorApi,
  useApagarAulaMutation,
  useApagarMaterialMutation,
  useLicoesPraticaQuery,
  useMudarAulaMutation,
  useOrdenarAulasMutation,
  type Aula,
  type Seccao,
} from "@/src/domains/teacher/professor/api";
import { erroProfessor } from "@/src/domains/teacher/professor/api";
import { useDispatch } from "react-redux";
import { FalaDaAulaProfessor } from "./FalaDaAula";
import { EditorQuestionario } from "./Questionario";

const TIPOS_VIDEO = "video/mp4,video/webm,video/quicktime";
const TIPOS_MATERIAL = ".pdf,.mp3,.m4a,.wav,.png,.jpg,.jpeg,.webp,.xlsx,.csv,.docx";

/** Editor de uma aula: vídeo, título, quando conta como vista, resumo, materiais, questionário e prática a seguir. */
export function PainelAula({
  cursoId,
  aula,
  seccao,
  seccoes,
  aoGuardar,
  aoApagada,
}: {
  cursoId: string;
  aula: Aula;
  seccao: Seccao;
  seccoes: Seccao[];
  aoGuardar: () => void;
  aoApagada: () => void;
}) {
  const dispatch = useDispatch();
  const [titulo, setTitulo] = useState(aula.titulo);
  const [resumo, setResumo] = useState(aula.resumo ?? "");
  const [erro, setErro] = useState<string | null>(null);
  const [envio, setEnvio] = useState<{ nome: string; f: number; tipo: "video" | "material" } | null>(null);
  const [apagar, setApagar] = useState(false);
  const [perguntas, setPerguntas] = useState(false);
  const cancelar = useRef<AbortController | null>(null);
  const inputVideo = useRef<HTMLInputElement>(null);
  const inputMaterial = useRef<HTMLInputElement>(null);

  const [mudar] = useMudarAulaMutation();
  const [ordenar] = useOrdenarAulasMutation();
  const [remover, { isLoading: aRemover }] = useApagarAulaMutation();
  const [removerMaterial] = useApagarMaterialMutation();

  const i = seccao.aulas.findIndex((a) => a.id === aula.id);

  async function guardar(campos: Parameters<typeof mudar>[0]) {
    setErro(null);
    try {
      await mudar(campos).unwrap();
      aoGuardar();
    } catch (e) {
      setErro(erroProfessor(e, "Não foi possível guardar. Tente outra vez."));
    }
  }

  async function mover(d: -1 | 1) {
    const ids = seccao.aulas.map((a) => a.id);
    [ids[i], ids[i + d]] = [ids[i + d], ids[i]];
    setErro(null);
    try {
      await ordenar({ seccao: seccao.id, ids }).unwrap();
      aoGuardar();
    } catch (e) {
      setErro(erroProfessor(e, "Não foi possível mudar a ordem."));
    }
  }

  async function enviar(ficheiro: File, tipo: "video" | "material") {
    setErro(null);
    const limite = tipo === "video" ? 2 * 1024 ** 3 : 20 * 1024 ** 2;
    if (ficheiro.size > limite) return setErro(`"${ficheiro.name}" tem ${tamanho(ficheiro.size)}. O máximo é ${tipo === "video" ? "2 GB" : "20 MB"}.`);
    const duracao = tipo === "video" ? await duracaoDoVideo(ficheiro) : null;
    cancelar.current = new AbortController();
    setEnvio({ nome: ficheiro.name, f: 0, tipo });
    try {
      await enviarFicheiro({ tipo, aula: aula.id }, ficheiro, (f) => setEnvio((v) => (v ? { ...v, f } : v)), cancelar.current.signal);
      if (tipo === "video" && duracao != null) await mudar({ id: aula.id, duracao_s: duracao }).unwrap();
      dispatch(professorApi.util.invalidateTags(["Estrutura", "Verificacao", "Cursos"]));
      aoGuardar();
    } catch (e) {
      if (!(e as { cancelado?: boolean })?.cancelado) setErro(erroProfessor(e, "O envio falhou. Tente outra vez."));
    } finally {
      setEnvio(null);
    }
  }

  return (
    <section aria-label={`Aula: ${aula.titulo}`} className="flex min-w-0 flex-1 flex-col gap-5">
      <div className="flex flex-col gap-5 xl:flex-row">
        <div className="flex w-full shrink-0 flex-col gap-2 xl:w-[360px]">
          <div className="pe-sobre-marca relative flex aspect-video w-full flex-col items-center justify-center gap-2 overflow-hidden rounded-pe-md bg-pe-azul-marca p-4 text-center text-pe-sobre-marca">
            {envio?.tipo === "video" ? (
              <>
                <span className="text-[15px] font-semibold">A enviar {envio.nome}</span>
                <span className="h-2 w-4/5 overflow-hidden rounded-full bg-[rgba(255,255,255,0.25)]">
                  <span className="block h-full bg-pe-realce transition-[width]" style={{ width: `${Math.round(envio.f * 100)}%` }} />
                </span>
                <span aria-live="polite" className="text-[14px] tabular-nums">
                  {Math.round(envio.f * 100)}%
                </span>
                <button type="button" onClick={() => cancelar.current?.abort()} className="text-[14px] font-semibold text-pe-sobre-marca underline underline-offset-[3px]">
                  Cancelar envio
                </button>
              </>
            ) : aula.video ? (
              <video key={aula.video.url} src={aula.video.url} controls preload="metadata" className="absolute inset-0 size-full bg-pe-azul-marca object-contain" />
            ) : (
              <>
                <Upload aria-hidden className="size-7 text-pe-realce" />
                {aula.tipo && aula.tipo !== "Video" ? (
                  <>
                    <span className="font-semibold">{aula.tipo === "Quiz" ? "Aula só com questionário" : "Aula de texto"}</span>
                    <span className="text-[14px] leading-5 opacity-90">Os alunos já a vêem. Se quiser, junte-lhe um vídeo.</span>
                  </>
                ) : (
                  <>
                    <span className="font-semibold">Esta aula ainda não tem vídeo</span>
                    <span className="text-[14px] leading-5 opacity-90">Os alunos só a vêem depois de enviar o vídeo.</span>
                  </>
                )}
                <span className="text-[14px] leading-5 opacity-90">MP4, WebM ou MOV, até 2 GB.</span>
                <Botao tipo="realce" tamanho="pequeno" onClick={() => inputVideo.current?.click()}>
                  Escolher vídeo
                </Botao>
              </>
            )}
          </div>
          {aula.video && !envio ? (
            <div className="flex flex-wrap items-center justify-between gap-x-3 text-[14px] leading-5">
              <span className="min-w-0 truncate text-pe-tinta-suave">
                {[aula.video.nome, duracaoPorExtenso(aula.duracao_s)].filter(Boolean).join(", ")}
              </span>
              <button type="button" onClick={() => inputVideo.current?.click()} className="min-h-11 font-semibold text-pe-azul-vivo underline underline-offset-[3px]">
                Trocar o vídeo
              </button>
            </div>
          ) : null}
          <input
            ref={inputVideo}
            type="file"
            accept={TIPOS_VIDEO}
            className="sr-only"
            tabIndex={-1}
            aria-hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (f) void enviar(f, "video");
            }}
          />
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <Campo
            rotulo="Título da aula"
            value={titulo}
            maxLength={120}
            onChange={(e) => setTitulo(e.target.value)}
            onBlur={() => {
              const t = titulo.trim();
              if (!t) return setTitulo(aula.titulo);
              if (t !== aula.titulo) void guardar({ id: aula.id, titulo: t });
            }}
          />
          <Escolha
            rotulo="Quando conta como vista"
            value={aula.percentagem_vista}
            onChange={(e) => void guardar({ id: aula.id, percentagem_vista: Number(e.target.value) as Aula["percentagem_vista"] })}
          >
            <option value={80}>Depois de ver 80% do vídeo</option>
            <option value={100}>Só depois de ver até ao fim</option>
            <option value={50}>Depois de ver 50% do vídeo</option>
          </Escolha>
        </div>
      </div>

      <AreaTexto
        rotulo="Resumo para o aluno"
        rows={3}
        maxLength={600}
        value={resumo}
        placeholder="Nesta aula aprende a pedir um documento com prazo e a responder quando lho pedem."
        onChange={(e) => setResumo(e.target.value)}
        onBlur={() => resumo.trim() !== (aula.resumo ?? "").trim() && void guardar({ id: aula.id, resumo: resumo.trim() })}
      />

      <div className="flex flex-col gap-2">
        <span className="font-semibold">Materiais para descarregar</span>
        {aula.materiais.length ? (
          <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
            {aula.materiais.map((m) => (
              <li key={m.id} className="flex items-center gap-2.5 rounded-pe-sm bg-pe-fundo-suave py-1 pl-3 pr-1">
                <FileText aria-hidden className="size-[18px] shrink-0 text-pe-tinta-suave" />
                <a href={m.url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate text-pe-tinta">
                  {m.nome}
                </a>
                <span className="shrink-0 text-[13px] text-pe-tinta-suave">{tamanho(m.tamanho_bytes)}</span>
                <button
                  type="button"
                  aria-label={`Tirar ${m.nome}`}
                  onClick={async () => {
                    setErro(null);
                    try {
                      await removerMaterial(m.id).unwrap();
                      aoGuardar();
                    } catch (e) {
                      setErro(erroProfessor(e, "Não foi possível tirar o material."));
                    }
                  }}
                  className="flex size-10 shrink-0 items-center justify-center rounded-pe-sm text-pe-tinta-suave hover:bg-pe-fundo-forte hover:text-pe-tinta"
                >
                  <X aria-hidden className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {envio?.tipo === "material" ? (
          <p aria-live="polite" className="m-0 text-[15px]">
            A enviar {envio.nome}: {Math.round(envio.f * 100)}%
          </p>
        ) : (
          <Botao tipo="secundario" tamanho="pequeno" className="self-start" onClick={() => inputMaterial.current?.click()} disabled={!!envio}>
            <Paperclip aria-hidden className="size-[18px]" />
            Acrescentar material
          </Botao>
        )}
        <span className="text-pe-legenda text-pe-tinta-suave">PDF, áudio, imagens ou folhas de cálculo, até 20 MB cada.</span>
        <input
          ref={inputMaterial}
          type="file"
          accept={TIPOS_MATERIAL}
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (f) void enviar(f, "material");
          }}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 rounded-pe-md bg-pe-fundo-suave px-4 py-3.5">
        <span>
          <span className="font-semibold">Questionário da aula: </span>
          {aula.questionario.activo && aula.questionario.perguntas
            ? `${aula.questionario.perguntas} ${aula.questionario.perguntas === 1 ? "pergunta" : "perguntas"}, ${aula.questionario.nota_minima}% para passar`
            : "sem perguntas"}
        </span>
        <button type="button" onClick={() => setPerguntas(true)} className="min-h-11 font-semibold text-pe-azul-vivo underline underline-offset-[3px]">
          {aula.questionario.perguntas ? "Editar perguntas" : "Criar perguntas"}
        </button>
      </div>

      {aula.video && !envio ? <FalaDaAulaProfessor key={aula.id} cursoId={cursoId} aula={aula} /> : null}

      <EscolhaPratica cursoId={cursoId} aula={aula} aoEscolher={(licao) => void guardar({ id: aula.id, licao_pratica: licao })} />

      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}

      <div className="flex flex-wrap items-end gap-3 border-t border-pe-linha pt-4">
        {seccoes.length > 1 ? (
          <Escolha rotulo="Secção" className="min-w-[220px] flex-1" value={seccao.id} onChange={(e) => void guardar({ id: aula.id, seccao: e.target.value })}>
            {seccoes.map((s, k) => (
              <option key={s.id} value={s.id}>
                Secção {k + 1}: {s.titulo}
              </option>
            ))}
          </Escolha>
        ) : null}
        <div className="flex gap-2">
          <Botao tipo="secundario" tamanho="medio" onClick={() => mover(-1)} disabled={i <= 0} aria-label="Subir a aula">
            <ArrowUp aria-hidden className="size-[18px]" />
            Subir
          </Botao>
          <Botao tipo="secundario" tamanho="medio" onClick={() => mover(1)} disabled={i >= seccao.aulas.length - 1} aria-label="Descer a aula">
            <ArrowDown aria-hidden className="size-[18px]" />
            Descer
          </Botao>
        </div>
        <Botao tipo="ligacao" tamanho="medio" className="ml-auto text-pe-errado hover:text-pe-errado" onClick={() => setApagar(true)}>
          <Trash2 aria-hidden className="size-[18px]" />
          Apagar aula
        </Botao>
      </div>

      <Dialogo aberto={apagar} aoMudar={setApagar} titulo={`Apagar "${aula.titulo}"?`} descricao="O vídeo, os materiais e o questionário desta aula são apagados. O progresso dos alunos nesta aula também se perde.">
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={() => setApagar(false)}>
            Cancelar
          </Botao>
          <Botao
            tipo="perigo"
            tamanho="medio"
            disabled={aRemover}
            onClick={async () => {
              setErro(null);
              try {
                await remover(aula.id).unwrap();
                setApagar(false);
                aoApagada();
                aoGuardar();
              } catch (e) {
                setApagar(false);
                setErro(erroProfessor(e, "Não foi possível apagar a aula."));
              }
            }}
          >
            Apagar aula
          </Botao>
        </div>
      </Dialogo>

      {perguntas ? <EditorQuestionario aula={aula.id} titulo={aula.titulo} aoFechar={() => setPerguntas(false)} aoGuardar={aoGuardar} /> : null}
    </section>
  );
}

/** "Lição de prática a seguir a esta aula": uma lição dos cursos de prática do professor, ou nenhuma. */
function EscolhaPratica({ cursoId, aula, aoEscolher }: { cursoId: string; aula: Aula; aoEscolher: (licao: string | null) => void }) {
  const { data: cursos, isLoading, isError } = useLicoesPraticaQuery(cursoId);
  const ligada = aula.licao_pratica ?? null;
  const comLicoes = (cursos ?? []).filter((c) => c.unidades.some((u) => u.licoes.length));

  let ajuda = "Os alunos vêem um botão para fazer esta lição depois do vídeo e do questionário. Os exercícios contam para a nota do curso.";
  if (isError) ajuda = "Não foi possível carregar os seus cursos de prática.";
  else if (!isLoading && !comLicoes.length) ajuda = "Ainda não tem lições de prática. Crie um curso de prática para poder ligar uma lição a esta aula.";
  else if (ligada && ligada.curso.estado !== "publicado") ajuda = `"${ligada.curso.titulo}" ainda não está publicado: os alunos só vêem o botão depois de o publicar.`;

  return (
    <Escolha
      rotulo="Lição de prática a seguir a esta aula"
      ajuda={ajuda}
      value={ligada?.id ?? ""}
      disabled={isLoading || (!comLicoes.length && !ligada)}
      onChange={(e) => aoEscolher(e.target.value || null)}
    >
      <option value="">Nenhuma</option>
      {comLicoes.flatMap((c) =>
        c.unidades
          .filter((u) => u.licoes.length)
          .map((u) => (
            <optgroup key={u.id} label={`${c.titulo}: ${u.titulo}`}>
              {u.licoes.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.titulo}
                </option>
              ))}
            </optgroup>
          ))
      )}
    </Escolha>
  );
}
