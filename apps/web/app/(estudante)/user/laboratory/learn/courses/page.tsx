"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, BookOpen } from "lucide-react";
import { Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { cnPe } from "@/lib/pe";
import { categoriaPt, nivelPt } from "@/src/domains/student/inicio/api";
import { idCursoActivo, useCursosPraticaQuery, useEscolherCursoMutation, useProgressoPraticaQuery } from "@/src/domains/student/laboratorio/api";

export default function EscolherCurso() {
  const router = useRouter();
  const { data: cursos, isLoading, isError, refetch } = useCursosPraticaQuery();
  const { data: progresso } = useProgressoPraticaQuery();
  const [escolher] = useEscolherCursoMutation();
  const [aEscolher, setAEscolher] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const actual = idCursoActivo(progresso?.active_course);

  const aoEscolher = async (id: string) => {
    if (id === actual) {
      router.push("/user/laboratory/learn");
      return;
    }
    setErro(null);
    setAEscolher(id);
    const r = await escolher(id);
    setAEscolher(null);
    if ("error" in r && r.error) {
      setErro("Não foi possível mudar de curso. Tente outra vez.");
      return;
    }
    router.push("/user/laboratory/learn");
  };

  return (
    <Pagina className="max-w-[880px]">
      <div className="flex flex-col gap-2">
        {actual ? (
          <Link href="/user/laboratory/learn" className="inline-flex min-h-11 items-center gap-1.5 self-start text-[15px] font-semibold underline-offset-[3px]">
            <ArrowLeft aria-hidden className="size-5" /> Laboratório de prática
          </Link>
        ) : null}
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Escolher curso</h1>
        <p className="m-0 text-pe-tinta-suave">
          {actual ? "Pode mudar de curso quando quiser. O progresso de cada um fica guardado." : "Escolha o curso em que quer praticar. Pode mudar quando quiser."}
        </p>
      </div>

      {erro ? (
        <p role="alert" className="m-0 rounded-pe-md bg-pe-errado-suave px-4 py-3">
          {erro}
        </p>
      ) : null}

      {isLoading ? (
        <div aria-busy="true" aria-label="A carregar cursos" className="grid gap-3 md:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <Osso key={i} className="h-[84px] rounded-pe-md" />
          ))}
        </div>
      ) : isError ? (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
          <p className="m-0">Não conseguimos carregar os cursos.</p>
          <Botao tamanho="pequeno" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : !cursos?.length ? (
        <div className="flex flex-col items-start gap-2 rounded-pe-md bg-pe-fundo-suave p-6">
          <h2 className="m-0 text-pe-titulo-s">Ainda não há cursos de prática</h2>
          <p className="m-0 text-pe-tinta-suave">Quando os professores publicarem cursos, aparecem aqui.</p>
        </div>
      ) : (
        <ul className="m-0 grid list-none gap-3 p-0 md:grid-cols-2">
          {cursos.map((c) => {
            const eActual = c.id === actual;
            const contexto = [c.category ? categoriaPt(c.category) : null, c.level ? nivelPt(c.level) : null].filter(Boolean).join(", ");
            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => void aoEscolher(c.id)}
                  disabled={!!aEscolher}
                  aria-current={eActual ? "true" : undefined}
                  className={cnPe(
                    "flex min-h-[84px] w-full items-center gap-3.5 rounded-pe-md px-3.5 py-3 text-left text-pe-tinta disabled:cursor-wait",
                    eActual ? "border-2 border-pe-azul-marca bg-pe-fundo-suave" : "border border-pe-linha bg-pe-fundo hover:border-pe-azul-marca"
                  )}
                >
                  <span
                    aria-hidden
                    className={cnPe("flex size-12 shrink-0 items-center justify-center rounded-pe-fala-s", eActual ? "bg-pe-azul-marca text-pe-sobre-marca" : "bg-pe-fundo-forte")}
                  >
                    <BookOpen className="size-6" />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="font-semibold leading-[22px]">{c.title}</span>
                    {contexto ? <span className="text-pe-legenda text-pe-tinta-suave">{contexto}</span> : null}
                  </span>
                  <span
                    className={cnPe(
                      "shrink-0 text-pe-legenda font-semibold",
                      eActual ? "rounded-pe-sm bg-pe-realce px-2.5 py-0.5" : "text-pe-azul-vivo"
                    )}
                  >
                    {aEscolher === c.id ? "A abrir…" : eActual ? "Actual" : "Escolher"}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Pagina>
  );
}
