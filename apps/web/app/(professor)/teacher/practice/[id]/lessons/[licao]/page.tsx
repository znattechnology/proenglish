"use client";

import { erroProfessor } from "@/src/domains/teacher/professor/api";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, Plus, Trash2, Volume2 } from "lucide-react";
import { Aviso, Botao, Etiqueta, Escolha, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { FormExercicio, errosDeExercicio, type ErrosExercicio } from "@/components/pe/professor/pratica/FormExercicio";
import { cnPe } from "@/lib/pe";
import {
  TIPOS,
  exercicioVazio,
  nomeTipo,
  nomeUnidade,
  resumoExercicio,
  useApagarExercicioMutation,
  useApagarLicaoMutation,
  useEstruturaPraticaQuery,
  useExerciciosQuery,
  useGerarAudioMutation,
  useGuardarExercicioMutation,
  useMudarLicaoMutation,
  useNovoExercicioMutation,
  useOrdenarExerciciosMutation,
  type Exercicio,
  type TipoExercicio,
} from "@/src/domains/teacher/professor/pratica";

const hora = (d: Date) => d.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" });

export default function EditorLicao() {
  return (
    <Pagina className="gap-6">
      <Suspense>
        <Editor />
      </Suspense>
    </Pagina>
  );
}

function Editor() {
  const { id, licao } = useParams<{ id: string; licao: string }>();
  const sp = useSearchParams();
  const router = useRouter();
  const { data, isError } = useExerciciosQuery(licao);
  const { data: estrutura } = useEstruturaPraticaQuery(id);
  const [mudarLicao] = useMudarLicaoMutation();
  const [apagarLicao, { isLoading: aApagarLicao }] = useApagarLicaoMutation();
  const [escolher, setEscolher] = useState(false);
  const [apagar, setApagar] = useState(false);
  const [guardadoAs, setGuardadoAs] = useState<Date | null>(null);
  const [novo, setNovo] = useState<Exercicio | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  // Alterações por guardar no exercício aberto: antes de mudar de exercício, pergunta.
  const sujo = useRef(false);
  const [pendente, setPendente] = useState<(() => void) | null>(null);
  const seguro = (accao: () => void) => (sujo.current ? setPendente(() => accao) : accao());

  if (isError && !data)
    return (
      <Aviso tipo="errado">
        Não conseguimos abrir a lição. <Link href={`/teacher/practice/${id}`}>Voltar ao curso</Link>
      </Aviso>
    );
  if (!data)
    return (
      <>
        <Osso className="h-[76px] w-3/4 max-w-[560px]" />
        <Osso className="h-96 rounded-pe-md" />
      </>
    );

  const lista = data.exercicios;
  const pedido = sp.get("exercicio");
  const actual = novo ? null : (lista.find((e) => e.id === pedido) ?? lista[0] ?? null);
  const escolherEx = (eid: string) => {
    sujo.current = false;
    setNovo(null);
    router.replace(`?exercicio=${eid}`, { scroll: false });
    if (window.matchMedia("(max-width: 1023px)").matches) {
      requestAnimationFrame(() => document.getElementById("exercicio")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    }
  };
  const unidades = estrutura?.unidades ?? [];
  const guardou = () => setGuardadoAs(new Date());

  return (
    <>
      <div className="flex flex-col gap-2">
        <Link href={`/teacher/practice/${id}`} className="inline-flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-vivo no-underline">
          <ChevronLeft aria-hidden className="size-[18px]" />
          {data.curso.titulo}
        </Link>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <label htmlFor="titulo-licao" className="text-pe-legenda text-pe-tinta-suave">
              Título da lição, na unidade {data.licao.unidade.ordem}{data.licao.unidade.titulo === `Unidade ${data.licao.unidade.ordem}` ? "" : ` (${data.licao.unidade.titulo})`}
            </label>
            <TituloLicao
              key={data.licao.id}
              inicial={data.licao.titulo}
              aoGuardar={async (t) => {
                setErro(null);
                try {
                  await mudarLicao({ id: licao, titulo: t }).unwrap();
                  guardou();
                  return true;
                } catch (e) {
                  setErro(erroProfessor(e, "Não foi possível mudar o título."));
                  return false;
                }
              }}
            />
          </div>
          <p className="m-0 text-pe-tinta-suave" aria-live="polite">
            {lista.length} {lista.length === 1 ? "exercício" : "exercícios"}
            {guardadoAs ? `. Guardado às ${hora(guardadoAs)}.` : "."}
          </p>
        </div>
      </div>

      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      {(() => {
        const semAudio = lista.filter((e) => e.tipo === "escuta" && !e.audio_url).length;
        return semAudio ? (
          <Aviso tipo="info">
            {semAudio === 1 ? "1 exercício de escuta não tem áudio" : `${semAudio} exercícios de escuta não têm áudio`}: os alunos saltam-nos até o gerar. Abra cada um e use &ldquo;Gerar áudio da frase&rdquo;.
          </Aviso>
        ) : null;
      })()}
      {lista.some((e) => e.tipo === "conversa") ? (
        <Aviso tipo="neutro">A conversa com o tutor dentro das lições está desligada por agora: os alunos saltam esses exercícios. Pode apagá-los.</Aviso>
      ) : null}
      {estrutura?.curso.estado === "publicado" && lista.length < 3 ? (
        <Aviso tipo="neutro">O curso está publicado. Uma lição nova só aparece aos alunos quando tiver pelo menos 3 exercícios completos; as que já existiam continuam visíveis.</Aviso>
      ) : null}
      {lista.length < 3 ? <Aviso tipo="info">Uma lição precisa de pelo menos 3 exercícios para o curso poder ser enviado para revisão.</Aviso> : null}

      <div className="flex flex-col gap-7 lg:flex-row lg:items-start">
        <aside aria-labelledby="t-ex" className="flex w-full shrink-0 flex-col gap-2 rounded-pe-md border border-pe-linha p-4 lg:sticky lg:top-6 lg:w-[340px]">
          <h2 id="t-ex" className="m-0 font-pe-titulo text-[16px] font-semibold leading-6">
            Exercícios
          </h2>
          {lista.length ? (
            <ol className="m-0 flex list-none flex-col gap-0.5 p-0">
              {lista.map((e, i) => {
                const act = actual?.id === e.id;
                return (
                  <li key={e.id}>
                    <button
                      type="button"
                      onClick={() => seguro(() => escolherEx(e.id!))}
                      aria-current={act ? "true" : undefined}
                      className={cnPe("flex w-full flex-col gap-0.5 rounded-pe-sm px-2.5 py-2 text-left", act ? "bg-pe-azul-marca text-pe-sobre-marca" : "hover:bg-pe-fundo-suave")}
                    >
                      <span className="flex items-center justify-between gap-2 text-[13px] font-semibold">
                        <span>
                          {i + 1}. {nomeTipo(e.tipo)}
                        </span>
                        {e.acerto != null ? <span className={cnPe("tabular-nums", act ? "" : e.acerto < 50 ? "text-pe-errado" : "text-pe-tinta-suave")}>{e.acerto}%</span> : null}
                      </span>
                      <span className="line-clamp-2 text-[15px] leading-5">{resumoExercicio(e) || "Sem texto"}</span>
                    </button>
                  </li>
                );
              })}
              {novo ? (
                <li>
                  <span className="flex flex-col gap-0.5 rounded-pe-sm bg-pe-azul-marca px-2.5 py-2 text-pe-sobre-marca">
                    <span className="text-[13px] font-semibold">
                      {lista.length + 1}. {nomeTipo(novo.tipo)}
                    </span>
                    <span className="text-[15px]">Novo, por guardar</span>
                  </span>
                </li>
              ) : null}
            </ol>
          ) : novo ? null : (
            <p className="m-0 text-[15px] text-pe-tinta-suave">Ainda sem exercícios.</p>
          )}
          <Botao tipo="secundario" tamanho="pequeno" className="mt-2 self-start" onClick={() => seguro(() => setEscolher(true))} disabled={lista.length >= 30}>
            <Plus aria-hidden className="size-[18px]" />
            Novo exercício
          </Botao>
          <div className="mt-3 flex flex-col gap-3 border-t border-pe-fundo-forte pt-3">
            {unidades.length > 1 ? (
              <Escolha
                rotulo="Unidade"
                value={data.licao.unidade.id}
                onChange={async (e) => {
                  setErro(null);
                  try {
                    await mudarLicao({ id: licao, unidade: e.target.value }).unwrap();
                    guardou();
                  } catch (x) {
                    setErro(erroProfessor(x, "Não foi possível mudar a lição de unidade."));
                  }
                }}
              >
                {unidades.map((u, k) => (
                  <option key={u.id} value={u.id}>
                    {nomeUnidade(k + 1, u.titulo)}
                  </option>
                ))}
              </Escolha>
            ) : null}
            <Botao tipo="ligacao" tamanho="pequeno" className="self-start text-pe-errado hover:text-pe-errado" onClick={() => setApagar(true)}>
              <Trash2 aria-hidden className="size-4" />
              Apagar lição
            </Botao>
          </div>
        </aside>

        <div id="exercicio" className="min-w-0 flex-1 scroll-mt-20">
          {novo ? (
            <PainelExercicio
              key={`novo-${novo.tipo}`}
              licao={licao}
              inicial={novo}
              n={lista.length + 1}
              total={lista.length + 1}
              ids={lista.map((e) => e.id!)}
              aoSujar={(v) => {
                sujo.current = v;
              }}
              aoErro={setErro}
              aoGuardar={(e) => {
                setNovo(null);
                guardou();
                escolherEx(e.id!);
              }}
              aoCancelar={() => {
                sujo.current = false;
                setNovo(null);
              }}
            />
          ) : actual ? (
            <PainelExercicio
              key={actual.id}
              licao={licao}
              inicial={actual}
              n={lista.findIndex((e) => e.id === actual.id) + 1}
              total={lista.length}
              ids={lista.map((e) => e.id!)}
              aoSujar={(v) => {
                sujo.current = v;
              }}
              aoErro={setErro}
              aoGuardar={guardou}
              aoMover={() => router.replace(`?exercicio=${actual.id}`, { scroll: false })}
              aoCancelar={() => {}}
            />
          ) : (
            <div className="flex flex-col items-start gap-2 rounded-pe-md bg-pe-fundo-suave p-6">
              <h2 className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">Acrescente o primeiro exercício</h2>
              <p className="m-0 text-pe-tinta-suave">Misture tipos: por exemplo pares para o vocabulário, completar e ordenar para a gramática, escuta e pronúncia no fim.</p>
              <div className="flex flex-wrap gap-2">
                <Botao tamanho="pequeno" onClick={() => setEscolher(true)}>
                  Escolher o tipo
                </Botao>
                <Botao asChild tipo="secundario" tamanho="pequeno">
                  <Link href={`/teacher/practice/${id}/generate?unidade=${data.licao.unidade.id}`}>Gerar uma lição com IA</Link>
                </Botao>
              </div>
            </div>
          )}
        </div>
      </div>

      <Dialogo aberto={escolher} aoMudar={setEscolher} titulo="Que tipo de exercício?" largura={640}>
        <ul className="m-0 grid list-none gap-2 p-0 sm:grid-cols-2">
          {TIPOS.map((t) => (
            <li key={t.valor}>
              <button
                type="button"
                onClick={() => {
                  sujo.current = false;
                  setNovo(exercicioVazio(t.valor as TipoExercicio));
                  setEscolher(false);
                }}
                className="flex h-full w-full flex-col gap-0.5 rounded-pe-md border-[1.5px] border-pe-linha p-3 text-left hover:border-pe-azul-marca hover:bg-pe-fundo-suave"
              >
                <span className="font-semibold">{t.nome}</span>
                <span className="text-[14px] leading-5 text-pe-tinta-suave">{t.texto}</span>
              </button>
            </li>
          ))}
        </ul>
      </Dialogo>

      <Dialogo aberto={!!pendente} aoMudar={(v) => !v && setPendente(null)} titulo="Tem alterações por guardar" descricao="Se sair deste exercício, as alterações que não guardou perdem-se.">
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={() => setPendente(null)}>
            Continuar a editar
          </Botao>
          <Botao
            tipo="perigo"
            tamanho="medio"
            onClick={() => {
              const a = pendente;
              sujo.current = false;
              setPendente(null);
              a?.();
            }}
          >
            Descartar alterações
          </Botao>
        </div>
      </Dialogo>

      <Dialogo aberto={apagar} aoMudar={setApagar} titulo={`Apagar "${data.licao.titulo}"?`} descricao={`Os ${lista.length} exercícios e o progresso dos alunos nesta lição são apagados.`}>
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={() => setApagar(false)}>
            Cancelar
          </Botao>
          <Botao
            tipo="perigo"
            tamanho="medio"
            disabled={aApagarLicao}
            onClick={async () => {
              setErro(null);
              try {
                await apagarLicao(licao).unwrap();
                router.push(`/teacher/practice/${id}`);
              } catch (e) {
                setApagar(false);
                setErro(erroProfessor(e, "Não foi possível apagar a lição."));
              }
            }}
          >
            Apagar lição
          </Botao>
        </div>
      </Dialogo>
    </>
  );
}

/** Só os campos que o professor edita, numa ordem fixa: diz se há alterações por guardar. */
function assinatura(e: Exercicio) {
  return JSON.stringify([e.tipo, e.enunciado, e.frase, e.opcoes.map((o) => [o.texto, o.certa]), e.pares.map((p) => [p.a, p.b]), e.resposta, e.explicacao, e.audio_url ?? null]);
}

function TituloLicao({ inicial, aoGuardar }: { inicial: string; aoGuardar: (t: string) => Promise<boolean> }) {
  const [titulo, setTitulo] = useState(inicial);
  return (
    <input
      id="titulo-licao"
      value={titulo}
      maxLength={120}
      onChange={(e) => setTitulo(e.target.value)}
      onBlur={() => {
        const t = titulo.trim();
        if (!t) return setTitulo(inicial);
        if (t !== inicial) void aoGuardar(t).then((ok) => !ok && setTitulo(inicial));
      }}
      className="-mx-2 h-12 w-full max-w-[640px] rounded-pe-sm border-[1.5px] border-transparent bg-transparent px-2 font-pe-titulo text-[26px] font-bold leading-8 hover:border-pe-linha focus:border-pe-linha-forte md:text-[30px]"
    />
  );
}

function PainelExercicio({
  licao,
  inicial,
  n,
  total,
  ids,
  aoGuardar,
  aoCancelar,
  aoSujar,
  aoErro,
  aoMover,
}: {
  aoSujar: (v: boolean) => void;
  aoErro: (m: string | null) => void;
  aoMover?: () => void;
  licao: string;
  inicial: Exercicio;
  n: number;
  total: number;
  ids: string[];
  aoGuardar: (e: Exercicio) => void;
  aoCancelar: () => void;
}) {
  const [e, setE] = useState<Exercicio>(inicial);
  const [erros, setErros] = useState<ErrosExercicio>({});
  const [geral, setGeral] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [apagar, setApagar] = useState(false);
  const [criar, { isLoading: aCriar }] = useNovoExercicioMutation();
  const [guardar, { isLoading: aGuardar }] = useGuardarExercicioMutation();
  const [remover, { isLoading: aRemover }] = useApagarExercicioMutation();
  const [ordenar] = useOrdenarExerciciosMutation();
  const [audio, { isLoading: aGerarAudio }] = useGerarAudioMutation();
  const novo = !inicial.id;
  const mudado = assinatura(e) !== assinatura(inicial);
  useEffect(() => {
    aoSujar(mudado);
  }, [mudado, aoSujar]);
  const temAudio = e.tipo === "escuta" || e.tipo === "pronuncia";

  async function gravar() {
    setErros({});
    setGeral(null);
    setAviso(null);
    try {
      const r = novo ? await criar({ licao, e }).unwrap() : await guardar({ ...e, id: inicial.id! }).unwrap();
      setE(r);
      aoGuardar(r);
      setAviso("Exercício guardado.");
    } catch (x) {
      setErros(errosDeExercicio(x));
      setGeral(erroProfessor(x, "Não foi possível guardar. Verifique os campos a vermelho."));
    }
  }

  const mover = async (d: -1 | 1) => {
    const i = n - 1;
    const v = [...ids];
    [v[i], v[i + d]] = [v[i + d], v[i]];
    aoErro(null);
    aoMover?.(); // fixa o exercício no endereço, para continuar aberto depois de mudar de lugar
    try {
      await ordenar({ licao, ids: v }).unwrap();
    } catch (x) {
      aoErro(erroProfessor(x, "Não foi possível mudar a ordem."));
    }
  };

  return (
    <article aria-label={`Exercício ${n}`} className="flex flex-col gap-5 rounded-pe-md border-2 border-pe-azul-marca p-5 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="m-0 flex items-center gap-2 font-pe-titulo text-[20px] font-semibold leading-7">
          Exercício {n}
          <Etiqueta>{nomeTipo(e.tipo)}</Etiqueta>
        </h2>
        {!novo && inicial.tentativas ? (
          <span className="text-pe-legenda text-pe-tinta-suave">
            {inicial.acerto}% de acerto em {inicial.tentativas} {inicial.tentativas === 1 ? "resposta" : "respostas"}
          </span>
        ) : null}
      </div>

      <FormExercicio e={e} aoMudar={setE} erros={erros} />

      {temAudio && !novo ? (
        <div className="flex flex-wrap items-center gap-3 rounded-pe-md bg-pe-fundo-suave px-4 py-3">
          {e.audio_url ? (
            <audio controls src={e.audio_url} className="h-10 max-w-full" />
          ) : (
            <span className="text-[15px]">Ainda sem áudio. O aluno precisa de o ouvir.</span>
          )}
          <Botao
            tipo="secundario"
            tamanho="pequeno"
            disabled={aGerarAudio || mudado}
            onClick={async () => {
              setGeral(null);
              try {
                const r = await audio(inicial.id!).unwrap();
                setE(r);
              } catch (x) {
                setGeral(erroProfessor(x, "Não foi possível gerar o áudio agora."));
              }
            }}
          >
            <Volume2 aria-hidden className="size-[18px]" />
            {aGerarAudio ? "A gerar…" : e.audio_url ? "Gerar outra vez" : "Gerar áudio da frase"}
          </Botao>
          {mudado ? <span className="text-pe-legenda text-pe-tinta-suave">Guarde primeiro as alterações.</span> : null}
        </div>
      ) : null}

      {geral ? <Aviso tipo="errado">{geral}</Aviso> : aviso && !mudado ? <Aviso tipo="certo">{aviso}</Aviso> : null}

      <div className="flex flex-wrap items-center gap-3 border-t border-pe-linha pt-4">
        <Botao tamanho="medio" onClick={gravar} disabled={aCriar || aGuardar || (!novo && !mudado)}>
          {aCriar || aGuardar ? "A guardar…" : "Guardar exercício"}
        </Botao>
        {novo ? (
          <Botao tipo="secundario" tamanho="medio" onClick={aoCancelar}>
            Cancelar
          </Botao>
        ) : (
          <>
            <Botao tipo="secundario" tamanho="medio" onClick={() => mover(-1)} disabled={n <= 1} aria-label="Subir o exercício">
              <ArrowUp aria-hidden className="size-[18px]" />
            </Botao>
            <Botao tipo="secundario" tamanho="medio" onClick={() => mover(1)} disabled={n >= total} aria-label="Descer o exercício">
              <ArrowDown aria-hidden className="size-[18px]" />
            </Botao>
            <Botao tipo="ligacao" tamanho="medio" className="ml-auto text-pe-errado hover:text-pe-errado" onClick={() => setApagar(true)}>
              <Trash2 aria-hidden className="size-[18px]" />
              Apagar exercício
            </Botao>
          </>
        )}
      </div>

      <Dialogo aberto={apagar} aoMudar={setApagar} titulo="Apagar este exercício?" descricao="As respostas dos alunos a este exercício também são apagadas.">
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={() => setApagar(false)}>
            Cancelar
          </Botao>
          <Botao
            tipo="perigo"
            tamanho="medio"
            disabled={aRemover}
            onClick={async () => {
              try {
                await remover(inicial.id!).unwrap();
                aoSujar(false);
                setApagar(false);
              } catch (x) {
                setApagar(false);
                aoErro(erroProfessor(x, "Não foi possível apagar o exercício."));
              }
            }}
          >
            Apagar exercício
          </Botao>
        </div>
      </Dialogo>
    </article>
  );
}
