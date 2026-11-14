"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { CheckCircle2, ImagePlus, XCircle } from "lucide-react";
import { useDispatch } from "react-redux";
import { Aviso, Botao, Etiqueta, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaCurso } from "@/components/pe/professor/editor/CabecaCurso";
import { DialogoArquivar } from "@/components/pe/professor/editor/Arquivar";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { enviarFicheiro } from "@/src/domains/teacher/professor/envio";
import {
  areaNivel,
  professorApi,
  useCancelarRevisaoMutation,
  useCursoQuery,
  useSubmeterMutation,
  useVerificacaoQuery,
} from "@/src/domains/teacher/professor/api";

export default function ReverCurso() {
  const { id } = useParams<{ id: string }>();
  const dispatch = useDispatch();
  const { data: curso, isError } = useCursoQuery(id);
  const { data: v, isFetching: aVerificar } = useVerificacaoQuery(id, { refetchOnMountOrArgChange: true });
  const [submeter, { isLoading: aSubmeter }] = useSubmeterMutation();
  const [cancelar, { isLoading: aCancelar }] = useCancelarRevisaoMutation();
  const [arquivar, setArquivar] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [enviado, setEnviado] = useState(false);
  const [capa, setCapa] = useState<number | null>(null);
  const input = useRef<HTMLInputElement>(null);

  if (isError) return <Pagina><Aviso tipo="errado">Não conseguimos abrir o curso. <Link href="/teacher/courses">Ver os seus cursos</Link></Aviso></Pagina>;
  if (!curso)
    return (
      <Pagina>
        <Osso className="h-[76px] w-3/4 max-w-[560px]" />
        <Osso className="h-80 rounded-pe-md" />
      </Pagina>
    );

  const editor = curso.tipo === "video" ? `/teacher/courses/${id}` : `/teacher/practice/${id}`;
  const falhas = v?.itens.filter((i) => !i.ok).length ?? 0;
  const podeEnviar = curso.estado === "rascunho" || curso.estado === "arquivado";

  async function mudarCapa(f: File) {
    setErro(null);
    if (f.size > 5 * 1024 ** 2) return setErro("A imagem tem mais de 5 MB. Escolha uma mais pequena.");
    setCapa(0);
    try {
      await enviarFicheiro({ tipo: "capa", curso: id }, f, setCapa);
      dispatch(professorApi.util.invalidateTags(["Curso", "Verificacao", "Cursos", "Painel", "Estrutura"]));
    } catch (e) {
      setErro(mensagemErro(e, "Não foi possível enviar a imagem."));
    } finally {
      setCapa(null);
    }
  }

  return (
    <Pagina className="gap-6">
      <CabecaCurso curso={curso} voltar={{ href: editor, nome: "Editor do curso" }} semAviso={enviado} />

      {enviado ? (
        <Aviso tipo="certo">
          <strong>Curso enviado para revisão.</strong> A equipa ProEnglish vai ver o curso e recebe uma notificação com a resposta. Se for aprovado, entra logo no
          catálogo.
        </Aviso>
      ) : null}

      <div className="flex flex-col gap-8 lg:flex-row lg:items-start">
        <section aria-labelledby="t-lista" className="flex min-w-0 flex-1 flex-col gap-2">
          <h2 id="t-lista" className="m-0 font-pe-titulo text-[20px] font-semibold leading-7">
            Lista de verificação
          </h2>
          {!v ? (
            <Osso className="h-64 rounded-pe-md" />
          ) : (
            <ul className="m-0 flex list-none flex-col p-0" aria-busy={aVerificar}>
              {v.itens.map((i) => (
                <li key={i.chave} className="flex gap-3 border-b border-pe-fundo-forte py-3">
                  {i.ok ? (
                    <CheckCircle2 aria-hidden className="mt-0.5 size-[22px] shrink-0 text-pe-certo" />
                  ) : (
                    <XCircle aria-hidden className="mt-0.5 size-[22px] shrink-0 text-pe-errado" />
                  )}
                  <span className="flex flex-col">
                    <span className="font-semibold leading-[22px]">
                      <span className="sr-only">{i.ok ? "Feito: " : "Por corrigir: "}</span>
                      {i.titulo}
                    </span>
                    {i.detalhe ? <span className="text-pe-legenda text-pe-tinta-suave">{i.detalhe}</span> : null}
                  </span>
                </li>
              ))}
              <li className="flex gap-3 border-b border-pe-fundo-forte py-3">
                <CheckCircle2 aria-hidden className="mt-0.5 size-[22px] shrink-0 text-pe-tinta-suave" />
                <span className="flex flex-col">
                  <span className="font-semibold leading-[22px]">Certificado</span>
                  <span className="text-pe-legenda text-pe-tinta-suave">
                    Emitido com nota final de {curso.definicoes.nota_minima}% ou mais.{" "}
                    <Link href={`${editor}/settings`} className="font-semibold">
                      Mudar
                    </Link>
                  </span>
                </span>
              </li>
            </ul>
          )}
          {v && podeEnviar ? (
            falhas ? (
              <p className="m-0 mt-2 font-semibold text-pe-errado">
                Corrija {falhas === 1 ? "o ponto" : `os ${falhas} pontos`} a vermelho para poder enviar.{" "}
                <Link href={editor} className="text-pe-errado">
                  Voltar ao editor
                </Link>
              </p>
            ) : (
              <p className="m-0 mt-2 text-pe-tinta-suave">Está tudo pronto. Depois de enviar, a equipa ProEnglish revê o curso antes de entrar no catálogo.</p>
            )
          ) : null}
        </section>

        <aside aria-label="Como aparece no catálogo" className="flex w-full shrink-0 flex-col overflow-hidden rounded-pe-md border border-pe-linha lg:w-[360px]">
          <div className="relative flex aspect-video items-center justify-center bg-pe-fundo-forte">
            {curso.imagem ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={curso.imagem} alt="" className="absolute inset-0 size-full object-cover" />
            ) : (
              <span className="px-6 text-center text-pe-legenda text-pe-tinta-suave">Sem imagem de capa. Use 1280 × 720, com pouco texto, para ler bem no telemóvel.</span>
            )}
          </div>
          <div className="flex flex-col gap-3 p-5">
            <Etiqueta>{areaNivel(curso)}</Etiqueta>
            <span className="font-pe-titulo text-[20px] font-bold leading-[26px]">{curso.titulo}</span>
            <span className="text-[15px] leading-[22px] text-pe-tinta-suave">{curso.descricao}</span>
            <span className="text-pe-legenda text-pe-tinta-suave">Assim aparece no catálogo dos alunos.</span>
            {curso.tipo === "video" ? (
              <>
                <Botao tipo="secundario" tamanho="pequeno" onClick={() => input.current?.click()} disabled={capa != null}>
                  <ImagePlus aria-hidden className="size-[18px]" />
                  {capa != null ? `A enviar ${Math.round(capa * 100)}%` : curso.imagem ? "Trocar a imagem de capa" : "Escolher imagem de capa"}
                </Botao>
                <input
                  ref={input}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="sr-only"
                  tabIndex={-1}
                  aria-hidden
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    e.target.value = "";
                    if (f) void mudarCapa(f);
                  }}
                />
              </>
            ) : null}

            {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}

            {podeEnviar ? (
              <Botao
                tamanho="medio"
                larguraTotal
                disabled={!v?.pode_submeter || aSubmeter}
                onClick={async () => {
                  setErro(null);
                  try {
                    await submeter(id).unwrap();
                    setEnviado(true);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  } catch (e) {
                    setErro(mensagemErro(e, "Não foi possível enviar o curso. Tente outra vez."));
                  }
                }}
              >
                {aSubmeter ? "A enviar…" : curso.estado === "arquivado" ? "Enviar outra vez para revisão" : "Enviar para revisão"}
              </Botao>
            ) : curso.estado === "em_revisao" ? (
              <Botao
                tipo="secundario"
                tamanho="medio"
                larguraTotal
                disabled={aCancelar}
                onClick={async () => {
                  setErro(null);
                  setEnviado(false);
                  try {
                    await cancelar(id).unwrap();
                  } catch (e) {
                    setErro(mensagemErro(e, "Não foi possível cancelar a revisão."));
                  }
                }}
              >
                Cancelar a revisão
              </Botao>
            ) : null}
            {curso.estado === "publicado" ? (
              <Botao tipo="perigo" tamanho="medio" larguraTotal onClick={() => setArquivar(true)}>
                Arquivar curso
              </Botao>
            ) : null}
          </div>
        </aside>
      </div>

      <DialogoArquivar curso={curso} aberto={arquivar} aoMudar={setArquivar} />
    </Pagina>
  );
}
