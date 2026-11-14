"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Loader2, Mic } from "lucide-react";
import { Aviso, Botao, Osso } from "@/components/pe";
import { LinhaTentativa, ResultadoExame } from "@/components/pe/curso/Exame";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Viva } from "@/components/pe/licao/ConversaCurta";
import type { ExameOral } from "@/src/domains/shared/exameOral";
import { erroConversa } from "@/src/domains/student/conversa/api";
import { useComecarExameMutation, useCursoQuery, useExameQuery, useLazyResultadoExameQuery, type EstadoExame, type ExameComecado } from "@/src/domains/student/curso/api";

type Fase = { tipo: "inicio" } | { tipo: "viva"; dados: ExameComecado } | { tipo: "a_avaliar" } | { tipo: "resultado"; exame: ExameOral };

const espera = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Exame oral do curso: o que é avaliado, o consentimento para gravar, a conversa com o tutor
 * no papel de examinador (até 10 minutos, sem gastar os minutos do plano) e o resultado.
 */
export default function PaginaExame() {
  const { courseId } = useParams<{ courseId: string }>();
  const { data: curso } = useCursoQuery(courseId);
  const { data: estado, isLoading, isError, refetch } = useExameQuery(courseId);
  const [lerExame] = useLazyResultadoExameQuery();
  const [fase, setFase] = useState<Fase>({ tipo: "inicio" });
  const [erro, setErro] = useState<string | null>(null);

  const mostrar = async (id: string) => {
    setFase({ tipo: "a_avaliar" });
    setErro(null);
    // A avaliação acontece ao terminar; se ainda estiver a correr, tenta mais algumas vezes.
    for (let i = 0; i < 6; i++) {
      try {
        const e = await lerExame(id).unwrap();
        if (e.estado !== "em_curso" && e.estado !== "a_avaliar") {
          setFase({ tipo: "resultado", exame: e });
          void refetch();
          return;
        }
      } catch {
        break;
      }
      await espera(3000);
    }
    setErro("O resultado ainda não está pronto. Volte a abrir esta página daqui a um minuto.");
    setFase({ tipo: "inicio" });
    void refetch();
  };

  return (
    <Pagina className="max-w-[1040px] gap-6">
      <Link href={`/user/courses/${courseId}`} className="inline-flex min-h-11 items-center gap-1.5 self-start text-[15px] font-semibold underline-offset-[3px]">
        <ArrowLeft aria-hidden className="size-5" /> {curso?.curso.title ?? "Voltar ao curso"}
      </Link>

      {fase.tipo === "viva" ? (
        <>
          <div className="flex flex-col gap-1">
            <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8">Exame oral a decorrer</h1>
            <p className="m-0 text-pe-tinta-suave">
              Fale o mais que conseguir. O examinador não corrige durante o exame.
              {fase.dados.gravacao ? " Esta conversa está a ser gravada." : ""}
            </p>
          </div>
          <Viva dados={fase.dados} frases={[]} aoTerminar={() => void mostrar(fase.dados.exame_id)} />
        </>
      ) : fase.tipo === "a_avaliar" ? (
        <div role="status" className="flex flex-col items-start gap-3 py-8">
          <Loader2 aria-hidden className="size-8 text-pe-azul-marca motion-safe:animate-spin" />
          <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8">A avaliar o seu exame…</h1>
          <p className="m-0 text-pe-tinta-suave">Demora até um minuto. Não feche esta página.</p>
        </div>
      ) : fase.tipo === "resultado" ? (
        <>
          <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Resultado do exame oral</h1>
          <ResultadoExame exame={fase.exame} courseId={courseId} aoRepetir={() => setFase({ tipo: "inicio" })} />
          <div className="flex flex-wrap gap-3">
            <Botao asChild tipo="secundario">
              <Link href={`/user/courses/${courseId}/grades`}>Ver as notas do curso</Link>
            </Botao>
            <Botao tipo="ligacao" onClick={() => setFase({ tipo: "inicio" })}>
              Voltar ao exame
            </Botao>
          </div>
        </>
      ) : isError ? (
        <Aviso tipo="errado">Não conseguimos abrir o exame deste curso. Confirme que está inscrito e tente outra vez.</Aviso>
      ) : isLoading || !estado ? (
        <div aria-busy="true" aria-label="A carregar" className="flex flex-col gap-4">
          <Osso className="h-[60px] w-3/4 max-w-[480px]" />
          <Osso className="h-[240px] rounded-pe-md" />
        </div>
      ) : (
        <Introducao estado={estado} courseId={courseId} erro={erro} aoComecar={(d) => setFase({ tipo: "viva", dados: d })} aoAbrir={(id) => void mostrar(id)} />
      )}
    </Pagina>
  );
}

function Introducao({ estado: e, courseId, erro, aoComecar, aoAbrir }: { estado: EstadoExame; courseId: string; erro: string | null; aoComecar: (d: ExameComecado) => void; aoAbrir: (id: string) => void }) {
  const [consentimento, setConsentimento] = useState(false);
  const [comecar, { isLoading }] = useComecarExameMutation();
  const [erroInicio, setErroInicio] = useState<string | null>(null);

  const abrir = async () => {
    setErroInicio(null);
    try {
      aoComecar(await comecar({ courseId, consentimento }).unwrap());
    } catch (x) {
      setErroInicio(erroConversa(x, "Não foi possível começar o exame agora."));
    }
  };

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="m-0 font-pe-titulo text-[28px] font-bold leading-9 md:text-pe-titulo-l">Exame oral</h1>
        <p className="m-0 max-w-[64ch] text-pe-tinta-suave">
          {e.duracao_minutos - 2} a {e.duracao_minutos} minutos de conversa em inglês com o tutor, no papel de examinador. É obrigatório para o certificado e vale 40% da nota do curso. Não gasta os minutos de conversa do seu plano.
        </p>
      </div>

      {erro ? <Aviso tipo="info">{erro}</Aviso> : null}

      <div className="grid gap-8 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex flex-col gap-6">
          <section aria-labelledby="t-como" className="flex flex-col gap-2">
            <h2 id="t-como" className="m-0 font-pe-titulo text-pe-titulo-s">
              Como é o exame
            </h2>
            <ol className="m-0 flex flex-col gap-1.5 pl-5">
              <li>Apresenta-se e fala um pouco do seu trabalho.</li>
              <li>Faz duas ou três tarefas de trabalho a partir das situações do curso: informar, pedir, explicar, resolver um problema.</li>
              <li>Dá a sua opinião sobre um tema do curso.</li>
            </ol>
            <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">O examinador não corrige nem dá pistas. Use as frases que aprendeu no curso, sem as ler.</p>
          </section>

          {e.temas.length ? (
            <section aria-labelledby="t-temas" className="flex flex-col gap-2">
              <h2 id="t-temas" className="m-0 font-pe-titulo text-pe-titulo-s">
                Situações do curso
              </h2>
              <ul className="m-0 flex list-disc flex-col gap-1 pl-5">
                {e.temas.map((t) => (
                  <li key={t.titulo}>
                    <span className="font-semibold">{t.titulo}</span>
                    {t.descricao ? <span className="text-pe-tinta-suave">: {t.descricao}</span> : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {e.frases.length ? (
            <section aria-labelledby="t-frases" className="flex flex-col gap-2">
              <h2 id="t-frases" className="m-0 font-pe-titulo text-pe-titulo-s">
                Frases do curso para rever antes
              </h2>
              <ul className="m-0 flex list-none flex-col p-0">
                {e.frases.map((f) => (
                  <li key={f.en} className="border-b border-pe-fundo-forte py-2">
                    <span lang="en" className="block font-semibold">
                      {f.en}
                    </span>
                    {f.pt ? <span className="text-[15px] text-pe-tinta-suave">{f.pt}</span> : null}
                  </li>
                ))}
              </ul>
              <p className="m-0 text-pe-legenda text-pe-tinta-suave">Durante o exame não aparecem no ecrã.</p>
            </section>
          ) : null}
        </div>

        <div className="flex flex-col gap-6">
          <section aria-labelledby="t-avaliado" className="flex flex-col gap-2 rounded-pe-md bg-pe-fundo-suave p-5">
            <h2 id="t-avaliado" className="m-0 text-[17px] font-semibold leading-6">
              O que é avaliado
            </h2>
            <ul className="m-0 flex list-disc flex-col gap-1 pl-5 text-[15px] leading-[22px]">
              <li>Fluência: falar sem parar muito e manter a conversa.</li>
              <li>Gramática e vocabulário para o nível {e.nivel_alvo ?? "do curso"}.</li>
              <li>Tarefas: fazer o que cada tarefa pede.</li>
            </ul>
            <p className="m-0 text-[15px] leading-[22px]">
              Passa com {Math.round(e.nota_minima)}% ou mais. Se não passar, pode repetir 7 dias depois. O professor do curso pode rever a nota.
            </p>
          </section>

          {e.tentativas.length ? (
            <section aria-labelledby="t-tentativas" className="flex flex-col gap-1">
              <h2 id="t-tentativas" className="m-0 text-[17px] font-semibold leading-6">
                As suas tentativas
              </h2>
              <ul className="m-0 flex list-none flex-col p-0">
                {e.tentativas
                  .filter((t) => t.estado !== "em_curso")
                  .map((t) => (
                    <LinhaTentativa key={t.id} t={t} aoAbrir={() => aoAbrir(t.id)} />
                  ))}
              </ul>
            </section>
          ) : null}
        </div>
      </div>

      {e.disponivel ? (
        <section aria-labelledby="t-comecar" className="flex flex-col gap-4 rounded-pe-md border-[1.5px] border-pe-azul-marca p-5 md:p-6">
          <h2 id="t-comecar" className="m-0 font-pe-titulo text-[20px] font-semibold leading-[26px]">
            Antes de começar
          </h2>
          <p className="m-0 max-w-[64ch] text-[15px] leading-[22px]">
            Esteja num sítio calmo, com o microfone ligado. Pode gravar o exame para o professor o ouvir antes de confirmar a nota. Não é obrigatório: sem gravação o exame vale o mesmo.
          </p>
          <label className="flex max-w-[64ch] cursor-pointer items-start gap-3">
            <input type="checkbox" checked={consentimento} onChange={(x) => setConsentimento(x.target.checked)} className="mt-1 size-5 shrink-0 accent-pe-azul-marca" />
            <span>
              Autorizo a gravação desta prova para o professor a poder ouvir.
              <span className="block text-pe-legenda text-pe-tinta-suave">
                Só o professor do curso e você a podem ouvir. É apagada ao fim de 12 meses e pode apagá-la antes. Ver a{" "}
                <Link href="/privacidade#gravacoes" className="font-semibold text-pe-azul-marca">
                  política de privacidade
                </Link>
                .
              </span>
            </span>
          </label>
          {erroInicio ? <Aviso tipo="errado">{erroInicio}</Aviso> : null}
          <Botao className="self-start" disabled={isLoading} onClick={() => void abrir()}>
            {isLoading ? <Loader2 aria-hidden className="motion-safe:animate-spin" /> : <Mic aria-hidden />}
            Começar o exame
          </Botao>
        </section>
      ) : (
        <Aviso tipo={e.motivo === "aprovado" ? "certo" : "neutro"}>{e.mensagem}</Aviso>
      )}
    </>
  );
}
