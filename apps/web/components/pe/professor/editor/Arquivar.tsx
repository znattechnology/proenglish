"use client";

import { useState } from "react";
import { Aviso, Botao } from "@/components/pe";
import { Dialogo } from "@/components/pe/Dialogo";
import { cnPe } from "@/lib/pe";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { useArquivarMutation, type DetalheCurso } from "@/src/domains/teacher/professor/api";

/** Arquivar: o curso sai do catálogo. O professor escolhe se os inscritos podem terminar. */
export function DialogoArquivar({ curso, aberto, aoMudar }: { curso: DetalheCurso; aberto: boolean; aoMudar: (v: boolean) => void }) {
  const [modo, setModo] = useState<"manter" | "fechar">("manter");
  const [erro, setErro] = useState<string | null>(null);
  const [arquivar, { isLoading }] = useArquivarMutation();
  const n = curso.alunos;
  return (
    <Dialogo
      aberto={aberto}
      aoMudar={aoMudar}
      titulo={`Arquivar "${curso.titulo}"?`}
      descricao={
        <>
          O curso sai do catálogo e deixa de aceitar inscrições.
          {n ? ` Tem ${n.toLocaleString("pt-PT")} ${n === 1 ? "aluno inscrito" : "alunos inscritos"}.` : " Ainda não tem alunos inscritos."}
        </>
      }
      largura={560}
    >
      {n ? (
        <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
          <legend className="mb-2 p-0 font-semibold">E os alunos inscritos?</legend>
          {(
            [
              { v: "manter", nome: "Podem terminar o curso", texto: "Recomendado. Mantêm o progresso e o certificado." },
              { v: "fechar", nome: "Fechar para todos", texto: "Os alunos deixam de ver as aulas. Os certificados já emitidos continuam válidos." },
            ] as const
          ).map((o) => (
            <label
              key={o.v}
              className={cnPe(
                "flex cursor-pointer items-start gap-3 rounded-pe-md p-4",
                modo === o.v ? "border-2 border-pe-azul-marca bg-pe-fundo-suave" : "border-[1.5px] border-pe-linha hover:bg-pe-fundo-suave"
              )}
            >
              <input type="radio" name="modo-arquivo" checked={modo === o.v} onChange={() => setModo(o.v)} className="mt-1 size-5 shrink-0 accent-pe-azul-marca" />
              <span className="flex flex-col">
                <span className="font-semibold">{o.nome}</span>
                <span className="text-[15px] leading-[22px] text-pe-tinta-suave">{o.texto}</span>
              </span>
            </label>
          ))}
        </fieldset>
      ) : null}
      <p className="m-0 text-pe-tinta-suave">Pode voltar a publicar o curso quando quiser; volta a passar pela revisão.</p>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <div className="flex flex-wrap justify-end gap-3">
        <Botao tipo="secundario" tamanho="medio" onClick={() => aoMudar(false)}>
          Cancelar
        </Botao>
        <Botao
          tipo="perigo"
          tamanho="medio"
          disabled={isLoading}
          onClick={async () => {
            setErro(null);
            try {
              await arquivar({ id: curso.id, modo }).unwrap();
              aoMudar(false);
            } catch (e) {
              setErro(mensagemErro(e, "Não foi possível arquivar o curso."));
            }
          }}
        >
          Arquivar curso
        </Botao>
      </div>
    </Dialogo>
  );
}
