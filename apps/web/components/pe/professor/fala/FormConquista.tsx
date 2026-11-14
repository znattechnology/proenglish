"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronLeft } from "lucide-react";
import { Aviso, Botao, Campo, Escolha, Etiqueta } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { errosPorCampo } from "@/components/pe/conta/Partes";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import {
  RARIDADE,
  useApagarConquistaMutation,
  useCriarConquistaMutation,
  useMudarConquistaMutation,
  useOpcoesConquistaQuery,
  type Conquista,
  type NovaConquista,
  type Raridade,
} from "@/src/domains/teacher/professor/fala";
import { Medalha } from "./Medalha";

const vazia: NovaConquista = { nome: "", descricao: "", icone: "", regra: { tipo: "conversas", meta: 15, curso: null }, raridade: "rara", pontos: 50, activa: true };

export function FormConquista({ inicial }: { inicial?: Conquista }) {
  const router = useRouter();
  const { data: opcoes } = useOpcoesConquistaQuery();
  const [criar, { isLoading: aCriar }] = useCriarConquistaMutation();
  const [mudar, { isLoading: aMudar }] = useMudarConquistaMutation();
  const [remover, { isLoading: aRemover }] = useApagarConquistaMutation();
  const [v, setV] = useState<NovaConquista>(inicial ? { ...inicial, regra: { ...inicial.regra, curso: inicial.regra.curso?.id ?? null } } : vazia);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const [apagar, setApagar] = useState(false);
  const muda = (p: Partial<NovaConquista>) => setV((x) => ({ ...x, ...p }));
  const regra = (p: Partial<NovaConquista["regra"]>) => setV((x) => ({ ...x, regra: { ...x.regra, ...p } }));
  const tipo = opcoes?.tipos.find((t) => t.valor === v.regra.tipo);
  // Sem símbolo escolhido, usa a meta (só cabe até 3 caracteres: 1000 ou mais leva uma estrela).
  const icone = v.icone.trim() || (String(v.regra.meta).length <= 3 ? String(v.regra.meta) : "★");

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setGeral(null);
    const er: Record<string, string> = {};
    if (v.nome.trim().length < 3) er.nome = "Escreva o nome da conquista.";
    if (!v.descricao.trim()) er.descricao = "Diga ao aluno o que fez para a ganhar.";
    if (!Number.isInteger(v.regra.meta) || v.regra.meta < 1) er.meta = "Escreva um número inteiro a partir de 1.";
    setErros(er);
    if (Object.keys(er).length) return;
    const corpo = { ...v, nome: v.nome.trim(), descricao: v.descricao.trim(), icone };
    try {
      if (inicial) await mudar({ id: inicial.id, ...corpo }).unwrap();
      else await criar(corpo).unwrap();
      router.push("/teacher/achievements");
    } catch (x) {
      setErros(Object.fromEntries(Object.entries(errosPorCampo(x)).map(([k, m]) => [k.replace("regra.", ""), m])));
      setGeral(mensagemErro(x, "Não foi possível guardar. Tente outra vez."));
    }
  }

  return (
    <>
      <div className="flex flex-col gap-2">
        <Link href="/teacher/achievements" className="inline-flex min-h-11 items-center gap-1 self-start text-[15px] font-semibold text-pe-azul-vivo no-underline">
          <ChevronLeft aria-hidden className="size-[18px]" />
          Conquistas
        </Link>
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 tracking-[-0.015em] md:text-[32px] md:leading-[38px]">{inicial ? inicial.nome : "Nova conquista"}</h1>
      </div>

      <div className="flex flex-col gap-8 lg:flex-row-reverse lg:items-start">
        <aside aria-label="Assim aparece ao aluno" className="flex w-full flex-col items-center gap-3 rounded-pe-md bg-pe-fundo-suave p-6 text-center lg:sticky lg:top-6 lg:w-[320px]">
          <Medalha icone={icone} raridade={v.raridade} grande />
          <span className="font-pe-titulo text-[20px] font-bold leading-7">{v.nome.trim() || "Nome da conquista"}</span>
          <span className="text-[15px] leading-[22px] text-pe-tinta-suave">{v.descricao.trim() || "O que o aluno fez para a ganhar."}</span>
          <span className="flex gap-2">
            <Etiqueta>{RARIDADE[v.raridade]}</Etiqueta>
            <Etiqueta tipo="realce">+{v.pontos} pontos</Etiqueta>
          </span>
          <span className="text-pe-legenda text-pe-tinta-suave">Assim aparece ao aluno</span>
        </aside>

        <form noValidate onSubmit={guardar} className="flex min-w-0 max-w-[640px] flex-1 flex-col gap-5">
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_140px]">
            <Campo rotulo="Nome" value={v.nome} maxLength={40} onChange={(e) => muda({ nome: e.target.value })} erro={erros.nome} placeholder="Quinze conversas" />
            <Campo rotulo="Símbolo" value={v.icone} maxLength={3} onChange={(e) => muda({ icone: e.target.value })} erro={erros.icone} ajuda="Até 3 caracteres." placeholder={String(v.regra.meta)} />
          </div>
          <Campo rotulo="Descrição para o aluno" value={v.descricao} maxLength={120} onChange={(e) => muda({ descricao: e.target.value })} erro={erros.descricao} placeholder="Fez 15 conversas com o tutor." />
          <div className="grid gap-4 sm:grid-cols-2">
            <Escolha rotulo="Ganha-se ao" value={v.regra.tipo} onChange={(e) => regra({ tipo: e.target.value })} erro={erros.tipo}>
              {(opcoes?.tipos ?? [{ valor: v.regra.tipo, nome: v.regra.tipo, unidade: "" }]).map((t) => (
                <option key={t.valor} value={t.valor}>
                  {t.nome}
                </option>
              ))}
            </Escolha>
            <Campo
              rotulo="Meta"
              type="number"
              min={1}
              max={10000}
              value={v.regra.meta}
              onChange={(e) => regra({ meta: Number(e.target.value) })}
              erro={erros.meta}
              ajuda={tipo?.unidade ? `Em ${tipo.unidade}.` : undefined}
            />
          </div>
          <Escolha rotulo="Contar em" value={v.regra.curso ?? ""} onChange={(e) => regra({ curso: e.target.value || null })} erro={erros.curso}>
            <option value="">Todos os meus cursos</option>
            {opcoes?.cursos.map((c) => (
              <option key={c.id} value={c.id}>
                {c.titulo}
              </option>
            ))}
          </Escolha>
          <div className="grid gap-4 sm:grid-cols-2">
            <Escolha rotulo="Raridade" value={v.raridade} onChange={(e) => muda({ raridade: e.target.value as Raridade })}>
              {(Object.keys(RARIDADE) as Raridade[]).map((r) => (
                <option key={r} value={r}>
                  {RARIDADE[r]}
                </option>
              ))}
            </Escolha>
            <Campo rotulo="Pontos que dá" type="number" min={5} max={500} step={5} value={v.pontos} onChange={(e) => muda({ pontos: Number(e.target.value) })} erro={erros.pontos} ajuda="Entre 5 e 500." />
          </div>
          {geral ? <Aviso tipo="errado">{geral}</Aviso> : null}
          <div className="flex flex-wrap items-center gap-3 border-t border-pe-linha pt-5">
            <Botao type="submit" tamanho="medio" disabled={aCriar || aMudar}>
              {aCriar || aMudar ? "A guardar…" : inicial ? "Guardar alterações" : "Criar conquista"}
            </Botao>
            <Botao asChild tipo="secundario" tamanho="medio">
              <Link href="/teacher/achievements">Cancelar</Link>
            </Botao>
            {inicial ? (
              <Botao tipo="ligacao" tamanho="medio" className="ml-auto text-pe-errado hover:text-pe-errado" onClick={() => setApagar(true)}>
                Apagar conquista
              </Botao>
            ) : null}
          </div>
        </form>
      </div>

      {inicial ? (
        <Dialogo aberto={apagar} aoMudar={setApagar} titulo={`Apagar "${inicial.nome}"?`} descricao={inicial.alunos_que_tem ? `${inicial.alunos_que_tem} alunos já a têm. Em vez de apagar, desligue-a: eles mantêm a medalha e mais ninguém a ganha.` : "Ninguém a ganhou ainda."}>
          {geral ? <Aviso tipo="errado">{geral}</Aviso> : null}
          <div className="flex flex-wrap justify-end gap-3">
            <Botao tipo="secundario" tamanho="medio" onClick={() => setApagar(false)}>
              Cancelar
            </Botao>
            {inicial.alunos_que_tem ? (
              <Botao
                tamanho="medio"
                onClick={async () => {
                  setGeral(null);
                  try {
                    await mudar({ id: inicial.id, activa: false }).unwrap();
                    router.push("/teacher/achievements");
                  } catch (x) {
                    setGeral(mensagemErro(x, "Não foi possível desligar."));
                  }
                }}
              >
                Desligar
              </Botao>
            ) : (
              <Botao
                tipo="perigo"
                tamanho="medio"
                disabled={aRemover}
                onClick={async () => {
                  setGeral(null);
                  try {
                    await remover(inicial.id).unwrap();
                    router.push("/teacher/achievements");
                  } catch (x) {
                    setGeral(mensagemErro(x, "Não foi possível apagar."));
                  }
                }}
              >
                Apagar conquista
              </Botao>
            )}
          </div>
        </Dialogo>
      ) : null}
    </>
  );
}
