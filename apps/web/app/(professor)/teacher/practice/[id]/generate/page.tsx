"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ChevronLeft, Film, Sparkles, TriangleAlert } from "lucide-react";
import { AreaTexto, Aviso, Botao, Campo, Escolha, Etiqueta, Osso } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { FormExercicio } from "@/components/pe/professor/pratica/FormExercicio";
import { cnPe } from "@/lib/pe";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import {
  nomeTipo,
  nomeUnidade,
  resumoExercicio,
  useEstruturaPraticaQuery,
  useGerarLicaoMutation,
  useGuardarLicaoGeradaMutation,
  type Exercicio,
} from "@/src/domains/teacher/professor/pratica";
import { useMudarAulaMutation } from "@/src/domains/teacher/professor/api";
import { useFrasesAulaQuery } from "@/src/domains/teacher/professor/aulaVideo";

export default function GerarLicao() {
  return (
    <Pagina className="gap-6">
      <Suspense>
        <Gerador />
      </Suspense>
    </Pagina>
  );
}

type Item = { e: Exercicio; manter: boolean; erro?: string };

function Gerador() {
  const { id } = useParams<{ id: string }>();
  const sp = useSearchParams();
  const router = useRouter();
  const { data: estrutura, isError: erroEstrutura, refetch } = useEstruturaPraticaQuery(id);
  const [gerar, { isLoading: aGerar }] = useGerarLicaoMutation();
  const [guardar, { isLoading: aGuardar }] = useGuardarLicaoGeradaMutation();

  const [unidadeEscolhida, setUnidade] = useState(sp.get("unidade") ?? "");
  // A partir de uma aula em vídeo (?aula=<id>): objectivo e frases vêm da aula, e a lição pode ficar ligada a ela.
  const aulaId = sp.get("aula") ?? "";
  const { data: fonte, isError: erroFonte } = useFrasesAulaQuery(aulaId, { skip: !aulaId });
  const [ligar, setLigar] = useState(true);
  const [mudarAula] = useMudarAulaMutation();
  const sugerido = fonte ? `Praticar as frases da aula em vídeo «${fonte.aula.titulo}» e usá-las em voz alta em situações de trabalho.`.slice(0, 500) : "";
  const frasesFonte = (fonte?.frases ?? []).filter((f) => f.estado === "aprovada").map((f) => f.texto);
  // null = o professor ainda não mexeu: mostra o que vem da aula.
  const [objectivoEscrito, setObjectivo] = useState<string | null>(null);
  const [palavrasEscritas, setPalavras] = useState<string | null>(null);
  const objectivo = objectivoEscrito ?? sugerido;
  const palavras = palavrasEscritas ?? frasesFonte.join(", ");
  const [quantos, setQuantos] = useState(8);
  const [titulo, setTitulo] = useState("");
  const [itens, setItens] = useState<Item[] | null>(null);
  const [descartados, setDescartados] = useState(0);
  const [erro, setErro] = useState<string | null>(null);
  const [erroObjectivo, setErroObjectivo] = useState<string | undefined>();
  const [aEditar, setAEditar] = useState<number | null>(null);

  // Por defeito, a última unidade do curso.
  const unidade = unidadeEscolhida || estrutura?.unidades[estrutura.unidades.length - 1]?.id || "";

  if (erroEstrutura && !estrutura)
    return (
      <Aviso tipo="errado">
        Não conseguimos abrir o curso.{" "}
        <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
          Tentar outra vez
        </button>
      </Aviso>
    );
  if (!estrutura)
    return (
      <>
        <Osso className="h-[76px] w-3/4 max-w-[560px]" />
        <Osso className="h-96 rounded-pe-md" />
      </>
    );

  const curso = estrutura.curso;
  const mantidos = itens?.filter((i) => i.manter) ?? [];

  async function pedir() {
    setErro(null);
    if (objectivo.trim().length < 10) return setErroObjectivo("Descreva em uma ou duas frases o que o aluno deve conseguir fazer.");
    setErroObjectivo(undefined);
    try {
      const r = await gerar({
        curso: id,
        unidade,
        objectivo: objectivo.trim(),
        palavras: palavras
          .split(",")
          .map((p) => p.trim())
          .filter(Boolean),
        quantos,
        ...(aulaId && fonte ? { aula: aulaId } : {}),
      }).unwrap();
      setItens(r.exercicios.map((e) => ({ e, manter: true })));
      setDescartados(r.descartados);
      setTitulo(r.titulo_sugerido);
    } catch (x) {
      setErro(mensagemErro(x, "A IA não respondeu. Tente outra vez daqui a pouco."));
    }
  }

  async function gravar() {
    setErro(null);
    if (!titulo.trim()) return setErro("Escreva o título da lição.");
    try {
      const r = await guardar({ unidade, titulo: titulo.trim(), exercicios: mantidos.map((i) => i.e) }).unwrap();
      if (fonte && ligar) {
        try {
          await mudarAula({ id: fonte.aula.id, licao_pratica: r.licao.id }).unwrap();
        } catch {
          // A lição ficou guardada; ligar à aula pode fazer-se depois no editor do curso em vídeo.
        }
      }
      router.push(`/teacher/practice/${id}/lessons/${r.licao.id}`);
    } catch (x) {
      const d = (x as { data?: { details?: { exercicios?: Record<string, unknown> } } })?.data?.details?.exercicios;
      if (d && itens) {
        const indices = itens.map((it, k) => (it.manter ? k : -1)).filter((k) => k >= 0);
        setItens(
          itens.map((it, k) => {
            const pos = indices.indexOf(k);
            const m = pos >= 0 ? d[String(pos)] : undefined;
            const texto = m ? (typeof m === "string" ? m : Object.values(m as Record<string, string[]>).flat()[0]) : undefined;
            return { ...it, erro: texto };
          })
        );
      }
      setErro(mensagemErro(x, "Não foi possível guardar a lição."));
    }
  }

  return (
    <>
      <div className="flex flex-col gap-2">
        <Link href={`/teacher/practice/${id}`} className="inline-flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-vivo no-underline">
          <ChevronLeft aria-hidden className="size-[18px]" />
          {curso.titulo}
        </Link>
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 tracking-[-0.015em] md:text-[32px] md:leading-[38px]">Gerar lição com IA</h1>
        {aulaId ? (
          fonte ? (
            <Aviso tipo="neutro" icone={<Film aria-hidden />}>
              A partir da aula em vídeo <strong>{fonte.aula.titulo}</strong> ({fonte.aula.curso.titulo}): a IA usa{" "}
              {frasesFonte.length ? `as ${frasesFonte.length} frases aprovadas` : "a transcrição (ainda não há frases aprovadas)"} e a transcrição do vídeo.
            </Aviso>
          ) : erroFonte ? (
            <Aviso tipo="errado">Não conseguimos abrir a aula em vídeo. Pode gerar a lição na mesma, sem os dados da aula.</Aviso>
          ) : null
        ) : null}
        <p className="m-0 text-pe-tinta-suave">Descreva o objectivo e a IA propõe exercícios, do reconhecer ao dizer: pelo menos metade da lição é falada (pronúncia e responder em voz alta). Nada chega aos alunos sem a sua revisão.</p>
      </div>

      {!estrutura.unidades.length ? (
        <Aviso tipo="info">
          Crie primeiro uma unidade no curso. <Link href={`/teacher/practice/${id}`}>Ir para as unidades</Link>
        </Aviso>
      ) : (
        <div className="flex flex-col gap-8 lg:flex-row lg:items-start">
          <form
            noValidate
            className="flex w-full shrink-0 flex-col gap-4 lg:sticky lg:top-6 lg:w-[380px]"
            onSubmit={(e) => {
              e.preventDefault();
              void pedir();
            }}
          >
            <Escolha rotulo="Para onde vai" value={unidade} onChange={(e) => setUnidade(e.target.value)}>
              {estrutura.unidades.map((u, k) => (
                <option key={u.id} value={u.id}>
                  {nomeUnidade(k + 1, u.titulo)}
                </option>
              ))}
            </Escolha>
            <AreaTexto
              rotulo="O que o aluno deve conseguir fazer"
              rows={3}
              maxLength={500}
              value={objectivo}
              onChange={(e) => setObjectivo(e.target.value)}
              erro={erroObjectivo}
              placeholder="Pedir à equipa o registo de incidentes do turno e confirmar o prazo."
            />
            <Campo rotulo="Palavras e frases que quer incluir" value={palavras} onChange={(e) => setPalavras(e.target.value)} ajuda="Separe por vírgulas." placeholder="incident log, by the end of the shift, still open" />
            <Escolha rotulo="Quantos exercícios" value={quantos} onChange={(e) => setQuantos(Number(e.target.value))}>
              {[6, 8, 10, 12].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </Escolha>
            <Botao type="submit" tamanho="medio" disabled={aGerar}>
              <Sparkles aria-hidden className="size-[18px]" />
              {aGerar ? "A gerar, pode demorar até um minuto…" : itens ? "Gerar outra vez" : "Gerar exercícios"}
            </Botao>
          </form>

          <section aria-labelledby="t-rascunho" aria-busy={aGerar} className="flex min-w-0 flex-1 flex-col gap-3">
            {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
            {aGerar && !itens ? (
              <div className="flex flex-col gap-2">
                {Array.from({ length: Math.min(quantos, 6) }, (_, i) => (
                  <Osso key={i} className="h-[60px] rounded-pe-md" />
                ))}
              </div>
            ) : !itens ? (
              <div className="flex flex-col gap-2 rounded-pe-md bg-pe-fundo-suave p-6">
                <h2 id="t-rascunho" className="m-0 font-pe-titulo text-[20px] font-semibold leading-7">
                  O rascunho aparece aqui
                </h2>
                <p className="m-0 text-pe-tinta-suave">
                  A IA usa a área e o nível do curso e as lições que já existem na unidade. Pode tirar os exercícios de que não gostar e editar os outros antes de guardar.
                </p>
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h2 id="t-rascunho" className="m-0 font-pe-titulo text-[20px] font-semibold leading-7">
                    Rascunho gerado: {itens.length} exercícios
                  </h2>
                  <span className="text-pe-legenda text-pe-tinta-suave">{mantidos.length} para guardar</span>
                </div>
                <Aviso tipo="info" icone={<TriangleAlert aria-hidden />}>
                  Reveja cada frase antes de guardar. A IA pode errar no vocabulário técnico. Os exercícios de escuta precisam de áudio: gere-o no editor da lição depois de guardar, senão os alunos saltam-nos.
                  {descartados ? ` ${descartados} ${descartados === 1 ? "exercício foi tirado (incompleto, ou escrito a mais para metade da lição ser falada)" : "exercícios foram tirados (incompletos, ou escritos a mais para metade da lição ser falada)"}.` : ""}
                </Aviso>
                <ul className={cnPe("m-0 flex list-none flex-col p-0", aGerar && "opacity-60")}>
                  {itens.map((it, k) => (
                    <li key={k} className="flex flex-col gap-1 border-b border-pe-fundo-forte py-3">
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={it.manter}
                          onChange={(x) => setItens(itens.map((y, j) => (j === k ? { ...y, manter: x.target.checked } : y)))}
                          aria-label={`Guardar o exercício ${k + 1}`}
                          className="size-5 shrink-0 accent-pe-azul-marca"
                        />
                        <Etiqueta className="shrink-0">{nomeTipo(it.e.tipo)}</Etiqueta>
                        <span className={cnPe("min-w-0 flex-1", !it.manter && "text-pe-tinta-suave line-through")}>{resumoExercicio(it.e)}</span>
                        <button type="button" onClick={() => setAEditar(k)} className="min-h-11 shrink-0 font-semibold text-pe-azul-vivo underline underline-offset-[3px]">
                          Editar<span className="sr-only"> o exercício {k + 1}</span>
                        </button>
                      </div>
                      {it.erro ? <p className="m-0 pl-8 text-pe-legenda font-semibold text-pe-errado">{it.erro}</p> : null}
                    </li>
                  ))}
                </ul>
                {fonte ? (
                  <label className="flex min-h-11 items-center gap-3 border-t border-pe-linha pt-4">
                    <input type="checkbox" checked={ligar} onChange={(e) => setLigar(e.target.checked)} className="size-5 shrink-0 accent-pe-azul-marca" />
                    <span>
                      Mostrar esta lição aos alunos a seguir à aula <strong>{fonte.aula.titulo}</strong>
                    </span>
                  </label>
                ) : null}
                <div className="flex flex-col gap-3 border-t border-pe-linha pt-4 sm:flex-row sm:items-end">
                  <Campo className="flex-1" rotulo="Título da lição" value={titulo} maxLength={120} onChange={(e) => setTitulo(e.target.value)} />
                  <div className="flex flex-wrap gap-3">
                    <Botao
                      tipo="secundario"
                      tamanho="medio"
                      onClick={() => {
                        setItens(null);
                        setTitulo("");
                      }}
                    >
                      Descartar
                    </Botao>
                    <Botao tamanho="medio" onClick={gravar} disabled={aGuardar || mantidos.length < 3}>
                      {aGuardar ? "A guardar…" : `Guardar ${mantidos.length} exercícios como lição`}
                    </Botao>
                  </div>
                </div>
                {mantidos.length < 3 ? <p className="m-0 text-pe-legenda text-pe-tinta-suave">Uma lição precisa de pelo menos 3 exercícios.</p> : null}
              </>
            )}
          </section>
        </div>
      )}

      {aEditar != null && itens ? (
        <EditarGerado
          e={itens[aEditar].e}
          n={aEditar + 1}
          aoFechar={() => setAEditar(null)}
          aoGuardar={(e) => {
            setItens(itens.map((y, j) => (j === aEditar ? { ...y, e, erro: undefined, manter: true } : y)));
            setAEditar(null);
          }}
        />
      ) : null}
    </>
  );
}

function EditarGerado({ e: inicial, n, aoFechar, aoGuardar }: { e: Exercicio; n: number; aoFechar: () => void; aoGuardar: (e: Exercicio) => void }) {
  const [e, setE] = useState(inicial);
  return (
    <Dialogo aberto aoMudar={(v) => !v && aoFechar()} titulo={`Exercício ${n}: ${nomeTipo(e.tipo)}`} descricao="As alterações ficam no rascunho até guardar a lição." largura={680}>
      <div className="-mx-1 max-h-[min(60vh,620px)] overflow-y-auto px-1 pb-1">
        <FormExercicio e={e} aoMudar={setE} />
      </div>
      <div className="flex flex-wrap justify-end gap-3">
        <Botao tipo="secundario" tamanho="medio" onClick={aoFechar}>
          Cancelar
        </Botao>
        <Botao tamanho="medio" onClick={() => aoGuardar(e)}>
          Usar estas alterações
        </Botao>
      </div>
    </Dialogo>
  );
}
