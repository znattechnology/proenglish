"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Lock } from "lucide-react";
import { BarraProgresso, Botao, Osso } from "@/components/pe";
import { Pagina } from "@/components/pe/estudante/Pagina";
import { Competicoes } from "@/components/pe/estatisticas/Competicoes";
import { cnPe } from "@/lib/pe";
import { useConquistasQuery, useLigaQuery, type Conquista, type Liga } from "@/src/domains/student/progresso/api";

const fmt = (n: number) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");

export default function PaginaConquistas() {
  const { data: conquistas, isError: erroC, refetch: refetchC } = useConquistasQuery();
  const { data: liga, isError: erroL, refetch: refetchL } = useLigaQuery();
  const ganhas = conquistas?.filter((c) => c.isUnlocked).length ?? 0;
  const temCompeticoes = !!(liga?.competicoes?.length || liga?.competicoes_terminadas?.length || liga?.premios?.length);

  useEffect(() => {
    // Os avisos das competições e da liga abrem esta página em #liga: a secção só aparece
    // depois de os dados chegarem, por isso o browser não consegue lá ir sozinho.
    if (liga && window.location.hash === "#liga") document.getElementById("liga")?.scrollIntoView({ block: "start" });
  }, [liga]);

  return (
    <Pagina>
      <div className="flex flex-col gap-2">
        <h1 className="m-0 font-pe-titulo text-[26px] font-bold leading-8 md:text-pe-titulo-l">Conquistas e liga</h1>
        <p className="m-0 text-pe-tinta-suave">
          {conquistas ? `${ganhas} de ${conquistas.length} conquistas.` : " "}
          {liga ? ` ${liga.liga.nome}, ${liga.eu.posicao}.º lugar esta semana.` : ""}
        </p>
      </div>

      <div className="grid items-start gap-8 lg:grid-cols-[3fr_2fr]">
        <section aria-labelledby="titulo-conquistas" className="flex min-w-0 flex-col gap-3">
          <h2 id="titulo-conquistas" className="m-0 font-pe-titulo text-pe-titulo-s">
            Conquistas
          </h2>
          {erroC ? (
            <Erro texto="Não conseguimos carregar as conquistas." aoTentar={refetchC} />
          ) : !conquistas ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {[0, 1, 2, 3].map((i) => (
                <Osso key={i} className="h-[110px] rounded-pe-md" />
              ))}
            </div>
          ) : (
            <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2">
              {[...conquistas]
                .sort((a, b) => Number(b.isUnlocked) - Number(a.isUnlocked) || (b.progress?.percentage ?? 0) - (a.progress?.percentage ?? 0))
                .map((c) => (
                  <CartaoConquista key={c.id} c={c} />
                ))}
            </ul>
          )}
        </section>

        <section id="liga" aria-labelledby="titulo-liga" className={cnPe("flex min-w-0 scroll-mt-8 flex-col gap-3", !temCompeticoes && "lg:sticky lg:top-8")}>
          {erroL ? (
            <Erro texto="Não conseguimos carregar a liga." aoTentar={refetchL} />
          ) : !liga ? (
            <Osso className="h-[420px] rounded-pe-md" />
          ) : (
            <>
              <TabelaLiga l={liga} />
              {temCompeticoes ? (
                <div className="mt-5 border-t border-pe-linha pt-6">
                  <Competicoes actuais={liga.competicoes ?? []} terminadas={liga.competicoes_terminadas ?? []} premios={liga.premios ?? []} />
                </div>
              ) : null}
            </>
          )}
        </section>
      </div>
    </Pagina>
  );
}

function CartaoConquista({ c }: { c: Conquista }) {
  const sigla = c.icon && !/^[\p{L}\p{N}]/u.test(c.icon) ? c.icon : c.title.slice(0, 2);
  return (
    <li className={cnPe("flex min-w-0 gap-4 rounded-pe-md p-5", c.isUnlocked ? "border border-pe-linha" : "border border-pe-fundo-suave bg-pe-fundo-suave")}>
      <span
        aria-hidden
        className={cnPe(
          "flex size-12 shrink-0 items-center justify-center rounded-[16px_16px_16px_0] font-pe-titulo text-[20px] font-bold",
          c.isUnlocked ? "pe-sobre-marca bg-pe-azul-marca text-pe-sobre-marca" : "bg-pe-fundo-forte text-pe-tinta-suave grayscale"
        )}
      >
        {c.isUnlocked ? sigla : <Lock className="size-5" />}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <h3 className="m-0 text-[17px] font-semibold leading-6">{c.title}</h3>
        <p className="m-0 text-[15px] leading-[22px] text-pe-tinta-suave">{c.description}</p>
        {c.isUnlocked ? (
          <span className="text-[14px] font-semibold leading-5 text-pe-certo">Conquistada {c.unlockedAt ?? ""}</span>
        ) : c.progress ? (
          <span className="flex flex-col gap-1.5 pt-1">
            <span className="text-[14px] font-semibold leading-5 tabular-nums">
              {fmt(c.progress.current)} de {fmt(c.progress.target)}
              {c.progress.unit ? ` ${c.progress.unit}` : ""}
            </span>
            <BarraProgresso valor={c.progress.percentage} rotulo={`Progresso em ${c.title}`} />
          </span>
        ) : (
          <span className="text-[14px] font-semibold leading-5">Por conquistar</span>
        )}
      </div>
    </li>
  );
}

function TabelaLiga({ l }: { l: Liga }) {
  const dias = Math.floor(l.semana.segundos_ate_fim / 86_400);
  const horas = Math.floor((l.semana.segundos_ate_fim % 86_400) / 3_600);
  const termina = dias ? `termina daqui a ${dias} ${dias === 1 ? "dia" : "dias"}` : `termina daqui a ${horas} h`;
  return (
    <>
      <div className="flex flex-col gap-0.5">
        <h2 id="titulo-liga" className="m-0 font-pe-titulo text-pe-titulo-s">
          {l.liga.nome}
        </h2>
        <span className="text-pe-legenda text-pe-tinta-suave">Pontos desta semana, que {termina}.</span>
      </div>
      <div className="overflow-hidden rounded-pe-md border border-pe-linha">
        <table className="w-full border-collapse text-left text-[15px] leading-[22px]">
          <thead>
            <tr className="text-pe-tinta-suave">
              <th scope="col" className="w-16 px-4 py-2.5 font-normal">
                Lugar
              </th>
              <th scope="col" className="px-2 py-2.5 font-normal">
                Estudante
              </th>
              <th scope="col" className="px-4 py-2.5 text-right font-normal">
                Pontos
              </th>
            </tr>
          </thead>
          <tbody>
            {l.ranking.map((j) => (
              <tr key={`${j.posicao}-${j.nome}`} aria-current={j.sou_eu ? "true" : undefined} className={cnPe("border-t border-pe-linha", j.sou_eu && "bg-pe-realce-suave font-semibold")}>
                <td className="px-4 py-2.5 tabular-nums">{j.posicao}.º</td>
                <td className="px-2 py-2.5">{j.sou_eu ? `${j.nome} (você)` : j.nome}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">{fmt(j.pontos_semana)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="m-0 text-[15px] leading-[22px]">
        {l.eu.pontos_para_lugar_acima ? `Faltam-lhe ${fmt(l.eu.pontos_para_lugar_acima)} pontos para subir um lugar. ` : l.eu.posicao === 1 ? "Está em 1.º lugar esta semana. " : ""}
        {l.regra_promocao.descricao}
      </p>
      {l.regra_promocao.proxima_liga && l.regra_promocao.pontos_em_falta !== null ? (
        <BarraProgresso
          valor={(100 * (l.eu.pontos_totais - l.liga.pontos_minimos)) / Math.max(1, l.regra_promocao.proxima_liga.pontos_minimos - l.liga.pontos_minimos)}
          rotulo={`Pontos até à ${l.regra_promocao.proxima_liga.nome}`}
          cor="realce"
        />
      ) : null}
      <div className="flex flex-wrap gap-3 pt-1">
        <Botao asChild tamanho="medio">
          <Link href="/user/laboratory/learn">Praticar uma lição</Link>
        </Botao>
        <Botao asChild tipo="secundario" tamanho="medio">
          <Link href="/user/laboratory/speaking/real-time">Conversar com o tutor</Link>
        </Botao>
      </div>
    </>
  );
}

function Erro({ texto, aoTentar }: { texto: string; aoTentar: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-pe-md bg-pe-errado-suave p-5">
      <p className="m-0">{texto}</p>
      <Botao tamanho="pequeno" onClick={aoTentar}>
        Tentar outra vez
      </Botao>
    </div>
  );
}
