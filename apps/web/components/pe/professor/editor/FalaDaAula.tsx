"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useDispatch } from "react-redux";
import { CheckCircle2, Dumbbell, Loader2, Pencil, Plus, Sparkles, Trash2, X } from "lucide-react";
import { Aviso, Botao, Campo, Escolha, Etiqueta } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { cnPe } from "@/lib/pe";
import { erroProfessor, useLicoesPraticaQuery, type Aula } from "@/src/domains/teacher/professor/api";
import {
  aulaVideoApi,
  lerTempo,
  mmss,
  useApagarFraseMutation,
  useAprovarTodasMutation,
  useFrasesAulaQuery,
  useGuardarTranscricaoMutation,
  useMudarFraseMutation,
  useNovaFraseMutation,
  useProporFrasesMutation,
  useTranscreverMutation,
  useTranscricaoQuery,
  type FraseAula,
  type LinhaTranscricao,
  type NovaFrase,
  type Transcricao,
} from "@/src/domains/teacher/professor/aulaVideo";

const POLL = 4000;
const RECENTE_MS = 15 * 60 * 1000;

function aTranscrever(t?: Pick<Transcricao, "estado" | "desde"> | null) {
  if (!t) return false;
  if (t.estado === "a_processar") return true;
  // 'pendente' só conta como em curso se foi pedido há pouco (aulas antigas ficam pendentes sem nada a correr).
  return t.estado === "pendente" && !!t.desde && Date.now() - new Date(t.desde).getTime() < RECENTE_MS;
}

/** Transcrição, frases da aula e "criar lição de prática" de uma aula com vídeo. */
export function FalaDaAulaProfessor({ cursoId, aula }: { cursoId: string; aula: Aula }) {
  const dispatch = useDispatch();
  const { data: t } = useTranscricaoQuery(aula.id);
  const emCurso = aTranscrever(t ?? aula.transcricao);
  // Segunda subscrição só para vigiar enquanto transcreve (sem estado extra no componente).
  useTranscricaoQuery(aula.id, { pollingInterval: emCurso ? POLL : 0 });

  // Acabou de transcrever: a IA pode ter proposto frases e a estrutura mostra o estado novo.
  const antes = useRef(emCurso);
  useEffect(() => {
    if (antes.current && !emCurso) dispatch(aulaVideoApi.util.invalidateTags([{ type: "FrasesAula", id: aula.id }, "Estrutura"]));
    antes.current = emCurso;
  }, [emCurso, aula.id, dispatch]);

  return (
    <div className="flex flex-col gap-5">
      <BlocoTranscricao aula={aula} t={t} emCurso={emCurso} />
      <Frases aula={aula} temTranscricao={!!t?.linhas.length} aTranscrever={emCurso} />
      <CriarLicao cursoId={cursoId} aula={aula} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Transcrição                                                          */
/* ------------------------------------------------------------------ */

function BlocoTranscricao({ aula, t, emCurso }: { aula: Aula; t?: Transcricao; emCurso: boolean }) {
  const [transcrever, { isLoading }] = useTranscreverMutation();
  const [editar, setEditar] = useState(false);
  const [confirmar, setConfirmar] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const n = t?.linhas.length ?? 0;

  async function pedir(forcar = false) {
    setErro(null);
    setConfirmar(false);
    try {
      await transcrever({ aula: aula.id, forcar }).unwrap();
    } catch (e) {
      if ((e as { status?: number })?.status === 409) setConfirmar(true);
      else setErro(erroProfessor(e, "Não foi possível pedir a transcrição."));
    }
  }

  let estado: React.ReactNode;
  let accoes: React.ReactNode = null;
  if (!t) estado = <span className="text-pe-tinta-suave">A carregar a transcrição…</span>;
  else if (emCurso)
    estado = (
      <span className="inline-flex items-center gap-2" aria-live="polite">
        <Loader2 aria-hidden className="size-[18px] animate-spin text-pe-azul-marca" />A transcrever o vídeo… Pode continuar a editar a aula.
      </span>
    );
  else if (t.estado === "pronta" || t.estado === "manual") {
    estado = (
      <span className="inline-flex items-center gap-2">
        <CheckCircle2 aria-hidden className="size-[18px] text-pe-certo" />
        {t.estado === "pronta" ? "Transcrição pronta" : "Transcrição escrita à mão"}, {n} {n === 1 ? "linha" : "linhas"}
      </span>
    );
    accoes = (
      <>
        <BotaoTexto onClick={() => setEditar(true)}>Ver e editar</BotaoTexto>
        {t.estado === "manual" && aula.video ? <BotaoTexto onClick={() => setConfirmar(true)}>Transcrever automaticamente</BotaoTexto> : null}
      </>
    );
  } else if (t.estado === "erro") {
    estado = <span className="font-semibold text-pe-errado">Não foi possível transcrever o vídeo.</span>;
    accoes = (
      <>
        <BotaoTexto onClick={() => void pedir()} disabled={isLoading}>
          Tentar outra vez
        </BotaoTexto>
        <BotaoTexto onClick={() => setEditar(true)}>Escrever à mão</BotaoTexto>
      </>
    );
  } else {
    estado = <span className="text-pe-tinta-suave">O vídeo ainda não foi transcrito.</span>;
    accoes = (
      <>
        <BotaoTexto onClick={() => void pedir()} disabled={isLoading}>
          Transcrever o vídeo
        </BotaoTexto>
        <BotaoTexto onClick={() => setEditar(true)}>Escrever à mão</BotaoTexto>
      </>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-pe-md bg-pe-fundo-suave px-4 py-3.5">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <span className="min-w-0">
          <span className="font-semibold">Transcrição em inglês: </span>
          {estado}
        </span>
        {accoes ? <span className="flex flex-wrap gap-x-4">{accoes}</span> : null}
      </div>
      {t?.estado === "erro" && t.erro && !emCurso ? <p className="m-0 text-[15px] leading-[22px]">{t.erro}</p> : null}
      {t?.video_mudou ? <p className="m-0 text-[15px] leading-[22px]">O vídeo mudou depois de a transcrição ser escrita. Confirme que o texto e os tempos ainda batem certo.</p> : null}
      {!emCurso && t && (t.estado === "pronta" || t.estado === "manual") ? (
        <p className="m-0 text-pe-legenda text-pe-tinta-suave">Os alunos lêem-na por baixo do vídeo e tocam numa linha para ir a esse momento.</p>
      ) : null}
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}

      <Dialogo
        aberto={confirmar}
        aoMudar={setConfirmar}
        titulo="Substituir a transcrição escrita à mão?"
        descricao="A transcrição automática apaga as alterações que fez ao texto. As frases da aula ficam como estão."
      >
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={() => setConfirmar(false)}>
            Manter a minha
          </Botao>
          <Botao tamanho="medio" onClick={() => void pedir(true)} disabled={isLoading}>
            Transcrever automaticamente
          </Botao>
        </div>
      </Dialogo>

      {editar && t ? <EditorTranscricao aula={aula.id} linhas={t.linhas} aoFechar={() => setEditar(false)} /> : null}
    </div>
  );
}

function BotaoTexto({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" {...props} className="min-h-11 font-semibold text-pe-azul-vivo underline underline-offset-[3px] disabled:opacity-60">
      {children}
    </button>
  );
}

type LinhaEditada = { chave: number; tempo: string; texto: string; fim: number | null };

function EditorTranscricao({ aula, linhas, aoFechar }: { aula: string; linhas: LinhaTranscricao[]; aoFechar: () => void }) {
  const [guardar, { isLoading }] = useGuardarTranscricaoMutation();
  const seguinte = useRef(linhas.length);
  const [itens, setItens] = useState<LinhaEditada[]>(() => linhas.map((l, i) => ({ chave: i, tempo: mmss(l.start), texto: l.text, fim: l.end })));
  const [erro, setErro] = useState<string | null>(null);

  const mudar = (chave: number, campo: "tempo" | "texto", valor: string) => setItens((v) => v.map((x) => (x.chave === chave ? { ...x, [campo]: valor, ...(campo === "tempo" ? { fim: null } : {}) } : x)));

  async function gravar() {
    setErro(null);
    const out: LinhaTranscricao[] = [];
    for (const [i, l] of itens.entries()) {
      const s = lerTempo(l.tempo);
      if (s == null) return setErro(`Linha ${i + 1}: escreva o tempo como 1:05.`);
      out.push({ start: s, end: l.fim ?? s, text: l.texto });
    }
    try {
      await guardar({ aula, linhas: out }).unwrap();
      aoFechar();
    } catch (e) {
      setErro(erroProfessor(e, "Não foi possível guardar a transcrição."));
    }
  }

  return (
    <Dialogo aberto aoMudar={(v) => !v && aoFechar()} titulo="Transcrição do vídeo" descricao="Corrija o texto ou o momento de cada linha (minutos:segundos). As linhas vazias são tiradas." largura={720}>
      <ol className="-mx-1 m-0 flex max-h-[min(55vh,560px)] list-none flex-col gap-1.5 overflow-y-auto p-0 px-1">
        {itens.map((l, i) => (
          <li key={l.chave} className="flex items-start gap-2">
            <input
              value={l.tempo}
              onChange={(e) => mudar(l.chave, "tempo", e.target.value)}
              aria-label={`Tempo da linha ${i + 1}`}
              inputMode="numeric"
              className="h-11 w-[72px] shrink-0 rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo px-2 text-center text-[15px] tabular-nums text-pe-tinta"
            />
            <textarea
              value={l.texto}
              onChange={(e) => mudar(l.chave, "texto", e.target.value)}
              aria-label={`Texto da linha ${i + 1}`}
              lang="en"
              rows={1}
              className="min-h-11 min-w-0 flex-1 resize-y rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo px-3 py-2 text-[15px] leading-[22px] text-pe-tinta"
            />
            <button
              type="button"
              aria-label={`Tirar a linha ${i + 1}`}
              onClick={() => setItens((v) => v.filter((x) => x.chave !== l.chave))}
              className="flex size-11 shrink-0 items-center justify-center rounded-pe-sm text-pe-tinta-suave hover:bg-pe-fundo-forte hover:text-pe-tinta"
            >
              <X aria-hidden className="size-4" />
            </button>
          </li>
        ))}
      </ol>
      {!itens.length ? <p className="m-0 text-pe-tinta-suave">Ainda não há linhas.</p> : null}
      <Botao
        tipo="ligacao"
        tamanho="pequeno"
        className="self-start"
        onClick={() => {
          const ultimo = itens.length ? (lerTempo(itens[itens.length - 1].tempo) ?? 0) + 5 : 0;
          setItens((v) => [...v, { chave: seguinte.current++, tempo: mmss(ultimo), texto: "", fim: null }]);
        }}
      >
        <Plus aria-hidden /> Acrescentar linha
      </Botao>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="flex flex-wrap justify-end gap-3">
        <Botao tipo="secundario" tamanho="medio" onClick={aoFechar}>
          Cancelar
        </Botao>
        <Botao tamanho="medio" onClick={() => void gravar()} disabled={isLoading}>
          {isLoading ? "A guardar…" : "Guardar a transcrição"}
        </Botao>
      </div>
    </Dialogo>
  );
}

/* ------------------------------------------------------------------ */
/* Frases da aula                                                       */
/* ------------------------------------------------------------------ */

function Frases({ aula, temTranscricao, aTranscrever }: { aula: Aula; temTranscricao: boolean; aTranscrever: boolean }) {
  const { data } = useFrasesAulaQuery(aula.id);
  const aPropor = data?.ia.estado === "a_processar";
  useFrasesAulaQuery(aula.id, { pollingInterval: aPropor || aTranscrever ? POLL : 0 });
  const [propor, { isLoading: aPedir }] = useProporFrasesMutation();
  const [aprovarTodas, { isLoading: aAprovar }] = useAprovarTodasMutation();
  const [mudar] = useMudarFraseMutation();
  const [apagar] = useApagarFraseMutation();
  const [novaFrase] = useNovaFraseMutation();
  const [aEditar, setAEditar] = useState<number | "nova" | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const frases = data?.frases ?? [];
  const propostas = frases.filter((f) => f.estado === "proposta");
  const aprovadas = frases.length - propostas.length;

  async function correr(accao: () => Promise<unknown>, falha: string) {
    setErro(null);
    try {
      await accao();
    } catch (e) {
      setErro(erroProfessor(e, falha));
    }
  }

  return (
    <section aria-labelledby={`t-frases-${aula.id}`} className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <h3 id={`t-frases-${aula.id}`} className="m-0 text-[17px] font-semibold leading-6">
          Frases da aula
        </h3>
        <p className="m-0 text-pe-legenda text-pe-tinta-suave">
          Os alunos repetem estas frases em voz alta depois do vídeo e usam-nas numa conversa com o tutor. Só as aprovadas chegam aos alunos
          {frases.length ? `: ${aprovadas} de ${frases.length} aprovadas.` : "."}
        </p>
      </div>

      {aPropor || aPedir ? (
        <p aria-live="polite" className="m-0 inline-flex items-center gap-2 text-[15px]">
          <Loader2 aria-hidden className="size-[18px] animate-spin text-pe-azul-marca" /> A IA está a escolher as frases do vídeo…
        </p>
      ) : !frases.length ? (
        <p className="m-0 rounded-pe-md border border-dashed border-pe-linha-forte px-4 py-3 text-[15px] text-pe-tinta-suave">
          {aTranscrever
            ? "Quando a transcrição acabar, a IA propõe as frases e as palavras mais úteis do vídeo."
            : temTranscricao
              ? "Ainda não há frases. Peça à IA que as proponha a partir da transcrição, ou escreva-as."
              : "Transcreva o vídeo para a IA propor frases, ou escreva-as à mão."}
        </p>
      ) : null}
      {data?.ia.estado === "erro" && !aPedir && data.ia.erro ? <Aviso tipo="errado">{data.ia.erro}</Aviso> : null}

      {frases.length ? (
        <ul className="m-0 flex list-none flex-col p-0">
          {frases.map((f) =>
            aEditar === f.id ? (
              <li key={f.id} className="border-b border-pe-fundo-forte py-3">
                <FormFrase
                  inicial={f}
                  aoCancelar={() => setAEditar(null)}
                  aoGuardar={(v) => correr(async () => {
                    await mudar({ aula: aula.id, id: f.id, ...v }).unwrap();
                    setAEditar(null);
                  }, "Não foi possível guardar a frase.")}
                />
              </li>
            ) : (
              <li key={f.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-pe-fundo-forte py-2.5">
                <Etiqueta tipo={f.estado === "aprovada" ? "certo" : "neutra"} className="shrink-0">
                  {f.estado === "aprovada" ? <CheckCircle2 aria-hidden className="size-4" /> : null}
                  {f.tipo === "palavra" ? "Palavra" : "Frase"}
                  <span className="sr-only">{f.estado === "aprovada" ? " aprovada" : " por aprovar"}</span>
                </Etiqueta>
                <span className="flex min-w-0 flex-1 basis-[240px] flex-col">
                  <span lang="en" className={cnPe("leading-[22px]", f.estado === "proposta" && "text-pe-tinta-suave")}>
                    {f.texto}
                  </span>
                  <span className="text-pe-legenda text-pe-tinta-suave">
                    {[f.traducao, f.inicio != null ? `no vídeo em ${mmss(f.inicio)}` : "não aparece no vídeo (os alunos ouvem a voz do browser)"].filter(Boolean).join(". ")}
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-1">
                  {f.estado === "proposta" ? (
                    <Botao tipo="secundario" tamanho="pequeno" onClick={() => correr(() => mudar({ aula: aula.id, id: f.id, estado: "aprovada" }).unwrap(), "Não foi possível aprovar.")}>
                      Aprovar
                    </Botao>
                  ) : null}
                  <button type="button" aria-label={`Editar "${f.texto}"`} onClick={() => setAEditar(f.id)} className="flex size-11 items-center justify-center rounded-pe-sm text-pe-tinta-suave hover:bg-pe-fundo-forte hover:text-pe-tinta">
                    <Pencil aria-hidden className="size-[18px]" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Apagar "${f.texto}"`}
                    onClick={() => correr(() => apagar({ aula: aula.id, id: f.id }).unwrap(), "Não foi possível apagar a frase.")}
                    className="flex size-11 items-center justify-center rounded-pe-sm text-pe-tinta-suave hover:bg-pe-fundo-forte hover:text-pe-errado"
                  >
                    <Trash2 aria-hidden className="size-[18px]" />
                  </button>
                </span>
              </li>
            )
          )}
        </ul>
      ) : null}

      {aEditar === "nova" ? (
        <FormFrase
          aoCancelar={() => setAEditar(null)}
          aoGuardar={(v) => correr(async () => {
            await novaFrase({ aula: aula.id, ...v }).unwrap();
            setAEditar(null);
          }, "Não foi possível acrescentar a frase.")}
        />
      ) : null}

      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}

      <div className="flex flex-wrap gap-2">
        {propostas.length ? (
          <Botao tamanho="pequeno" onClick={() => correr(() => aprovarTodas(aula.id).unwrap(), "Não foi possível aprovar.")} disabled={aAprovar}>
            <CheckCircle2 aria-hidden /> Aprovar todas ({propostas.length})
          </Botao>
        ) : null}
        {temTranscricao ? (
          <Botao tipo="secundario" tamanho="pequeno" onClick={() => correr(() => propor(aula.id).unwrap(), "A IA não conseguiu propor frases agora.")} disabled={aPedir || aPropor}>
            <Sparkles aria-hidden /> {frases.some((f) => f.criada_por_ia) ? "Propor outra vez com IA" : "Propor frases com IA"}
          </Botao>
        ) : null}
        <Botao tipo="ligacao" tamanho="pequeno" onClick={() => setAEditar("nova")} disabled={aEditar === "nova"}>
          <Plus aria-hidden /> Acrescentar frase
        </Botao>
      </div>
      {frases.some((f) => f.criada_por_ia && f.estado === "proposta") ? (
        <p className="m-0 text-pe-legenda text-pe-tinta-suave">Propor outra vez substitui as propostas por aprovar. As aprovadas e as que escreveu ficam.</p>
      ) : null}
    </section>
  );
}

function FormFrase({ inicial, aoGuardar, aoCancelar }: { inicial?: FraseAula; aoGuardar: (v: NovaFrase) => Promise<void>; aoCancelar: () => void }) {
  const [texto, setTexto] = useState(inicial?.texto ?? "");
  const [traducao, setTraducao] = useState(inicial?.traducao ?? "");
  const [tipo, setTipo] = useState<FraseAula["tipo"]>(inicial?.tipo ?? "frase");
  const [inicio, setInicio] = useState(mmss(inicial?.inicio));
  const [fim, setFim] = useState(mmss(inicial?.fim));
  const [erros, setErros] = useState<Record<string, string>>({});
  const [aGuardar, setAGuardar] = useState(false);

  async function guardar() {
    const e: Record<string, string> = {};
    if (!texto.trim()) e.texto = "Escreva a frase em inglês.";
    const i = lerTempo(inicio);
    const f = lerTempo(fim);
    if (i === undefined) e.inicio = "Use minutos:segundos, p.ex. 1:05.";
    if (f === undefined) e.fim = "Use minutos:segundos, p.ex. 1:12.";
    if (i != null && f != null && f <= i) e.fim = "O fim tem de ser depois do início.";
    setErros(e);
    if (Object.keys(e).length) return;
    const v: NovaFrase = { texto: texto.trim(), traducao: traducao.trim(), tipo };
    // Numa frase nova sem tempos, o servidor procura-a na transcrição.
    if (inicial || i != null) Object.assign(v, { inicio: i ?? null, fim: f ?? null });
    setAGuardar(true);
    await aoGuardar(v);
    setAGuardar(false);
  }

  return (
    <div className="flex flex-col gap-3 rounded-pe-md border-[1.5px] border-pe-linha p-4">
      <Campo rotulo="Frase ou palavra em inglês" lang="en" value={texto} maxLength={300} onChange={(e) => setTexto(e.target.value)} erro={erros.texto} placeholder="Could you send me the report by Friday?" />
      <Campo rotulo="Tradução" value={traducao} maxLength={300} onChange={(e) => setTraducao(e.target.value)} placeholder="Pode enviar-me o relatório até sexta-feira?" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Escolha rotulo="Tipo" value={tipo} onChange={(e) => setTipo(e.target.value as FraseAula["tipo"])}>
          <option value="frase">Frase</option>
          <option value="palavra">Palavra</option>
        </Escolha>
        <Campo rotulo="Começa no vídeo em" value={inicio} onChange={(e) => setInicio(e.target.value)} erro={erros.inicio} placeholder="0:42" inputMode="numeric" />
        <Campo rotulo="Acaba em" value={fim} onChange={(e) => setFim(e.target.value)} erro={erros.fim} placeholder="0:46" inputMode="numeric" />
      </div>
      <p className="m-0 text-pe-legenda text-pe-tinta-suave">Os alunos ouvem este pedaço do vídeo antes de repetir. Sem tempos, ouvem a voz do browser.</p>
      <div className="flex flex-wrap justify-end gap-3">
        <Botao tipo="secundario" tamanho="pequeno" onClick={aoCancelar}>
          Cancelar
        </Botao>
        <Botao tamanho="pequeno" onClick={() => void guardar()} disabled={aGuardar}>
          {inicial ? "Guardar a frase" : "Acrescentar e aprovar"}
        </Botao>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Criar uma lição de prática a partir da aula                          */
/* ------------------------------------------------------------------ */

function CriarLicao({ cursoId, aula }: { cursoId: string; aula: Aula }) {
  const router = useRouter();
  const [aberto, setAberto] = useState(false);
  const { data: cursos, isLoading } = useLicoesPraticaQuery(cursoId, { skip: !aberto });
  const unidades = (cursos ?? []).flatMap((c) => c.unidades.map((u) => ({ curso: c, unidade: u })));
  const [escolha, setEscolha] = useState("");
  const valor = escolha || (unidades[0] ? `${unidades[0].curso.id}|${unidades[0].unidade.id}` : "");

  return (
    <div className="flex flex-col gap-2 rounded-pe-md border border-pe-linha px-4 py-3.5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="flex min-w-0 flex-col">
          <span className="font-semibold">Lição de prática a partir desta aula</span>
          <span className="text-pe-legenda text-pe-tinta-suave">A IA prepara exercícios com as frases aprovadas e a transcrição. Revê tudo antes de guardar.</span>
        </span>
        <Botao tipo="secundario" tamanho="pequeno" onClick={() => setAberto(true)}>
          <Dumbbell aria-hidden /> Criar lição de prática
        </Botao>
      </div>
      <Dialogo aberto={aberto} aoMudar={setAberto} titulo="Criar lição de prática a partir desta aula" descricao={`A lição fica numa unidade de um dos seus cursos de prática. No fim pode ligá-la a "${aula.titulo}".`}>
        {isLoading ? (
          <p className="m-0 inline-flex items-center gap-2">
            <Loader2 aria-hidden className="size-[18px] animate-spin" /> A carregar os seus cursos de prática…
          </p>
        ) : unidades.length ? (
          <Escolha rotulo="Para onde vai a lição" value={valor} onChange={(e) => setEscolha(e.target.value)}>
            {(cursos ?? [])
              .filter((c) => c.unidades.length)
              .map((c) => (
                <optgroup key={c.id} label={c.titulo}>
                  {c.unidades.map((u) => (
                    <option key={u.id} value={`${c.id}|${u.id}`}>
                      {u.titulo}
                    </option>
                  ))}
                </optgroup>
              ))}
          </Escolha>
        ) : (
          <Aviso tipo="info">Ainda não tem cursos de prática com unidades. Crie um curso de prática e uma unidade, e volte aqui.</Aviso>
        )}
        <div className="flex flex-wrap justify-end gap-3">
          <Botao tipo="secundario" tamanho="medio" onClick={() => setAberto(false)}>
            Cancelar
          </Botao>
          <Botao
            tamanho="medio"
            disabled={!valor}
            onClick={() => {
              const [curso, unidade] = valor.split("|");
              router.push(`/teacher/practice/${curso}/generate?unidade=${unidade}&aula=${aula.id}`);
            }}
          >
            Continuar
          </Botao>
        </div>
      </Dialogo>
    </div>
  );
}
