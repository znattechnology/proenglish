"use client";

import Link from "next/link";
import { useState } from "react";
import { BarraProgresso, Botao, Etiqueta, Osso } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import { COMPETENCIAS_EXAME, dataCurta, type ExameOral } from "@/src/domains/shared/exameOral";
import { useApagarGravacaoExameMutation, useExameQuery } from "@/src/domains/student/curso/api";

/** Cartão na página do curso: o estado do exame oral e a ligação para ele. */
export function CartaoExame({ courseId }: { courseId: string }) {
  const { data: e, isLoading } = useExameQuery(courseId);
  if (isLoading) return <Osso className="h-[150px] rounded-pe-md" />;
  if (!e || e.motivo === "curso_pratica") return null;
  const ultimo = e.tentativas.find((t) => t.estado === "avaliado");
  const texto = e.aprovado
    ? `Passou${ultimo?.nivel_cefr ? ` com nível de fala ${ultimo.nivel_cefr}` : ""}.`
    : e.disponivel
      ? `${e.duracao_minutos} minutos a falar com o tutor. Precisa de ${Math.round(e.nota_minima)}% para o certificado.`
      : e.mensagem ?? "";
  return (
    <Link
      href={`/user/courses/${courseId}/exame`}
      className={cnPe(
        "flex flex-col gap-1.5 rounded-pe-md p-[22px] no-underline",
        e.disponivel ? "pe-sobre-marca bg-pe-azul-marca text-pe-sobre-marca hover:bg-pe-azul-vivo hover:text-pe-sobre-marca" : "border border-pe-linha text-pe-tinta hover:bg-pe-fundo-suave hover:text-pe-tinta"
      )}
    >
      <span className="font-pe-titulo text-[20px] font-semibold leading-[26px]">Exame oral</span>
      <span className="text-[15px] leading-[22px]">{texto}</span>
      <span className="font-semibold underline underline-offset-[3px]">{e.disponivel ? "Preparar o exame" : e.aprovado ? "Ver o resultado" : "Ver o exame"}</span>
    </Link>
  );
}

/** Notas por competência (aluno e professor). A pronúncia só aparece quando foi medida. */
export function NotasDoExame({ exame, compacto = false }: { exame: ExameOral; compacto?: boolean }) {
  return (
    <ul className={cnPe("m-0 grid list-none gap-x-6 p-0", !compacto && "sm:grid-cols-2")}>
      {COMPETENCIAS_EXAME.filter((c) => exame.notas[c.chave] != null).map((c) => {
        const v = Math.round(exame.notas[c.chave] as number);
        return (
          <li key={c.chave} className="flex flex-col gap-1.5 border-b border-pe-fundo-forte py-2.5">
            <span className="flex items-baseline justify-between gap-3">
              <span className="font-semibold">{c.nome}</span>
              <span className="font-pe-titulo text-[18px] font-bold tabular-nums">{v}</span>
            </span>
            <BarraProgresso valor={v} rotulo={c.nome} cor={v >= exame.nota_minima ? "certo" : undefined} />
            {compacto ? null : <span className="text-pe-legenda text-pe-tinta-suave">{c.ajuda}</span>}
          </li>
        );
      })}
    </ul>
  );
}

/** Resultado de uma tentativa, para o aluno. */
export function ResultadoExame({ exame, courseId, aoRepetir }: { exame: ExameOral; courseId: string; aoRepetir?: () => void }) {
  const [apagar, { isLoading: aApagar }] = useApagarGravacaoExameMutation();
  const [gravacao, setGravacao] = useState(exame.gravacao_url);
  const [confirmar, setConfirmar] = useState(false);

  if (exame.estado === "insuficiente" || exame.estado === "anulado")
    return (
      <section className="flex flex-col gap-3 rounded-pe-md bg-pe-fundo-suave p-5">
        <h2 className="m-0 font-pe-titulo text-[22px] font-bold leading-7">Este exame não teve nota</h2>
        <p className="m-0">
          {exame.estado === "anulado" ? "A chamada não chegou a ligar." : "Não ouvimos respostas suficientes para avaliar."} Esta tentativa não conta: pode fazer o exame outra vez.
        </p>
        {aoRepetir ? (
          <Botao className="self-start" onClick={aoRepetir}>
            Voltar ao exame
          </Botao>
        ) : null}
      </section>
    );

  const nota = Math.round(exame.nota ?? 0);
  return (
    <div className="flex flex-col gap-6">
      <section
        aria-labelledby="t-resultado-exame"
        className={cnPe(
          "flex flex-col gap-2 rounded-[28px_28px_28px_0] px-6 py-6 md:flex-row md:items-center md:gap-8 md:px-8",
          exame.aprovado ? "pe-sobre-marca bg-pe-azul-marca text-pe-sobre-marca" : "bg-pe-fundo-suave text-pe-tinta"
        )}
      >
        <span className="font-pe-titulo text-[56px] font-bold leading-[60px] tracking-[-0.02em] tabular-nums">{nota}%</span>
        <span className="flex flex-col gap-1">
          <h2 id="t-resultado-exame" className="m-0 font-pe-titulo text-[22px] font-semibold leading-7">
            {exame.aprovado ? "Passou no exame oral" : "Ainda não passou no exame oral"}
          </h2>
          <span className="text-[15px] leading-[22px]">
            {exame.nivel_cefr ? `Nível de fala atingido: ${exame.nivel_cefr}. ` : ""}
            {exame.aprovado
              ? "Conta para a nota e para o certificado do curso."
              : `Precisa de ${Math.round(exame.nota_minima)}%.${exame.pode_repetir_em ? ` Pode repetir a partir de ${dataCurta(exame.pode_repetir_em)}.` : ""}`}
          </span>
          {exame.revisao ? (
            <span className="text-[15px] leading-[22px]">
              Nota revista pelo professor{exame.revisao.por ? ` ${exame.revisao.por}` : ""} (a da IA era {Math.round(exame.nota_ia ?? 0)}%).
              {exame.revisao.comentario ? ` «${exame.revisao.comentario}»` : ""}
            </span>
          ) : null}
        </span>
      </section>

      <section aria-labelledby="t-notas-exame" className="flex flex-col gap-2">
        <h2 id="t-notas-exame" className="m-0 font-pe-titulo text-pe-titulo-s">
          Notas por competência
        </h2>
        <NotasDoExame exame={exame} />
        <p className="m-0 text-pe-legenda text-pe-tinta-suave">A pronúncia ainda não é avaliada no exame: a nota é a média das outras.</p>
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        {exame.relatorio || exame.a_treinar.length ? (
          <section aria-labelledby="t-treinar" className="flex flex-col gap-2">
            <h2 id="t-treinar" className="m-0 font-pe-titulo text-pe-titulo-s">
              O que treinar
            </h2>
            {exame.relatorio ? <p className="m-0">{exame.relatorio}</p> : null}
            {exame.a_treinar.length ? (
              <ul className="m-0 flex list-disc flex-col gap-1 pl-5">
                {exame.a_treinar.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            ) : null}
          </section>
        ) : null}
        {exame.frases_total ? (
          <section aria-labelledby="t-frases-exame" className="flex flex-col gap-2">
            <h2 id="t-frases-exame" className="m-0 font-pe-titulo text-pe-titulo-s">
              Frases do curso
            </h2>
            <p className="m-0">
              Disse sozinho {exame.frases_usadas.length} de {exame.frases_total} frases do curso.
            </p>
            {exame.frases_usadas.length ? (
              <ul className="m-0 flex list-none flex-col gap-1 p-0">
                {exame.frases_usadas.map((f) => (
                  <li key={f} lang="en" className="font-semibold">
                    {f}
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        ) : null}
      </div>

      {exame.consentimento_gravacao ? (
        <section aria-labelledby="t-gravacao" className="flex flex-col gap-2 rounded-pe-md border border-pe-linha p-5">
          <h2 id="t-gravacao" className="m-0 text-[17px] font-semibold leading-6">
            Gravação do exame
          </h2>
          {gravacao ? (
            <>
              <audio controls preload="none" src={gravacao} className="w-full max-w-[520px]">
                O seu browser não toca áudio.
              </audio>
              <p className="m-0 text-pe-legenda text-pe-tinta-suave">Só o professor do curso e você a podem ouvir. É apagada ao fim de 12 meses.</p>
              {confirmar ? (
                <div className="flex flex-wrap items-center gap-3">
                  <Botao
                    tipo="perigo"
                    tamanho="pequeno"
                    disabled={aApagar}
                    onClick={async () => {
                      try {
                        await apagar({ id: exame.id, courseId }).unwrap();
                        setGravacao(null);
                      } finally {
                        setConfirmar(false);
                      }
                    }}
                  >
                    Apagar a gravação
                  </Botao>
                  <Botao tipo="ligacao" tamanho="pequeno" onClick={() => setConfirmar(false)}>
                    Manter
                  </Botao>
                </div>
              ) : (
                <Botao tipo="ligacao" tamanho="pequeno" className="self-start" onClick={() => setConfirmar(true)}>
                  Apagar a gravação
                </Botao>
              )}
            </>
          ) : (
            <p className="m-0 text-[15px] text-pe-tinta-suave">{exame.gravacao_apagada ? "A gravação foi apagada." : "A gravação ainda não está disponível. Volte a abrir daqui a pouco."}</p>
          )}
        </section>
      ) : null}
    </div>
  );
}

/** Uma linha da lista de tentativas. */
export function LinhaTentativa({ t, aoAbrir }: { t: ExameOral; aoAbrir: () => void }) {
  const nota = t.estado === "avaliado" ? `${Math.round(t.nota ?? 0)}%` : t.estado === "insuficiente" || t.estado === "anulado" ? "Sem nota" : "A avaliar";
  return (
    <li className="flex items-center justify-between gap-3 border-b border-pe-fundo-forte py-3">
      <span className="flex flex-col">
        <span className="font-semibold">{dataCurta(t.criado_em)}</span>
        <span className="text-pe-legenda text-pe-tinta-suave">{t.nivel_cefr ? `Nível de fala ${t.nivel_cefr}` : " "}</span>
      </span>
      <span className="flex items-center gap-3">
        {t.estado === "avaliado" ? <Etiqueta tipo={t.aprovado ? "certo" : "neutra"}>{t.aprovado ? `Passou, ${nota}` : nota}</Etiqueta> : <Etiqueta>{nota}</Etiqueta>}
        <Botao tipo="ligacao" tamanho="pequeno" onClick={aoAbrir}>
          Ver
        </Botao>
      </span>
    </li>
  );
}
