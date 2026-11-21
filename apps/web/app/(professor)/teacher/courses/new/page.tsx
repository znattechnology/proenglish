"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { Check, ChevronLeft, FlaskConical, Plus, Video, X } from "lucide-react";
import { AreaTexto, Aviso, Botao, Campo, Escolha } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { cnPe } from "@/lib/pe";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { useCriarCursoMutation, useOpcoesQuery, type TipoCurso } from "@/src/domains/teacher/professor/api";
import { DESCRICAO_NIVEL, OPCOES_NIVEL, nomeCompletoNivel, normalizarNivel } from "@/src/domains/shared/niveis";

const PASSOS = ["Tipo e tema", "Público", "Estrutura", "Rever"] as const;

const TIPOS: { valor: TipoCurso; nome: string; texto: string; Icone: typeof Video }[] = [
  { valor: "video", nome: "Curso em vídeo", texto: "Aulas gravadas em secções, com materiais e questionário em cada aula.", Icone: Video },
  { valor: "pratica", nome: "Curso de prática", texto: "Unidades e lições curtas no laboratório, com vidas, pontos e os 9 tipos de exercício.", Icone: FlaskConical },
];

export default function CriarCurso() {
  return (
    <Pagina className="max-w-[880px] gap-6">
      <Suspense>
        <Assistente />
      </Suspense>
    </Pagina>
  );
}

function Assistente() {
  const router = useRouter();
  const sp = useSearchParams();
  const [criar, { isLoading }] = useCriarCursoMutation();

  const [passo, setPasso] = useState(0);
  const [tipo, setTipo] = useState<TipoCurso>(sp.get("tipo") === "pratica" ? "pratica" : "video");
  const { data: opcoes } = useOpcoesQuery(tipo);
  const [titulo, setTitulo] = useState("");
  const [areaEscolhida, setArea] = useState("");
  const [nivelEscolhido, setNivel] = useState("");
  // Até a pessoa escolher, vale a primeira opção que a API devolve.
  const area = opcoes?.areas.some((a) => a.valor === areaEscolhida) ? areaEscolhida : (opcoes?.areas.find((a) => !a.legado)?.valor ?? "");
  // Até a pessoa escolher, A2 (o nível por omissão dos cursos).
  const nivel = normalizarNivel(nivelEscolhido) ?? "A2";
  const [descricao, setDescricao] = useState("");
  const [acesso, setAcesso] = useState<"todos" | "premium">("premium");
  const [partes, setPartes] = useState<string[]>(["", ""]);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const titulo1 = useRef<HTMLHeadingElement>(null);

  // Ao mudar de passo, o foco vai para o título do passo (quem usa leitor de ecrã sabe onde está).
  useEffect(() => {
    window.scrollTo({ top: 0 });
    titulo1.current?.focus({ preventScroll: true });
  }, [passo]);

  const voltarA = tipo === "pratica" ? "/teacher/practice" : "/teacher/courses";
  const nomeParte = tipo === "video" ? "secção" : "unidade";
  const nomeArea = opcoes?.areas.find((a) => a.valor === area)?.nome ?? area;
  const nomeNivel = nomeCompletoNivel(nivel) ?? nivel;
  const partesFeitas = partes.map((p) => p.trim()).filter(Boolean);

  function validar(p: number) {
    const e: Record<string, string> = {};
    if (p === 0) {
      if (!titulo.trim()) e.titulo = "Escreva o título do curso.";
      else if (titulo.trim().length > 60) e.titulo = `Tem ${titulo.trim().length} caracteres. O máximo é 60.`;
      if (!descricao.trim()) e.descricao = "Escreva uma frase sobre o que o curso ensina.";
    }
    setErros(e);
    return !Object.keys(e).length;
  }

  async function concluir() {
    setErroGeral(null);
    try {
      const c = await criar({
        tipo,
        titulo: titulo.trim(),
        descricao: descricao.trim(),
        area,
        nivel,
        acesso,
        ...(tipo === "video" ? { seccoes: partesFeitas } : { unidades: partesFeitas }),
      }).unwrap();
      router.push(tipo === "video" ? `/teacher/courses/${c.id}` : `/teacher/practice/${c.id}`);
    } catch (er) {
      setErroGeral(mensagemErro(er, "Não foi possível criar o curso. Tente outra vez."));
    }
  }

  return (
    <>
      <div className="flex flex-col gap-2">
        <Link href={voltarA} className="inline-flex min-h-11 items-center gap-1 self-start font-semibold text-pe-azul-vivo no-underline">
          <ChevronLeft aria-hidden className="size-[18px]" />
          {tipo === "pratica" ? "Cursos de prática" : "Cursos em vídeo"}
        </Link>
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 tracking-[-0.015em] md:text-[32px] md:leading-[38px]">Criar curso</h1>
        <p className="m-0 text-pe-tinta-suave">Pode mudar tudo isto mais tarde. O curso fica em rascunho até o enviar para revisão.</p>
      </div>

      <ol aria-label="Passos" className="m-0 grid list-none grid-cols-4 gap-2 p-0">
        {PASSOS.map((nome, i) => (
          <li key={nome} aria-current={i === passo ? "step" : undefined} className="flex flex-col gap-1.5">
            <span className={cnPe("h-1.5 rounded-full", i <= passo ? "bg-pe-azul-marca" : "bg-pe-fundo-forte")} />
            <span className={cnPe("text-[13px] leading-[18px] sm:text-pe-legenda", i === passo ? "font-semibold text-pe-tinta" : "text-pe-tinta-suave")}>
              <span className="hidden sm:inline">{i + 1}. </span>
              {nome}
            </span>
          </li>
        ))}
      </ol>

      <form
        noValidate
        className="flex flex-col gap-6"
        onSubmit={(e) => {
          e.preventDefault();
          if (!validar(passo)) return;
          if (passo < PASSOS.length - 1) setPasso(passo + 1);
          else void concluir();
        }}
      >
        {passo === 0 ? (
          <>
            <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
              <legend className="mb-3 p-0">
                <h2 ref={titulo1} tabIndex={-1} className="m-0 font-pe-titulo text-[22px] font-semibold leading-7 outline-none">
                  Que tipo de curso?
                </h2>
              </legend>
              <div className="grid gap-3 sm:grid-cols-2">
                {TIPOS.map(({ valor, nome, texto, Icone }) => {
                  const sel = tipo === valor;
                  return (
                    <label
                      key={valor}
                      className={cnPe(
                        "relative flex cursor-pointer flex-col gap-1.5 rounded-pe-md p-4 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pe-azul-vivo",
                        sel ? "border-2 border-pe-azul-marca bg-pe-fundo-suave" : "border-[1.5px] border-pe-linha bg-pe-fundo hover:bg-pe-fundo-suave"
                      )}
                    >
                      <input type="radio" name="tipo" value={valor} checked={sel} onChange={() => setTipo(valor)} className="sr-only" />
                      <Icone aria-hidden className="size-[26px]" />
                      <span className="font-semibold">{nome}</span>
                      <span className="text-[15px] leading-[22px] text-pe-tinta-suave">{texto}</span>
                      {sel ? (
                        <span aria-hidden className="absolute right-3 top-3 flex size-6 items-center justify-center rounded-full bg-pe-azul-marca text-pe-sobre-marca">
                          <Check className="size-4" />
                        </span>
                      ) : null}
                    </label>
                  );
                })}
              </div>
            </fieldset>
            <Campo
              rotulo="Título"
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              maxLength={80}
              placeholder="Passagem de turno"
              erro={erros.titulo}
              ajuda={`Diga o que o aluno vai conseguir fazer. ${titulo.trim().length} de 60 caracteres.`}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Escolha rotulo="Área" value={area} onChange={(e) => setArea(e.target.value)} disabled={!opcoes}>
                {opcoes?.areas.filter((a) => !a.legado).map((a) => (
                  <option key={a.valor} value={a.valor}>
                    {a.nome}
                  </option>
                ))}
              </Escolha>
              <Escolha rotulo="Nível" value={nivel} onChange={(e) => setNivel(e.target.value)} ajuda={DESCRICAO_NIVEL[nivel]}>
                {OPCOES_NIVEL.map((n) => (
                  <option key={n.valor} value={n.valor}>
                    {n.nome}
                  </option>
                ))}
              </Escolha>
            </div>
            <AreaTexto
              rotulo="Descrição curta"
              rows={3}
              maxLength={300}
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              placeholder="Inglês para entregar e receber o turno: tarefas pendentes, riscos e equipamento."
              erro={erros.descricao}
              ajuda="Aparece no catálogo, por baixo do título."
            />
          </>
        ) : passo === 1 ? (
          <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
            <legend className="mb-1 p-0">
              <h2 ref={titulo1} tabIndex={-1} className="m-0 font-pe-titulo text-[22px] font-semibold leading-7 outline-none">
                Quem pode fazer este curso?
              </h2>
            </legend>
            <p className="m-0 mb-2 text-pe-tinta-suave">Os alunos do Gratuito vêem o curso no catálogo, mas só os planos indicados o podem abrir.</p>
            {(
              [
                { v: "premium", nome: "Planos Premium e Premium Plus", texto: "Recomendado para cursos completos, com várias secções ou unidades." },
                { v: "todos", nome: "Todos os alunos, incluindo o Gratuito", texto: "Bom para cursos curtos de introdução que trazem alunos novos." },
              ] as const
            ).map((o) => (
              <label
                key={o.v}
                className={cnPe(
                  "flex cursor-pointer items-start gap-3 rounded-pe-md p-4 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pe-azul-vivo",
                  acesso === o.v ? "border-2 border-pe-azul-marca bg-pe-fundo-suave" : "border-[1.5px] border-pe-linha hover:bg-pe-fundo-suave"
                )}
              >
                <input type="radio" name="acesso" checked={acesso === o.v} onChange={() => setAcesso(o.v)} className="mt-1 size-5 shrink-0 accent-pe-azul-marca" />
                <span className="flex flex-col">
                  <span className="font-semibold">{o.nome}</span>
                  <span className="text-[15px] leading-[22px] text-pe-tinta-suave">{o.texto}</span>
                </span>
              </label>
            ))}
          </fieldset>
        ) : passo === 2 ? (
          <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
            <legend className="mb-1 p-0">
              <h2 ref={titulo1} tabIndex={-1} className="m-0 font-pe-titulo text-[22px] font-semibold leading-7 outline-none">
                {tipo === "video" ? "Em que secções divide o curso?" : "Em que unidades divide o curso?"}
              </h2>
            </legend>
            <p className="m-0 mb-2 text-pe-tinta-suave">
              {tipo === "video"
                ? "Uma secção junta aulas sobre o mesmo momento ou tema. Pode deixar em branco e criar as secções no editor."
                : "Uma unidade junta lições sobre o mesmo tema. Pode deixar em branco e criar as unidades no editor."}
            </p>
            <ol className="m-0 flex list-none flex-col gap-2 p-0">
              {partes.map((p, i) => (
                <li key={i} className="flex items-end gap-2">
                  <Campo
                    className="flex-1"
                    rotulo={`${tipo === "video" ? "Secção" : "Unidade"} ${i + 1}`}
                    value={p}
                    maxLength={80}
                    placeholder={i === 0 ? (tipo === "video" ? "Antes da reunião" : "Segurança no estaleiro") : ""}
                    onChange={(e) => setPartes((v) => v.map((x, j) => (j === i ? e.target.value : x)))}
                  />
                  {partes.length > 1 ? (
                    <button
                      type="button"
                      onClick={() => setPartes((v) => v.filter((_, j) => j !== i))}
                      aria-label={`Tirar a ${nomeParte} ${i + 1}`}
                      className="flex size-12 shrink-0 items-center justify-center rounded-pe-sm text-pe-tinta-suave hover:bg-pe-fundo-suave hover:text-pe-tinta"
                    >
                      <X aria-hidden className="size-5" />
                    </button>
                  ) : null}
                </li>
              ))}
            </ol>
            {partes.length < 12 ? (
              <Botao tipo="ligacao" tamanho="pequeno" className="self-start" onClick={() => setPartes((v) => [...v, ""])}>
                <Plus aria-hidden className="size-[18px]" />
                Acrescentar {nomeParte}
              </Botao>
            ) : null}
          </fieldset>
        ) : (
          <section className="flex flex-col gap-4">
            <h2 ref={titulo1} tabIndex={-1} className="m-0 font-pe-titulo text-[22px] font-semibold leading-7 outline-none">
              Rever
            </h2>
            <dl className="m-0 flex flex-col">
              {[
                { nome: "Tipo", valor: TIPOS.find((t) => t.valor === tipo)?.nome, ir: 0 },
                { nome: "Título", valor: titulo.trim(), ir: 0 },
                { nome: "Área e nível", valor: `${nomeArea}, ${nomeNivel}`, ir: 0 },
                { nome: "Descrição", valor: descricao.trim(), ir: 0 },
                { nome: "Quem pode fazer", valor: acesso === "premium" ? "Planos Premium e Premium Plus" : "Todos os alunos", ir: 1 },
                {
                  nome: tipo === "video" ? "Secções" : "Unidades",
                  valor: partesFeitas.length ? partesFeitas.join("; ") : "Nenhuma ainda: crie-as no editor",
                  ir: 2,
                },
              ].map((l) => (
                <div key={l.nome} className="flex flex-col gap-0.5 border-b border-pe-fundo-forte py-3 sm:flex-row sm:gap-6">
                  <dt className="shrink-0 text-pe-tinta-suave sm:w-44">{l.nome}</dt>
                  <dd className="m-0 flex-1">{l.valor}</dd>
                  <dd className="m-0">
                    <button type="button" onClick={() => setPasso(l.ir)} className="font-semibold text-pe-azul-vivo underline underline-offset-[3px]">
                      Mudar<span className="sr-only">: {l.nome}</span>
                    </button>
                  </dd>
                </div>
              ))}
            </dl>
            <p className="m-0 text-pe-tinta-suave">
              O curso é criado em rascunho. Nenhum aluno o vê até o enviar para revisão e a equipa ProEnglish o aprovar.
            </p>
          </section>
        )}

        {erroGeral ? <Aviso tipo="errado">{erroGeral}</Aviso> : null}

        <div className="flex flex-wrap items-center justify-end gap-3 border-t border-pe-linha pt-5">
          {passo === 0 ? (
            <Botao asChild tipo="secundario" tamanho="medio">
              <Link href={voltarA}>Cancelar</Link>
            </Botao>
          ) : (
            <Botao tipo="secundario" tamanho="medio" onClick={() => setPasso(passo - 1)}>
              Voltar
            </Botao>
          )}
          <Botao type="submit" tamanho="medio" disabled={isLoading || !opcoes}>
            {passo < PASSOS.length - 1 ? "Continuar" : isLoading ? "A criar…" : "Criar rascunho"}
          </Botao>
        </div>
      </form>
    </>
  );
}
