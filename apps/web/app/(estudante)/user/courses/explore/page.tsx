"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { categoriaPt, useCatalogoCursosQuery, useMeusCursosQuery } from "@/src/domains/student/inicio/api";
import { Botao, Separadores } from "@/components/pe";
import { Pilulas } from "@/components/pe/Interativos";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { EsqueletoLista, LinhaCursoCatalogo, ListaCursos, SEPARADORES_CURSOS } from "@/components/pe/estudante/Cursos";

const TODAS = "Todas";

/** Sem acentos nem maiúsculas, para a procura encontrar "inglês" escrito "ingles". */
function normal(t: string) {
  return t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export default function ExplorarCursos() {
  const { user } = useDjangoAuth();
  const { data, isLoading, isError, refetch } = useCatalogoCursosQuery();
  const { data: meus } = useMeusCursosQuery(user?.id ?? "", { skip: !user });
  const [procura, setProcura] = useState("");
  const [area, setArea] = useState(TODAS);

  const inscritos = useMemo(() => new Set((meus ?? []).map((c) => c.courseId)), [meus]);
  const areas = useMemo(() => {
    const unicas = Array.from(new Set((data?.cursos ?? []).map((c) => categoriaPt(c.category)).filter(Boolean) as string[]));
    return [TODAS, ...unicas.sort((a, b) => a.localeCompare(b, "pt"))];
  }, [data]);

  const visiveis = useMemo(() => {
    const q = normal(procura.trim());
    return (data?.cursos ?? []).filter((c) => {
      if (area !== TODAS && categoriaPt(c.category) !== area) return false;
      if (!q) return true;
      return normal(`${c.title} ${c.description ?? ""} ${categoriaPt(c.category) ?? ""}`).includes(q);
    });
  }, [data, procura, area]);

  return (
    <Pagina>
      <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Cursos</h1>
      <Separadores rotulo="Cursos" activo="Explorar" itens={SEPARADORES_CURSOS} />

      <div className="flex flex-col gap-3">
        <label className="flex h-12 items-center gap-2 rounded-pe-sm border-[1.5px] border-pe-linha-forte px-3 focus-within:outline focus-within:outline-[3px] focus-within:outline-offset-2 focus-within:outline-pe-azul-vivo md:max-w-[480px]">
          <Search aria-hidden className="size-[18px] shrink-0 text-pe-tinta-suave" />
          <span className="sr-only">Procurar um curso</span>
          <input
            type="search"
            value={procura}
            onChange={(e) => setProcura(e.target.value)}
            placeholder="Procurar: reuniões, emails, atendimento"
            className="h-full flex-1 border-0 bg-transparent text-[16px] text-pe-tinta outline-none placeholder:text-pe-tinta-suave"
          />
        </label>
        {areas.length > 2 ? <Pilulas rotulo="Área profissional" opcoes={areas} valor={area} aoMudar={setArea} /> : null}
      </div>

      {isLoading ? (
        <EsqueletoLista linhas={4} />
      ) : isError ? (
        <div role="alert" className="flex flex-col gap-3 rounded-pe-md bg-pe-errado-suave px-4 py-4">
          <p className="m-0">
            <span className="font-semibold">Não conseguimos carregar os cursos.</span> O problema é do nosso lado.
          </p>
          <Botao tipo="secundario" tamanho="pequeno" className="self-start" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : visiveis.length === 0 ? (
        <div className="flex flex-col items-start gap-3">
          <p className="m-0">
            {procura.trim()
              ? `Nenhum curso com "${procura.trim()}"${area !== TODAS ? ` em ${area}` : ""}.`
              : `Ainda não há cursos em ${area}.`}
          </p>
          <Botao
            tipo="secundario"
            tamanho="pequeno"
            onClick={() => {
              setProcura("");
              setArea(TODAS);
            }}
          >
            Ver todos os cursos
          </Botao>
        </div>
      ) : (
        <>
          <p className="m-0 text-pe-legenda text-pe-tinta-suave" aria-live="polite">
            {visiveis.length} {visiveis.length === 1 ? "curso" : "cursos"}
          </p>
          <ListaCursos className="md:grid md:grid-cols-2 md:gap-x-8 xl:grid-cols-3">
            {visiveis.map((c) => (
              <LinhaCursoCatalogo key={c.courseId} curso={c} inscrito={inscritos.has(c.courseId)} />
            ))}
          </ListaCursos>
        </>
      )}
    </Pagina>
  );
}
