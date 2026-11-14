"use client";

import { useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Aviso, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaSeccao, SEPARADORES_OPINIOES } from "@/components/pe/admin/Comum";
import { mensagemErro } from "@/src/domains/student/subscricao/api";
import { useMudarTestemunhoMutation, useOrdenarTestemunhosMutation, useTestemunhosQuery } from "@/src/domains/admin/administracao/negocio";

const botaoIcone = "flex size-10 items-center justify-center rounded-pe-sm text-pe-tinta-suave hover:bg-pe-fundo-forte hover:text-pe-tinta disabled:opacity-40";

export default function Testemunhos() {
  const { data, isError, refetch } = useTestemunhosQuery();
  const [mudar] = useMudarTestemunhoMutation();
  const [ordenar] = useOrdenarTestemunhosMutation();
  const [erro, setErro] = useState<string | null>(null);
  const lista = data ?? [];
  const visiveis = lista.filter((t) => t.mostrar);
  const mover = (i: number, d: -1 | 1) => {
    const ids = lista.map((t) => t.id);
    [ids[i], ids[i + d]] = [ids[i + d], ids[i]];
    setErro(null);
    ordenar(ids)
      .unwrap()
      .catch((x) => setErro(mensagemErro(x, "Não foi possível mudar a ordem.")));
  };

  return (
    <Pagina className="gap-7">
      <CabecaSeccao titulo="Opiniões e testemunhos" texto="Opiniões aprovadas que o aluno autorizou mostrar. Aparecem as 3 primeiras visíveis na página inicial." activo="Testemunhos no site" itens={SEPARADORES_OPINIOES} />
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      {isError ? (
        <Aviso tipo="errado">
          Não conseguimos carregar os testemunhos.{" "}
          <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
            Tentar outra vez
          </button>
        </Aviso>
      ) : !data ? (
        <Osso className="h-64 rounded-pe-md" />
      ) : !lista.length ? (
        <p className="m-0 rounded-pe-md bg-pe-fundo-suave p-5">Ainda não há testemunhos. Aprove opiniões com comentário de alunos que aceitaram aparecer no site.</p>
      ) : (
        <div className="grid gap-8 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] xl:items-start">
          <ol className="m-0 flex list-none flex-col p-0">
            {lista.map((t, i) => (
              <li key={t.id} className="flex items-center gap-3 border-b border-pe-fundo-forte py-3">
                <span className="flex flex-col">
                  <button type="button" className={botaoIcone} disabled={i === 0} onClick={() => mover(i, -1)} aria-label={`Subir o testemunho de ${t.nome_curto}`}>
                    <ArrowUp aria-hidden className="size-4" />
                  </button>
                  <button type="button" className={botaoIcone} disabled={i === lista.length - 1} onClick={() => mover(i, 1)} aria-label={`Descer o testemunho de ${t.nome_curto}`}>
                    <ArrowDown aria-hidden className="size-4" />
                  </button>
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="font-semibold">
                    {t.nome_curto}
                    {t.area ? <span className="font-normal text-pe-tinta-suave">, {t.area}</span> : null}
                  </span>
                  <span className="text-[15px]">“{t.texto}”</span>
                  <span className="text-pe-legenda text-pe-tinta-suave">{t.nota} de 5</span>
                </span>
                <label className="flex min-h-11 shrink-0 cursor-pointer items-center gap-2 text-[15px]">
                  <input
                    type="checkbox"
                    checked={t.mostrar}
                    onChange={(e) => {
                      setErro(null);
                      mudar({ id: t.id, mostrar: e.target.checked })
                        .unwrap()
                        .catch((x) => setErro(mensagemErro(x, "Não foi possível mudar.")));
                    }}
                    className="size-5 accent-pe-azul-marca"
                  />
                  Mostrar
                </label>
              </li>
            ))}
          </ol>
          <aside aria-label="Assim aparece na página inicial" className="flex flex-col gap-3 rounded-pe-md bg-pe-fundo-suave p-5">
            <span className="text-pe-legenda font-semibold text-pe-tinta-suave">Assim aparece na página inicial</span>
            {visiveis.slice(0, 3).map((t) => (
              <figure key={t.id} className="m-0 flex flex-col gap-1 rounded-pe-md bg-pe-fundo p-4">
                <blockquote className="m-0">“{t.texto}”</blockquote>
                <figcaption className="text-pe-legenda text-pe-tinta-suave">
                  {t.nome_curto}
                  {t.area ? `, ${t.area}` : ""}
                </figcaption>
              </figure>
            ))}
            {!visiveis.length ? <p className="m-0 text-[15px]">Nenhum testemunho visível.</p> : null}
            <p className="m-0 text-pe-legenda text-pe-tinta-suave">Só o primeiro nome, a inicial do apelido e a área, como a pessoa autorizou.</p>
          </aside>
        </div>
      )}
    </Pagina>
  );
}
