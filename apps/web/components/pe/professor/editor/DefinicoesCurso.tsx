"use client";

import { useState } from "react";
import { AreaTexto, Aviso, Botao, Campo, Escolha, Interruptor } from "@/components/pe";
import { DESCRICAO_NIVEL, OPCOES_NIVEL, normalizarNivel } from "@/src/domains/shared/niveis";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { useMudarCursoMutation, useOpcoesQuery, type DefinicoesCurso, type DetalheCurso } from "@/src/domains/teacher/professor/api";
import { DialogoArquivar } from "./Arquivar";

const titulo2 = "m-0 font-pe-titulo text-[20px] font-semibold leading-7";

/** Dados e regras de um curso (vídeo ou prática). Guarda tudo com um botão. */
export function FormDefinicoes({ curso }: { curso: DetalheCurso }) {
  const { data: opcoes } = useOpcoesQuery(curso.tipo);
  const [mudar, { isLoading }] = useMudarCursoMutation();
  const [titulo, setTitulo] = useState(curso.titulo);
  const [descricao, setDescricao] = useState(curso.descricao ?? "");
  const [area, setArea] = useState(curso.categoria);
  const [nivel, setNivel] = useState(normalizarNivel(curso.nivel_codigo) ?? "A2");
  const [acesso, setAcesso] = useState(curso.acesso);
  const [d, setD] = useState<DefinicoesCurso>(curso.definicoes);
  const [maximo, setMaximo] = useState(curso.definicoes.maximo_alunos?.toString() ?? "");
  const [erros, setErros] = useState<Record<string, string>>({});
  const [estado, setEstado] = useState<{ tipo: "certo" | "errado"; texto: string } | null>(null);
  const [arquivar, setArquivar] = useState(false);
  const pratica = curso.tipo === "pratica";
  const muda = (p: Partial<DefinicoesCurso>) => setD((v) => ({ ...v, ...p }));

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setEstado(null);
    const er: Record<string, string> = {};
    if (!titulo.trim()) er.titulo = "Escreva o título do curso.";
    else if (titulo.trim().length > 60) er.titulo = "O título tem mais de 60 caracteres.";
    if (d.nota_minima < 50 || d.nota_minima > 100) er.nota = "Escolha um valor entre 50 e 100.";
    const max = maximo.trim() ? Number(maximo) : null;
    if (max != null && (!Number.isInteger(max) || max < 1)) er.maximo = "Escreva um número inteiro, ou deixe vazio para não ter limite.";
    setErros(er);
    if (Object.keys(er).length) return;
    try {
      await mudar({ id: curso.id, titulo: titulo.trim(), descricao: descricao.trim(), area, nivel, ...(acesso && acesso !== curso.acesso ? { acesso } : {}), definicoes: { ...d, maximo_alunos: max } }).unwrap();
      setEstado({ tipo: "certo", texto: "Alterações guardadas." });
    } catch (x) {
      setEstado({ tipo: "errado", texto: mensagemErro(x, "Não foi possível guardar. Tente outra vez.") });
    }
  }

  return (
    <form noValidate onSubmit={guardar} className="flex max-w-[760px] flex-col gap-8">
      <section className="flex flex-col gap-4" aria-labelledby="t-dados">
        <h2 id="t-dados" className={titulo2}>
          Dados do curso
        </h2>
        <Campo rotulo="Título" value={titulo} maxLength={80} onChange={(e) => setTitulo(e.target.value)} erro={erros.titulo} ajuda={`${titulo.trim().length} de 60 caracteres.`} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Escolha rotulo="Área" value={area} onChange={(e) => setArea(e.target.value)} disabled={!opcoes}>
            {(opcoes?.areas.filter((a) => !a.legado || a.valor === curso.categoria) ?? [{ valor: curso.categoria, nome: curso.area ?? curso.categoria }]).map((a) => (
              <option key={a.valor} value={a.valor}>
                {a.nome}
              </option>
            ))}
          </Escolha>
          <Escolha rotulo="Nível" value={nivel} onChange={(e) => setNivel(normalizarNivel(e.target.value) ?? nivel)} ajuda={DESCRICAO_NIVEL[nivel]}>
            {OPCOES_NIVEL.map((n) => (
              <option key={n.valor} value={n.valor}>
                {n.nome}
              </option>
            ))}
          </Escolha>
        </div>
        <AreaTexto rotulo="Descrição curta" rows={3} maxLength={300} value={descricao} onChange={(e) => setDescricao(e.target.value)} />
      </section>

      <section className="flex flex-col gap-1" aria-labelledby="t-acesso">
        <h2 id="t-acesso" className={`${titulo2} mb-2`}>
          Acesso e inscrição
        </h2>
        <Interruptor rotulo="Aparece no catálogo" descricao="Os alunos encontram o curso em Explorar. Desligado, só entra quem já está inscrito." ligado={d.visivel_catalogo} aoMudar={(v) => muda({ visivel_catalogo: v })} />
        <Interruptor rotulo="Inscrição livre" descricao="O aluno entra sem precisar de aprovação. Desligado, o curso não aceita alunos novos." ligado={d.inscricao_livre} aoMudar={(v) => muda({ inscricao_livre: v })} />
        {acesso ? (
        <Escolha
          className="mb-3 max-w-[420px]"
          rotulo="Quem pode fazer o curso"
          value={acesso}
          onChange={(e) => setAcesso(e.target.value as "todos" | "premium")}
          ajuda="Os alunos dos outros planos vêem o curso no catálogo, mas não o podem abrir."
        >
          <option value="premium">Planos Premium e Premium Plus</option>
          <option value="todos">Todos os alunos, incluindo o Gratuito</option>
        </Escolha>
        ) : null}
        {pratica ? (
          <Interruptor rotulo="Pode repetir lições" descricao="Ao repetir uma lição já feita ganha pontos e recupera vidas." ligado={d.pode_repetir} aoMudar={(v) => muda({ pode_repetir: v })} />
        ) : null}
        <Campo
          className="mt-3 max-w-[240px]"
          rotulo="Máximo de alunos"
          inputMode="numeric"
          value={maximo}
          onChange={(e) => setMaximo(e.target.value.replace(/\D/g, ""))}
          erro={erros.maximo}
          ajuda="Deixe vazio para não ter limite."
        />
      </section>

      <section className="flex flex-col gap-4" aria-labelledby="t-avaliacao">
        <h2 id="t-avaliacao" className={titulo2}>
          Avaliação e certificado
        </h2>
        <Campo
          className="max-w-[240px]"
          rotulo="Nota mínima para o certificado"
          type="number"
          min={50}
          max={100}
          step={5}
          value={d.nota_minima}
          onChange={(e) => muda({ nota_minima: Number(e.target.value) })}
          erro={erros.nota}
          ajuda="Em percentagem, entre 50 e 100."
        />
        <Interruptor
          rotulo="Certificado automático"
          descricao="Emitido quando o aluno chega à nota mínima. Desligado, o aluno pede-o na página do curso."
          ligado={d.certificado_automatico}
          aoMudar={(v) => muda({ certificado_automatico: v })}
        />
      </section>

      {estado ? <Aviso tipo={estado.tipo}>{estado.texto}</Aviso> : null}
      <Botao type="submit" tamanho="medio" className="self-start" disabled={isLoading}>
        {isLoading ? "A guardar…" : "Guardar alterações"}
      </Botao>

      {curso.estado === "publicado" ? (
        <section className="flex flex-col items-start gap-2 border-t border-pe-linha pt-6" aria-labelledby="t-arquivar">
          <h2 id="t-arquivar" className={titulo2}>
            Arquivar o curso
          </h2>
          <p className="m-0 text-pe-tinta-suave">Deixa de aceitar alunos novos. Quem já está inscrito pode continuar, se assim escolher.</p>
          <Botao tipo="perigo" tamanho="pequeno" onClick={() => setArquivar(true)}>
            Arquivar curso
          </Botao>
          <DialogoArquivar curso={curso} aberto={arquivar} aoMudar={setArquivar} />
        </section>
      ) : null}
    </form>
  );
}
