"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Aviso, Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { CabecaCurso } from "@/components/pe/professor/editor/CabecaCurso";
import { Estrutura } from "@/components/pe/professor/editor/Estrutura";
import { PainelAula } from "@/components/pe/professor/editor/PainelAula";
import { useEstruturaQuery, useNovaAulaMutation, useNovaSeccaoMutation } from "@/src/domains/teacher/professor/api";
import { erroProfessor } from "@/src/domains/teacher/professor/api";

export default function EditorCursoVideo() {
  return (
    <Pagina className="gap-6">
      <Suspense>
        <Editor />
      </Suspense>
    </Pagina>
  );
}

const hora = (d: Date) => d.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" });

function Editor() {
  const { id } = useParams<{ id: string }>();
  const sp = useSearchParams();
  const router = useRouter();
  const { data, isError, error, refetch } = useEstruturaQuery(id);
  const [novaAula, { isLoading: aCriarAula }] = useNovaAulaMutation();
  const [novaSeccao, { isLoading: aCriarSeccao }] = useNovaSeccaoMutation();
  const [guardadoAs, setGuardadoAs] = useState<Date | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const seccoes = data?.seccoes ?? [];
  const todas = seccoes.flatMap((s) => s.aulas.map((a) => ({ a, s })));
  const pedida = sp.get("aula");
  const actual = todas.find((x) => x.a.id === pedida) ?? todas[0] ?? null;

  const escolher = (aula: string | null) => {
    const q = new URLSearchParams(sp.toString());
    if (aula) q.set("aula", aula);
    else q.delete("aula");
    router.replace(`?${q.toString()}`, { scroll: false });
    if (aula && window.matchMedia("(max-width: 1023px)").matches) {
      requestAnimationFrame(() => document.getElementById("aula")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    }
  };

  // Um curso de prática aberto por engano aqui vai para o editor certo.
  useEffect(() => {
    if (data?.curso.tipo === "pratica") router.replace(`/teacher/practice/${id}`);
  }, [data, id, router]);

  const guardou = () => setGuardadoAs(new Date());

  if (isError && !data)
    return (
      <Aviso tipo="errado">
        {(error as { status?: number })?.status === 404 ? (
          <>
            Este curso não existe ou não é seu. <Link href="/teacher/courses">Ver os seus cursos</Link>
          </>
        ) : (
          <>
            Não conseguimos abrir o curso.{" "}
            <button type="button" onClick={() => refetch()} className="font-semibold underline underline-offset-[3px]">
              Tentar outra vez
            </button>
          </>
        )}
      </Aviso>
    );

  if (!data)
    return (
      <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-6">
        <Osso className="h-[76px] w-3/4 max-w-[560px]" />
        <div className="flex flex-col gap-6 lg:flex-row">
          <Osso className="h-80 rounded-pe-md lg:w-[340px]" />
          <Osso className="h-80 flex-1 rounded-pe-md" />
        </div>
      </div>
    );

  const { curso } = data;

  return (
    <>
      <CabecaCurso curso={curso} separador="Aulas" nota={guardadoAs ? `Alterações guardadas às ${hora(guardadoAs)}.` : null}>
        <Botao asChild tamanho="medio">
          <Link href={`/teacher/courses/${id}/publish`}>{curso.estado === "rascunho" || curso.estado === "arquivado" ? "Rever e enviar" : "Rever o curso"}</Link>
        </Botao>
      </CabecaCurso>

      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}

      <div className="flex flex-col gap-7 lg:flex-row lg:items-start">
        <Estrutura
          curso={id}
          seccoes={seccoes}
          aulaActiva={actual?.a.id ?? null}
          aoEscolher={escolher}
          aCriar={aCriarAula || aCriarSeccao}
          aoGuardar={guardou}
          aoErro={setErro}
          aoNovaSeccao={async () => {
            setErro(null);
            try {
              await novaSeccao({ curso: id, titulo: `Secção ${seccoes.length + 1}` }).unwrap();
              guardou();
            } catch (e) {
              setErro(erroProfessor(e, "Não foi possível criar a secção."));
            }
          }}
          aoNovaAula={async () => {
            setErro(null);
            const alvo = actual?.s ?? seccoes[seccoes.length - 1];
            if (!alvo) return;
            try {
              const a = await novaAula({ seccao: alvo.id, titulo: "Nova aula" }).unwrap();
              guardou();
              escolher(a.id);
            } catch (e) {
              setErro(erroProfessor(e, "Não foi possível criar a aula."));
            }
          }}
        />
        <div id="aula" className="flex min-w-0 flex-1 scroll-mt-20">
          {actual ? (
            <PainelAula key={actual.a.id} cursoId={id} aula={actual.a} seccao={actual.s} seccoes={seccoes} aoGuardar={guardou} aoApagada={() => escolher(null)} />
          ) : (
            <div className="flex flex-1 flex-col items-start gap-2 rounded-pe-md bg-pe-fundo-suave p-6">
              <h2 className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">{seccoes.length ? "Crie a primeira aula" : "Comece por uma secção"}</h2>
              <p className="m-0 text-pe-tinta-suave">
                {seccoes.length
                  ? "Cada aula tem um vídeo, um resumo, materiais para descarregar e, se quiser, um questionário."
                  : "As secções organizam as aulas por momento ou tema, por exemplo “Antes da reunião” e “Durante a reunião”."}
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
