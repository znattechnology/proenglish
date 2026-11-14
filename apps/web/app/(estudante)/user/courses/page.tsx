"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { BookOpen } from "lucide-react";
import { useDjangoAuth } from "@/hooks/useDjangoAuth";
import { useCatalogoCursosQuery, useMeusCursosQuery } from "@/src/domains/student/inicio/api";
import { Botao, MarcaIcone, Separadores } from "@/components/pe";
import { Pilulas } from "@/components/pe/Interativos";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { EsqueletoLista, LinhaCursoCatalogo, LinhaCursoInscrito, ListaCursos, SEPARADORES_CURSOS } from "@/components/pe/estudante/Cursos";

const ESTADOS = ["Em progresso", "Concluídos"] as const;
type Estado = (typeof ESTADOS)[number];

export default function OsMeusCursos() {
  const { user } = useDjangoAuth();
  const userId = user?.id ?? "";
  const { data: cursos, isLoading, isError, refetch } = useMeusCursosQuery(userId, { skip: !userId });
  const [estado, setEstado] = useState<Estado>("Em progresso");
  const [progressos, setProgressos] = useState<Record<string, number>>({});

  const aoSaberProgresso = useCallback((id: string, pct: number) => {
    setProgressos((p) => (p[id] === pct ? p : { ...p, [id]: pct }));
  }, []);

  const contagem = useMemo(() => {
    const valores = (cursos ?? []).map((c) => progressos[c.courseId]).filter((v) => v !== undefined);
    const concluidos = valores.filter((v) => v === 100).length;
    return { concluidos, emProgresso: (cursos?.length ?? 0) - concluidos };
  }, [cursos, progressos]);

  const rotulos = { "Em progresso": `Em progresso (${contagem.emProgresso})`, Concluídos: `Concluídos (${contagem.concluidos})` } as const;

  return (
    <Pagina>
      <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Cursos</h1>
      <Separadores rotulo="Cursos" activo="Os meus" itens={SEPARADORES_CURSOS} />

      {isLoading ? (
        <EsqueletoLista />
      ) : isError ? (
        <div role="alert" className="flex flex-col gap-3 rounded-pe-md bg-pe-errado-suave px-4 py-4">
          <p className="m-0">
            <span className="font-semibold">Não conseguimos carregar os seus cursos.</span> O problema é do nosso lado; o seu progresso está guardado.
          </p>
          <Botao tipo="secundario" tamanho="pequeno" className="self-start" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : !cursos || cursos.length === 0 ? (
        <SemCursos />
      ) : (
        <>
          <Pilulas
            rotulo="Mostrar cursos"
            opcoes={ESTADOS.map((e) => rotulos[e])}
            valor={rotulos[estado]}
            aoMudar={(v) => setEstado(v.startsWith("Conclu") ? "Concluídos" : "Em progresso")}
          />
          <ListaCursos className="lg:grid lg:grid-cols-2 lg:gap-x-10">
            {cursos.map((c) => {
              const pct = progressos[c.courseId];
              const concluido = pct === 100;
              const escondido = pct !== undefined && (estado === "Concluídos" ? !concluido : concluido);
              return <LinhaCursoInscrito key={c.courseId} curso={c} userId={userId} aoSaberProgresso={aoSaberProgresso} escondido={escondido} />;
            })}
          </ListaCursos>
          {estado === "Concluídos" && contagem.concluidos === 0 ? (
            <p className="m-0 text-pe-tinta-suave">Ainda não concluiu nenhum curso. Quando terminar um, o certificado aparece em Certificados.</p>
          ) : null}
        </>
      )}
    </Pagina>
  );
}

/** Estado vazio: convida a escolher o primeiro curso e sugere dois. */
function SemCursos() {
  const { data } = useCatalogoCursosQuery();
  const sugestoes = data?.cursos.slice(0, 2) ?? [];
  return (
    <div className="flex flex-col gap-8 md:flex-row md:items-start md:gap-12">
      <div className="flex max-w-[480px] flex-col items-start gap-4">
        <MarcaIcone tamanho={80}>
          <BookOpen />
        </MarcaIcone>
        <div className="flex flex-col gap-2">
          <h2 className="m-0 text-[24px] font-bold leading-[30px]">Ainda não começou nenhum curso</h2>
          <p className="m-0 text-pe-tinta-suave">Escolha um curso da sua área. A primeira aula leva cerca de 8 minutos.</p>
        </div>
        <Botao asChild className="self-stretch md:self-start">
          <Link href="/user/courses/explore">Explorar cursos</Link>
        </Botao>
      </div>
      {sugestoes.length > 0 ? (
        <section aria-labelledby="titulo-sugeridos" className="flex flex-1 flex-col gap-1">
          <h2 id="titulo-sugeridos" className="m-0 text-[17px] font-semibold leading-6">
            Para começar
          </h2>
          <ListaCursos>
            {sugestoes.map((c) => (
              <LinhaCursoCatalogo key={c.courseId} curso={c} />
            ))}
          </ListaCursos>
        </section>
      ) : null}
    </div>
  );
}
