"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft, Plus, X } from "lucide-react";
import { AreaTexto, Aviso, Botao, Campo, Escolha } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { cnPe } from "@/lib/pe";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import {
  useApagarSituacaoMutation,
  useCriarSituacaoMutation,
  useMudarSituacaoMutation,
  useOpcoesSituacaoQuery,
  type NovaSituacao,
  type Situacao,
} from "@/src/domains/teacher/professor/fala";

const vazia: NovaSituacao = { nome: "", descricao: "", papel_tutor: "", frases: [""], curso: null, nivel: "B1", duracao_min: 5, correccao: "suave", estado: "rascunho" };

/** Criar ou editar uma situação de conversa com o tutor. */
export function FormSituacao({ inicial }: { inicial?: Situacao }) {
  const router = useRouter();
  const { data: opcoes } = useOpcoesSituacaoQuery();
  const [criar, { isLoading: aCriar }] = useCriarSituacaoMutation();
  const [mudar, { isLoading: aMudar }] = useMudarSituacaoMutation();
  const [remover, { isLoading: aRemover }] = useApagarSituacaoMutation();
  const [v, setV] = useState<NovaSituacao>(
    inicial ? { ...inicial, curso: inicial.curso?.id ?? null, frases: inicial.frases.length ? inicial.frases : [""] } : vazia
  );
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const [apagar, setApagar] = useState(false);
  const muda = (p: Partial<NovaSituacao>) => setV((x) => ({ ...x, ...p }));
  const aGuardar = aCriar || aMudar;

  async function guardar(estado: NovaSituacao["estado"]) {
    setGeral(null);
    const er: Record<string, string> = {};
    if (v.nome.trim().length < 3) er.nome = "Escreva o nome que o aluno vê.";
    if (v.descricao.trim().length < 20) er.descricao = "Descreva a cena em pelo menos uma frase completa.";
    if (!v.papel_tutor.trim()) er.papel_tutor = "Diga que papel faz o tutor.";
    setErros(er);
    if (Object.keys(er).length) return;
    const corpo = { ...v, estado, nome: v.nome.trim(), descricao: v.descricao.trim(), papel_tutor: v.papel_tutor.trim(), frases: v.frases.map((f) => f.trim()).filter(Boolean) };
    try {
      if (inicial) await mudar({ id: inicial.id, ...corpo }).unwrap();
      else await criar(corpo).unwrap();
      router.push("/teacher/speaking");
    } catch (x) {
      setErros(errosPorCampo(x));
      setGeral(mensagemErro(x, "Não foi possível guardar. Tente outra vez."));
    }
  }

  return (
    <>
      <div className="flex flex-col gap-2">
        <Link href="/teacher/speaking" className="inline-flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-vivo no-underline">
          <ChevronLeft aria-hidden className="size-[18px]" />
          Conversa e escuta
        </Link>
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 tracking-[-0.015em] md:text-[32px] md:leading-[38px]">{inicial ? inicial.nome : "Nova situação de conversa"}</h1>
        <p className="m-0 text-pe-tinta-suave">O tutor de IA usa esta descrição para conduzir a conversa.</p>
      </div>

      <form noValidate onSubmit={(e) => { e.preventDefault(); void guardar("activo"); }} className="flex max-w-[760px] flex-col gap-5">
        <Campo rotulo="Nome que o aluno vê" value={v.nome} maxLength={80} onChange={(e) => muda({ nome: e.target.value })} erro={erros.nome} placeholder="Pedir um relatório" />
        <AreaTexto
          rotulo="O que acontece"
          rows={4}
          maxLength={600}
          value={v.descricao}
          onChange={(e) => muda({ descricao: e.target.value })}
          erro={erros.descricao}
          placeholder="O aluno é técnico de segurança. O tutor faz de supervisor e pede o relatório de perfuração até sexta. O aluno tem de aceitar, confirmar o prazo e dizer o que o relatório inclui."
          ajuda={`Quem é o aluno, o que quer o tutor e o que o aluno tem de conseguir. ${v.descricao.length} de 600 caracteres.`}
        />
        <Campo
          rotulo="Papel do tutor"
          value={v.papel_tutor}
          maxLength={200}
          onChange={(e) => muda({ papel_tutor: e.target.value })}
          erro={erros.papel_tutor}
          placeholder="Supervisor de perfuração, exigente mas cordial"
          ajuda="O tutor mantém este papel durante toda a conversa."
        />
        <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
          <legend className="mb-1.5 p-0 text-pe-rotulo">Frases que o aluno deve usar (opcional)</legend>
          {v.frases.map((f, k) => (
            <div key={k} className="flex items-center gap-1">
              <input
                value={f}
                maxLength={160}
                aria-label={`Frase ${k + 1}`}
                placeholder={k === 0 ? "I'll have it ready by Friday." : ""}
                onChange={(e) => muda({ frases: v.frases.map((x, j) => (j === k ? e.target.value : x)) })}
                className="h-11 w-full rounded-pe-sm border-[1.5px] border-pe-linha-forte px-3 font-pe-texto text-[16px]"
              />
              {v.frases.length > 1 ? (
                <button type="button" aria-label={`Tirar a frase ${k + 1}`} onClick={() => muda({ frases: v.frases.filter((_, j) => j !== k) })} className="flex size-10 shrink-0 items-center justify-center text-pe-tinta-suave hover:text-pe-tinta">
                  <X aria-hidden className="size-4" />
                </button>
              ) : null}
            </div>
          ))}
          {v.frases.length < 8 ? (
            <Botao tipo="ligacao" tamanho="pequeno" className="self-start" onClick={() => muda({ frases: [...v.frases, ""] })}>
              <Plus aria-hidden className="size-4" />
              Acrescentar frase
            </Botao>
          ) : null}
          {erros.frases ? <p className="m-0 text-pe-legenda font-semibold text-pe-errado">{erros.frases}</p> : null}
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-3">
          <Escolha rotulo="Curso" value={v.curso ?? ""} onChange={(e) => muda({ curso: e.target.value || null })} erro={erros.curso}>
            <option value="">Geral (todos os seus alunos)</option>
            {opcoes?.cursos.map((c) => (
              <option key={c.id} value={c.id}>
                {c.titulo}
              </option>
            ))}
          </Escolha>
          <Escolha rotulo="Nível" value={v.nivel} onChange={(e) => muda({ nivel: e.target.value })} erro={erros.nivel}>
            {(opcoes?.niveis ?? ["A1", "A2", "B1", "B2", "C1", "C2"].map((n) => ({ valor: n, nome: n }))).map((n) => (
              <option key={n.valor} value={n.valor}>
                {n.nome}
              </option>
            ))}
          </Escolha>
          <Escolha rotulo="Duração sugerida" value={v.duracao_min} onChange={(e) => muda({ duracao_min: Number(e.target.value) as NovaSituacao["duracao_min"] })}>
            {(opcoes?.duracoes ?? [3, 5, 10]).map((d) => (
              <option key={d} value={d}>
                {d} minutos
              </option>
            ))}
          </Escolha>
        </div>

        <fieldset className="m-0 border-0 p-0">
          <legend className="mb-1.5 p-0 text-pe-rotulo">Correcção por defeito</legend>
          <div className="flex flex-wrap gap-2">
            {(
              [
                { v: "suave", nome: "Suave", texto: "repete a frase já corrigida, sem interromper" },
                { v: "directa", nome: "Directa", texto: "diz logo o erro e a forma certa" },
              ] as const
            ).map((o) => (
              <label key={o.v} className={cnPe("flex min-h-11 cursor-pointer items-center gap-1.5 rounded-pe-sm px-4", v.correccao === o.v ? "bg-pe-azul-marca text-pe-sobre-marca" : "border-[1.5px] border-pe-linha-forte")}>
                <input type="radio" name="correccao" checked={v.correccao === o.v} onChange={() => muda({ correccao: o.v })} className="sr-only" />
                <span className="font-semibold">{o.nome}</span>
                <span className="text-[14px] opacity-80">{o.texto}</span>
              </label>
            ))}
          </div>
          <p className="m-0 mt-1.5 text-pe-legenda text-pe-tinta-suave">O aluno pode mudar antes de começar.</p>
        </fieldset>

        {geral ? <Aviso tipo="errado">{geral}</Aviso> : null}
        <div className="flex flex-wrap items-center gap-3 border-t border-pe-linha pt-5">
          <Botao type="submit" tamanho="medio" disabled={aGuardar}>
            {aGuardar ? "A guardar…" : inicial?.estado === "activo" ? "Guardar alterações" : "Guardar e publicar"}
          </Botao>
          <Botao tipo="secundario" tamanho="medio" disabled={aGuardar} onClick={() => void guardar("rascunho")}>
            {inicial?.estado === "activo" ? "Desligar (voltar a rascunho)" : "Guardar rascunho"}
          </Botao>
          {inicial ? (
            <Botao tipo="ligacao" tamanho="medio" className="ml-auto text-pe-errado hover:text-pe-errado" onClick={() => setApagar(true)}>
              Apagar situação
            </Botao>
          ) : null}
        </div>
      </form>

      {inicial ? (
        <Dialogo aberto={apagar} aoMudar={setApagar} titulo={`Apagar "${inicial.nome}"?`} descricao="Só é possível apagar situações que ainda não foram usadas. Se já houver conversas, desligue-a em vez de apagar.">
          {geral ? <Aviso tipo="errado">{geral}</Aviso> : null}
          <div className="flex flex-wrap justify-end gap-3">
            <Botao tipo="secundario" tamanho="medio" onClick={() => setApagar(false)}>
              Cancelar
            </Botao>
            <Botao
              tipo="perigo"
              tamanho="medio"
              disabled={aRemover}
              onClick={async () => {
                setGeral(null);
                try {
                  await remover(inicial.id).unwrap();
                  router.push("/teacher/speaking");
                } catch (x) {
                  setGeral(mensagemErro(x, "Não foi possível apagar."));
                }
              }}
            >
              Apagar situação
            </Botao>
          </div>
        </Dialogo>
      ) : null}
    </>
  );
}
