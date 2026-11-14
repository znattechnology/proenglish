"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Copy, Download, Lock } from "lucide-react";
import { Aviso, BarraProgresso, Botao, Etiqueta, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { dataPt, diaMesCurto, mensagemErro } from "@/src/domains/student/subscricao/api";
import { useCertificadosQuery, useEmitirCertificadoMutation, type Certificados } from "@/src/domains/student/progresso/api";

export default function PaginaCertificados() {
  const { data, isLoading, isError, refetch } = useCertificadosQuery();

  return (
    <Pagina className="max-w-[1040px]">
      <div className="flex flex-col gap-2">
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Certificados</h1>
        <p className="m-0 max-w-[68ch] text-pe-tinta-suave">Cada certificado tem um número. Qualquer empresa pode confirmá-lo pela ligação de verificação, sem precisar de conta.</p>
      </div>

      {isError ? (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
          <p className="m-0">Não conseguimos carregar os certificados.</p>
          <Botao tamanho="pequeno" onClick={() => refetch()}>
            Tentar outra vez
          </Botao>
        </div>
      ) : isLoading || !data ? (
        <Osso className="h-[200px] max-w-[900px] rounded-pe-md" />
      ) : (
        <>
          {!data.plano_inclui_certificados ? (
            <div className="flex max-w-[900px] flex-col items-start gap-3 rounded-pe-md bg-pe-realce-suave p-5 md:flex-row md:items-center md:justify-between">
              <span className="flex items-start gap-2.5 text-[15px] leading-[22px]">
                <Lock aria-hidden className="mt-0.5 size-5 shrink-0" />
                Os certificados fazem parte do Premium e do Premium Plus. O progresso dos seus cursos fica guardado.
              </span>
              <Botao asChild tipo="realce" tamanho="pequeno">
                <Link href="/user/upgrade?plan=PREMIUM">Passar para Premium</Link>
              </Botao>
            </div>
          ) : null}

          {data.certificados.length ? (
            <section aria-label="Certificados emitidos" className="flex flex-col gap-4">
              {data.certificados.map((c) => (
                <CartaoCertificado key={c.id} c={c} />
              ))}
            </section>
          ) : (
            <div className="flex max-w-[900px] flex-col gap-1 rounded-pe-md bg-pe-fundo-suave p-6">
              <h2 className="m-0 text-pe-titulo-s">Ainda não tem certificados</h2>
              <p className="m-0 text-pe-tinta-suave">Conclua um curso com 70% ou mais na nota final para receber o primeiro.</p>
            </div>
          )}

          {data.em_curso.length ? <ACaminho emCurso={data.em_curso} podeEmitir={data.plano_inclui_certificados} /> : null}
        </>
      )}
    </Pagina>
  );
}

function CartaoCertificado({ c }: { c: Certificados["certificados"][number] }) {
  const [copiado, setCopiado] = useState(false);
  const [mostrar, setMostrar] = useState(false);
  const revogado = c.estado === "revogado";
  return (
    <article aria-labelledby={`cert-${c.id}`} className="flex max-w-[900px] flex-wrap overflow-hidden rounded-pe-md border border-pe-linha">
      <div className="pe-sobre-marca flex min-w-0 flex-[1_1_260px] flex-col justify-between gap-6 rounded-br-[28px] bg-pe-azul-marca p-6 text-pe-sobre-marca md:p-7">
        <span className="text-[14px] font-semibold leading-5">Certificado de conclusão</span>
        <h2 id={`cert-${c.id}`} className="m-0 font-pe-titulo text-[24px] font-bold leading-[30px] md:text-[26px] md:leading-8">
          {c.curso.titulo}
        </h2>
        <span className="font-pe-titulo text-[15px] font-semibold tracking-[0.04em] tabular-nums">{c.numero}</span>
      </div>
      <div className="flex min-w-0 flex-[2_1_380px] flex-col justify-between gap-6 p-6 md:p-7">
        <dl className="m-0 grid grid-cols-2 gap-4 sm:grid-cols-3">
          <div className="flex flex-col">
            <dt className="text-pe-legenda text-pe-tinta-suave">Nota final</dt>
            <dd className="m-0 font-pe-titulo text-[24px] font-bold tabular-nums">{Math.round(c.nota_final)}%</dd>
          </div>
          <div className="flex flex-col">
            <dt className="text-pe-legenda text-pe-tinta-suave">Emitido em</dt>
            <dd className="m-0 pt-1 font-semibold">{diaMesCurto(new Date(c.emitido_em), true)}</dd>
          </div>
          <div className="flex flex-col">
            <dt className="text-pe-legenda text-pe-tinta-suave">Estado</dt>
            <dd className="m-0 pt-1">
              <Etiqueta tipo={revogado ? "errado" : "certo"}>{revogado ? "Revogado" : "Válido"}</Etiqueta>
            </dd>
          </div>
        </dl>
        {revogado ? (
          <Aviso tipo="errado">Este certificado foi revogado e já não é válido. Fale com o apoio se tiver dúvidas.</Aviso>
        ) : (
          <div className="flex flex-wrap gap-3">
            <Botao asChild tamanho="medio">
              <a href={c.pdf_url} download>
                <Download aria-hidden /> Descarregar em PDF
              </a>
            </Botao>
            <Botao
              tipo="secundario"
              tamanho="medio"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(c.ligacao_verificacao);
                  setCopiado(true);
                  setTimeout(() => setCopiado(false), 2500);
                } catch {
                  setMostrar(true); // sem acesso à área de transferência: mostra a ligação para copiar à mão
                }
              }}
            >
              {copiado ? <Check aria-hidden /> : <Copy aria-hidden />}
              {copiado ? "Ligação copiada" : "Copiar ligação de verificação"}
            </Botao>
            <span aria-live="polite" className="sr-only">
              {copiado ? "Ligação copiada" : ""}
            </span>
            {mostrar ? (
              <input readOnly value={c.ligacao_verificacao} aria-label="Ligação de verificação" onFocus={(e) => e.currentTarget.select()} className="h-11 w-full rounded-pe-sm border border-pe-linha bg-pe-fundo-suave px-3 text-[14px]" autoFocus />
            ) : null}
          </div>
        )}
      </div>
    </article>
  );
}


function ACaminho({ emCurso, podeEmitir }: { emCurso: Certificados["em_curso"]; podeEmitir: boolean }) {
  const [emitir, { isLoading }] = useEmitirCertificadoMutation();
  const [erro, setErro] = useState<string | null>(null);
  return (
    <section aria-labelledby="titulo-caminho" className="flex max-w-[900px] flex-col gap-3 pt-2">
      <h2 id="titulo-caminho" className="m-0 font-pe-titulo text-pe-titulo-s">
        A caminho de um certificado
      </h2>
      {erro ? <Aviso tipo="errado">{erro}</Aviso> : null}
      <ul className="m-0 flex list-none flex-col p-0">
        {emCurso.map((c) => {
          const falta = c.em_falta[0];
          return (
            <li key={c.curso.id} className="flex flex-col gap-2 border-b border-pe-fundo-forte py-4 md:flex-row md:items-center md:gap-6">
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <div className="flex items-baseline justify-between gap-3">
                  <Link href={`/user/courses/${c.curso.id}/grades`} className="font-semibold leading-[22px] text-pe-tinta underline-offset-[3px]">
                    {c.curso.titulo}
                  </Link>
                  <span className="shrink-0 font-pe-titulo text-[18px] font-bold tabular-nums">{Math.round(c.nota_final)}%</span>
                </div>
                <BarraProgresso valor={c.progresso} rotulo={`Aulas concluídas em ${c.curso.titulo}`} />
                <span className="text-pe-legenda text-pe-tinta-suave">
                  {c.pode_emitir
                    ? "Cumpre tudo o que o certificado pede."
                    : falta
                      ? `${falta.mensagem}${c.em_falta.length > 1 ? `. Falta${c.em_falta.length > 2 ? "m" : ""} mais ${c.em_falta.length - 1} ${c.em_falta.length > 2 ? "requisitos" : "requisito"}.` : ""}`
                      : `Precisa de ${c.nota_minima}% na nota final.`}
                </span>
              </div>
              {c.pode_emitir && podeEmitir ? (
                <Botao
                  tamanho="medio"
                  disabled={isLoading}
                  onClick={async () => {
                    setErro(null);
                    const r = await emitir(c.curso.id);
                    if ("error" in r && r.error) setErro(mensagemErro(r.error, "Não foi possível emitir o certificado."));
                  }}
                >
                  Receber o certificado
                </Botao>
              ) : (
                <Botao asChild tipo="ligacao" tamanho="pequeno" className="self-start md:self-center">
                  <Link href={`/user/courses/${c.curso.id}`}>Continuar o curso</Link>
                </Botao>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
