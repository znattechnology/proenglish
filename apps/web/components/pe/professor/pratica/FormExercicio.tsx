"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";
import { AreaTexto, Botao, Campo } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import { palavrasEntreParenteses, type Exercicio } from "@/src/domains/teacher/professor/pratica";

export type ErrosExercicio = Record<string, string>;

const entrada = "h-11 w-full min-w-0 rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo px-3 font-pe-texto text-[16px] text-pe-tinta aria-[invalid=true]:border-2 aria-[invalid=true]:border-pe-errado";
const legenda = "mb-1.5 p-0 text-pe-rotulo text-pe-tinta";
const erroTexto = "m-0 text-pe-legenda font-semibold text-pe-errado";

/** Erros do servidor (`details`) para cada campo do formulário. */
export function errosDeExercicio(e: unknown): ErrosExercicio {
  const d = (e as { data?: { details?: Record<string, unknown> } })?.data?.details;
  if (!d) return {};
  const r: ErrosExercicio = {};
  for (const [k, v] of Object.entries(d)) {
    const m = Array.isArray(v) ? v[0] : typeof v === "string" ? v : null;
    if (typeof m === "string") r[k] = m;
    else if (v && typeof v === "object") r[k] = Object.values(v as Record<string, string[]>).flat()[0] ?? "";
  }
  return r;
}

/** Junta as palavras entre parênteses (certas) com as opções erradas, como a API espera. */
export function opcoesCompletar(frase: string, erradas: string[]) {
  return [...palavrasEntreParenteses(frase).map((t) => ({ texto: t, certa: true })), ...erradas.map((t) => ({ texto: t, certa: false }))];
}

/**
 * Formulário de um exercício de qualquer tipo, com o que o aluno vê.
 * Controlado: o pai guarda o exercício e decide quando gravar.
 */
export function FormExercicio({ e, aoMudar, erros = {} }: { e: Exercicio; aoMudar: (e: Exercicio) => void; erros?: ErrosExercicio }) {
  // Mudar a frase de uma escuta ou pronúncia torna o áudio antigo errado: tira-o (gera-se outra vez).
  const muda = (p: Partial<Exercicio>) =>
    aoMudar({ ...e, ...p, ...(p.frase !== undefined && p.frase !== e.frase && (e.tipo === "escuta" || e.tipo === "pronuncia") ? { audio_url: null } : {}) });
  return (
    <div className="flex flex-col gap-5">
      {e.tipo === "escolher" || e.tipo === "assistir" ? (
        <>
          <Campo rotulo="Pergunta" value={e.enunciado} onChange={(x) => muda({ enunciado: x.target.value })} erro={erros.enunciado} placeholder="Which sentence is correct?" />
          <Opcoes e={e} muda={muda} erro={erros.opcoes} />
        </>
      ) : e.tipo === "verdadeiro_falso" ? (
        <>
          <Campo rotulo="Afirmação" value={e.enunciado} onChange={(x) => muda({ enunciado: x.target.value })} erro={erros.enunciado} placeholder={'"Pending" quer dizer "por fazer".'} />
          <fieldset className="m-0 border-0 p-0">
            <legend className={legenda}>A afirmação é</legend>
            <div className="flex gap-2">
              {(["verdadeiro", "falso"] as const).map((v) => (
                <label key={v} className={cnPe("flex min-h-11 cursor-pointer items-center gap-2 rounded-pe-sm px-4 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pe-azul-vivo", e.resposta === v ? "bg-pe-azul-marca text-pe-sobre-marca" : "border-[1.5px] border-pe-linha-forte")}>
                  <input type="radio" name="vf" checked={e.resposta === v} onChange={() => muda({ resposta: v })} className="sr-only" />
                  {v === "verdadeiro" ? "Verdadeira" : "Falsa"}
                </label>
              ))}
            </div>
          </fieldset>
        </>
      ) : e.tipo === "completar" ? (
        <Completar e={e} muda={muda} erros={erros} />
      ) : e.tipo === "traduzir" ? (
        <>
          <Campo rotulo="Frase em português" value={e.enunciado} onChange={(x) => muda({ enunciado: x.target.value })} erro={erros.enunciado} placeholder="A equipa da noite deixou três tarefas por fazer." />
          <Campo rotulo="Tradução em inglês" value={e.resposta} onChange={(x) => muda({ resposta: x.target.value })} erro={erros.resposta} placeholder="The night shift left three tasks unfinished." />
          <Lista
            rotulo="Outras traduções aceites (opcional)"
            valores={e.opcoes.filter((o) => o.certa).map((o) => o.texto)}
            aoMudar={(v) => muda({ opcoes: [...v.map((t) => ({ texto: t, certa: true })), ...e.opcoes.filter((o) => !o.certa)] })}
            maximo={5}
            acrescentar="Acrescentar tradução"
            erro={erros.opcoes}
          />
          <Lista
            rotulo="Opções erradas (opcional)"
            ajuda="Com opções erradas, o aluno escolhe a tradução em vez de a escrever."
            valores={e.opcoes.filter((o) => !o.certa).map((o) => o.texto)}
            aoMudar={(v) => muda({ opcoes: [...e.opcoes.filter((o) => o.certa), ...v.map((t) => ({ texto: t, certa: false }))] })}
            maximo={5}
            acrescentar="Acrescentar opção errada"
          />
        </>
      ) : e.tipo === "ordenar" ? (
        <>
          <Campo rotulo="O que a frase quer dizer, em português" value={e.enunciado} onChange={(x) => muda({ enunciado: x.target.value })} erro={erros.enunciado} placeholder="Envie o relatório antes da reunião." />
          <Campo
            rotulo="Frase em inglês, pela ordem certa"
            value={e.resposta}
            onChange={(x) => muda({ resposta: x.target.value })}
            erro={erros.resposta}
            ajuda="Entre 3 e 15 palavras. O aluno recebe-as baralhadas."
            placeholder="Send the report before the meeting."
          />
          {e.resposta.trim() ? (
            <Previsao>
              <span className="flex flex-wrap gap-2">
                {baralhar(e.resposta.trim().split(/\s+/)).map((p, i) => (
                  <span key={i} className="rounded-pe-sm border-[1.5px] border-pe-linha-forte bg-pe-fundo px-3 py-1 text-[17px]">
                    {p}
                  </span>
                ))}
              </span>
            </Previsao>
          ) : null}
        </>
      ) : e.tipo === "pares" ? (
        <Pares e={e} muda={muda} erro={erros.pares} />
      ) : e.tipo === "escuta" ? (
        <Escuta e={e} muda={muda} erros={erros} />
      ) : e.tipo === "pronuncia" ? (
        <>
          <Campo rotulo="Frase que o aluno diz" value={e.frase} onChange={(x) => muda({ frase: x.target.value })} erro={erros.frase} placeholder="Please wear your safety glasses." />
          <Campo rotulo="Instrução (opcional)" value={e.enunciado} onChange={(x) => muda({ enunciado: x.target.value })} erro={erros.enunciado} placeholder="Diga em voz alta." />
        </>
      ) : e.tipo === "responder" ? (
        <>
          <Campo
            rotulo="Pergunta, em inglês"
            value={e.enunciado}
            onChange={(x) => muda({ enunciado: x.target.value })}
            erro={erros.enunciado}
            ajuda="O aluno ouve e lê a pergunta, e responde em voz alta com as suas palavras."
            placeholder="When can you send me the shift report?"
          />
          <Campo
            rotulo="Frase-alvo"
            value={e.frase}
            onChange={(x) => muda({ frase: x.target.value })}
            erro={erros.frase}
            ajuda='A frase ou estrutura da lição que a resposta deve usar. Pode usar "..." para a parte livre.'
            placeholder="I'll have it ready by ..."
          />
          <Campo
            rotulo="Exemplo de resposta"
            value={e.resposta}
            onChange={(x) => muda({ resposta: x.target.value })}
            erro={erros.resposta}
            ajuda="Uma resposta boa que usa a frase-alvo. O aluno vê-a depois de responder."
            placeholder="I'll have it ready by five o'clock."
          />
          <Campo rotulo="Contexto (opcional)" value={e.contexto ?? ""} onChange={(x) => muda({ contexto: x.target.value })} erro={erros.contexto} placeholder="O seu supervisor pergunta pelo relatório do turno." />
        </>
      ) : e.tipo === "conversa" ? (
        <>
          <AreaTexto
            rotulo="Situação"
            rows={3}
            value={e.enunciado}
            onChange={(x) => muda({ enunciado: x.target.value })}
            erro={erros.enunciado}
            ajuda="Quem é o tutor e o que acontece. A conversa dura 1 a 2 minutos e aparece no fim da lição."
            placeholder="O tutor é o supervisor e pede o relatório do turno."
          />
          <Lista
            rotulo="Frases da lição que o aluno deve usar (2 ou 3)"
            valores={e.frases_alvo ?? []}
            aoMudar={(v) => muda({ frases_alvo: v })}
            maximo={3}
            acrescentar="Acrescentar frase"
            erro={erros.frases_alvo}
          />
        </>
      ) : null}

      <AreaTexto
        rotulo="Explicação em português (opcional)"
        rows={2}
        value={e.explicacao}
        onChange={(x) => muda({ explicacao: x.target.value })}
        erro={erros.explicacao}
        ajuda="Aparece depois de responder."
        placeholder={'"Pending" quer dizer que ainda está por fazer. Usa-se muito em relatórios de turno.'}
      />
    </div>
  );
}

function Previsao({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2 rounded-pe-md bg-pe-fundo-suave px-5 py-4">
      <span className="text-pe-legenda font-semibold text-pe-tinta-suave">Como o aluno vê</span>
      {children}
    </div>
  );
}

function baralhar<T>(v: T[]) {
  // Determinístico para a pré-visualização não saltar a cada tecla: roda metade das palavras.
  const k = Math.ceil(v.length / 2);
  return [...v.slice(k), ...v.slice(0, k)];
}

function Opcoes({ e, muda, erro }: { e: Exercicio; muda: (p: Partial<Exercicio>) => void; erro?: string }) {
  const ops = e.opcoes;
  // Imagens nas respostas ("Escolha a imagem: a receipt"): o texto continua a ser obrigatório.
  const [comImagens, setComImagens] = useState(() => ops.some((o) => o.imagem));
  const mudaOpcao = (k: number, p: Partial<Exercicio["opcoes"][number]>) => muda({ opcoes: ops.map((y, j) => (j === k ? { ...y, ...p } : y)) });
  return (
    <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
      <legend className={legenda}>Respostas: marque a certa</legend>
      <label className="flex items-center gap-2 text-[15px]">
        <input
          type="checkbox"
          checked={comImagens}
          onChange={(x) => {
            setComImagens(x.target.checked);
            if (!x.target.checked) muda({ opcoes: ops.map((o) => ({ ...o, imagem: null })) });
          }}
          className="size-4 accent-pe-azul-marca"
        />
        Respostas com imagem
      </label>
      {ops.map((o, k) => (
        <div key={k} className={cnPe("flex flex-col gap-2 rounded-pe-sm px-2 py-1", o.certa && "bg-pe-certo-suave")}>
          <div className="flex items-center gap-2">
            <input
              type="radio"
              name="certa"
              checked={o.certa}
              onChange={() => muda({ opcoes: ops.map((x, j) => ({ ...x, certa: j === k })) })}
              aria-label={`Resposta ${k + 1} é a certa`}
              className="size-5 shrink-0 accent-pe-certo"
            />
            <input value={o.texto} aria-label={`Resposta ${k + 1}`} onChange={(x) => mudaOpcao(k, { texto: x.target.value })} className={entrada} />
            {ops.length > 2 ? (
              <button
                type="button"
                aria-label={`Tirar a resposta ${k + 1}`}
                onClick={() => {
                  const resto = ops.filter((_, j) => j !== k);
                  if (o.certa && resto.length) resto[0] = { ...resto[0], certa: true };
                  muda({ opcoes: resto });
                }}
                className="flex size-10 shrink-0 items-center justify-center rounded-pe-sm text-pe-tinta-suave hover:text-pe-tinta"
              >
                <X aria-hidden className="size-4" />
              </button>
            ) : null}
          </div>
          {comImagens ? (
            <div className="flex items-center gap-2 pl-7">
              {o.imagem ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={o.imagem} alt="" className="size-12 shrink-0 rounded-pe-sm border border-pe-linha bg-white object-contain" />
              ) : null}
              <input
                value={o.imagem ?? ""}
                inputMode="url"
                placeholder="https://… (endereço da imagem)"
                aria-label={`Imagem da resposta ${k + 1}`}
                onChange={(x) => mudaOpcao(k, { imagem: x.target.value.trim() || null })}
                className={entrada}
              />
            </div>
          ) : null}
        </div>
      ))}
      {ops.length < 6 ? (
        <Botao tipo="ligacao" tamanho="pequeno" className="self-start" onClick={() => muda({ opcoes: [...ops, { texto: "", certa: false }] })}>
          <Plus aria-hidden className="size-4" />
          Acrescentar resposta
        </Botao>
      ) : null}
      {erro ? <p className={erroTexto}>{erro}</p> : null}
    </fieldset>
  );
}

function Lista({ rotulo, valores, aoMudar, maximo, acrescentar, erro, ajuda }: { rotulo: string; valores: string[]; aoMudar: (v: string[]) => void; maximo: number; acrescentar: string; erro?: string; ajuda?: string }) {
  return (
    <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
      <legend className={legenda}>{rotulo}</legend>
      {ajuda ? <p className="-mt-1 m-0 text-pe-legenda text-pe-tinta-suave">{ajuda}</p> : null}
      <div className="grid gap-2 sm:grid-cols-2">
        {valores.map((v, k) => (
          <div key={k} className="flex items-center gap-1">
            <input value={v} aria-label={`${rotulo} ${k + 1}`} onChange={(x) => aoMudar(valores.map((y, j) => (j === k ? x.target.value : y)))} className={entrada} />
            <button type="button" aria-label={`Tirar ${k + 1}`} onClick={() => aoMudar(valores.filter((_, j) => j !== k))} className="flex size-10 shrink-0 items-center justify-center text-pe-tinta-suave hover:text-pe-tinta">
              <X aria-hidden className="size-4" />
            </button>
          </div>
        ))}
      </div>
      {valores.length < maximo ? (
        <Botao tipo="ligacao" tamanho="pequeno" className="self-start" onClick={() => aoMudar([...valores, ""])}>
          <Plus aria-hidden className="size-4" />
          {acrescentar}
        </Botao>
      ) : null}
      {erro ? <p className={erroTexto}>{erro}</p> : null}
    </fieldset>
  );
}

function Completar({ e, muda, erros }: { e: Exercicio; muda: (p: Partial<Exercicio>) => void; erros: ErrosExercicio }) {
  const erradas = e.opcoes.filter((o) => !o.certa).map((o) => o.texto);
  const partes = e.frase.split(/(\[[^\]]+\])/g);
  return (
    <>
      <Campo
        rotulo="Frase em inglês"
        value={e.frase}
        onChange={(x) => muda({ frase: x.target.value, opcoes: opcoesCompletar(x.target.value, erradas) })}
        erro={erros.frase}
        ajuda="Ponha entre parênteses rectos a palavra que o aluno tem de escolher."
        placeholder="Two valves are still [pending] inspection."
      />
      {e.frase.trim() ? (
        <Previsao>
          <p className="m-0 text-[19px] leading-[29px]">
            {partes.map((p, i) =>
              /^\[[^\]]+\]$/.test(p) ? (
                <span key={i} className="mx-0.5 inline-block min-w-16 rounded-pe-sm bg-pe-realce px-2.5 text-center">
                  {p.slice(1, -1)}
                </span>
              ) : (
                <span key={i}>{p}</span>
              )
            )}
          </p>
        </Previsao>
      ) : null}
      <Lista
        rotulo="Opções erradas"
        valores={erradas}
        aoMudar={(v) => muda({ opcoes: opcoesCompletar(e.frase, v) })}
        maximo={5}
        acrescentar="Acrescentar opção errada"
        erro={erros.opcoes}
        ajuda="Palavras parecidas que o aluno pode confundir. Sem opções erradas, o aluno escreve a palavra."
      />
      <Campo rotulo="Instrução (opcional)" value={e.enunciado} onChange={(x) => muda({ enunciado: x.target.value })} erro={erros.enunciado} placeholder="Escolha a palavra que falta." />
    </>
  );
}

function Pares({ e, muda, erro }: { e: Exercicio; muda: (p: Partial<Exercicio>) => void; erro?: string }) {
  return (
    <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
      <legend className={legenda}>Pares: inglês e português</legend>
      {e.pares.map((p, k) => (
        <div key={k} className="flex items-center gap-2">
          <input value={p.a} aria-label={`Par ${k + 1}, em inglês`} placeholder="handover" onChange={(x) => muda({ pares: e.pares.map((y, j) => (j === k ? { ...y, a: x.target.value } : y)) })} className={entrada} />
          <span aria-hidden className="text-pe-tinta-suave">=</span>
          <input value={p.b} aria-label={`Par ${k + 1}, em português`} placeholder="passagem de turno" onChange={(x) => muda({ pares: e.pares.map((y, j) => (j === k ? { ...y, b: x.target.value } : y)) })} className={entrada} />
          {e.pares.length > 3 ? (
            <button type="button" aria-label={`Tirar o par ${k + 1}`} onClick={() => muda({ pares: e.pares.filter((_, j) => j !== k) })} className="flex size-10 shrink-0 items-center justify-center text-pe-tinta-suave hover:text-pe-tinta">
              <X aria-hidden className="size-4" />
            </button>
          ) : null}
        </div>
      ))}
      {e.pares.length < 8 ? (
        <Botao tipo="ligacao" tamanho="pequeno" className="self-start" onClick={() => muda({ pares: [...e.pares, { a: "", b: "" }] })}>
          <Plus aria-hidden className="size-4" />
          Acrescentar par
        </Botao>
      ) : null}
      {erro ? <p className={erroTexto}>{erro}</p> : null}
    </fieldset>
  );
}

function Escuta({ e, muda, erros }: { e: Exercicio; muda: (p: Partial<Exercicio>) => void; erros: ErrosExercicio }) {
  const ditado = !e.opcoes.length;
  return (
    <>
      <Campo rotulo="Frase que o aluno ouve" value={e.frase} onChange={(x) => muda({ frase: x.target.value })} erro={erros.frase} placeholder="The pressure test is scheduled for two." />
      <fieldset className="m-0 border-0 p-0">
        <legend className={legenda}>O que o aluno faz</legend>
        <div className="flex flex-wrap gap-2">
          {[
            { v: true, nome: "Escreve o que ouviu" },
            { v: false, nome: "Responde a uma pergunta" },
          ].map((o) => (
            <label key={o.nome} className={cnPe("flex min-h-11 cursor-pointer items-center rounded-pe-sm px-4 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pe-azul-vivo", ditado === o.v ? "bg-pe-azul-marca text-pe-sobre-marca" : "border-[1.5px] border-pe-linha-forte")}>
              <input
                type="radio"
                name="modo-escuta"
                checked={ditado === o.v}
                onChange={() => muda(o.v ? { opcoes: [], enunciado: "" } : { opcoes: [{ texto: "", certa: true }, { texto: "", certa: false }, { texto: "", certa: false }] })}
                className="sr-only"
              />
              {o.nome}
            </label>
          ))}
        </div>
      </fieldset>
      {ditado ? null : (
        <>
          <Campo rotulo="Pergunta" value={e.enunciado} onChange={(x) => muda({ enunciado: x.target.value })} erro={erros.enunciado} placeholder="Quando é o teste de pressão?" />
          <Opcoes e={e} muda={muda} erro={erros.opcoes} />
        </>
      )}
    </>
  );
}
