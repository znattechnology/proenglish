import { Award, Medal } from "lucide-react";
import { Etiqueta } from "@/components/pe";
import { cnPe } from "@/lib/pe";
import type { Competicao, PremioGanho } from "@/src/domains/student/progresso/api";

const fmt = (n: number) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");

/** "2026-11-16" -> "16/11" */
const dia = (iso: string) => {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
};

const PREMIO_CURTO: Record<string, string> = {
  certificado_merito: "um certificado de mérito",
  medalha: "uma medalha",
  plano: "um mês de plano",
};

function unidade(c: { unidade: string }, n: number) {
  if (n !== 1) return c.unidade;
  return { lições: "lição", pontos: "ponto", minutos: "minuto", dias: "dia" }[c.unidade] ?? c.unidade;
}

function listaCursos(cursos: { titulo: string }[]) {
  const t = cursos.map((c) => `«${c.titulo}»`);
  return t.length <= 1 ? t.join("") : `${t.slice(0, -1).join(", ")} e ${t[t.length - 1]}`;
}

function quando(c: Competicao) {
  if (c.estado === "agendada") return `Começa a ${dia(c.inicio)}`;
  const n = c.dias_restantes ?? 0;
  return n <= 1 ? "Termina hoje" : `Faltam ${n} dias`;
}

/** Competições dos cursos do aluno: a decorrer, terminadas e prémios ganhos (secção #liga). */
export function Competicoes({ actuais, terminadas, premios }: { actuais: Competicao[]; terminadas: Competicao[]; premios: PremioGanho[] }) {
  if (!actuais.length && !terminadas.length && !premios.length) return null;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-0.5">
        <h2 id="titulo-competicoes" className="m-0 font-pe-titulo text-pe-titulo-s">
          Competições
        </h2>
        <span className="text-pe-legenda text-pe-tinta-suave">Participa automaticamente nas competições dos seus cursos.</span>
      </div>

      {actuais.length ? (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {actuais.map((c) => (
            <CartaoCompeticao key={c.id} c={c} />
          ))}
        </ul>
      ) : null}

      {premios.length ? <Premios premios={premios} /> : null}

      {terminadas.length ? (
        <details className="group rounded-pe-md border border-pe-linha">
          <summary className="cursor-pointer list-none px-4 py-3 font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pe-azul-vivo [&::-webkit-details-marker]:hidden">
            Competições terminadas ({terminadas.length})
            <span aria-hidden className="float-right text-pe-tinta-suave group-open:rotate-180">
              ▾
            </span>
          </summary>
          <ul className="m-0 flex list-none flex-col p-0">
            {terminadas.map((c) => (
              <Terminada key={c.id} c={c} />
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function CartaoCompeticao({ c }: { c: Competicao }) {
  const titulo = `competicao-${c.id}`;
  return (
    <li aria-labelledby={titulo} className="flex min-w-0 flex-col gap-3 rounded-pe-md border border-pe-linha p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 id={titulo} className="m-0 min-w-0 text-[17px] font-semibold leading-6">
          {c.nome}
        </h3>
        <Etiqueta tipo={c.estado === "activa" && (c.dias_restantes ?? 0) <= 1 ? "realce" : "neutra"}>{quando(c)}</Etiqueta>
      </div>
      <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">
        Conta {c.conta_nome.toLowerCase()}, de {dia(c.inicio)} a {dia(c.fim)}
        {c.cursos?.length ? `, no${c.cursos.length > 1 ? "s cursos" : " curso"} ${listaCursos(c.cursos)}` : ""}. Prémio para{" "}
        {c.premio_lugares === 1 ? "o 1.º lugar" : `os ${c.premio_lugares} primeiros`}: {PREMIO_CURTO[c.premio] ?? c.premio_nome.toLowerCase()}.
      </p>

      {c.estado === "activa" ? (
        <>
          <p className="m-0 flex flex-wrap items-baseline gap-x-2">
            {c.meu_lugar ? (
              <>
                <span className="font-pe-titulo text-[24px] font-bold leading-8 tabular-nums">{c.meu_lugar}.º lugar</span>
                <span className="text-[15px] leading-[22px] text-pe-tinta-suave">
                  com {fmt(c.meu_valor)} {unidade(c, c.meu_valor)}, entre {c.participantes} {c.participantes === 1 ? "participante" : "participantes"}
                </span>
              </>
            ) : (
              <span className="text-[15px] leading-[22px]">Ainda não tem lugar nesta competição.</span>
            )}
          </p>
          {c.topo.length ? <Topo c={c} /> : null}
        </>
      ) : null}
    </li>
  );
}

function Topo({ c }: { c: Competicao }) {
  return (
    <ol aria-label={`Primeiros lugares em ${c.nome}`} className="m-0 flex list-none flex-col gap-1 p-0">
      {c.topo.map((t, i) => (
        <li
          key={`${t.lugar}-${t.nome}-${i}`}
          aria-current={t.sou_eu ? "true" : undefined}
          className={cnPe("flex items-center gap-3 rounded-pe-sm px-3 py-1.5 text-[15px] leading-[22px]", t.sou_eu ? "bg-pe-realce-suave font-semibold" : "bg-pe-fundo-suave")}
        >
          <span className="w-8 shrink-0 tabular-nums">{t.lugar}.º</span>
          <span className="min-w-0 flex-1 truncate">{t.sou_eu ? `${t.nome} (você)` : t.nome}</span>
          <span className="tabular-nums">
            {fmt(t.valor)} <span className="sr-only">{unidade(c, t.valor)}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function Terminada({ c }: { c: Competicao }) {
  const ganhou = !!c.meu_premio;
  return (
    <li className="flex flex-col gap-1.5 border-t border-pe-linha px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold leading-[22px]">{c.nome}</span>
        {ganhou ? <Etiqueta tipo="certo">Ganhou {PREMIO_CURTO[c.meu_premio as string] ?? "um prémio"}</Etiqueta> : null}
      </div>
      <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">
        Terminou a {dia(c.fim)}.{" "}
        {c.meu_lugar
          ? `Ficou em ${c.meu_lugar}.º lugar com ${fmt(c.meu_valor)} ${unidade(c, c.meu_valor)}, entre ${c.participantes} participantes.`
          : "Não ficou classificado."}
        {c.topo.length ? ` Primeiros: ${c.topo.map((t) => `${t.lugar}.º ${t.sou_eu ? "você" : t.nome}`).join(", ")}.` : ""}
      </p>
      {c.certificado_url ? (
        <a href={c.certificado_url} target="_blank" rel="noreferrer" className="w-fit text-[15px] font-semibold text-pe-azul-marca underline underline-offset-2">
          Abrir o certificado de mérito
        </a>
      ) : null}
    </li>
  );
}

function Premios({ premios }: { premios: PremioGanho[] }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="m-0 text-[17px] font-semibold leading-6">Os seus prémios</h3>
      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
        {premios.map((p) => {
          const Icone = p.premio === "medalha" ? Medal : Award;
          return (
            <li key={`${p.competicao_id}-${p.premio}`} className="flex min-w-0 items-center gap-2.5 rounded-pe-md bg-pe-fundo-suave px-3 py-2">
              <span aria-hidden className="pe-sobre-marca flex size-9 shrink-0 items-center justify-center rounded-full bg-pe-azul-marca text-pe-sobre-marca">
                <Icone className="size-5" />
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="text-[15px] font-semibold leading-5">
                  {p.premio_nome}
                  {p.lugar ? `, ${p.lugar}.º lugar` : ""}
                </span>
                <span className="truncate text-pe-legenda text-pe-tinta-suave">
                  {p.certificado_url ? (
                    <a href={p.certificado_url} target="_blank" rel="noreferrer" className="underline underline-offset-2">
                      {p.competicao}
                    </a>
                  ) : (
                    p.competicao
                  )}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
