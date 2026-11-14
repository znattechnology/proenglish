"use client";

import { useProfessorPublicoQuery } from "@/src/domains/student/curso/api";

/** O professor do curso, como ele próprio se apresenta. Sem perfil preenchido, não aparece. */
export function SobreProfessor({ id }: { id?: string }) {
  const { data: p } = useProfessorPublicoQuery(id ?? "", { skip: !id });
  if (!p || (!p.sobre && !p.especialidade)) return null;
  const linha = [p.especialidade, p.cidade].filter(Boolean).join(", ");
  return (
    <section aria-labelledby="t-professor" className="flex flex-col gap-3">
      <h2 id="t-professor" className="m-0 font-pe-titulo text-pe-titulo-s">
        Quem ensina
      </h2>
      <div className="flex items-start gap-4">
        {p.fotografia ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={p.fotografia} alt="" className="size-16 shrink-0 rounded-pe-fala object-cover" />
        ) : (
          <span aria-hidden className="flex size-16 shrink-0 items-center justify-center rounded-pe-fala bg-pe-azul-marca font-pe-titulo text-[22px] font-bold text-pe-sobre-marca">
            {p.iniciais}
          </span>
        )}
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex flex-col">
            <span className="font-semibold">Prof. {p.nome}</span>
            {linha ? <span className="text-pe-legenda text-pe-tinta-suave">{linha}</span> : null}
          </div>
          {p.experiencia ? <p className="m-0 text-[15px] leading-[22px]">{p.experiencia}</p> : null}
          {p.sobre ? <p className="m-0 max-w-[68ch] whitespace-pre-line text-[15px] leading-[22px] text-pe-tinta-suave">{p.sobre}</p> : null}
          <span className="text-pe-legenda text-pe-tinta-suave">
            {p.cursos_publicados} {p.cursos_publicados === 1 ? "curso" : "cursos"} na ProEnglish{p.desde ? `, desde ${p.desde}` : ""}.
          </span>
        </div>
      </div>
    </section>
  );
}
